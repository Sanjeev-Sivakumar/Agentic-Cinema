import pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "HEALTHY"
        assert data["service"] == "Chain of Title"
        assert "storage_backend" in data
        assert "database_backend" in data

@pytest.mark.asyncio
@patch("app.agents.root_agent.root_agent.execute_pipeline", new_callable=AsyncMock)
async def test_production_lifecycle_api(mock_execute):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create production
        payload = {
            "title": "Neon Horizon",
            "description": "Cyberpunk narrative short",
            "director": "K. Scott",
            "studio": "Sol Cinema",
            "budget_tier": "Studio Indie",
        }
        res = await client.post("/productions", json=payload)
        assert res.status_code == 201
        prod = res.json()
        prod_id = prod["id"]
        assert prod["title"] == "Neon Horizon"

        # Get production
        res = await client.get(f"/productions/{prod_id}")
        assert res.status_code == 200
        assert res.json()["id"] == prod_id

        # Upload script
        res = await client.post(
            f"/productions/{prod_id}/script",
            data={"script_text": "SCENE 1: Arjun enters coffee shop."},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "SUCCESS"

        # Register footage
        res = await client.post(
            f"/productions/{prod_id}/footage",
            data={"footage_path_override": "d:/media/neon_footage.mp4"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "SUCCESS"

        # Check status
        res = await client.get(f"/productions/{prod_id}/status")
        assert res.status_code == 200
        status_data = res.json()
        assert status_data["has_script"] is True
        assert status_data["has_footage"] is True

        # Trigger analysis
        res = await client.post(f"/productions/{prod_id}/analyze")
        assert res.status_code == 202
        job_data = res.json()
        assert job_data["production_id"] == prod_id
        assert "job_id" in job_data
