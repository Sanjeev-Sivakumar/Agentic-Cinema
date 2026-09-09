from typing import Any, Dict, List
from app.core.logging import logger
from app.models.entity import Entity, EntitySource, EntityType, RiskLevel, VisualCertainty

class EntityService:
    """
    Converts raw vision & Gemini detections into typed Entity domain models.
    """

    TYPE_MAP = {
        "brand": EntityType.BRAND,
        "trademark": EntityType.TRADEMARK,
        "product": EntityType.PRODUCT,
        "company": EntityType.COMPANY,
        "person": EntityType.PERSON,
        "public_figure": EntityType.PUBLIC_FIGURE,
        "artist": EntityType.PUBLIC_FIGURE,
        "music": EntityType.MUSIC,
        "artwork": EntityType.ARTWORK,
        "poster": EntityType.POSTER,
        "book": EntityType.BOOK,
        "film": EntityType.FILM,
        "tv_show": EntityType.TV_SHOW,
        "tv": EntityType.TV_SHOW,
        "location": EntityType.LOCATION,
        "signage": EntityType.SIGNAGE,
        "vehicle": EntityType.VEHICLE,
        "other": EntityType.OTHER,
    }

    def create_entity_from_detection(
        self,
        detection: Dict[str, Any],
        production_id: str,
        job_id: str,
        scene_number: int,
        timestamp: float,
        frame_path: str,
    ) -> Entity:
        name = detection.get("name", "Unknown Entity").strip()
        raw_type = str(detection.get("entity_type", "brand")).lower()
        entity_type = self.TYPE_MAP.get(raw_type, EntityType.BRAND)
        confidence = float(detection.get("confidence", 0.85))
        visual_basis = detection.get("observation") or detection.get("visual_basis", "Visual presence in video frame")
        prominence = detection.get("prominence", "medium")
        commercial_ctx = bool(detection.get("commercial_context", False))

        evidence_type = str(detection.get("evidence_type") or detection.get("certainty") or "direct").lower()
        certainty = VisualCertainty.DIRECTLY_VISIBLE
        if "infer" in evidence_type:
            certainty = VisualCertainty.INFERRED
        elif "uncert" in evidence_type:
            certainty = VisualCertainty.UNCERTAIN

        # Estimate clearance risk score
        risk_score = 75.0 if prominence == "high" else (50.0 if prominence == "medium" else 30.0)
        risk_level = RiskLevel.HIGH if risk_score >= 70 else (RiskLevel.MEDIUM if risk_score >= 40 else RiskLevel.LOW)

        return Entity(
            production_id=production_id,
            job_id=job_id,
            name=name,
            entity_type=entity_type,
            sources=[EntitySource.VISUAL],
            confidence=confidence,
            scene=scene_number,
            timestamp=timestamp,
            context=visual_basis,
            frame_path=frame_path,
            clearance_type="TRADEMARK" if entity_type in {EntityType.BRAND, EntityType.TRADEMARK, EntityType.PRODUCT} else "COPYRIGHT",
            risk_level=risk_level,
            risk_score=risk_score,
            visual_basis=visual_basis,
            prominence=prominence,
            commercial_context=commercial_ctx,
            visual_certainty=certainty,
        )

entity_service = EntityService()
