"""
Visual Remediation Studio API Endpoints (Phase 12).
Supports listing, triggering, and approving non-destructive optical cleanup proposals.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.models.remediation import RemediationStatus, RemediationType
from app.repositories import get_remediation_repo, get_entity_repo
from app.services.visual_remediation_service import visual_remediation_service

router = APIRouter(prefix="/remediations", tags=["visual_remediation"])


class RemediationGenerateRequest(BaseModel):
    entity_id: str
    remediation_type: Optional[RemediationType] = RemediationType.BLUR_REMOVE
    job_id: Optional[str] = "job_default"


class RemediationStatusUpdate(BaseModel):
    status: RemediationStatus
    reviewed_by: Optional[str] = "VFX Supervisor"
    notes: Optional[str] = None


@router.get(
    "/{production_id}",
    response_model=List[Dict[str, Any]],
    summary="List visual remediation proposals for a production",
)
async def list_remediations(production_id: str):
    repo = get_remediation_repo()
    proposals = await repo.list_for_production(production_id)
    return [p.model_dump(mode="json") if hasattr(p, "model_dump") else p for p in proposals]


@router.post(
    "/{production_id}/generate",
    response_model=Dict[str, Any],
    summary="Generate on-demand visual remediation proposal for an entity",
)
async def generate_remediation_proposal(
    production_id: str,
    payload: RemediationGenerateRequest,
):
    entity_repo = get_entity_repo()
    entity = await entity_repo.get(payload.entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    proposal = await visual_remediation_service.generate_proposal(
        entity=entity,
        remediation_type=payload.remediation_type or RemediationType.BLUR_REMOVE,
        job_id=payload.job_id or "job_default",
    )

    if not proposal:
        raise HTTPException(
            status_code=422,
            detail="Failed to generate visual remediation: No valid candidate frame with bounding box found.",
        )

    rem_repo = get_remediation_repo()
    await rem_repo.save(proposal)
    return proposal.model_dump(mode="json")


@router.post(
    "/{production_id}/{remediation_id}/status",
    response_model=Dict[str, Any],
    summary="Update remediation approval status (ACCEPTED, REJECTED, IN_REVIEW)",
)
async def update_remediation_status(
    production_id: str,
    remediation_id: str,
    payload: RemediationStatusUpdate,
):
    rem_repo = get_remediation_repo()
    proposal = await rem_repo.get(remediation_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Remediation proposal not found")

    proposal.status = payload.status
    if payload.reviewed_by:
        proposal.reviewed_by = payload.reviewed_by
        proposal.reviewed_at = datetime.now(timezone.utc)
    if payload.notes:
        proposal.notes = payload.notes

    await rem_repo.save(proposal)
    return {
        "remediation_id": proposal.remediation_id,
        "status": proposal.status.value,
        "reviewed_by": proposal.reviewed_by,
        "reviewed_at": proposal.reviewed_at.isoformat() if proposal.reviewed_at else None,
    }
