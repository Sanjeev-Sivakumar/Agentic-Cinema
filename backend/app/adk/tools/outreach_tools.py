"""
ADK Clearance Outreach Tools (Phase 11).
Automates drafting rights clearance request packages and registers DRAFTS in Gmail.
STRICT RULE: DRAFT ONLY. Requires human approval before sending.
"""
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.events import EventType, PipelineStage
from app.adk.context import WorkflowContext
from app.adk.callbacks import WorkflowCallbacks
from app.services.clearance_outreach_service import clearance_outreach_service
from app.repositories import get_outreach_repo


async def draft_clearance_outreach_tool(
    context: WorkflowContext,
    entity_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generates formal clearance permission request drafts for entities requiring review.
    """
    import time
    start_time = time.perf_counter()
    logger.info(
        f"[ADK] Stage 10 CLEARANCE_OUTREACH started (production_id='{context.production_id}', "
        f"target_entity_ids={len(entity_ids) if entity_ids else 'all'})"
    )
    entities = await context.entity_repo.list_by_production(context.production_id)
    if entity_ids:
        entities = [e for e in entities if e.id in entity_ids]

    outreach_repo = get_outreach_repo()
    drafts: List[Dict[str, Any]] = []

    for entity in entities:
        # Load related resolution and research
        resolution = await context.resolution_repo.get_by_entity(entity.id)
        research = await context.research_repo.get_by_entity(entity.id)

        # Generate outreach draft
        draft = await clearance_outreach_service.generate_outreach_draft(
            entity=entity,
            research=research,
            resolution=resolution,
            production_title=f"Production {context.production_id}",
            create_gmail_draft=True,
        )

        await outreach_repo.save(draft)
        drafts.append(draft.model_dump(mode="json"))

        await WorkflowCallbacks.emit_event(
            context=context,
            event_type=EventType.OUTREACH_DRAFTED,
            stage=PipelineStage.CLEARANCE_OUTREACH,
            payload={
                "outreach_id": draft.outreach_id,
                "entity_id": entity.id,
                "entity_name": entity.name,
                "rights_holder": draft.rights_holder,
                "recipient_email": draft.recipient_email,
                "subject": draft.subject,
                "status": draft.status.value,
                "gmail_draft_id": draft.gmail_draft_id,
            },
            message=f"Drafted clearance permission letter for '{entity.name}' -> {draft.rights_holder} (Gmail Draft: {draft.gmail_draft_id or 'Stored'})",
        )

    duration = time.perf_counter() - start_time
    duration_ms = int(duration * 1000)
    logger.info(
        f"[ADK] Stage 10 CLEARANCE_OUTREACH completed drafted={len(drafts)} "
        f"(production_id={context.production_id}, duration_ms={duration_ms})"
    )
    return {
        "status": "COMPLETED",
        "count": len(drafts),
        "drafts": drafts,
    }

