from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

class EvidenceType(str, Enum):
    VIDEO_FRAME = "VIDEO_FRAME"
    SCRIPT_EXCERPT = "SCRIPT_EXCERPT"
    OCR_DETECTION = "OCR_DETECTION"
    OBJECT_BOUNDING_BOX = "OBJECT_BOUNDING_BOX"
    AUDIO_WAVEFORM = "AUDIO_WAVEFORM"
    RESEARCH_EVIDENCE = "RESEARCH_EVIDENCE"

class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: f"evi_{uuid.uuid4().hex[:10]}")
    production_id: Optional[str] = "global"
    entity_id: Optional[str] = None
    job_id: Optional[str] = None
    evidence_type: EvidenceType = EvidenceType.VIDEO_FRAME
    timestamp: Optional[float] = None
    scene_number: Optional[int] = None
    frame_path: Optional[str] = None
    ocr_text: Optional[str] = None
    bounding_box: Optional[List[float]] = None  # [x_norm, y_norm, width_norm, height_norm]
    confidence: float = 0.90
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Research-specific evidence extensions
    entity_name: Optional[str] = None
    claim: Optional[str] = None
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    excerpt: Optional[str] = None
    source_type: Optional[str] = None  # "official", "registry", "news", "secondary", "local_fixture"
    candidate_rights_holder: Optional[str] = None
    registration_number: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    provider: Optional[str] = None

    @property
    def evidence_id(self) -> str:
        """Alias for standard ID field."""
        return self.id
