from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, computed_field, model_validator
from app.models.entity import VerificationStatus

class VerificationDecision(str, Enum):
    CONFIRMED = "CONFIRMED"
    REVIEW = "REVIEW"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class VerificationCheck(BaseModel):
    check_id: str = Field(default_factory=lambda: f"chk_{uuid.uuid4().hex[:8]}")
    name: str
    passed: bool
    evidence_evaluated: List[str] = Field(default_factory=list)
    explanation: str
    severity_if_failed: str = "MEDIUM"  # "HIGH", "MEDIUM", "LOW"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class VerificationResult(BaseModel):
    verification_id: str = Field(default_factory=lambda: f"ver_{uuid.uuid4().hex[:10]}")
    entity_id: str
    production_id: str
    entity_name: str = ""
    decision: VerificationDecision = VerificationDecision.REVIEW
    confidence: float = 0.8
    checks_run: List[VerificationCheck] = Field(default_factory=list)
    claims_supported: List[str] = Field(default_factory=list)
    claims_disputed: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    recommended_action: str = ""
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    registry_source: str = "USPTO / Trademark Database"
    registration_number: Optional[str] = None
    notes: Optional[str] = None
    license_required: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def handle_compat_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "id" in data and "verification_id" not in data:
                data["verification_id"] = data["id"]
            if "status" in data and "decision" not in data:
                status_val = data["status"]
                if hasattr(status_val, "value"):
                    status_val = status_val.value
                if status_val == "CONFIRMED":
                    data["decision"] = VerificationDecision.CONFIRMED
                elif status_val == "DISPUTED":
                    data["decision"] = VerificationDecision.REJECTED
                elif status_val == "INCONCLUSIVE":
                    data["decision"] = VerificationDecision.INSUFFICIENT_EVIDENCE
                else:
                    data["decision"] = VerificationDecision.REVIEW
            if "rights_holder" in data:
                if "metadata" not in data or data["metadata"] is None:
                    data["metadata"] = {}
                data["metadata"]["rights_holder"] = data["rights_holder"]
            if "match_confidence" in data and "confidence" not in data:
                data["confidence"] = data["match_confidence"]
        return data

    @computed_field
    @property
    def id(self) -> str:
        return self.verification_id

    @computed_field
    @property
    def status(self) -> VerificationStatus:
        if self.decision == VerificationDecision.CONFIRMED:
            return VerificationStatus.CONFIRMED
        elif self.decision == VerificationDecision.REJECTED:
            return VerificationStatus.DISPUTED
        elif self.decision == VerificationDecision.INSUFFICIENT_EVIDENCE:
            return VerificationStatus.INCONCLUSIVE
        return VerificationStatus.UNVERIFIED

    @computed_field
    @property
    def rights_holder(self) -> str:
        if "rights_holder" in self.metadata:
            return str(self.metadata["rights_holder"])
        return self.entity_name or "Pending Verification"

    @computed_field
    @property
    def match_confidence(self) -> float:
        return self.confidence
