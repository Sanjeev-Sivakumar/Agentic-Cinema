import pytest
from app.models.events import EventType, PipelineStage, ProcessingEvent

def test_processing_event_creation():
    event = ProcessingEvent(
        production_id="prod_test123",
        job_id="job_test456",
        event_type=EventType.ENTITY_DETECTED,
        stage=PipelineStage.OBJECT_DETECTION,
        progress=45.0,
        message="Detected trademark logo on coffee cup",
        scene_number=2,
        video_timestamp=14.7,
        entity_id="ent_789",
        entity_name="Starlight Coffee",
        entity_type="BRAND",
        confidence=0.96,
        risk_level="HIGH",
        risk_score=82.0,
        frame_path="frames/scene02_147.jpg",
        metadata={"bounding_box": [0.4, 0.5, 0.1, 0.2]},
    )

    assert event.event_id.startswith("evt_")
    assert event.production_id == "prod_test123"
    assert event.event_type == EventType.ENTITY_DETECTED
    assert event.stage == PipelineStage.OBJECT_DETECTION
    assert event.confidence == 0.96
    assert event.risk_score == 82.0

def test_processing_event_serialization():
    event = ProcessingEvent(
        production_id="prod_01",
        job_id="job_01",
        event_type=EventType.VISUAL_ONLY_DISCOVERED,
        stage=PipelineStage.ENTITY_MERGE,
        progress=58.0,
        message="Discovered visual-only brand unreferenced in script",
        entity_name="Vintage Canvas Art",
    )

    data = event.to_dict()
    assert data["event_type"] == "VISUAL_ONLY_DISCOVERED"
    assert data["stage"] == "Entity Merge"
    assert "timestamp" in data

    sse_msg = event.to_sse_message()
    assert sse_msg.startswith("event: VISUAL_ONLY_DISCOVERED\n")
    assert "data: {" in sse_msg
    assert f"id: {event.event_id}\n\n" in sse_msg
