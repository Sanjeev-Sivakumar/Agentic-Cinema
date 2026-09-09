import pytest
from app.models.entity import Entity, EntitySource, EntityType, RiskLevel
from app.models.video import ExtractedFrame, FrameRanking, OCRResult, ObjectDetectionResult, Scene
from app.services import (
    deduplication_service,
    entity_service,
    frame_ranking_service,
    ocr_service,
    object_detection_service,
    scene_detection_service,
    screenplay_comparison_service,
    video_service,
)

def test_video_metadata_missing_file():
    with pytest.raises(FileNotFoundError):
        video_service.inspect_video("non_existent_video.mp4")

def test_frame_ranking_signals():
    frame = ExtractedFrame(
        scene_number=1,
        video_timestamp=12.5,
        local_path="frames/test.jpg",
        position_in_scene="middle",
    )
    ocr_hits = [
        OCRResult(text="STARLIGHT COFFEE", confidence=0.95, bounding_box=[0.1, 0.1, 0.2, 0.2], frame_id=frame.frame_id, timestamp=12.5, is_brand_candidate=True)
    ]
    obj_hits = [
        ObjectDetectionResult(class_name="cup", confidence=0.88, bounding_box=[0.1, 0.1, 0.2, 0.2], frame_id=frame.frame_id, timestamp=12.5)
    ]

    ranking = frame_ranking_service.rank_frame(frame, ocr_hits, obj_hits)
    assert ranking.ranking_score > 60.0
    assert ranking.ocr_count == 1
    assert ranking.object_count == 1

def test_entity_service_conversion():
    detection = {
        "name": "Apex Smartphone X10",
        "entity_type": "product",
        "confidence": 0.94,
        "visual_basis": "Held by character in foreground",
        "prominence": "high",
        "commercial_context": False,
        "certainty": "DIRECTLY_VISIBLE",
    }
    entity = entity_service.create_entity_from_detection(
        detection=detection,
        production_id="prod_01",
        job_id="job_01",
        scene_number=2,
        timestamp=18.4,
        frame_path="frames/scene02_184.jpg",
    )
    assert entity.name == "Apex Smartphone X10"
    assert entity.entity_type == EntityType.PRODUCT
    assert entity.confidence == 0.94
    assert entity.risk_score >= 70.0
    assert entity.classification.value == "VISUAL_ONLY"

def test_entity_deduplication():
    e1 = Entity(
        production_id="prod_01",
        name="Coca Cola",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        confidence=0.85,
        scene=1,
        frame_path="frames/sc01.jpg",
    )
    e2 = Entity(
        production_id="prod_01",
        name="Coca-Cola",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        confidence=0.95,
        scene=2,
        frame_path="frames/sc02.jpg",
    )
    canonical, merged = deduplication_service.deduplicate_entities([e1, e2])
    assert len(canonical) == 1
    assert len(merged) == 1
    assert canonical[0].confidence == 0.95
    assert len(canonical[0].evidence_ids) >= 1

def test_screenplay_comparison_visual_only_isolation():
    script_text = "SCENE 1: Arjun enters the cafe and pulls out an Apex smartphone."
    e_script = Entity(
        production_id="prod_01",
        name="Apex Smartphone",
        entity_type=EntityType.PRODUCT,
        sources=[EntitySource.VISUAL],
    )
    e_unscripted_brand = Entity(
        production_id="prod_01",
        name="Starlight Roast Coffee",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
    )

    all_entities, visual_only = screenplay_comparison_service.compare_against_screenplay(
        [e_script, e_unscripted_brand],
        script_text,
    )

    assert e_script.classification.value == "BOTH"
    assert e_unscripted_brand.classification.value == "VISUAL_ONLY"
    assert len(visual_only) == 1
    assert visual_only[0].name == "Starlight Roast Coffee"
