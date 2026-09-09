"""
Visual Remediation Studio Models (Phase 12).
Proposes Gaussian blur, neutral prop replacement, and AI inpainting
for unscripted VISUAL_ONLY or high-risk visual entities.
Constraint: PROPOSED REMEDIATION — HUMAN/EDITOR REVIEW REQUIRED. Never overwrites original video footage.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class RemediationType(str, Enum):
    BLUR_REMOVE = "BLUR_REMOVE"
    NEUTRAL_REPLACEMENT = "NEUTRAL_REPLACEMENT"
    AI_INPAINTING = "AI_INPAINTING"


class RemediationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    IN_REVIEW = "IN_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class VisualRemediationProposal(BaseModel):
    remediation_id: str = Field(default_factory=lambda: f"rem_{uuid.uuid4().hex[:10]}")
    entity_id: str
    production_id: str
    job_id: str = "job_default"
    entity_name: str
    scene_number: Optional[int] = None
    timestamp: Optional[float] = None
    original_frame_path: str
    original_frame_url: Optional[str] = None
    mask_path: str
    mask_url: Optional[str] = None
    proposed_frame_path: str
    proposed_frame_url: Optional[str] = None
    comparison_frame_path: Optional[str] = None
    comparison_frame_url: Optional[str] = None
    remediation_type: RemediationType = RemediationType.BLUR_REMOVE
    bounding_box: List[int] = Field(default_factory=list)  # [ymin, xmin, ymax, xmax] or [x, y, w, h]
    status: RemediationStatus = RemediationStatus.PROPOSED
    disclaimer: str = "PROPOSED REMEDIATION — HUMAN/EDITOR REVIEW REQUIRED. Original video footage remains unmodified."
    vfx_time_estimate_hours: float = 1.5
    vfx_cost_estimate_usd: float = 1200.0
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.remediation_id

    @property
    def remediated_frame_path(self) -> str:
        return self.proposed_frame_path

    @property
    def remediated_frame_url(self) -> Optional[str]:
        return self.proposed_frame_url

    @property
    def human_review_disclaimer(self) -> str:
        return self.disclaimer
