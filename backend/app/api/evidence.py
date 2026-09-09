from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from app.models.evidence import Evidence
from app.repositories import get_evidence_repo, get_production_repo

router = APIRouter(prefix="/productions", tags=["evidence"])

@router.get("/{production_id}/evidence", response_model=List[Evidence])
async def list_evidence(
    production_id: str,
    entity_id: Optional[str] = Query(None, description="Filter evidence by entity ID"),
) -> List[Evidence]:
    """Retrieve evidence frames, bounding boxes, and excerpts."""
    prod_repo = get_production_repo()
    evidence_repo = get_evidence_repo()

    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    if entity_id:
        return await evidence_repo.list_by_entity(entity_id)
    return await evidence_repo.list_by_production(production_id)
