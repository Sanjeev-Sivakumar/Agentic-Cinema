"""
ADK Visual Remediation Tools (Phase 12).
Generates proposed optical cleanups (Gaussian blur, neutral replacement, AI inpainting)
for VISUAL_ONLY and high-risk visual entities.
SAFETY GUARANTEE: Never modifies original footage.
"""
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.entity import EntityClassification
from app.models.events import EventType, PipelineStage
from app.models.remediation import RemediationType
from app.adk.context import WorkflowContext
from app.adk.callbacks import WorkflowCallbacks
from app.services.visual_remediation_service import visual_remediation_service
from app.repositories import get_remediation_repo


async def generate_visual_remediation_tool(
    context: WorkflowContext,
    entity_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generates non-destructive visual remediation proposals for visual entities.
    """
    import time
    start_time = time.perf_counter()
    logger.info(
        f"[ADK] Stage 11 VISUAL_REMEDIATION started (production_id='{context.production_id}', "
        f"target_entity_ids={len(entity_ids) if entity_ids else 'all'})"
    )
    entities = await context.entity_repo.list_by_production(context.production_id)
    if entity_ids:
        entities = [e for e in entities if e.id in entity_ids]

    remediation_repo = get_remediation_repo()
    proposals: List[Dict[str, Any]] = []

    # Prioritize VISUAL_ONLY entities and entities with visual frames
    visual_entities = [
        e for e in entities
        if e.classification in (EntityClassification.VISUAL_ONLY, EntityClassification.BOTH)
        or bool(e.frame_path) or bool(e.evidence_frames)
    ]

    for entity in visual_entities:
        # Determine appropriate remediation type
        rem_type = RemediationType.BLUR_REMOVE
        if entity.classification == EntityClassification.VISUAL_ONLY:
            rem_type = RemediationType.NEUTRAL_REPLACEMENT

        proposal = await visual_remediation_service.generate_proposal(
            entity=entity,
            remediation_type=rem_type,
            job_id=context.state.job_id,
        )

        if proposal:
            await remediation_repo.save(proposal)
            proposals.append(proposal.model_dump(mode="json"))

            await WorkflowCallbacks.emit_event(
                context=context,
                event_type=EventType.REMEDIATION_PROPOSED,
                stage=PipelineStage.VISUAL_REMEDIATION,
                payload={
                    "remediation_id": proposal.remediation_id,
                    "entity_id": entity.id,
                    "entity_name": entity.name,
                    "remediation_type": proposal.remediation_type.value,
                    "proposed_frame_url": proposal.proposed_frame_url,
                    "comparison_frame_url": proposal.comparison_frame_url,
                    "status": proposal.status.value,
                },
                message=f"Generated visual remediation proposal for '{entity.name}' ({proposal.remediation_type.value}): {proposal.proposed_frame_path}",
            )

    duration = time.perf_counter() - start_time
    duration_ms = int(duration * 1000)
    logger.info(
        f"[ADK] Stage 11 VISUAL_REMEDIATION completed proposals={len(proposals)} "
        f"(production_id={context.production_id}, duration_ms={duration_ms})"
    )
    return {
        "status": "COMPLETED",
        "count": len(proposals),
        "proposals": proposals,
    }

