from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from app.models.analysis import AnalysisJob, JobStatus
from app.repositories import get_job_repo, get_production_repo

router = APIRouter(prefix="/productions", tags=["analysis"])

@router.get("/{production_id}/analysis", response_model=List[AnalysisJob])
async def list_analysis_jobs(production_id: str) -> List[AnalysisJob]:
    """List all analysis jobs for a production."""
    prod_repo = get_production_repo()
    job_repo = get_job_repo()

    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    return await job_repo.get_by_production(production_id)


@router.get("/{production_id}/analysis/{job_id}", response_model=AnalysisJob)
async def get_analysis_job(production_id: str, job_id: str) -> AnalysisJob:
    """Get a specific analysis job by ID."""
    prod_repo = get_production_repo()
    job_repo = get_job_repo()

    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    job = await job_repo.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis job '{job_id}' not found",
        )

    return job


@router.post("/{production_id}/analysis/{job_id}/cancel", response_model=AnalysisJob)
async def cancel_analysis_job(production_id: str, job_id: str) -> AnalysisJob:
    """Cancel an active analysis job."""
    prod_repo = get_production_repo()
    job_repo = get_job_repo()

    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    job = await job_repo.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis job '{job_id}' not found",
        )

    from app.agents.root_agent import root_agent
    root_agent.cancel_job(job_id)

    job.status = JobStatus.CANCELLED
    await job_repo.update(job)
    return job
