from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from app.core.config import settings
from app.adk.runner import run_production_workflow
from app.repositories import get_production_repo, get_orchestration_repo

router = APIRouter(prefix="/productions", tags=["orchestration"])


class OrchestrationRequest(BaseModel):
    job_id: Optional[str] = None
    force_refresh: bool = False
    mode: str = Field(
        default="live" if getattr(settings, "GEMINI_API_KEY", "") else "offline",
        description="Execution mode: 'offline' or 'live'",
    )
    video_path: Optional[str] = Field(
        default=None,
        description="Optional path to video file (e.g. 'test_video1.mp4' or 'test_video.mp4')",
    )
    research_provider: Optional[str] = Field(
        default="parallel" if getattr(settings, "PARALLEL_API_KEY", "") else "local",
        description="Research provider: 'parallel' or 'local'",
    )


@router.post(
    "/{production_id}/orchestrate",
    status_code=status.HTTP_200_OK,
    summary="Trigger autonomous clearance orchestration via Google ADK",
)
async def orchestrate_production(
    production_id: str,
    payload: OrchestrationRequest = OrchestrationRequest(),
):
    """
    Triggers the Google ADK Root Agent to coordinate specialized clearance agents
    across the entire dependency DAG. Returns structured OrchestrationResult.
    """
    mode = payload.mode.lower()
    if mode not in ("offline", "live"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid orchestration mode '{payload.mode}'. Must be 'offline' or 'live'.",
        )

    prod_repo = get_production_repo()
    prod = await prod_repo.get(production_id)
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    # If video_path specified in payload, update production footage path
    if payload.video_path:
        prod.footage_path = payload.video_path.strip()
        await prod_repo.update(prod)
        logger.info(f"[OrchestrationAPI] Updated production {production_id} footage_path to '{prod.footage_path}'")

    # In live mode, ensure configured live AI provider is active
    if mode == "live":
        if getattr(settings, "GEMINI_API_KEY", ""):
            settings.AI_PROVIDER = "gemini"


    try:
        result = await run_production_workflow(
            production_id=production_id,
            job_id=payload.job_id,
            force_refresh=payload.force_refresh,
            mode=mode,
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"[OrchestrationAPI] Execution error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Autonomous orchestration failed: {str(e)}",
        )



@router.get(
    "/{production_id}/orchestrate",
    status_code=status.HTTP_200_OK,
    summary="Get latest orchestration result for a production",
)
async def get_latest_orchestration(production_id: str):
    """Retrieve the most recent autonomous orchestration outcome for a production."""
    prod_repo = get_production_repo()
    prod = await prod_repo.get(production_id)
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    orch_repo = get_orchestration_repo()
    latest = await orch_repo.get_latest_for_production(production_id)
    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No orchestration results found for production '{production_id}'",
        )

    return latest.to_dict()


@router.get(
    "/{production_id}/orchestrate/{workflow_id}",
    status_code=status.HTTP_200_OK,
    summary="Get specific orchestration result by workflow ID",
)
async def get_orchestration_by_id(production_id: str, workflow_id: str):
    """Retrieve a specific orchestration result by workflow ID."""
    orch_repo = get_orchestration_repo()
    result = await orch_repo.get(workflow_id)
    if not result or result.production_id != production_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Orchestration workflow '{workflow_id}' not found for production '{production_id}'",
        )

    return result.to_dict()
