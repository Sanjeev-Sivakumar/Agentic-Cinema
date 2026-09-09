from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import cv2
import numpy as np
import pytest

from app.core.config import settings
from app.models.analysis import AnalysisJob, JobStatus
from app.models.entity import Entity, EntityClassification, EntitySource, EntityType
from app.models.events import EventType, PipelineStage
from app.models.video import (
    ExtractedFrame,
    FrameRanking,
    OCRResult,
    ObjectDetection,
    RankedFrame,
    Scene,
    VideoMetadata,
)
from app.services import (
    deduplication_service,
    entity_service,
    frame_extraction_service,
    frame_ranking_service,
    get_vision_provider,
    ocr_service,
    object_detection_service,
    scene_detection_service,
    screenplay_comparison_service,
    video_service,
)
from app.services.frame_extraction import FrameExtractionService
from app.services.video import VideoDurationLimitExceededError, VideoReadError
from app.services.vision_provider import GeminiVisionProvider, GroqVisionProvider, LocalHeuristicVisionProvider
from app.agents.visual_agent import visual_agent

def create_synthetic_micro_video(output_path: str, duration_sec: float = 1.0, fps: int = 24) -> str:
    """Generate a minimal synthetic MP4 fixture in tmp_path (less than 1 MB, 24 frames)."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 320, 240
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(path), fourcc, fps, (width, height))

    total_frames = int(duration_sec * fps)
    for f in range(total_frames):
        img = np.zeros((height, width, 3), dtype=np.uint8)
        if f < total_frames // 2:
            cv2.rectangle(img, (50, 50), (150, 150), (255, 0, 0), -1)
            cv2.putText(img, "TEST", (60, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        else:
            cv2.circle(img, (160, 120), 40, (0, 255, 0), -1)
        out.write(img)

    out.release()
    return str(path)


# =========================================================================
# 1. Video Metadata Tests
# =========================================================================
def test_video_metadata_valid(tmp_path):
    vid_path = create_synthetic_micro_video(str(tmp_path / "valid.mp4"), duration_sec=1.0, fps=24)
    meta = video_service.inspect_video(vid_path)
    assert meta.filename == "valid.mp4"
    assert meta.fps == 24.0
    assert meta.frame_count == 24
    assert meta.duration_seconds == 1.0
    assert meta.width == 320
    assert meta.height == 240

def test_video_metadata_missing_file():
    with pytest.raises(FileNotFoundError):
        video_service.inspect_video("non_existent_path_12345.mp4")

def test_video_metadata_invalid_file(tmp_path):
    bad_file = tmp_path / "corrupt.mp4"
    bad_file.write_text("not a real video content")
    with pytest.raises(VideoReadError):
        video_service.inspect_video(str(bad_file))

def test_video_duration_limit_exceeded(tmp_path):
    vid_path = create_synthetic_micro_video(str(tmp_path / "exceeded.mp4"), duration_sec=1.0, fps=24)
    # Temporarily set max duration to 0.5s to test rejection
    custom_service = type(video_service)(max_duration_seconds=0.5)
    with pytest.raises(VideoDurationLimitExceededError):
        custom_service.inspect_video(vid_path)


# =========================================================================
# 2. Scene Detection Tests
# =========================================================================
def test_scene_model_and_ordering(tmp_path):
    vid_path = create_synthetic_micro_video(str(tmp_path / "scenes.mp4"), duration_sec=2.0, fps=24)
    meta = video_service.inspect_video(vid_path)
    scenes = scene_detection_service.detect_scenes(vid_path, "prod_test", "job_test", meta)

    assert len(scenes) >= 1
    for i, scn in enumerate(scenes):
        assert scn.scene_number == i + 1
        assert scn.start_time <= scn.end_time
        assert scn.duration_seconds > 0
        assert scn.start_frame <= scn.end_frame


# =========================================================================
# 3. Candidate Frame Extraction Tests
# =========================================================================
@pytest.mark.asyncio
async def test_frame_extraction_count_and_positions(tmp_path):
    vid_path = create_synthetic_micro_video(str(tmp_path / "extract.mp4"), duration_sec=1.5, fps=24)
    meta = video_service.inspect_video(vid_path)
    scene = Scene(
        production_id="p1",
        job_id="j1",
        scene_number=1,
        start_time=0.0,
        end_time=1.5,
        duration_seconds=1.5,
        start_frame=0,
        end_frame=36,
    )
    extractor = FrameExtractionService(frames_per_scene=3)
    frames = await extractor.extract_scene_frames(vid_path, [scene], "p1", "j1", meta)
    assert len(frames) == 3
    positions = [f.position_in_scene for f in frames]
    assert "start" in positions
    assert "middle" in positions
    assert "end" in positions
    for f in frames:
        assert Path(f.local_path).exists()
        assert f.video_timestamp >= 0.0


# =========================================================================
# 4. OCR Service Tests
# =========================================================================
def test_ocr_result_structure_and_mock():
    frame = ExtractedFrame(
        frame_id="frm_ocr_01",
        scene_number=1,
        video_timestamp=10.5,
        local_path="frames/test.jpg",
    )
    mock_reader = MagicMock()
    mock_reader.readtext.return_value = [
        ([[10, 10], [90, 10], [90, 40], [10, 40]], "COFFEE", 0.94)
    ]

    with patch.object(ocr_service, "_reader", mock_reader):
        with patch("cv2.imread", return_value=np.zeros((100, 100, 3), dtype=np.uint8)):
            with patch("pathlib.Path.exists", return_value=True):
                results = ocr_service.process_frame("dummy.jpg", frame)
                assert len(results) == 1
                res = results[0]
                assert res.text == "COFFEE"
                assert res.confidence == 0.94
                assert res.frame_id == "frm_ocr_01"
                assert len(res.bounding_boxes) == 1
                assert res.is_brand_candidate is True


# =========================================================================
# 5. Object Detection Tests
# =========================================================================
def test_object_detection_mock():
    frame = ExtractedFrame(
        frame_id="frm_obj_01",
        scene_number=1,
        video_timestamp=12.0,
        local_path="frames/test.jpg",
    )
    mock_box = MagicMock()
    mock_box.cls = [0]
    mock_box.conf = [0.88]
    mock_box.xyxy = [[10.0, 20.0, 50.0, 80.0]]

    mock_result = MagicMock()
    mock_result.boxes = [mock_box]
    mock_result.names = {0: "bottle"}

    mock_model = MagicMock(return_value=[mock_result])
    with patch.object(object_detection_service, "_model", mock_model):
        with patch("cv2.imread", return_value=np.zeros((100, 100, 3), dtype=np.uint8)):
            with patch("pathlib.Path.exists", return_value=True):
                detections = object_detection_service.detect_objects("dummy.jpg", frame)
                assert len(detections) == 1
                det = detections[0]
                assert det.label == "bottle"
                assert det.confidence == 0.88
                assert len(det.bbox) == 4
                assert det.frame_id == "frm_obj_01"


# =========================================================================
# 6. Frame Ranking Tests
# =========================================================================
def test_frame_ranking_order():
    frame_high = ExtractedFrame(
        frame_id="frm_high",
        scene_number=1,
        video_timestamp=5.0,
        local_path="f1.jpg",
        position_in_scene="middle",
    )
    frame_low = ExtractedFrame(
        frame_id="frm_low",
        scene_number=1,
        video_timestamp=5.5,
        local_path="f2.jpg",
        position_in_scene="end",
    )

    ocr_brand = [OCRResult(frame_id="frm_high", text="NIKE", confidence=0.95, is_brand_candidate=True)]
    obj_item = [ObjectDetection(frame_id="frm_high", label="cup", confidence=0.85)]

    rank_high = frame_ranking_service.rank_frame(frame_high, ocr_brand, obj_item)
    rank_low = frame_ranking_service.rank_frame(frame_low, [], [])

    assert rank_high.score > rank_low.score
    selected = frame_ranking_service.select_vision_frames([rank_low, rank_high])
    assert len(selected) == 1
    assert selected[0].frame_id == "frm_high"


# =========================================================================
# 7. VisionProvider Abstraction Tests (Mocked API calls)
# =========================================================================
@pytest.mark.asyncio
async def test_gemini_vision_provider_mock(tmp_path):
    dummy_img = tmp_path / "gemini_frame.jpg"
    dummy_img.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"entities": [{"name": "Coca-Cola", "entity_type": "brand", "confidence": 0.93, "observation": "Visible can", "evidence_type": "direct"}]}'
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiVisionProvider(api_key="mock_key")
    provider._client = mock_client

    res = await provider.analyze_frame(str(dummy_img), {"timestamp": 12.4, "scene_number": 1})
    assert res["status"] in ("VISION_SUCCESS", "SUCCESS")
    assert len(res["entities"]) == 1
    assert res["entities"][0]["name"] == "Coca-Cola"
    assert res["entities"][0]["evidence_type"] == "direct"

@pytest.mark.asyncio
async def test_groq_vision_provider_mock(tmp_path):
    dummy_img = tmp_path / "groq_frame.jpg"
    dummy_img.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb")

    mock_choice = MagicMock()
    mock_choice.message.content = '{"entities": [{"name": "Apple iPhone", "entity_type": "product", "confidence": 0.91, "observation": "Held in hand", "evidence_type": "direct"}]}'
    mock_completion = MagicMock(choices=[mock_choice])

    mock_sdk = MagicMock()
    mock_sdk.chat.completions.create = AsyncMock(return_value=mock_completion)

    provider = GroqVisionProvider(api_key="mock_key")
    provider._sdk_client = mock_sdk

    res = await provider.analyze_frame(str(dummy_img), {"timestamp": 15.2, "scene_number": 2})
    assert res["status"] == "SUCCESS"
    assert res["model"] == "qwen/qwen3.6-27b"
    assert len(res["entities"]) == 1
    assert res["entities"][0]["name"] == "Apple iPhone"

def test_vision_provider_factory():
    # Test fallback when keys are empty and using default configured provider
    with patch.object(settings, "AI_PROVIDER", "gemini"), patch.object(settings, "GROQ_API_KEY", ""), patch.object(settings, "GEMINI_API_KEY", ""):
        prov_fallback = get_vision_provider()
        assert isinstance(prov_fallback, LocalHeuristicVisionProvider)

    # Test explicit provider selection
    prov_groq = get_vision_provider("groq")
    assert isinstance(prov_groq, GroqVisionProvider)

    prov_gem = get_vision_provider("gemini")
    assert isinstance(prov_gem, GeminiVisionProvider)



# =========================================================================
# 8. Entity Deduplication Tests
# =========================================================================
def test_entity_deduplication_variations():
    e1 = Entity(
        production_id="p1",
        name="Coca Cola",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        confidence=0.85,
        scene=1,
        timestamp=4.2,
        frame_path="frames/f1.jpg",
    )
    e2 = Entity(
        production_id="p1",
        name="Coca-Cola",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        confidence=0.95,
        scene=2,
        timestamp=12.8,
        frame_path="frames/f2.jpg",
    )
    e3 = Entity(
        production_id="p1",
        name="COCA COLA",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        confidence=0.90,
        scene=3,
        timestamp=20.1,
        frame_path="frames/f3.jpg",
    )

    canonical, merged = deduplication_service.deduplicate_entities([e1, e2, e3])
    assert len(canonical) == 1
    assert len(merged) == 2
    canon = canonical[0]
    assert canon.appearances == 3
    assert canon.first_seen_timestamp == 4.2
    assert canon.last_seen_timestamp == 20.1
    assert canon.confidence == 0.95
    assert len(canon.evidence_frames) == 3


# =========================================================================
# 9. Screenplay Comparison Tests (BOTH, SCRIPT_ONLY, VISUAL_ONLY)
# =========================================================================
def test_screenplay_comparison_classifications():
    script_text = "SCENE 1: Arjun enters the room drinking a Coke while checking his watch."

    e_coke = Entity(production_id="p1", name="Coke", entity_type=EntityType.BRAND, sources=[EntitySource.VISUAL])
    e_nike = Entity(production_id="p1", name="Nike", entity_type=EntityType.BRAND, sources=[EntitySource.VISUAL])
    e_apple = Entity(production_id="p1", name="Apple", entity_type=EntityType.BRAND, sources=[EntitySource.VISUAL])

    script_only_ent = Entity(production_id="p1", name="Rolex Watch", entity_type=EntityType.PRODUCT, sources=[EntitySource.SCRIPT])

    all_compared, visual_only = screenplay_comparison_service.compare_against_screenplay(
        footage_entities=[e_coke, e_nike, e_apple],
        screenplay_text=script_text,
        script_entities=[script_only_ent],
    )

    classifications = {e.name: e.classification for e in all_compared}
    assert classifications["Coke"] == EntityClassification.BOTH
    assert classifications["Nike"] == EntityClassification.VISUAL_ONLY
    assert classifications["Apple"] == EntityClassification.VISUAL_ONLY
    assert classifications["Rolex Watch"] == EntityClassification.SCRIPT_ONLY

    vo_names = {v.name for v in visual_only}
    assert "Nike" in vo_names
    assert "Apple" in vo_names
    assert "Coke" not in vo_names


# =========================================================================
# 10. Pipeline Events and Cancellation Tests
# =========================================================================
@pytest.mark.asyncio
async def test_visual_pipeline_cancellation(tmp_path):
    vid_path = create_synthetic_micro_video(str(tmp_path / "cancel.mp4"), duration_sec=1.0, fps=24)
    job = AnalysisJob.create_new(production_id="prod_cancel")

    emitted_events = []
    async def mock_emit(job, event_type, **kwargs):
        emitted_events.append(event_type)

    # Immediately cancelled
    results = await visual_agent.execute_visual_pipeline(
        footage_path=vid_path,
        production_id="prod_cancel",
        job_id=job.job_id,
        job=job,
        emit_callback=mock_emit,
        is_cancelled=lambda: True,
    )

    assert results["scenes"] == []
    assert results["extracted_frames"] == []
