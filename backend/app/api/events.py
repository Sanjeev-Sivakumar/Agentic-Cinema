import asyncio
from typing import AsyncIterator
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from app.core.logging import logger
from app.models.events import ProcessingEvent
from app.repositories import get_job_repo, get_production_repo
from app.services.events import event_bus

router = APIRouter(prefix="/productions", tags=["events"])

@router.get("/{production_id}/analysis/{job_id}/events")
async def stream_analysis_events(
    production_id: str,
    job_id: str,
    request: Request,
):
    """
    Real-time Server-Sent Events (SSE) stream for an analysis job.
    Streams actual ProcessingEvent objects as they are emitted during video/screenplay processing.
    Replays existing history for reconnection continuity.
    """
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

    async def event_generator() -> AsyncIterator[str]:
        logger.info(f"[SSE] Client connected to event stream for job {job_id}")
        try:
            async for event in event_bus.subscribe(job_id):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"[SSE] Client disconnected for job {job_id}")
                    break
                yield event.to_sse_message()
        except (asyncio.CancelledError, GeneratorExit):
            logger.info(f"[SSE] Stream cancelled for job {job_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
