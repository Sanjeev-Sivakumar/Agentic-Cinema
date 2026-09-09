import time
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.verification import VerificationResult, VerificationDecision
from app.agents.verification_agent import verification_agent
from app.adk.context import WorkflowContext


async def verify_entities_tool(
    context: WorkflowContext,
    entity_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    ADK tool for adversarial evidence verification (Phase 6).
    Challenges whether findings are grounded in real visual evidence, registry corroboration,
    and screenplay alignment. Detects contradictions and updates state.
    """
    start_time = time.perf_counter()
    try:
        results: List[VerificationResult] = await verification_agent.verify_production(
            production_id=context.production_id,
            job_id=context.job_id,
            entity_ids=entity_ids,
            force_refresh=context.force_refresh,
        )

        verif_ids = [getattr(r, 'id', getattr(r, 'verification_id', '')) for r in results]
        context.state.verification_result_ids = verif_ids

        confirmed_count = sum(1 for r in results if r.decision == VerificationDecision.CONFIRMED)
        review_count = sum(1 for r in results if r.decision == VerificationDecision.REVIEW)
        rejected_count = sum(1 for r in results if r.decision == VerificationDecision.REJECTED)
        contradiction_count = sum(1 for r in results if getattr(r, 'contradiction_detected', False) or bool(getattr(r, 'contradictions', [])))

        duration = time.perf_counter() - start_time
        return {
            "status": "COMPLETED",
            "total_verified": len(results),
            "confirmed_count": confirmed_count,
            "review_count": review_count,
            "rejected_count": rejected_count,
            "contradiction_count": contradiction_count,
            "verification_result_ids": verif_ids,
            "duration": round(duration, 3),
        }

    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"[ADK VerificationTool] Verification failed: {e}", exc_info=True)
        context.state.record_error(f"Verification failed: {str(e)}")
        return {
            "status": "FAILED",
            "error": str(e),
            "verification_result_ids": [],
            "duration": round(duration, 3),
        }
