"""
ADK Financial Exposure Tools (Phase 10).
Calculates statutory liabilities, licensing benchmarks, and remediation costs
for entities in the workflow.
"""
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.events import EventType, PipelineStage
from app.adk.context import WorkflowContext
from app.adk.callbacks import WorkflowCallbacks
from app.services.financial_exposure_engine import financial_exposure_engine
from app.repositories import get_financial_exposure_repo


async def calculate_financial_exposure_tool(
    context: WorkflowContext,
    entity_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Evaluates financial clearance exposures for all identified entities.
    """
    logger.info(f"[ADK ExposureTool] Calculating financial exposure for production '{context.production_id}'")
    entities = await context.entity_repo.list_by_production(context.production_id)
    if entity_ids:
        entities = [e for e in entities if e.id in entity_ids]

    exposure_repo = get_financial_exposure_repo()
    exposures: List[Dict[str, Any]] = []

    for entity in entities:
        # Load related risk & research data
        risk = await context.risk_repo.get_by_entity(entity.id)
        research = await context.research_repo.get_by_entity(entity.id)

        exposure = await financial_exposure_engine.calculate_exposure(
            entity=entity,
            risk=risk,
            research=research,
            evidence_ids=list(context.state.evidence_ids),
        )

        await exposure_repo.save(exposure)
        exposures.append(exposure.model_dump(mode="json"))

        await WorkflowCallbacks.emit_event(
            context=context,
            event_type=EventType.FINANCIAL_EXPOSURE_CALCULATED,
            stage=PipelineStage.FINANCIAL_EXPOSURE,
            payload={
                "entity_id": entity.id,
                "entity_name": entity.name,
                "status": exposure.status.value,
                "estimated_low": exposure.estimated_low,
                "estimated_high": exposure.estimated_high,
                "currency": exposure.currency,
            },
            message=f"Financial exposure calculated for '{entity.name}': ${exposure.estimated_low:,.2f} – ${exposure.estimated_high:,.2f} USD ({exposure.status.value})",
        )

    logger.info(f"[ADK ExposureTool] Calculated financial exposures for {len(exposures)} entities.")
    return {
        "status": "COMPLETED",
        "calculated_count": len(exposures),
        "count": len(exposures),
        "exposures": exposures,
    }

