from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import uuid
from pydantic import BaseModel, Field, computed_field

class EntitySource(str, Enum):
    SCRIPT = "SCRIPT"
    VISUAL = "VISUAL"
    AUDIO = "AUDIO"

class EntityClassification(str, Enum):
    BOTH = "BOTH"
    SCRIPT_ONLY = "SCRIPT_ONLY"
    VISUAL_ONLY = "VISUAL_ONLY"
    AUDIO_ONLY = "AUDIO_ONLY"

class EntityType(str, Enum):
    BRAND = "BRAND"
    TRADEMARK = "TRADEMARK"
    PRODUCT = "PRODUCT"
    COMPANY = "COMPANY"
    PERSON = "PERSON"
    PUBLIC_FIGURE = "PUBLIC_FIGURE"
    MUSIC = "MUSIC"
    ARTWORK = "ARTWORK"
    POSTER = "POSTER"
    BOOK = "BOOK"
    FILM = "FILM"
    TV_SHOW = "TV_SHOW"
    FILM_TV = "FILM_TV"
    LOCATION = "LOCATION"
    SIGNAGE = "SIGNAGE"
    VEHICLE = "VEHICLE"
    OTHER = "OTHER"

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"

class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    UNVERIFIED = "UNVERIFIED"
    CONFIRMED = "CONFIRMED"
    DISPUTED = "DISPUTED"
    INCONCLUSIVE = "INCONCLUSIVE"

class ResolutionStatus(str, Enum):
    PENDING = "PENDING"
    FAIR_USE_ARGUMENT = "FAIR_USE_ARGUMENT"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"
    BLUR_REQUIRED = "BLUR_REQUIRED"
    POST_PRODUCTION_BLUR = "POST_PRODUCTION_BLUR"
    REPLACE_REQUIRED = "REPLACE_REQUIRED"
    APPROVED = "APPROVED"

class VisualCertainty(str, Enum):
    DIRECTLY_VISIBLE = "DIRECTLY_VISIBLE"
    INFERRED = "INFERRED"
    UNCERTAIN = "UNCERTAIN"

class Entity(BaseModel):
    id: str = Field(default_factory=lambda: f"ent_{uuid.uuid4().hex[:10]}")
    production_id: str
    job_id: Optional[str] = None
    name: str
    entity_type: EntityType = EntityType.BRAND
    sources: List[EntitySource] = Field(default_factory=lambda: [EntitySource.VISUAL])
    confidence: float = 0.85
    scene: Optional[int] = None
    timestamp: Optional[float] = None
    first_seen_timestamp: Optional[float] = None
    last_seen_timestamp: Optional[float] = None
    appearances: int = 1
    context: Optional[str] = None
    frame_path: Optional[str] = None
    bounding_box: List[float] = Field(default_factory=list)
    clearance_type: str = "TRADEMARK"
    risk_id: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    risk_score: float = 0.0
    risk_confidence: float = 0.0
    rights_holder: Optional[str] = None
    research_status: Optional[str] = None
    candidate_rights_holder: Optional[str] = None
    research_confidence: float = 0.0
    evidence_ids: List[str] = Field(default_factory=list)
    evidence_frames: List[str] = Field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.PENDING
    verification_id: Optional[str] = None
    verification_decision: Optional[str] = None
    verification_confidence: float = 0.0
    resolution_id: Optional[str] = None
    resolution_status: Union[str, Any] = "PENDING"
    resolution_priority: Optional[str] = None
    resolution_action: Optional[str] = None
    visual_basis: Optional[str] = None
    prominence: Optional[str] = "medium"  # "high", "medium", "low"
    commercial_context: bool = False
    visual_certainty: VisualCertainty = VisualCertainty.DIRECTLY_VISIBLE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @computed_field
    @property
    def source(self) -> str:
        """Helper for primary source string representation"""
        if len(self.sources) > 1:
            return "BOTH"
        return self.sources[0].value if self.sources else "VISUAL"

    @computed_field
    @property
    def classification(self) -> EntityClassification:
        """Derive entity classification from source sets without hardcoding"""
        has_script = EntitySource.SCRIPT in self.sources
        has_visual = EntitySource.VISUAL in self.sources
        has_audio = EntitySource.AUDIO in self.sources

        if has_script and has_visual:
            return EntityClassification.BOTH
        if has_script and not has_visual and not has_audio:
            return EntityClassification.SCRIPT_ONLY
        if has_visual and not has_script:
            return EntityClassification.VISUAL_ONLY
        if has_audio and not has_script and not has_visual:
            return EntityClassification.AUDIO_ONLY
        return EntityClassification.VISUAL_ONLY
