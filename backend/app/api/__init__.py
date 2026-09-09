from fastapi import APIRouter
from app.api.productions import router as productions_router
from app.api.analysis import router as analysis_router
from app.api.entities import router as entities_router
from app.api.evidence import router as evidence_router
from app.api.requests import router as requests_router
from app.api.reports import router as reports_router
from app.api.events import router as events_router
from app.api.orchestration import router as orchestration_router
from app.api.financial_exposure import router as exposure_router
from app.api.outreach import router as outreach_router
from app.api.remediations import router as remediations_router

api_router = APIRouter()
api_router.include_router(productions_router)
api_router.include_router(analysis_router)
api_router.include_router(entities_router)
api_router.include_router(evidence_router)
api_router.include_router(requests_router)
api_router.include_router(reports_router)
api_router.include_router(events_router)
api_router.include_router(orchestration_router)
api_router.include_router(exposure_router)
api_router.include_router(outreach_router)
api_router.include_router(remediations_router)

__all__ = ["api_router"]
