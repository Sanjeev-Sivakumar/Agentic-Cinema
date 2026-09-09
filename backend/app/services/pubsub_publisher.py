"""
Google Cloud Pub/Sub Event Publisher Adapter for Chain of Title.
Publishes real-time pipeline lifecycle events to Google Cloud Pub/Sub topic:
  Project: chain-of-title-cinema-2026 (or GCP_PROJECT_ID)
  Topic: chain-of-title-events (or PUBSUB_TOPIC)

Safety & Resilience Guarantees:
- Completely optional: When PUBSUB_ENABLED=false (default), no Google SDK calls or credentials are required.
- Non-blocking: Errors or timeouts never block or fail the core pipeline.
- ₹0 / Free-tier safe: Uses standard 10GB/month free tier ingestion.
"""
import asyncio
import json
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.logging import logger
from app.models.events import ProcessingEvent


class PubSubEventPublisher:
    """
    Publisher adapter for Google Cloud Pub/Sub.
    Dispatches ProcessingEvent instances as JSON payloads with metadata attributes.
    """

    def __init__(self):
        self._client: Optional[Any] = None
        self._topic_path: Optional[str] = None
        self._init_failed: bool = False

    def _get_client(self) -> Optional[Any]:
        """Lazy-initialize the official Google Cloud Pub/Sub PublisherClient."""
        if not settings.is_pubsub_enabled:
            return None

        if self._client is not None:
            return self._client

        if self._init_failed:
            return None

        try:
            from google.cloud import pubsub_v1
            self._client = pubsub_v1.PublisherClient()
            self._topic_path = settings.pubsub_topic_path
            logger.info(f"[PubSubPublisher] Initialized Google Cloud Pub/Sub client for topic '{self._topic_path}'")
            return self._client
        except Exception as e:
            self._init_failed = True
            logger.warning(
                f"[PubSubPublisher] Failed to initialize Google Cloud Pub/Sub client: {e}. "
                f"Pub/Sub publishing will be disabled for this session."
            )
            return None

    def _prepare_message(self, event: ProcessingEvent) -> tuple[bytes, Dict[str, str]]:
        """Serialize event into UTF-8 JSON bytes and string metadata attributes."""
        event_dict = event.to_dict()
        data_bytes = json.dumps(event_dict, default=str).encode("utf-8")

        # Pub/Sub attributes must all be string values
        attributes: Dict[str, str] = {
            "event_id": str(event.event_id),
            "event_type": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
            "job_id": str(event.job_id),
            "production_id": str(event.production_id),
            "sequence_number": str(event.sequence_number),
            "timestamp": event.timestamp.isoformat(),
        }
        if event.stage:
            attributes["stage"] = event.stage.value if hasattr(event.stage, "value") else str(event.stage)
        if event.workflow_id:
            attributes["workflow_id"] = str(event.workflow_id)

        return data_bytes, attributes

    async def publish_event(self, event: ProcessingEvent) -> bool:
        """
        Asynchronously publish a ProcessingEvent to Google Cloud Pub/Sub.
        Returns True if successfully dispatched, False otherwise.
        """
        if not settings.PUBSUB_ENABLED:
            return False

        client = self._get_client()
        if client is None:
            return False

        topic_path = self._topic_path or settings.pubsub_topic_path

        try:
            data_bytes, attributes = self._prepare_message(event)

            # Publish is a threadpool operation in the official google-cloud-pubsub SDK
            loop = asyncio.get_running_loop()
            future = await loop.run_in_executor(
                None,
                lambda: client.publish(topic_path, data=data_bytes, **attributes)
            )

            # Wait for publish completion in background without blocking main execution thread
            message_id = await loop.run_in_executor(None, lambda: future.result(timeout=5.0))
            logger.debug(
                f"[PubSubPublisher] Published {event.event_type} for job {event.job_id} "
                f"to {topic_path} (Message ID: {message_id})"
            )
            return True

        except Exception as e:
            logger.warning(
                f"[PubSubPublisher] Failed to publish event '{event.event_id}' ({event.event_type}) "
                f"to Pub/Sub topic '{topic_path}': {e}"
            )
            return False

    def close(self) -> None:
        """Clean up publisher client resources."""
        if self._client is not None and hasattr(self._client, "stop"):
            try:
                self._client.stop()
            except Exception:
                pass
        self._client = None
        self._init_failed = False


# Singleton instance
pubsub_publisher = PubSubEventPublisher()
