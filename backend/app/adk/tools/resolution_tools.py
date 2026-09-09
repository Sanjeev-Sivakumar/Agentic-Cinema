import time
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.resolution import ResolutionResult, ResolutionStatus
from app.agents.resolution_agent import resolution_agent
from app.adk.context import WorkflowContext


async def resolve_entities_tool(
    context: WorkflowContext,
    entity_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    ADK tool for operational clearance resolution (Phase 7).
    Recommends actionable clearance workflows (License, Blur, Replace, Escalate, Human Review).
    Enforces terminal HUMAN_REVIEW boundaries where uncertainty remains.
    """
    start_time = time.perf_counter()
    try:
        results: List[ResolutionResult] = await resolution_agent.resolve_production(
            production_id=context.production_id,
            job_id=context.job_id,
            force_refresh=context.force_refresh,
        )

        res_ids = [r.id for r in results]
        context.state.resolution_result_ids = res_ids

        action_required_count = sum(1 for r in results if r.resolution_status == ResolutionStatus.ACTION_REQUIRED)
        human_review_count = sum(1 for r in results if r.resolution_status == ResolutionStatus.HUMAN_REVIEW)
        resolved_count = sum(1 for r in results if r.resolution_status == ResolutionStatus.RESOLVED)
        replacement_count = sum(1 for r in results if r.resolution_status == ResolutionStatus.REPLACEMENT_RECOMMENDED)
        escalated_count = sum(1 for r in results if r.resolution_status == ResolutionStatus.ESCALATED)

        duration = time.perf_counter() - start_time
        return {
            "status": "COMPLETED",
            "total_resolved": len(results),
            "action_required_count": action_required_count,
            "human_review_count": human_review_count,
            "resolved_count": resolved_count,
            "replacement_count": replacement_count,
            "escalated_count": escalated_count,
            "resolution_result_ids": res_ids,
            "duration": round(duration, 3),
        }

    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"[ADK ResolutionTool] Resolution failed: {e}", exc_info=True)
        context.state.record_error(f"Resolution failed: {str(e)}")
        return {
            "status": "FAILED",
            "error": str(e),
            "resolution_result_ids": [],
            "duration": round(duration, 3),
        }
