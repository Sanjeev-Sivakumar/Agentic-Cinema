from pathlib import Path
import cv2
import numpy as np
import pytest
from app.agents.root_agent import root_agent
from app.models.analysis import AnalysisJob, JobStatus
from app.models.events import EventType
from app.models.production import Production
from app.repositories import get_entity_repo, get_job_repo, get_production_repo
from app.services import event_bus

def create_synthetic_test_video(output_path: str, duration_sec: int = 3, fps: int = 24):
    """
    Generate a real synthetic MP4 video fixture with 2 distinct scenes and visible brand/text.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    width, height = 640, 360
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(path), fourcc, fps, (width, height))

    total_frames = int(duration_sec * fps)
    split_frame = total_frames // 2

    for f in range(total_frames):
        if f < split_frame:
            # Scene 1: Blue background with "STARLIGHT CAFE" text and cup shape
            img = np.full((height, width, 3), (120, 60, 20), dtype=np.uint8)
            cv2.putText(img, "STARLIGHT CAFE", (80, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
            cv2.rectangle(img, (400, 100), (500, 260), (200, 200, 200), -1)
        else:
            # Scene 2: Dark green background with "RETRO POSTER"
            img = np.full((height, width, 3), (20, 100, 40), dtype=np.uint8)
            cv2.putText(img, "RETRO POSTER", (100, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
            cv2.circle(img, (450, 180), 60, (0, 200, 255), -1)

        out.write(img)

    out.release()
    return str(path)

@pytest.mark.asyncio
async def test_full_video_pipeline_integration(tmp_path):
    video_path = create_synthetic_test_video(str(tmp_path / "test_footage.mp4"), duration_sec=2, fps=24)

    prod_repo = get_production_repo()
    job_repo = get_job_repo()
    entity_repo = get_entity_repo()

    prod = Production(
        title="Synthetic Pipeline Test Film",
        footage_path=video_path,
        metadata={"script_text": "SCENE 1: Arjun enters room without any coffee mentioned."},
    )
    await prod_repo.create(prod)

    job = AnalysisJob.create_new(production_id=prod.id)
    await job_repo.create(job)

    # Execute the full 12-stage pipeline
    completed_job = await root_agent.execute_pipeline(prod.id, job.job_id)

    assert completed_job.status == JobStatus.COMPLETED
    assert completed_job.progress == 100.0
    assert completed_job.frames_processed > 0
    assert completed_job.scenes_detected >= 1

    # Check event bus history for real events
    history = event_bus.get_history(job.job_id)
    event_types = [e.event_type for e in history]

    assert EventType.ANALYSIS_STARTED in event_types
    assert EventType.SCENE_DETECTED in event_types
    assert EventType.FRAME_EXTRACTED in event_types
    assert EventType.OCR_COMPLETED in event_types
    assert EventType.FRAME_SELECTED_FOR_VISION in event_types
    assert EventType.VISION_ANALYSIS_COMPLETED in event_types
    assert EventType.ANALYSIS_COMPLETED in event_types
