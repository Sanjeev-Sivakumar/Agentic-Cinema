from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.agents.research_agent import ResearchAgent, research_agent
from app.core.config import settings
from app.main import app
from app.models.entity import Entity, EntityClassification, EntitySource, EntityType
from app.models.events import EventType
from app.models.evidence import Evidence, EvidenceType
from app.models.production import Production
from app.models.research import ResearchResult, ResearchStatus
from app.repositories import (
    get_entity_repo,
    get_production_repo,
    get_research_repo,
)
from app.services.events import event_bus
from app.services.research_provider import (
    LocalResearchProvider,
    ParallelResearchProvider,
    ResearchQueryBuilder,
    get_research_provider,
    query_builder,
)

# =========================================================================
# Provider Tests (1 - 5)
# =========================================================================
@pytest.mark.asyncio
async def test_local_provider_success():
    provider = LocalResearchProvider()
    result = await provider.research_entity("Coca-Cola", "brand")
    assert result.status == ResearchStatus.SUCCESS
    assert result.candidate_rights_holder == "The Coca-Cola Company"
    assert result.identity_confidence >= 0.95
    assert len(result.evidence) >= 1
    assert result.provider == "local"

@pytest.mark.asyncio
async def test_local_provider_unknown_entity():
    provider = LocalResearchProvider()
    result = await provider.research_entity("TotallyUnknownBrandXYZ123", "brand")
    assert result.status == ResearchStatus.NOT_FOUND
    assert result.candidate_rights_holder is None
    assert result.identity_confidence == 0.0
    assert len(result.evidence) == 0

@pytest.mark.asyncio
async def test_local_provider_malformed_input():
    provider = LocalResearchProvider()
    res1 = await provider.research_entity("", "")
    assert res1.status == ResearchStatus.NOT_FOUND

    res2 = await provider.research_entity("   ", "other")
    assert res2.status == ResearchStatus.NOT_FOUND

def test_provider_factory_defaults_to_local():
    with patch.object(settings, "RESEARCH_PROVIDER", "local"):
        prov = get_research_provider()
        assert isinstance(prov, LocalResearchProvider)
        assert prov.provider_name == "local"

    # Default without explicit override
    prov_default = get_research_provider()
    assert isinstance(prov_default, LocalResearchProvider)

@pytest.mark.asyncio
async def test_parallel_provider_does_not_execute_in_tests():
    # Verify that ParallelResearchProvider.research_entity would raise or fail if invoked
    # and prove tests don't invoke Parallel against the live network
    with patch.object(
        ParallelResearchProvider,
        "research_entity",
        side_effect=AssertionError("CRITICAL: Parallel API network provider must NEVER be called in tests!"),
    ):
        agent = ResearchAgent()
        test_ent = Entity(production_id="p_safe", name="Nike", entity_type=EntityType.BRAND)
        result = await agent.research_entity(test_ent)
        assert result.status == ResearchStatus.SUCCESS
        assert result.candidate_rights_holder == "NIKE, Inc."

# =========================================================================
# Query Builder Tests (6 - 9)
# =========================================================================
def test_query_builder_brand():
    qb = ResearchQueryBuilder()
    q = qb.build_query("Coca-Cola", "brand")
    assert '"Coca-Cola"' in q
    assert "brand" in q
    assert "rights holder" in q

def test_query_builder_music():
    qb = ResearchQueryBuilder()
    q = qb.build_query("Midnight City", "music", context="Track by M83 playing on radio.")
    assert '"Midnight City"' in q
    assert "artist" in q or "music" in q
    assert '"M83"' in q

def test_query_builder_artwork():
    qb = ResearchQueryBuilder()
    q = qb.build_query("Starry Night", "artwork")
    assert '"Starry Night"' in q
    assert "artwork" in q or "copyright" in q

def test_query_builder_film():
    qb = ResearchQueryBuilder()
    q = qb.build_query("Inception", "film")
    assert '"Inception"' in q
    assert "film" in q or "production" in q

# =========================================================================
# Evidence Tests (10 - 12)
# =========================================================================
def test_evidence_validation():
    evi = Evidence(
        production_id="p1",
        evidence_type=EvidenceType.RESEARCH_EVIDENCE,
        entity_name="Nike",
        claim="NIKE, Inc. holds registered trademark rights.",
        source_type="local_fixture",
        confidence=0.96,
        provider="local",
    )
    assert evi.id.startswith("evi_")
    assert evi.evidence_id == evi.id
    assert evi.claim.startswith("NIKE, Inc.")
    assert evi.confidence == 0.96

def test_local_fixture_has_no_fake_url():
    provider = LocalResearchProvider()
    result = provider.research_entity("Apple", "brand")
    import asyncio
    res = asyncio.run(result)
    assert len(res.evidence) >= 1
    for evi in res.evidence:
        assert evi.source_url is None
        assert evi.source_type == "local_fixture"

def test_multiple_evidence_items():
    res = ResearchResult(
        production_id="p1",
        entity_name="TestMulti",
        status=ResearchStatus.SUCCESS,
        candidate_rights_holder="Multi Corp",
        evidence=[
            Evidence(entity_name="TestMulti", claim="Claim 1", source_type="official", confidence=0.9),
            Evidence(entity_name="TestMulti", claim="Claim 2", source_type="registry", confidence=0.85),
        ],
    )
    assert len(res.evidence) == 2
    assert res.evidence[0].claim == "Claim 1"
    assert res.evidence[1].claim == "Claim 2"

# =========================================================================
# Agent Tests (13 - 18)
# =========================================================================
@pytest.mark.asyncio
async def test_single_entity_research():
    agent = ResearchAgent()
    ent = Entity(production_id="p_single", name="Pepsi", entity_type=EntityType.BRAND)
    result = await agent.research_entity(ent)

    assert result.status == ResearchStatus.SUCCESS
    assert result.candidate_rights_holder == "PepsiCo, Inc."
    assert ent.research_status == "SUCCESS"
    assert ent.candidate_rights_holder == "PepsiCo, Inc."
    assert ent.rights_holder == "PepsiCo, Inc."
    assert ent.research_confidence >= 0.90

@pytest.mark.asyncio
async def test_batch_entity_research():
    agent = ResearchAgent()
    entities = [
        Entity(production_id="p_batch", name="Nike", entity_type=EntityType.BRAND),
        Entity(production_id="p_batch", name="Netflix", entity_type=EntityType.COMPANY),
    ]
    results = await agent.research_entities(entities, production_id="p_batch")

    assert len(results) == 2
    names = {r.entity_name for r in results}
    assert "Nike" in names
    assert "Netflix" in names
    assert all(r.status == ResearchStatus.SUCCESS for r in results)

@pytest.mark.asyncio
async def test_duplicate_entity_handling():
    agent = ResearchAgent()
    # Two separate Entity instances for same brand (e.g. detected in Scene 1 and Scene 3)
    ent1 = Entity(production_id="p_dup", name="Coca-Cola", scene=1, entity_type=EntityType.BRAND)
    ent2 = Entity(production_id="p_dup", name="Coca-Cola", scene=3, entity_type=EntityType.BRAND)

    results = await agent.research_entities([ent1, ent2], production_id="p_dup")
    assert len(results) == 2
    # Both entities enriched with same rights holder
    assert ent1.candidate_rights_holder == "The Coca-Cola Company"
    assert ent2.candidate_rights_holder == "The Coca-Cola Company"

@pytest.mark.asyncio
async def test_visual_only_prioritization():
    agent = ResearchAgent()
    # Create entities with different classifications
    script_ent = Entity(
        production_id="p_prio",
        name="Rolex",
        sources=[EntitySource.SCRIPT],
        confidence=0.90,
    )
    both_ent = Entity(
        production_id="p_prio",
        name="Nike",
        sources=[EntitySource.SCRIPT, EntitySource.VISUAL],
        confidence=0.90,
    )
    visual_only_ent = Entity(
        production_id="p_prio",
        name="Netflix",
        sources=[EntitySource.VISUAL],
        confidence=0.85,
    )

    # Input in random order: SCRIPT_ONLY, BOTH, VISUAL_ONLY
    input_list = [script_ent, both_ent, visual_only_ent]

    # Mock research_entity to record execution order
    execution_order = []
    original_research = agent.research_entity

    async def mock_exec(entity, **kwargs):
        execution_order.append(entity.classification)
        return await original_research(entity, **kwargs)

    agent.research_entity = mock_exec
    await agent.research_entities(input_list, production_id="p_prio")

    # Priority must execute VISUAL_ONLY (1st), BOTH (2nd), SCRIPT_ONLY (3rd)
    assert execution_order[0] == EntityClassification.VISUAL_ONLY
    assert execution_order[1] == EntityClassification.BOTH
    assert execution_order[2] == EntityClassification.SCRIPT_ONLY

@pytest.mark.asyncio
async def test_error_isolation():
    mock_prov = MagicMock()
    mock_prov.provider_name = "mock_flaky"

    async def flaky_research(entity_name, **kwargs):
        if entity_name == "FaultyBrand":
            raise RuntimeError("Database connection timeout")
        return ResearchResult(
            entity_name=entity_name,
            status=ResearchStatus.SUCCESS,
            candidate_rights_holder=f"Owner of {entity_name}",
            provider="mock_flaky",
        )

    mock_prov.research_entity = AsyncMock(side_effect=flaky_research)
    agent = ResearchAgent(provider=mock_prov)

    entities = [
        Entity(production_id="p_iso", name="FaultyBrand"),
        Entity(production_id="p_iso", name="GoodBrand"),
    ]

    results = await agent.research_entities(entities, production_id="p_iso")
    assert len(results) == 2
    # Faulty entity failed gracefully, Good entity succeeded
    assert results[0].status == ResearchStatus.API_ERROR
    assert results[1].status == ResearchStatus.SUCCESS

@pytest.mark.asyncio
async def test_idempotency_caching():
    agent = ResearchAgent()
    ent = Entity(production_id="p_idem", name="McDonald's", entity_type=EntityType.BRAND)

    # First call
    res1 = await agent.research_entity(ent, force_refresh=False)
    assert res1.status == ResearchStatus.SUCCESS

    # Second call without force_refresh uses repository cache
    res2 = await agent.research_entity(ent, force_refresh=False)
    assert res1.id == res2.id

# =========================================================================
# Event Tests (19 - 23)
# =========================================================================
@pytest.mark.asyncio
async def test_event_research_started():
    agent = ResearchAgent()
    job_id = "job_evt_start"
    ent = Entity(production_id="p_evt", name="Apple", entity_type=EntityType.BRAND)
    await agent.research_entities([ent], production_id="p_evt", job_id=job_id)

    history = event_bus.get_history(job_id)
    start_events = [e for e in history if e.event_type == EventType.RESEARCH_STARTED]
    assert len(start_events) == 1
    assert start_events[0].metadata.get("total_entities") == 1

@pytest.mark.asyncio
async def test_event_research_query_built():
    agent = ResearchAgent()
    job_id = "job_evt_query"
    ent = Entity(production_id="p_evt", name="Nike", entity_type=EntityType.BRAND)
    await agent.research_entity(ent, job_id=job_id)

    history = event_bus.get_history(job_id)
    query_events = [e for e in history if e.event_type == EventType.RESEARCH_QUERY_BUILT]
    assert len(query_events) == 1
    assert "Nike" in query_events[0].metadata.get("query", "")

@pytest.mark.asyncio
async def test_event_research_result_received():
    agent = ResearchAgent()
    job_id = "job_evt_result"
    ent = Entity(production_id="p_evt", name="Google", entity_type=EntityType.COMPANY)
    await agent.research_entity(ent, job_id=job_id)

    history = event_bus.get_history(job_id)
    res_events = [e for e in history if e.event_type == EventType.RESEARCH_RESULT_RECEIVED]
    assert len(res_events) == 1
    assert res_events[0].metadata.get("status") == "SUCCESS"

@pytest.mark.asyncio
async def test_event_research_completed():
    agent = ResearchAgent()
    job_id = "job_evt_comp"
    ent = Entity(production_id="p_evt", name="YouTube", entity_type=EntityType.COMPANY)
    await agent.research_entities([ent], production_id="p_evt", job_id=job_id)

    history = event_bus.get_history(job_id)
    comp_events = [e for e in history if e.event_type == EventType.RESEARCH_COMPLETED]
    assert len(comp_events) == 1
    assert comp_events[0].progress == 100.0

@pytest.mark.asyncio
async def test_event_research_failed():
    mock_prov = MagicMock()
    mock_prov.provider_name = "failing"
    mock_prov.research_entity = AsyncMock(side_effect=RuntimeError("Fatal provider explosion"))

    agent = ResearchAgent(provider=mock_prov)
    job_id = "job_evt_fail"
    ent = Entity(production_id="p_evt", name="CrashBrand")
    res = await agent.research_entity(ent, job_id=job_id)
    assert res.status == ResearchStatus.API_ERROR

# =========================================================================
# API Tests (24 - 26)
# =========================================================================
@pytest.mark.asyncio
async def test_api_research_endpoint():
    prod_repo = get_production_repo()
    entity_repo = get_entity_repo()

    prod = Production(title="API Research Film")
    saved_prod = await prod_repo.create(prod)

    ent = Entity(production_id=saved_prod.id, name="Coca-Cola", entity_type=EntityType.BRAND)
    saved_ent = await entity_repo.create(ent)

    client = TestClient(app)
    payload = {"entity_ids": [saved_ent.id]}
    response = client.post(f"/productions/{saved_prod.id}/research", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["production_id"] == saved_prod.id
    assert len(data["results"]) == 1
    assert data["results"][0]["entity_name"] == "Coca-Cola"
    assert data["results"][0]["candidate_rights_holder"] == "The Coca-Cola Company"
    assert data["results"][0]["status"] == "SUCCESS"

@pytest.mark.asyncio
async def test_api_research_invalid_entity():
    prod_repo = get_production_repo()
    prod = Production(title="API Invalid Entity Film")
    saved_prod = await prod_repo.create(prod)

    client = TestClient(app)
    payload = {"entity_ids": ["non_existent_ent_999"]}
    response = client.post(f"/productions/{saved_prod.id}/research", json=payload)

    assert response.status_code == 200
    data = response.json()
    # Invalid ID is skipped cleanly
    assert len(data["results"]) == 0

@pytest.mark.asyncio
async def test_api_research_empty_entity_list():
    prod_repo = get_production_repo()
    entity_repo = get_entity_repo()

    prod = Production(title="API Empty List Film")
    saved_prod = await prod_repo.create(prod)

    ent = Entity(production_id=saved_prod.id, name="Nike", entity_type=EntityType.BRAND)
    await entity_repo.create(ent)

    client = TestClient(app)
    # Empty entity_ids researches all entities in the production
    response = client.post(f"/productions/{saved_prod.id}/research", json={})
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["entity_name"] == "Nike"

# =========================================================================
# Zero Network Verification (Test 27)
# =========================================================================
@pytest.mark.asyncio
async def test_zero_network_verification():
    """
    Explicit proof that Phase 4 research executes with zero external API calls:
    - Parallel: 0 calls
    - Gemini: 0 calls
    - Groq: 0 calls
    - Google Cloud: 0 calls
    """
    with patch("httpx.AsyncClient.post", side_effect=AssertionError("EXTERNAL NETWORK CALL DETECTED!")) as mock_http:
        agent = ResearchAgent()
        ent = Entity(production_id="p_zero", name="Coca-Cola", entity_type=EntityType.BRAND)
        result = await agent.research_entity(ent)

        assert result.status == ResearchStatus.SUCCESS
        assert result.candidate_rights_holder == "The Coca-Cola Company"
        assert result.provider == "local"
        mock_http.assert_not_called()
