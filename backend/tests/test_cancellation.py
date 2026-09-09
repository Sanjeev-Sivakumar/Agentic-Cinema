import pytest
from httpx import ASGITransport, AsyncClient
from app.agents.root_agent import root_agent
from app.main import app
from app.models.analysis import AnalysisJob, JobStatus
from app.models.production import Production
from app.repositories import get_job_repo, get_production_repo

@pytest.mark.asyncio
async def test_job_cancellation_api():
    transport = ASGITransport(app=app)
    prod_repo = get_production_repo()
    job_repo = get_job_repo()

    prod = Production(title="Cancellation Test Film")
    await prod_repo.create(prod)

    job = AnalysisJob.create_new(production_id=prod.id)
    await job_repo.create(job)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/productions/{prod.id}/analysis/{job.job_id}/cancel")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "CANCELLED"
        assert root_agent.is_cancelled(job.job_id) is True
