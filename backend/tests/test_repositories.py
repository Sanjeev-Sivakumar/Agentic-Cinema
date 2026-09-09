import pytest
from app.models.production import Production, ProductionStatus
from app.models.analysis import AnalysisJob, JobStatus
from app.models.entity import Entity, EntitySource, EntityType, RiskLevel
from app.models.evidence import Evidence, EvidenceType
from app.models.risk import RiskAssessment, RiskFactor, RiskCategory
from app.repositories.local.in_memory import (
    InMemoryProductionRepository,
    InMemoryAnalysisJobRepository,
    InMemoryEntityRepository,
    InMemoryEvidenceRepository,
    InMemoryRiskRepository,
)

@pytest.mark.asyncio
async def test_production_repository_crud():
    repo = InMemoryProductionRepository()
    prod = Production(title="The Cyber Heist", director="Alex Rivera")
    created = await repo.create(prod)

    assert created.id.startswith("prod_")
    assert created.title == "The Cyber Heist"

    fetched = await repo.get(created.id)
    assert fetched is not None
    assert fetched.director == "Alex Rivera"

    fetched.status = ProductionStatus.READY_FOR_ANALYSIS
    updated = await repo.update(fetched)
    assert updated.status == ProductionStatus.READY_FOR_ANALYSIS

    all_prods = await repo.list_all()
    assert len(all_prods) == 1

    deleted = await repo.delete(created.id)
    assert deleted is True
    assert await repo.get(created.id) is None

@pytest.mark.asyncio
async def test_entity_and_job_repositories():
    job_repo = InMemoryAnalysisJobRepository()
    entity_repo = InMemoryEntityRepository()

    job = AnalysisJob.create_new(production_id="prod_100")
    await job_repo.create(job)
    assert len(job.stages) >= 12

    e1 = Entity(
        production_id="prod_100",
        job_id=job.job_id,
        name="Retro Neon Sign",
        entity_type=EntityType.SIGNAGE,
        sources=[EntitySource.VISUAL],
    )
    await entity_repo.create(e1)

    entities = await entity_repo.list_by_production("prod_100")
    assert len(entities) == 1
    assert entities[0].classification.value == "VISUAL_ONLY"
