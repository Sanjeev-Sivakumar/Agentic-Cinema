from typing import Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.models.video import ExtractedFrame, FrameRanking, OCRResult, ObjectDetection, ObjectDetectionResult, RankedFrame

class FrameRankingService:
    """
    Local multi-signal frame ranking service for Gemini cost minimization.
    Ranks candidate frames within each scene based on OCR text presence,
    brand candidates, object detection density, and visual complexity.
    """

    def __init__(
        self,
        frames_per_scene: Optional[int] = None,
        max_job_frames: Optional[int] = None,
    ):
        self.frames_per_scene = frames_per_scene or getattr(settings, "VISION_FRAMES_PER_SCENE", getattr(settings, "GEMINI_FRAMES_PER_SCENE", 1))
        self.max_job_frames = max_job_frames or getattr(settings, "MAX_VISION_FRAMES_PER_JOB", getattr(settings, "GEMINI_MAX_FRAMES_PER_JOB", 50))
        logger.info(
            f"[FrameRankingService] Initialized (candidate_extraction_per_scene={getattr(settings, 'FRAMES_PER_SCENE', 3)}, "
            f"vision_selected_per_scene={self.frames_per_scene}, max_vision_budget={self.max_job_frames})"
        )

    def rank_frame(
        self,
        frame: ExtractedFrame,
        ocr_results: List[OCRResult],
        object_results: List[ObjectDetectionResult],
    ) -> FrameRanking:
        """Compute composite ranking score for an individual candidate frame."""
        score = 0.0
        reasons: List[str] = []

        # 1. OCR text signal (Highest weight for clearance intelligence)
        brand_candidates = [r for r in ocr_results if r.is_brand_candidate]
        if brand_candidates:
            score += 45.0 + len(brand_candidates) * 10.0
            reasons.append(f"Detected {len(brand_candidates)} high-contrast brand/text candidate regions")
        elif ocr_results:
            score += 25.0 + len(ocr_results) * 5.0
            reasons.append(f"Found {len(ocr_results)} text elements")

        if ocr_results:
            avg_ocr_conf = sum(r.confidence for r in ocr_results) / len(ocr_results)
            score += avg_ocr_conf * 10.0

        # 2. Object detection signal
        clearance_objects = [
            o for o in object_results
            if (o.label or o.class_name) in {"bottle", "cup", "cell phone", "laptop", "car", "book", "poster", "sign", "candidate_product"}
        ]
        if clearance_objects:
            score += 30.0 + len(clearance_objects) * 5.0
            reasons.append(f"Identified {len(clearance_objects)} potential clearance objects ({', '.join(set((o.label or o.class_name) for o in clearance_objects[:3]))})")
        elif object_results:
            score += 15.0
            reasons.append(f"Detected {len(object_results)} visual objects")

        if object_results:
            avg_obj_conf = sum(o.confidence for o in object_results) / len(object_results)
            score += avg_obj_conf * 10.0

        # 3. Scene position heuristics (middle frames often provide optimal framing)
        if frame.position_in_scene == "middle":
            score += 10.0
            reasons.append("Optimal mid-scene composition")
        else:
            score += 5.0

        return RankedFrame(
            frame_id=frame.frame_id,
            scene_number=frame.scene_number,
            video_timestamp=frame.video_timestamp,
            frame_path=frame.local_path,
            score=round(score, 2),
            ranking_score=round(score, 2),
            reasons=reasons,
            ranking_reasons=reasons,
            ocr_count=len(ocr_results),
            object_count=len(object_results),
        )

    def select_vision_frames(
        self,
        ranked_frames: List[FrameRanking],
    ) -> List[FrameRanking]:
        """
        Group ranked frames by scene and select top N frames per scene,
        respecting total job budget limits.
        """
        by_scene: Dict[int, List[FrameRanking]] = {}
        for r in ranked_frames:
            by_scene.setdefault(r.scene_number, []).append(r)

        per_scene_limit = getattr(settings, "VISION_FRAMES_PER_SCENE", getattr(settings, "GEMINI_FRAMES_PER_SCENE", self.frames_per_scene))
        max_budget = getattr(settings, "MAX_VISION_FRAMES_PER_JOB", getattr(settings, "GEMINI_MAX_FRAMES_PER_JOB", self.max_job_frames))

        selected: List[FrameRanking] = []
        if len(by_scene) <= max_budget:
            # Guarantee at least 1 top candidate frame per detected scene
            for scene_num, scene_rankings in sorted(by_scene.items()):
                sorted_scene = sorted(scene_rankings, key=lambda x: x.ranking_score, reverse=True)
                if sorted_scene:
                    selected.append(sorted_scene[0])

            # Allocate remaining budget to secondary frames from highest-scoring scenes
            remaining_budget = max_budget - len(selected)
            if remaining_budget > 0 and per_scene_limit > 1:
                secondary = []
                for scene_num, scene_rankings in sorted(by_scene.items()):
                    sorted_scene = sorted(scene_rankings, key=lambda x: x.ranking_score, reverse=True)
                    secondary.extend(sorted_scene[1:per_scene_limit])
                secondary_sorted = sorted(secondary, key=lambda x: x.ranking_score, reverse=True)
                selected.extend(secondary_sorted[:remaining_budget])
        else:
            # When scenes exceed budget, pick the top scenes by best candidate score
            scene_bests = [
                max(rankings, key=lambda x: x.ranking_score)
                for rankings in by_scene.values()
                if rankings
            ]
            selected = sorted(scene_bests, key=lambda x: x.ranking_score, reverse=True)[:max_budget]

        logger.info(f"[FrameRankingService] Selected {len(selected)} highest-value frames for multimodal vision (budget: {max_budget})")
        return selected

frame_ranking_service = FrameRankingService()
