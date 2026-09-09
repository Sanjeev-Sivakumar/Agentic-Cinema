from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, model_validator
from app.models.evidence import Evidence

class ResearchStatus(str, Enum):
    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    API_ERROR = "API_ERROR"
    RATE_LIMITED = "RATE_LIMITED"

class ResearchResult(BaseModel):
    """
    Structured factual research result for a clearance-relevant entity.
    Represents objective identity and rights-holder findings without legal conclusions.
    """
    id: str = Field(default_factory=lambda: f"res_{uuid.uuid4().hex[:10]}")
    production_id: Optional[str] = "global"
    job_id: Optional[str] = None
    entity_id: Optional[str] = None
    entity_name: str
    entity_type: str = "brand"

    status: ResearchStatus = ResearchStatus.SUCCESS
    candidate_rights_holder: Optional[str] = None

    identity_confidence: float = 0.0
    research_confidence: float = 0.0

    evidence: List[Evidence] = Field(default_factory=list)
    query: Optional[str] = None
    provider: str = "local"
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def handle_compat_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rights_holder" in data and "candidate_rights_holder" not in data:
                data["candidate_rights_holder"] = data["rights_holder"]
        return data

    @property
    def rights_holder(self) -> Optional[str]:
        return self.candidate_rights_holder

    @property
    def confidence(self) -> float:
        return self.research_confidence or self.identity_confidence

    def get(self, item: str, default: Any = None) -> Any:
        """Dictionary-like access compatibility for callers expecting dict."""
        if item == "rights_holder":
            return self.candidate_rights_holder or default
        if hasattr(self, item):
            val = getattr(self, item)
            return val if val is not None else default
        return self.metadata.get(item, default)
