import time
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.research import ResearchResult, ResearchStatus
from app.agents.research_agent import research_agent
from app.adk.context import WorkflowContext


async def research_entities_tool(
    context: WorkflowContext,
    entity_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    ADK tool for trademark and rights holder research.
    Coordinates evidence-backed intelligence queries across local registries (and Parallel if configured),
    enriches entity records, persists research findings, and isolates failures.
    """
    start_time = time.perf_counter()
    try:
        all_entities = await context.entity_repo.list_by_production(context.production_id)
        if entity_ids:
            id_set = set(entity_ids)
            target_entities = [e for e in all_entities if e.id in id_set]
        else:
            target_entities = all_entities

        if not target_entities:
            duration = time.perf_counter() - start_time
            logger.info(
                f"[ADK] Stage 5 PARALLEL_RESEARCH skipped (production_id={context.production_id}, no entities)"
            )
            return {
                "status": "SKIPPED",
                "message": "No entities available for research",
                "result_ids": [],
                "duration": round(duration, 3),
            }

        logger.info(
            f"[ADK] Stage 5 PARALLEL_RESEARCH started (production_id={context.production_id}, "
            f"entity_count={len(target_entities)}, mode={context.execution_mode})"
        )

        # Select active research provider dynamically based on execution mode without polluting global settings
        import os
        res_provider = None
        has_parallel_key = bool(getattr(context.config, "PARALLEL_API_KEY", "") or os.getenv("PARALLEL_API_KEY", ""))
        if (context.execution_mode == "live" and has_parallel_key) or getattr(context.config, "RESEARCH_PROVIDER", "").lower() == "parallel":
            from app.services.research_provider import get_research_provider
            res_provider = get_research_provider("parallel")
        elif context.execution_mode == "offline":
            from app.services.research_provider import get_research_provider
            res_provider = get_research_provider("local")

        results: List[ResearchResult] = await research_agent.research_entities(
            entities=target_entities,
            production_id=context.production_id,
            job_id=context.job_id,
            force_refresh=context.force_refresh,
            provider=res_provider,
        )

        res_ids = [r.id for r in results]
        context.state.research_result_ids = res_ids

        # Propagate all research evidence IDs into shared ADK workflow state
        for r in results:
            for ev in r.evidence:
                if ev.id not in context.state.evidence_ids:
                    context.state.evidence_ids.append(ev.id)

        success_count = sum(1 for r in results if r.status == ResearchStatus.SUCCESS)
        rights_holders_found = sum(1 for r in results if r.candidate_rights_holder)

        duration = time.perf_counter() - start_time
        duration_ms = int(duration * 1000)
        logger.info(
            f"[ADK] Stage 5 PARALLEL_RESEARCH completed results={len(results)} rights_holders_found={rights_holders_found} "
            f"(production_id={context.production_id}, duration_ms={duration_ms})"
        )
        return {
            "status": "COMPLETED",
            "total_researched": len(results),
            "success_count": success_count,
            "rights_holders_found": rights_holders_found,
            "result_ids": res_ids,
            "duration": round(duration, 3),
        }

    except Exception as e:
        duration = time.perf_counter() - start_time
        duration_ms = int(duration * 1000)
        logger.error(
            f"[ADK] Stage 5 PARALLEL_RESEARCH failed: {e} "
            f"(production_id={context.production_id}, duration_ms={duration_ms})",
            exc_info=True,
        )
        context.state.record_error(f"Research failed: {str(e)}")
        return {
            "status": "FAILED",
            "error": str(e),
            "result_ids": [],
            "duration": round(duration, 3),
        }
