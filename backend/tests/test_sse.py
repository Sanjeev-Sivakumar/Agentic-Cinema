import asyncio
import pytest
from app.models.analysis import AnalysisJob
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.models.production import Production
from app.repositories import get_job_repo, get_production_repo
from app.services.events import InMemoryEventBus
from app.main import app

@pytest.mark.asyncio
async def test_sse_event_formatting_and_stream():
    bus = InMemoryEventBus()
    job_id = "job_sse_test_123"

    evt1 = ProcessingEvent(
        production_id="prod_sse",
        job_id=job_id,
        event_type=EventType.STAGE_STARTED,
        stage=PipelineStage.SCREENPLAY_EXTRACTION,
        message="Stage 1 started for SSE test",
    )
    evt2 = ProcessingEvent(
        production_id="prod_sse",
        job_id=job_id,
        event_type=EventType.VISUAL_ONLY_DISCOVERED,
        stage=PipelineStage.ENTITY_MERGE,
        message="Visual Only entity detected",
        entity_name="Test Brand",
        confidence=0.98,
    )

    await bus.publish(evt1)
    await bus.publish(evt2)

    # Subscribe and verify SSE format for streamed messages
    streamed_messages = []
    async for event in bus.subscribe(job_id):
        sse_text = event.to_sse_message()
        streamed_messages.append(sse_text)
        if len(streamed_messages) == 2:
            break

    assert len(streamed_messages) == 2
    assert "event: STAGE_STARTED\n" in streamed_messages[0]
    assert "event: VISUAL_ONLY_DISCOVERED\n" in streamed_messages[1]
    assert "Test Brand" in streamed_messages[1]

def test_sse_route_registered():
    def extract_paths(item):
        paths = []
        for r in getattr(item, "routes", []):
            if hasattr(r, "path"):
                paths.append(r.path)
            if hasattr(r, "original_router"):
                paths.extend(extract_paths(r.original_router))
        return paths

    routes = extract_paths(app)
    assert "/productions/{production_id}/analysis/{job_id}/events" in routes


