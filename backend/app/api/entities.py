from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from app.models.entity import Entity, EntityClassification, EntityType, RiskLevel
from app.repositories import get_entity_repo, get_production_repo

router = APIRouter(prefix="/productions", tags=["entities"])

@router.get("/{production_id}/entities", response_model=List[Entity])
async def list_entities(
    production_id: str,
    job_id: Optional[str] = Query(None, description="Filter by analysis job ID"),
    classification: Optional[str] = Query(None, description="Filter by classification (BOTH, SCRIPT_ONLY, VISUAL_ONLY, AUDIO_ONLY)"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type (BRAND, ARTWORK, etc.)"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level (HIGH, MEDIUM, LOW)"),
) -> List[Entity]:
    """Retrieve all detected entities for a production with rich filters."""
    prod_repo = get_production_repo()
    entity_repo = get_entity_repo()

    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    if job_id:
        entities = await entity_repo.list_by_job(job_id)
    else:
        entities = await entity_repo.list_by_production(production_id)

    if classification:
        entities = [e for e in entities if e.classification.value == classification.upper()]

    if entity_type:
        entities = [e for e in entities if e.entity_type.value == entity_type.upper()]

    if risk_level:
        entities = [e for e in entities if e.risk_level.value == risk_level.upper()]

    return entities
