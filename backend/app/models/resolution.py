from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, computed_field, model_validator

class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    MORE_EVIDENCE_REQUIRED = "MORE_EVIDENCE_REQUIRED"
    RESEARCH_REQUIRED = "RESEARCH_REQUIRED"
    REPLACEMENT_RECOMMENDED = "REPLACEMENT_RECOMMENDED"
    ESCALATED = "ESCALATED"
    UNRESOLVED = "UNRESOLVED"
    PENDING = "PENDING"

class ResolutionAction(str, Enum):
    NO_ACTION = "NO_ACTION"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    COLLECT_EVIDENCE = "COLLECT_EVIDENCE"
    CONDUCT_RESEARCH = "CONDUCT_RESEARCH"
    REQUEST_RIGHTS_INFORMATION = "REQUEST_RIGHTS_INFORMATION"
    REQUEST_LICENSE_INFORMATION = "REQUEST_LICENSE_INFORMATION"
    REVIEW_MUSIC_USAGE = "REVIEW_MUSIC_USAGE"
    REVIEW_BRAND_USAGE = "REVIEW_BRAND_USAGE"
    REVIEW_LOCATION_USAGE = "REVIEW_LOCATION_USAGE"
    REVIEW_ARTWORK_USAGE = "REVIEW_ARTWORK_USAGE"
    REVIEW_PUBLIC_FIGURE_USAGE = "REVIEW_PUBLIC_FIGURE_USAGE"
    CONSIDER_REPLACEMENT = "CONSIDER_REPLACEMENT"
    ESCALATE = "ESCALATE"

class ResolutionPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class ResolutionResult(BaseModel):
    resolution_id: str = Field(default_factory=lambda: f"res_{uuid.uuid4().hex[:10]}")
    entity_id: str
    production_id: str
    job_id: Optional[str] = None
    entity_name: str = ""
    entity_type: str = "BRAND"
    verification_decision: Optional[str] = None
    risk_level: str = "UNKNOWN"
    risk_score: float = 0.0
    resolution_status: ResolutionStatus = ResolutionStatus.UNRESOLVED
    recommended_action: ResolutionAction = ResolutionAction.HUMAN_REVIEW
    priority: ResolutionPriority = ResolutionPriority.MEDIUM
    action_reason: str = ""
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    required_information: List[str] = Field(default_factory=list)
    research_action: Optional[str] = None
    replacement_suggestion: Optional[str] = None
    confidence: float = 0.8
    resolver: str = "DeterministicResolutionEngine"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def handle_compat_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "id" in data and "resolution_id" not in data:
                data["resolution_id"] = data["id"]
            if "action_type" in data and "recommended_action" not in data:
                action_val = data["action_type"]
                if hasattr(action_val, "value"):
                    action_val = action_val.value
                data["recommended_action"] = action_val
            if "status" in data and "resolution_status" not in data:
                status_val = data["status"]
                if hasattr(status_val, "value"):
                    status_val = status_val.value
                data["resolution_status"] = status_val
        return data

    @computed_field
    @property
    def id(self) -> str:
        return self.resolution_id

    @computed_field
    @property
    def action_type(self) -> str:
        return self.recommended_action.value if hasattr(self.recommended_action, "value") else str(self.recommended_action)

    @computed_field
    @property
    def status(self) -> str:
        return self.resolution_status.value if hasattr(self.resolution_status, "value") else str(self.resolution_status)
