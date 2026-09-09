from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, Field

class ClearanceActionType(str, Enum):
    APPROVE_INCIDENTAL = "APPROVE_INCIDENTAL"
    FAIR_USE_ARGUMENT = "FAIR_USE_ARGUMENT"
    LICENSE_OUTREACH = "LICENSE_OUTREACH"
    POST_PRODUCTION_BLUR = "POST_PRODUCTION_BLUR"
    VFX_REPLACE = "VFX_REPLACE"
    CUT_SCENE = "CUT_SCENE"

class ClearanceStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    IN_PROGRESS = "IN_PROGRESS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"

class ClearanceRequest(BaseModel):
    id: str = Field(default_factory=lambda: f"clr_{uuid.uuid4().hex[:10]}")
    production_id: str
    entity_id: str
    action_type: ClearanceActionType = ClearanceActionType.LICENSE_OUTREACH
    status: ClearanceStatus = ClearanceStatus.PENDING_REVIEW
    assigned_to: Optional[str] = "Legal Clearance Team"
    rights_holder_contact: Optional[str] = None
    estimated_license_fee: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
