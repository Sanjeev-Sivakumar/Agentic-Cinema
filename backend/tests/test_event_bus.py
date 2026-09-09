import asyncio
import pytest
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.services.events import InMemoryEventBus

@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    bus = InMemoryEventBus()
    job_id = "job_test_stream"

    event1 = ProcessingEvent(
        production_id="prod_01",
        job_id=job_id,
        event_type=EventType.STAGE_STARTED,
        stage=PipelineStage.SCREENPLAY_EXTRACTION,
        message="Stage 1 started",
    )

    event2 = ProcessingEvent(
        production_id="prod_01",
        job_id=job_id,
        event_type=EventType.ENTITY_DETECTED,
        stage=PipelineStage.OCR,
        message="Found entity",
        entity_name="LogoX",
    )

    received = []

    async def consumer():
        async for evt in bus.subscribe(job_id):
            received.append(evt)
            if len(received) == 2:
                break

    task = asyncio.create_task(consumer())

    # Small delay to ensure subscriber is registered
    await asyncio.sleep(0.01)

    await bus.publish(event1)
    await bus.publish(event2)

    await asyncio.wait_for(task, timeout=2.0)

    assert len(received) == 2
    assert received[0].event_type == EventType.STAGE_STARTED
    assert received[1].entity_name == "LogoX"

@pytest.mark.asyncio
async def test_event_bus_history_replay():
    bus = InMemoryEventBus()
    job_id = "job_history_test"

    event = ProcessingEvent(
        production_id="prod_01",
        job_id=job_id,
        event_type=EventType.ANALYSIS_STARTED,
        message="Job initialized",
    )

    # Publish before subscriber connects
    await bus.publish(event)

    received = []
    async for evt in bus.subscribe(job_id):
        received.append(evt)
        break

    assert len(received) == 1
    assert received[0].event_id == event.event_id
    assert received[0].message == "Job initialized"
