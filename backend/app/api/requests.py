from typing import List
from fastapi import APIRouter, HTTPException, status
from app.models.clearance import ClearanceRequest
from app.repositories import get_clearance_repo, get_production_repo

router = APIRouter(prefix="/productions", tags=["requests"])

@router.get("/{production_id}/requests", response_model=List[ClearanceRequest])
async def list_clearance_requests(production_id: str) -> List[ClearanceRequest]:
    """Retrieve all clearance action requests and workflows for a production."""
    prod_repo = get_production_repo()
    clearance_repo = get_clearance_repo()

    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    return await clearance_repo.list_by_production(production_id)
