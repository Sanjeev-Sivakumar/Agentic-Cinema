"""
Clearance Outreach Models (Phase 11).
Automated Rights Permission Request Drafting and Approval Lifecycle.
Constraint: CREATE DRAFT ONLY — Never auto-sends without human approval.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class OutreachStatus(str, Enum):
    DRAFTED = "DRAFTED"
    PENDING_HUMAN_APPROVAL = "PENDING_HUMAN_APPROVAL"
    SENT = "SENT"
    AWAITING_RESPONSE = "AWAITING_RESPONSE"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    RESOLVED = "RESOLVED"


class ClearanceOutreachDraft(BaseModel):
    outreach_id: str = Field(default_factory=lambda: f"out_{uuid.uuid4().hex[:10]}")
    entity_id: str
    production_id: str
    entity_name: str
    rights_holder: str
    recipient_name: Optional[str] = "Clearance / Licensing Department"
    recipient_email: str
    subject: str
    body_text: str
    body_html: str
    scene_number: Optional[int] = None
    timestamp: Optional[float] = None
    exposure_duration_sec: Optional[float] = None
    requested_rights_scope: str = "Worldwide, Theatrical, Broadcast, Streaming & All Media in Perpetuity"
    status: OutreachStatus = OutreachStatus.DRAFTED
    requires_human_approval: bool = True
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    gmail_draft_id: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.outreach_id
