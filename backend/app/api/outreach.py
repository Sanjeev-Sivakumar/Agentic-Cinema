"""
Clearance Outreach API Endpoints (Phase 11).
Supports reviewing, approving, and managing the lifecycle of rights clearance request drafts.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.models.outreach import OutreachStatus
from app.repositories import get_outreach_repo
from app.services.gmail_service import gmail_service

router = APIRouter(prefix="/outreach", tags=["clearance_outreach"])


class OutreachStatusUpdate(BaseModel):
    status: OutreachStatus
    notes: Optional[str] = None
    approved_by: Optional[str] = "Legal Coordinator"


@router.get(
    "/{production_id}",
    response_model=List[Dict[str, Any]],
    summary="List all clearance outreach draft packages for a production",
)
async def list_outreach_drafts(production_id: str):
    repo = get_outreach_repo()
    drafts = await repo.list_for_production(production_id)
    return [d.model_dump(mode="json") if hasattr(d, "model_dump") else d for d in drafts]


@router.get(
    "/{production_id}/{outreach_id}",
    response_model=Dict[str, Any],
    summary="Get clearance outreach draft package details",
)
async def get_outreach_draft(production_id: str, outreach_id: str):
    repo = get_outreach_repo()
    draft = await repo.get(outreach_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Outreach draft not found")
    return draft.model_dump(mode="json") if hasattr(draft, "model_dump") else draft


@router.post(
    "/{production_id}/{outreach_id}/approve",
    response_model=Dict[str, Any],
    summary="Approve clearance permission request and sync Gmail draft",
)
async def approve_outreach_draft(
    production_id: str,
    outreach_id: str,
    approved_by: Optional[str] = "Lead Production Counsel",
):
    repo = get_outreach_repo()
    draft = await repo.get(outreach_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Outreach draft not found")

    draft.status = OutreachStatus.PENDING_HUMAN_APPROVAL
    draft.approved_by = approved_by
    draft.approved_at = datetime.now(timezone.utc)
    draft.updated_at = datetime.now(timezone.utc)

    # Ensure Gmail Draft exists
    if not draft.gmail_draft_id:
        g_res = await gmail_service.create_draft(
            to_email=draft.recipient_email,
            subject=draft.subject,
            body_text=draft.body_text,
            body_html=draft.body_html,
            outreach_id=draft.outreach_id,
        )
        draft.gmail_draft_id = g_res.get("draft_id")

    await repo.save(draft)
    return {
        "status": "APPROVED",
        "outreach_id": draft.outreach_id,
        "gmail_draft_id": draft.gmail_draft_id,
        "message": f"Outreach package approved by '{approved_by}'. Ready for review in Gmail/Dashboard.",
        "draft": draft.model_dump(mode="json") if hasattr(draft, "model_dump") else draft,
    }


@router.post(
    "/{production_id}/{outreach_id}/status",
    response_model=Dict[str, Any],
    summary="Update outreach lifecycle status (SENT, AWAITING_RESPONSE, APPROVED, DECLINED)",
)
async def update_outreach_status(
    production_id: str,
    outreach_id: str,
    payload: OutreachStatusUpdate,
):
    repo = get_outreach_repo()
    draft = await repo.get(outreach_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Outreach draft not found")

    draft.status = payload.status
    if payload.notes:
        draft.notes = payload.notes
    if payload.approved_by:
        draft.approved_by = payload.approved_by
    draft.updated_at = datetime.now(timezone.utc)

    await repo.save(draft)
    return {
        "outreach_id": draft.outreach_id,
        "status": draft.status.value,
        "updated_at": draft.updated_at.isoformat(),
    }
