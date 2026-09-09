"""
Financial Exposure API Endpoints (Phase 10).
"""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from app.repositories import get_financial_exposure_repo

router = APIRouter(prefix="/exposure", tags=["financial_exposure"])


@router.get(
    "/{production_id}",
    response_model=List[Dict[str, Any]],
    summary="List financial clearance exposure calculations for a production",
)
async def list_financial_exposures(production_id: str):
    repo = get_financial_exposure_repo()
    exposures = await repo.list_for_production(production_id)
    return [exp.model_dump(mode="json") if hasattr(exp, "model_dump") else exp for exp in exposures]
