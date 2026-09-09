import pytest
from app.models.entity import Entity, EntityClassification, EntityType
from app.models.financial_exposure import (
    ComparableCase,
    FinancialExposure,
    FinancialExposureStatus,
    LicensingBenchmark,
    RemediationCostEstimate,
    StatutoryDamages,
)
from app.models.production import Production
from app.models.research import ResearchResult, ResearchStatus
from app.models.risk import RiskAssessment, RiskLevel
from app.repositories import (
    get_entity_repo,
    get_financial_exposure_repo,
    get_production_repo,
    get_research_repo,
    get_risk_repo,
)
from app.services.financial_exposure_engine import financial_exposure_engine
from app.adk.context import WorkflowContext
from app.adk.state import ChainOfTitleState
from app.adk.tools.exposure_tools import calculate_financial_exposure_tool


@pytest.mark.asyncio
async def test_financial_exposure_statutory_framework():
    """Verify statutory damages and market benchmark modeling."""
    entity = Entity(
        id="ent_cadbury_01",
        production_id="prod_test_exp",
        name="Cadbury",
        entity_type=EntityType.BRAND,
        classification=EntityClassification.BOTH,
        risk_level="MEDIUM",
        risk_score=50.0,
    )

    risk = RiskAssessment(
        id="risk_cadbury_01",
        production_id="prod_test_exp",
        entity_id="ent_cadbury_01",
        risk_level=RiskLevel.MEDIUM,
        risk_score=50.0,
    )

    research = ResearchResult(
        id="res_cadbury_01",
        production_id="prod_test_exp",
        entity_id="ent_cadbury_01",
        entity_name="Cadbury",
        query='"Cadbury" corporate rights holder trademark status',
        provider="parallel",
        status=ResearchStatus.SUCCESS,
        candidate_rights_holder="Mondelez International / Cadbury UK Ltd",
        research_confidence=0.95,
    )

    exposure = await financial_exposure_engine.calculate_exposure(
        entity=entity,
        risk=risk,
        research=research,
    )

    assert exposure.entity_name == "Cadbury"
    assert exposure.status == FinancialExposureStatus.ESTIMATED
    assert exposure.estimated_low >= 1000.0
    assert exposure.estimated_high >= exposure.estimated_low
    assert exposure.statutory_framework is not None
    assert "15 U.S.C." in exposure.statutory_framework.statutory_code or "17 U.S.C." in exposure.statutory_framework.statutory_code
    assert exposure.licensing_benchmark is not None
    assert exposure.licensing_benchmark.low_fee > 0
    assert exposure.remediation_estimate is not None


@pytest.mark.asyncio
async def test_financial_exposure_not_estimable_for_generic():
    """Verify NOT_ESTIMABLE status for zero/low liability generic items."""
    entity = Entity(
        id="ent_generic_01",
        production_id="prod_test_exp",
        name="Coffee Mug",
        entity_type=EntityType.OTHER,
        classification=EntityClassification.VISUAL_ONLY,
        risk_level="LOW",
        risk_score=2.0,
    )

    risk = RiskAssessment(
        id="risk_generic_01",
        production_id="prod_test_exp",
        entity_id="ent_generic_01",
        risk_level=RiskLevel.LOW,
        risk_score=2.0,
    )

    exposure = await financial_exposure_engine.calculate_exposure(
        entity=entity,
        risk=risk,
        research=None,
    )

    assert exposure.status == FinancialExposureStatus.NOT_ESTIMABLE
    assert exposure.estimated_high == 0.0


@pytest.mark.asyncio
async def test_financial_exposure_repository_crud():
    """Verify repository storage and retrieval."""
    repo = get_financial_exposure_repo()
    exp = FinancialExposure(
        exposure_id="exp_test_01",
        entity_id="ent_test_01",
        production_id="prod_crud_exp",
        entity_name="Sony",
        status=FinancialExposureStatus.ESTIMATED,
        estimated_low=5000.0,
        estimated_high=50000.0,
        confidence=0.90,
    )

    await repo.save(exp)
    retrieved = await repo.get("exp_test_01")
    assert retrieved is not None
    assert retrieved.entity_name == "Sony"
    assert retrieved.estimated_high == 50000.0

    prod_list = await repo.list_for_production("prod_crud_exp")
    assert len(prod_list) >= 1
    assert any(x.id == "exp_test_01" for x in prod_list)


@pytest.mark.asyncio
async def test_adk_exposure_tool():
    """Verify ADK calculate_financial_exposure_tool execution."""
    prod_repo = get_production_repo()
    ent_repo = get_entity_repo()
    risk_repo = get_risk_repo()
    res_repo = get_research_repo()

    prod = Production(id="prod_adk_exp_test", title="ADK Exposure Film")
    await prod_repo.save(prod)

    ent = Entity(
        id="ent_adk_01",
        production_id="prod_adk_exp_test",
        name="Nike",
        entity_type=EntityType.BRAND,
        classification=EntityClassification.BOTH,
        risk_level="HIGH",
        risk_score=85.0,
    )
    await ent_repo.save(ent)

    rk = RiskAssessment(
        id="risk_adk_01",
        production_id="prod_adk_exp_test",
        entity_id="ent_adk_01",
        risk_level=RiskLevel.HIGH,
        risk_score=85.0,
    )
    await risk_repo.save(rk)

    state = ChainOfTitleState(
        production_id="prod_adk_exp_test",
        job_id="job_adk_exp_test",
    )
    state.entity_ids = ["ent_adk_01"]
    context = WorkflowContext(state=state)

    res = await calculate_financial_exposure_tool(context, entity_ids=["ent_adk_01"])
    assert res["status"] == "COMPLETED"
    assert res["calculated_count"] == 1
    assert "exposures" in res
    assert len(res["exposures"]) == 1
    assert res["exposures"][0]["entity_name"] == "Nike"
