from typing import Optional
from app.core.logging import logger
from app.models.orchestration import OrchestrationResult
from app.adk.state import ChainOfTitleState
from app.adk.context import WorkflowContext
from app.adk.root_agent import RootOrchestrator
from app.repositories import get_production_repo


async def run_production_workflow(
    production_id: str,
    job_id: Optional[str] = None,
    screenplay_text: Optional[str] = None,
    video_path: Optional[str] = None,
    force_refresh: bool = False,
    mode: str = "offline",
    **context_kwargs,
) -> OrchestrationResult:
    """
    Main entry point for Google ADK Autonomous Clearance Orchestration.
    Validates production, creates workflow state & context, executes Root Agent DAG,
    persists result in OrchestrationRepository, and returns the OrchestrationResult.
    """
    prod_repo = context_kwargs.get("production_repo") or get_production_repo()
    production = await prod_repo.get(production_id)
    if not production:
        raise ValueError(f"Production '{production_id}' not found")

    # Initialize shared workflow state
    effective_job_id = job_id or f"job_{production_id[:8]}"
    state = ChainOfTitleState(
        production_id=production_id,
        job_id=effective_job_id,
    )

    # Initialize context
    context = WorkflowContext(
        state=state,
        force_refresh=force_refresh,
        execution_mode=mode,
        **context_kwargs,
    )

    logger.info(
        f"[ADK Runner] Launching autonomous workflow '{state.workflow_id}' for production '{production_id}' "
        f"(Mode: {mode}, Force Refresh: {force_refresh})"
    )

    # Instantiate Root Orchestrator and run dependency graph
    orchestrator = RootOrchestrator()
    result = await orchestrator.orchestrate(
        context=context,
        screenplay_text=screenplay_text,
        video_path=video_path,
    )

    # Persist final result
    await context.orchestration_repo.save(result)
    logger.info(f"[ADK Runner] Workflow '{result.workflow_id}' finished with status '{result.status.value}'")

    return result
