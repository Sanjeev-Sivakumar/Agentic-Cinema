import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.agents.risk_agent import RiskAssessmentAgent, risk_agent
from app.models.entity import Entity, EntityClassification, EntitySource, EntityType
from app.models.events import EventType
from app.models.evidence import Evidence, EvidenceType
from app.models.production import Production
from app.models.research import ResearchResult, ResearchStatus
from app.models.risk import RiskAssessment, RiskLevel, RiskSignal
from app.repositories import (
    get_entity_repo,
    get_production_repo,
    get_research_repo,
    get_risk_repo,
)
from app.repositories.local.in_memory import InMemoryRiskRepository
from app.services.events import event_bus
from app.services.risk_scoring import (
    calculate_risk,
    compute_risk_assessment,
    compute_evidence_confidence,
    generate_triage_explanation,
)


# =========================================================================
# Suite 1: Pure Deterministic Scoring Engine (Tests 1 - 18)
# =========================================================================

def test_scoring_engine_low_risk():
    """Entity with script-only, small presence, high research confidence -> LOW risk (score < 40)."""
    entity = Entity(
        id="ent_low_01",
        production_id="prod_test",
        name="Antique Wooden Desk",
        entity_type=EntityType.OTHER,
        sources=[EntitySource.SCRIPT],
        classification=EntityClassification.SCRIPT_ONLY,
        confidence=0.88,
        bounding_box=[0.1, 0.1, 0.15, 0.15],
        appearances=1,
    )
    research = ResearchResult(
        research_id="res_01",
        entity_id="ent_low_01",
        production_id="prod_test",
        entity_name="Antique Wooden Desk",
        status=ResearchStatus.SUCCESS,
        candidate_rights_holder="Public Domain Antique",
        identity_confidence=0.95,
        clearance_recommendation="No clearance required. Generic prop.",
        provider="local",
    )

    assessment = compute_risk_assessment(entity, research)
    assert assessment.risk_level == RiskLevel.LOW
    assert 0 <= assessment.risk_score < 40
    assert assessment.confidence >= 0.70
    assert len(assessment.signals) == 8
    assert "LOW" in assessment.explanation


def test_scoring_engine_medium_risk():
    """Entity with artwork, visual-only presence, known rights holder -> MEDIUM risk (40-69)."""
    entity = Entity(
        id="ent_med_01",
        production_id="prod_test",
        name="Abstract Cityscape #9",
        entity_type=EntityType.ARTWORK,
        sources=[EntitySource.VISUAL],
        classification=EntityClassification.VISUAL_ONLY,
        confidence=0.85,
        bounding_box=[0.1, 0.1, 0.25, 0.25],  # small bbox area = 0.0225 (+5)
        appearances=2,  # duration (+5)
    )
    # Signals: VISUAL_ONLY(+25) + ARTWORK(+10) + Prominence(+5) + Duration(+5) = 45.0 (MEDIUM)
    assessment = compute_risk_assessment(entity, None)
    assert assessment.risk_level == RiskLevel.MEDIUM
    assert 40 <= assessment.risk_score < 70
    assert assessment.confidence >= 0.50
    assert "MEDIUM" in assessment.explanation


def test_scoring_engine_high_risk():
    """Entity with VISUAL_ONLY, prominent brand mark, multiple appearances -> HIGH risk (70-100)."""
    entity = Entity(
        id="ent_high_01",
        production_id="prod_test",
        name="Starlight Roast Coffee",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        classification=EntityClassification.VISUAL_ONLY,
        confidence=0.96,
        bounding_box=[0.25, 0.25, 0.75, 0.75],
        appearances=4,
    )
    research = ResearchResult(
        research_id="res_03",
        entity_id="ent_high_01",
        production_id="prod_test",
        entity_name="Starlight Roast Coffee",
        status=ResearchStatus.NOT_FOUND,
        candidate_rights_holder=None,
        identity_confidence=0.0,
        provider="local",
    )

    assessment = compute_risk_assessment(entity, research)
    assert assessment.risk_level == RiskLevel.HIGH
    assert 70 <= assessment.risk_score <= 100
    assert "HIGH" in assessment.explanation
    # Visual only signal must have contributed +25
    vo_sig = next(s for s in assessment.signals if s.signal_name == "VISUAL_ONLY")
    assert vo_sig.score_delta >= 25.0


def test_scoring_engine_unknown_low_confidence():
    """Entity with detection confidence < 0.35 must result in UNKNOWN, score 0.0, and never LOW."""
    entity = Entity(
        id="ent_unk_01",
        production_id="prod_test",
        name="Faint Glare",
        entity_type=EntityType.OTHER,
        sources=[EntitySource.VISUAL],
        confidence=0.20,
    )

    assessment = compute_risk_assessment(entity, None)
    assert assessment.risk_level == RiskLevel.UNKNOWN
    assert assessment.risk_score == 0.0
    assert assessment.confidence < 0.35
    assert "UNKNOWN" in assessment.explanation
    assert assessment.risk_level != RiskLevel.LOW


def test_scoring_engine_unknown_placeholder_name():
    """Entity with placeholder name ('Unknown', 'N/A') must result in UNKNOWN."""
    for name in ["Unknown", "UNKNOWN", "n/a", "N/A", "TBD", ""]:
        entity = Entity(
            id=f"ent_unk_{name}",
            production_id="prod_test",
            name=name,
            entity_type=EntityType.OTHER,
            sources=[EntitySource.VISUAL],
            confidence=0.90,
        )
        assessment = compute_risk_assessment(entity, None)
        assert assessment.risk_level == RiskLevel.UNKNOWN
        assert assessment.risk_score == 0.0


def test_signal_visual_prominence():
    """Entity with large bounding box (area > 0.04) triggers VISUAL_PROMINENCE signal."""
    large_ent = Entity(
        id="ent_vp_large",
        production_id="prod_test",
        name="Large Signage",
        entity_type=EntityType.SIGNAGE,
        sources=[EntitySource.VISUAL],
        confidence=0.90,
        bounding_box=[0.2, 0.2, 0.8, 0.8],  # area = 0.36
    )
    assessment = compute_risk_assessment(large_ent, None)
    vp_sig = next(s for s in assessment.signals if s.signal_name == "VISUAL_PROMINENCE")
    assert vp_sig.triggered is True
    assert vp_sig.score_delta >= 18.0


def test_signal_commercial_context():
    """Prominent BRAND entity triggers COMMERCIAL_CONTEXT signal."""
    brand_ent = Entity(
        id="ent_comm",
        production_id="prod_test",
        name="Super Cola",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        confidence=0.92,
        bounding_box=[0.3, 0.3, 0.6, 0.6],
    )
    assessment = compute_risk_assessment(brand_ent, None)
    comm_sig = next(s for s in assessment.signals if s.signal_name == "COMMERCIAL_CONTEXT")
    assert comm_sig.triggered is True
    assert comm_sig.score_delta >= 15.0


def test_signal_music_rights():
    """MUSIC entity triggers MUSIC_RIGHTS signal (+25 points) due to sync/master complexity."""
    music_ent = Entity(
        id="ent_music",
        production_id="prod_test",
        name="Midnight City",
        entity_type=EntityType.MUSIC,
        sources=[EntitySource.AUDIO],
        confidence=0.95,
    )
    assessment = compute_risk_assessment(music_ent, None)
    music_sig = next(s for s in assessment.signals if s.signal_name == "MUSIC_RIGHTS")
    assert music_sig.triggered is True
    assert music_sig.score_delta == 25.0


def test_signal_visual_only():
    """Entity with VISUAL_ONLY classification triggers VISUAL_ONLY signal (+25 points)."""
    vo_ent = Entity(
        id="ent_vo",
        production_id="prod_test",
        name="Unscripted Poster",
        entity_type=EntityType.ARTWORK,
        sources=[EntitySource.VISUAL],
        classification=EntityClassification.VISUAL_ONLY,
        confidence=0.85,
    )
    assessment = compute_risk_assessment(vo_ent, None)
    vo_sig = next(s for s in assessment.signals if s.signal_name == "VISUAL_ONLY")
    assert vo_sig.triggered is True
    assert vo_sig.score_delta == 25.0


def test_signal_research_confidence_low_vs_high():
    """High research confidence decreases score; unverified/low research confidence increases score."""
    ent = Entity(
        id="ent_res_test",
        production_id="prod_test",
        name="Acme Gadget",
        entity_type=EntityType.PRODUCT,
        sources=[EntitySource.VISUAL],
        confidence=0.85,
    )

    # High research confidence
    res_high = ResearchResult(
        research_id="r1",
        entity_id="ent_res_test",
        production_id="prod_test",
        entity_name="Acme Gadget",
        status=ResearchStatus.SUCCESS,
        candidate_rights_holder="Acme Corp",
        identity_confidence=0.95,
        provider="local",
    )
    assess_high = compute_risk_assessment(ent, res_high)
    sig_high = next(s for s in assess_high.signals if s.signal_name == "RESEARCH_CONFIDENCE")
    assert sig_high.score_delta < 0  # Reduces risk

    # Not found / unverified
    res_low = ResearchResult(
        research_id="r2",
        entity_id="ent_res_test",
        production_id="prod_test",
        entity_name="Acme Gadget",
        status=ResearchStatus.NOT_FOUND,
        candidate_rights_holder=None,
        identity_confidence=0.0,
        provider="local",
    )
    assess_low = compute_risk_assessment(ent, res_low)
    sig_low = next(s for s in assess_low.signals if s.signal_name == "RESEARCH_CONFIDENCE")
    assert sig_low.score_delta > 0  # Increases risk


def test_signal_entity_type_weights():
    """BRAND and MUSIC entities carry higher baseline type weight than PERSON or OTHER."""
    brand_ent = Entity(production_id="p", name="BrandX", entity_type=EntityType.BRAND, confidence=0.8)
    person_ent = Entity(production_id="p", name="PersonY", entity_type=EntityType.PERSON, confidence=0.8)

    brand_assess = compute_risk_assessment(brand_ent, None)
    person_assess = compute_risk_assessment(person_ent, None)

    brand_type_sig = next(s for s in brand_assess.signals if s.signal_name == "ENTITY_TYPE")
    person_type_sig = next(s for s in person_assess.signals if s.signal_name == "ENTITY_TYPE")

    assert brand_type_sig.score_delta > person_type_sig.score_delta


def test_signal_duration_appearances():
    """Entity with appearances > 3 triggers DURATION signal (+10 points)."""
    repeated_ent = Entity(
        production_id="p",
        name="Repeated Watch",
        entity_type=EntityType.PRODUCT,
        confidence=0.8,
        appearances=5,
    )
    assessment = compute_risk_assessment(repeated_ent, None)
    dur_sig = next(s for s in assessment.signals if s.signal_name == "DURATION")
    assert dur_sig.triggered is True
    assert dur_sig.score_delta == 10.0


def test_signal_screen_position():
    """Entity located in center frame triggers SCREEN_POSITION signal (+5 points)."""
    center_ent = Entity(
        production_id="p",
        name="Center Focus Logo",
        entity_type=EntityType.BRAND,
        confidence=0.8,
        bounding_box=[0.4, 0.4, 0.6, 0.6],  # center is (0.5, 0.5)
    )
    assessment = compute_risk_assessment(center_ent, None)
    pos_sig = next(s for s in assessment.signals if s.signal_name == "SCREEN_POSITION")
    assert pos_sig.triggered is True
    assert pos_sig.score_delta == 5.0


def test_scoring_determinism_and_repeatability():
    """Computing risk assessment 100 times with identical input yields identical outputs."""
    entity = Entity(
        id="ent_repeatable",
        production_id="prod_repeat",
        name="Quantum Cola",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        classification=EntityClassification.VISUAL_ONLY,
        confidence=0.91,
        bounding_box=[0.3, 0.3, 0.7, 0.7],
        appearances=2,
    )
    first = compute_risk_assessment(entity, None)
    for _ in range(100):
        subsequent = compute_risk_assessment(entity, None)
        assert subsequent.risk_score == first.risk_score
        assert subsequent.risk_level == first.risk_level
        assert subsequent.confidence == first.confidence
        assert [s.score_delta for s in subsequent.signals] == [s.score_delta for s in first.signals]


def test_scoring_bounds_clamping():
    """Risk scores are strictly clamped to [0, 100] under extreme input conditions."""
    # Max risk triggers
    max_ent = Entity(
        id="ent_max",
        production_id="p",
        name="Ultra Trademarked Music Brand",
        entity_type=EntityType.MUSIC,
        sources=[EntitySource.VISUAL],
        classification=EntityClassification.VISUAL_ONLY,
        confidence=1.0,
        bounding_box=[0.0, 0.0, 1.0, 1.0],
        appearances=20,
    )
    max_assess = compute_risk_assessment(max_ent, None)
    assert max_assess.risk_score <= 100.0

    # Min risk triggers
    min_ent = Entity(
        id="ent_min",
        production_id="p",
        name="Min Prop",
        entity_type=EntityType.OTHER,
        sources=[EntitySource.SCRIPT],
        classification=EntityClassification.SCRIPT_ONLY,
        confidence=0.4,
        appearances=1,
    )
    res_high = ResearchResult(
        research_id="r_min",
        entity_id="ent_min",
        production_id="p",
        entity_name="Min Prop",
        status=ResearchStatus.SUCCESS,
        identity_confidence=1.0,
        provider="local",
    )
    min_assess = compute_risk_assessment(min_ent, res_high)
    assert min_assess.risk_score >= 0.0


def test_scoring_missing_research_fallback():
    """Risk assessment succeeds smoothly with research_result=None."""
    entity = Entity(
        id="ent_no_res",
        production_id="p",
        name="Random Object",
        entity_type=EntityType.OTHER,
        sources=[EntitySource.VISUAL],
        confidence=0.75,
    )
    assessment = compute_risk_assessment(entity, None)
    assert assessment.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.UNKNOWN]
    assert 0.0 <= assessment.confidence <= 1.0


def test_scoring_malformed_entity_handling():
    """Risk engine handles entities with empty fields or out-of-bounds bounding boxes safely."""
    malformed = Entity(
        id="ent_malformed",
        production_id="p",
        name="Malformed Object",
        entity_type=EntityType.OTHER,
        sources=[],
        confidence=0.5,
        bounding_box=[-1.0, 2.0, -0.5, 3.0],
        appearances=-5,
    )
    assessment = compute_risk_assessment(malformed, None)
    assert assessment.risk_score >= 0.0
    assert assessment.risk_score <= 100.0


def test_evidence_quality_confidence():
    """Evidence quality confidence reflects detection confidence, evidence count, and research status."""
    ent = Entity(
        id="ent_conf_test",
        production_id="p",
        name="Widget",
        entity_type=EntityType.PRODUCT,
        confidence=0.90,
        evidence_ids=["evi_1", "evi_2"],
    )
    res = ResearchResult(
        research_id="r",
        entity_id="ent_conf_test",
        production_id="p",
        entity_name="Widget",
        status=ResearchStatus.SUCCESS,
        identity_confidence=0.85,
        provider="local",
    )
    conf = compute_evidence_confidence(ent, res)
    assert 0.70 <= conf <= 1.0


# =========================================================================
# Suite 2: RiskAssessmentAgent Unit Tests (Tests 19 - 27)
# =========================================================================

@pytest.mark.asyncio
async def test_agent_assess_single_entity():
    """RiskAssessmentAgent.assess_entity assesses entity and returns a RiskAssessment."""
    agent = RiskAssessmentAgent()
    entity = Entity(
        id="ent_agent_01",
        production_id="prod_agent_test",
        name="Neon Beverage",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        classification=EntityClassification.VISUAL_ONLY,
        confidence=0.92,
    )
    assessment = await agent.assess_entity(entity)
    assert isinstance(assessment, RiskAssessment)
    assert assessment.entity_id == entity.id
    assert assessment.production_id == entity.production_id
    assert assessment.risk_level == RiskLevel.HIGH


@pytest.mark.asyncio
async def test_agent_assess_entities_batch():
    """RiskAssessmentAgent.assess_entities processes multiple entities."""
    agent = RiskAssessmentAgent()
    entities = [
        Entity(id="e1", production_id="p_batch", name="Sign", entity_type=EntityType.SIGNAGE, confidence=0.8),
        Entity(id="e2", production_id="p_batch", name="Song", entity_type=EntityType.MUSIC, confidence=0.9),
    ]
    assessments = await agent.assess_entities(entities)
    assert len(assessments) == 2
    assert {a.entity_id for a in assessments} == {"e1", "e2"}


@pytest.mark.asyncio
async def test_agent_priority_sorting():
    """Agent processes VISUAL_ONLY first, then BOTH, then SCRIPT_ONLY."""
    agent = RiskAssessmentAgent()
    e_script = Entity(
        id="e_script",
        production_id="p_sort",
        name="Script Entity",
        entity_type=EntityType.OTHER,
        sources=[EntitySource.SCRIPT],
        classification=EntityClassification.SCRIPT_ONLY,
        confidence=0.8,
    )
    e_both = Entity(
        id="e_both",
        production_id="p_sort",
        name="Both Entity",
        entity_type=EntityType.OTHER,
        sources=[EntitySource.SCRIPT, EntitySource.VISUAL],
        classification=EntityClassification.BOTH,
        confidence=0.8,
    )
    e_visual = Entity(
        id="e_visual",
        production_id="p_sort",
        name="Visual Entity",
        entity_type=EntityType.OTHER,
        sources=[EntitySource.VISUAL],
        classification=EntityClassification.VISUAL_ONLY,
        confidence=0.8,
    )

    processed_order = []

    async def mock_assess_entity(entity, force=False, **kwargs):
        processed_order.append(entity.id)
        return compute_risk_assessment(entity, None)

    with patch.object(agent, "assess_entity", side_effect=mock_assess_entity):
        await agent.assess_entities([e_script, e_both, e_visual])

    assert processed_order == ["e_visual", "e_both", "e_script"]


@pytest.mark.asyncio
async def test_agent_idempotency_cache():
    """Repeated assessment of same entity reuses cached assessment when unchanged."""
    agent = RiskAssessmentAgent()
    entity = Entity(
        id="ent_idem_01",
        production_id="p_idem",
        name="Cached Logo",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        confidence=0.9,
    )

    first_assess = await agent.assess_entity(entity)
    second_assess = await agent.assess_entity(entity, force=False)

    assert first_assess.risk_id == second_assess.risk_id
    assert first_assess.created_at == second_assess.created_at


@pytest.mark.asyncio
async def test_agent_force_refresh():
    """Force=True recomputes and saves a new assessment even if already cached."""
    agent = RiskAssessmentAgent()
    entity = Entity(
        id="ent_force_01",
        production_id="p_force",
        name="Forced Logo",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        confidence=0.9,
    )

    first_assess = await agent.assess_entity(entity)
    await asyncio.sleep(0.01)
    refreshed_assess = await agent.assess_entity(entity, force=True)

    assert refreshed_assess.risk_id != first_assess.risk_id or refreshed_assess.created_at != first_assess.created_at


@pytest.mark.asyncio
async def test_agent_error_isolation():
    """Error on one entity does not prevent remaining entities from being assessed."""
    agent = RiskAssessmentAgent()
    good1 = Entity(id="g1", production_id="p_err", name="Good 1", entity_type=EntityType.OTHER, confidence=0.8)
    bad = Entity(id="bad", production_id="p_err", name="Bad Entity", entity_type=EntityType.OTHER, confidence=0.8)
    good2 = Entity(id="g2", production_id="p_err", name="Good 2", entity_type=EntityType.OTHER, confidence=0.8)

    orig_calc = calculate_risk

    def selective_calc(entity, **kwargs):
        if entity.id == "bad":
            raise ValueError("Simulated unexpected assessment explosion")
        return orig_calc(entity, **kwargs)

    with patch("app.agents.risk_agent.calculate_risk", side_effect=selective_calc):
        results = await agent.assess_entities([good1, bad, good2], force=True)

    assert len(results) == 2
    assert {r.entity_id for r in results} == {"g1", "g2"}


@pytest.mark.asyncio
async def test_agent_entity_enrichment():
    """Agent enriches entity in entity repository with risk_id, risk_level, risk_score, and risk_confidence."""
    agent = RiskAssessmentAgent()
    entity_repo = get_entity_repo()

    entity = Entity(
        id="ent_enrich_01",
        production_id="p_enrich",
        name="Enriched Phone",
        entity_type=EntityType.PRODUCT,
        sources=[EntitySource.VISUAL],
        confidence=0.88,
    )
    await entity_repo.save(entity)

    assessment = await agent.assess_entity(entity)

    updated_entity = await entity_repo.get("ent_enrich_01")
    assert updated_entity is not None
    assert updated_entity.risk_id == assessment.risk_id
    assert updated_entity.risk_level == assessment.risk_level.value
    assert updated_entity.risk_score == assessment.risk_score
    assert updated_entity.risk_confidence == assessment.confidence


@pytest.mark.asyncio
async def test_agent_assess_production():
    """assess_production gathers all entities for a production and assesses them."""
    agent = RiskAssessmentAgent()
    entity_repo = get_entity_repo()
    prod_repo = get_production_repo()
    prod_id = "prod_full_run"

    await prod_repo.save(Production(id=prod_id, title="Full Run Production"))
    e1 = Entity(id="pfr_e1", production_id=prod_id, name="Obj1", entity_type=EntityType.OTHER, confidence=0.8)
    e2 = Entity(id="pfr_e2", production_id=prod_id, name="Obj2", entity_type=EntityType.BRAND, confidence=0.9)
    await entity_repo.save(e1)
    await entity_repo.save(e2)

    assessments = await agent.assess_production(prod_id)
    assert len(assessments) == 2


@pytest.mark.asyncio
async def test_agent_assess_risk_backward_compat():
    """assess_risk(production_id, entity_id) backward compatibility wrapper operates correctly."""
    agent = RiskAssessmentAgent()
    entity_repo = get_entity_repo()

    entity = Entity(
        id="ent_bw_01",
        production_id="p_bw",
        name="Vintage Clock",
        entity_type=EntityType.PRODUCT,
        confidence=0.85,
    )
    await entity_repo.save(entity)

    assessment = await agent.assess_risk("p_bw", "ent_bw_01")
    assert assessment.entity_id == "ent_bw_01"
    assert assessment.overall_risk_level in ["LOW", "MEDIUM", "HIGH", "UNKNOWN"]


# =========================================================================
# Suite 3: SSE Events Integration (Tests 28 - 29)
# =========================================================================

@pytest.mark.asyncio
async def test_agent_sse_events_emitted():
    """Agent emits RISK_ASSESSMENT_STARTED, RISK_SIGNAL_CALCULATED, and RISK_ASSESSMENT_COMPLETED."""
    agent = RiskAssessmentAgent()
    entity = Entity(
        id="ent_sse_01",
        production_id="prod_sse",
        name="SSE Coffee",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        confidence=0.95,
    )

    published_events = []

    async def mock_publish(event):
        published_events.append(event.event_type)

    with patch.object(event_bus, "publish", side_effect=mock_publish):
        await agent.assess_entities([entity], force=True)

    assert EventType.RISK_ASSESSMENT_STARTED in published_events
    assert EventType.RISK_SIGNAL_CALCULATED in published_events
    assert EventType.RISK_ASSESSMENT_COMPLETED in published_events


@pytest.mark.asyncio
async def test_agent_sse_failed_event_on_error():
    """Agent emits RISK_ASSESSMENT_FAILED when an unexpected error occurs during entity assessment."""
    agent = RiskAssessmentAgent()
    entity = Entity(
        id="ent_sse_fail",
        production_id="prod_sse_fail",
        name="Faulty Entity",
        entity_type=EntityType.BRAND,
        confidence=0.9,
    )

    published_events = []

    async def mock_publish(event):
        published_events.append(event.event_type)

    with patch.object(event_bus, "publish", side_effect=mock_publish):
        with patch("app.agents.risk_agent.calculate_risk", side_effect=RuntimeError("Simulated engine crash")):
            await agent.assess_entities([entity], force=True)

    assert EventType.RISK_ASSESSMENT_FAILED in published_events



# =========================================================================
# Suite 4: Repository Layer Tests (Tests 30 - 33)
# =========================================================================

@pytest.mark.asyncio
async def test_risk_repo_save_and_get():
    """Save and retrieve a RiskAssessment by risk_id."""
    repo = InMemoryRiskRepository()
    assessment = RiskAssessment(
        risk_id="risk_repo_01",
        entity_id="ent_repo_01",
        production_id="prod_repo",
        entity_name="Test Mark",
        risk_level=RiskLevel.MEDIUM,
        risk_score=52.0,
        signals=[],
        explanation="Test explanation",
        confidence=0.88,
    )
    saved = await repo.save(assessment)
    assert saved.risk_id == "risk_repo_01"

    retrieved = await repo.get("risk_repo_01")
    assert retrieved is not None
    assert retrieved.entity_name == "Test Mark"
    assert retrieved.risk_score == 52.0


@pytest.mark.asyncio
async def test_risk_repo_get_by_entity():
    """Retrieve latest assessment for an entity."""
    repo = InMemoryRiskRepository()
    a1 = RiskAssessment(
        risk_id="r1",
        entity_id="ent_multi",
        production_id="p_rep",
        entity_name="Multi",
        risk_level=RiskLevel.LOW,
        risk_score=20.0,
        signals=[],
        explanation="Old",
        confidence=0.8,
        created_at=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
    )
    a2 = RiskAssessment(
        risk_id="r2",
        entity_id="ent_multi",
        production_id="p_rep",
        entity_name="Multi",
        risk_level=RiskLevel.HIGH,
        risk_score=80.0,
        signals=[],
        explanation="New",
        confidence=0.9,
        created_at=datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc),
    )
    await repo.save(a1)
    await repo.save(a2)

    latest = await repo.get_by_entity("ent_multi")
    assert latest is not None
    assert latest.risk_id == "r2"
    assert latest.risk_score == 80.0


@pytest.mark.asyncio
async def test_risk_repo_list_for_production():
    """List all assessments for a specific production."""
    repo = InMemoryRiskRepository()
    a1 = RiskAssessment(
        risk_id="ra1", entity_id="e1", production_id="prod_target",
        entity_name="Target 1", risk_level=RiskLevel.LOW, risk_score=15.0,
        signals=[], explanation="", confidence=0.85
    )
    a2 = RiskAssessment(
        risk_id="ra2", entity_id="e2", production_id="prod_target",
        entity_name="Target 2", risk_level=RiskLevel.HIGH, risk_score=85.0,
        signals=[], explanation="", confidence=0.9
    )
    a3 = RiskAssessment(
        risk_id="ra3", entity_id="e3", production_id="prod_other",
        entity_name="Other", risk_level=RiskLevel.MEDIUM, risk_score=50.0,
        signals=[], explanation="", confidence=0.8
    )
    await repo.save(a1)
    await repo.save(a2)
    await repo.save(a3)

    target_list = await repo.list_for_production("prod_target")
    assert len(target_list) == 2
    assert {a.risk_id for a in target_list} == {"ra1", "ra2"}


@pytest.mark.asyncio
async def test_risk_repo_thread_safety():
    """Concurrent async saves maintain data integrity with asyncio.Lock."""
    repo = InMemoryRiskRepository()

    async def save_item(i):
        assess = RiskAssessment(
            risk_id=f"concurrent_risk_{i}",
            entity_id=f"concurrent_ent_{i}",
            production_id="prod_concurrent",
            entity_name=f"Concurrent {i}",
            risk_level=RiskLevel.LOW,
            risk_score=float(i),
            signals=[],
            explanation="",
            confidence=0.8,
        )
        return await repo.save(assess)

    results = await asyncio.gather(*(save_item(i) for i in range(50)))
    assert len(results) == 50
    prod_items = await repo.list_for_production("prod_concurrent")
    assert len(prod_items) == 50


# =========================================================================
# Suite 5: REST API Endpoint Tests (Tests 34 - 37)
# =========================================================================

def test_api_assess_production_success():
    """POST /productions/{production_id}/risk-assessment triggers assessment and returns list."""
    client = TestClient(app)
    prod_repo = get_production_repo()
    entity_repo = get_entity_repo()

    prod_id = "prod_api_valid"
    prod = Production(id=prod_id, title="API Valid Production")
    asyncio.run(prod_repo.save(prod))

    ent1 = Entity(id="api_e1", production_id=prod_id, name="Brand Logo", entity_type=EntityType.BRAND, confidence=0.9)
    ent2 = Entity(id="api_e2", production_id=prod_id, name="Incidental Prop", entity_type=EntityType.OTHER, confidence=0.8)
    asyncio.run(entity_repo.save(ent1))
    asyncio.run(entity_repo.save(ent2))

    response = client.post(f"/productions/{prod_id}/risk-assessment")
    assert response.status_code == 200
    data = response.json()
    assert "assessments" in data
    assessments = data["assessments"]
    assert len(assessments) == 2
    assert all("risk_score" in item for item in assessments)
    assert all("risk_level" in item for item in assessments)


def test_api_assess_production_not_found():
    """POST /productions/{production_id}/risk-assessment with nonexistent ID returns 404."""
    client = TestClient(app)
    response = client.post("/productions/nonexistent_prod_99999/risk-assessment")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_api_assess_production_empty_entities():
    """POST /productions/{production_id}/risk-assessment on production with 0 entities returns 200 with empty list."""
    client = TestClient(app)
    prod_repo = get_production_repo()

    prod_id = "prod_api_empty"
    prod = Production(id=prod_id, title="Empty Production")
    asyncio.run(prod_repo.save(prod))

    response = client.post(f"/productions/{prod_id}/risk-assessment")
    assert response.status_code == 200
    data = response.json()
    assert "assessments" in data
    assert len(data["assessments"]) == 0


def test_api_assess_production_force_flag():
    """POST /productions/{production_id}/risk-assessment?force=true forces re-assessment."""
    client = TestClient(app)
    prod_repo = get_production_repo()
    entity_repo = get_entity_repo()

    prod_id = "prod_api_force"
    prod = Production(id=prod_id, title="Force Production")
    asyncio.run(prod_repo.save(prod))

    ent = Entity(id="api_force_ent", production_id=prod_id, name="Coffee Mug", entity_type=EntityType.PRODUCT, confidence=0.85)
    asyncio.run(entity_repo.save(ent))

    res1 = client.post(f"/productions/{prod_id}/risk-assessment")
    assert res1.status_code == 200

    res2 = client.post(f"/productions/{prod_id}/risk-assessment?force=true")
    assert res2.status_code == 200
    assert len(res2.json()["assessments"]) == 1



# =========================================================================
# Suite 6: Zero Network Verification (Test 38)
# =========================================================================

@pytest.mark.asyncio
async def test_zero_network_calls():
    """Verify that throughout risk assessment, zero external network calls are made."""
    with patch("urllib.request.urlopen", side_effect=AssertionError("CRITICAL: Network call intercepted in test!")):
        with patch("http.client.HTTPConnection.request", side_effect=AssertionError("CRITICAL: HTTP request intercepted!")):
            agent = RiskAssessmentAgent()
            entity = Entity(
                id="ent_zero_net",
                production_id="p_zero",
                name="Safe Brand",
                entity_type=EntityType.BRAND,
                sources=[EntitySource.VISUAL],
                confidence=0.9,
            )
            assessment = await agent.assess_entity(entity, force=True)
            assert assessment.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.UNKNOWN]
            assert 0.0 <= assessment.risk_score <= 100.0
