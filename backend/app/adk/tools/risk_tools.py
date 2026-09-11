import time
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.entity import RiskLevel
from app.models.risk import RiskAssessment
from app.agents.risk_agent import risk_agent
from app.adk.context import WorkflowContext


async def assess_risk_tool(
    context: WorkflowContext,
    entity_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    ADK tool for multi-factor risk assessment.
    Executes the deterministic RiskEngine, calculates exposure scores,
    enriches entities, persists risk assessments, and updates workflow state.
    """
    start_time = time.perf_counter()
    logger.info(
        f"[ADK] Stage 6 RISK_ASSESSMENT started (production_id={context.production_id}, "
        f"target_entity_ids={len(entity_ids) if entity_ids else 'all'})"
    )
    try:
        assess_fn = getattr(risk_agent, "assess_production", getattr(risk_agent, "assess_production_risk", None))
        assessments: List[RiskAssessment] = await assess_fn(
            production_id=context.production_id,
            entity_ids=entity_ids,
            job_id=context.job_id,
            force_refresh=context.force_refresh,
        )

        risk_ids = [a.id for a in assessments]
        context.state.risk_result_ids = risk_ids

        high_count = sum(1 for a in assessments if a.risk_level == RiskLevel.HIGH)
        medium_count = sum(1 for a in assessments if a.risk_level == RiskLevel.MEDIUM)
        low_count = sum(1 for a in assessments if a.risk_level == RiskLevel.LOW)
        unknown_count = sum(1 for a in assessments if a.risk_level == RiskLevel.UNKNOWN)

        duration = time.perf_counter() - start_time
        duration_ms = int(duration * 1000)
        logger.info(
            f"[ADK] Stage 6 RISK_ASSESSMENT completed assessed={len(assessments)} "
            f"(high={high_count}, medium={medium_count}, low={low_count}, unknown={unknown_count}, duration_ms={duration_ms})"
        )
        return {
            "status": "COMPLETED",
            "total_assessed": len(assessments),
            "high_risk_count": high_count,
            "medium_risk_count": medium_count,
            "low_risk_count": low_count,
            "unknown_risk_count": unknown_count,
            "risk_result_ids": risk_ids,
            "duration": round(duration, 3),
        }

    except Exception as e:
        duration = time.perf_counter() - start_time
        duration_ms = int(duration * 1000)
        logger.error(
            f"[ADK] Stage 6 RISK_ASSESSMENT failed: {e} "
            f"(production_id={context.production_id}, duration_ms={duration_ms})",
            exc_info=True,
        )
        context.state.record_error(f"Risk assessment failed: {str(e)}")
        return {
            "status": "FAILED",
            "error": str(e),
            "risk_result_ids": [],
            "duration": round(duration, 3),
        }
