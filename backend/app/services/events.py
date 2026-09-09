from abc import ABC, abstractmethod
import asyncio
from collections import defaultdict
from typing import AsyncIterator, Dict, List, Set
from app.core.logging import logger
from app.models.events import EventType, ProcessingEvent

class EventBus(ABC):
    """Abstract Event Bus interface for publishing and subscribing to real-time ProcessingEvents."""

    @abstractmethod
    async def publish(self, event: ProcessingEvent) -> None:
        """Publish an event to all active subscribers for the associated job."""
        pass

    @abstractmethod
    async def subscribe(self, job_id: str) -> AsyncIterator[ProcessingEvent]:
        """Subscribe to real-time events for a specific analysis job."""
        pass

    @abstractmethod
    def get_history(self, job_id: str) -> List[ProcessingEvent]:
        """Retrieve all recorded events for a job."""
        pass

    @abstractmethod
    def clear_job(self, job_id: str) -> None:
        """Clear cached history and subscribers for a job."""
        pass


class InMemoryEventBus(EventBus):
    """
    In-memory async event bus with fan-out queues per job.
    Supports historical event replay on reconnection and graceful subscriber cleanup.
    """

    def __init__(self, max_history_per_job: int = 1000):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._history: Dict[str, List[ProcessingEvent]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._max_history = max_history_per_job

    async def publish(self, event: ProcessingEvent) -> None:
        job_id = event.job_id
        async with self._lock:
            # Store in history buffer (capped)
            job_history = self._history[job_id]
            job_history.append(event)
            if len(job_history) > self._max_history:
                job_history.pop(0)

            # Copy active subscriber queues
            active_queues = list(self._subscribers.get(job_id, set()))

        logger.debug(f"[EventBus] Published {event.event_type.value} for job {job_id} to {len(active_queues)} subscribers")

        # Fan-out to all active subscribers without blocking
        for queue in active_queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"[EventBus] Queue full for subscriber on job {job_id}, dropping event {event.event_id}")

        # Cloud Pub/Sub fan-out (optional, non-blocking fire-and-forget)
        try:
            from app.services.pubsub_publisher import pubsub_publisher
            asyncio.create_task(pubsub_publisher.publish_event(event))
        except Exception as e:
            logger.debug(f"[EventBus] Pub/Sub dispatch error: {e}")

    async def subscribe(self, job_id: str) -> AsyncIterator[ProcessingEvent]:
        queue: asyncio.Queue[ProcessingEvent] = asyncio.Queue(maxsize=500)

        # Snapshot existing history to replay
        async with self._lock:
            existing_history = list(self._history.get(job_id, []))
            self._subscribers[job_id].add(queue)

        try:
            # First replay existing events so reconnecting clients catch up seamlessly
            for event in existing_history:
                yield event
                if event.event_type in (EventType.ANALYSIS_COMPLETED, EventType.ANALYSIS_FAILED, EventType.ANALYSIS_CANCELLED):
                    return

            # Then stream live events as they arrive
            while True:
                event = await queue.get()
                yield event
                queue.task_done()
                if event.event_type in (EventType.ANALYSIS_COMPLETED, EventType.ANALYSIS_FAILED, EventType.ANALYSIS_CANCELLED):
                    break
        except (asyncio.CancelledError, GeneratorExit):
            logger.debug(f"[EventBus] Subscriber disconnected for job {job_id}")
        finally:
            async with self._lock:
                if job_id in self._subscribers and queue in self._subscribers[job_id]:
                    self._subscribers[job_id].remove(queue)
                    if not self._subscribers[job_id]:
                        del self._subscribers[job_id]

    def get_history(self, job_id: str) -> List[ProcessingEvent]:
        return list(self._history.get(job_id, []))

    def clear_job(self, job_id: str) -> None:
        if job_id in self._history:
            del self._history[job_id]
        if job_id in self._subscribers:
            del self._subscribers[job_id]


# Singleton instance for in-memory event bus
event_bus: EventBus = InMemoryEventBus()
