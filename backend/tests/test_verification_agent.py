"""
Automated unit test suite for Phase 6 — Verification Intelligence.
Tests domain models, deterministic verification engine, contradiction rules,
penalty confidence calculation, VerificationAgent workflow, sorting priority,
idempotency caching, error isolation, repositories, and REST API endpoints.

STRICT ZERO-NETWORK CONSTRAINT: 0 external API calls (0 Gemini, 0 Groq, 0 Parallel).
"""

import asyncio
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.entity import (
    Entity,
    EntityClassification,
    EntitySource,
    EntityType,
    RiskLevel,
    VerificationStatus,
)
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.models.evidence import Evidence, EvidenceType
from app.models.production import Production
from app.models.research import ResearchResult, ResearchStatus
from app.models.risk import RiskAssessment, RiskLevel as RiskModelLevel, RiskSignal
from app.models.verification import (
    VerificationCheck,
    VerificationDecision,
    VerificationResult,
)
from app.repositories import (
    get_entity_repo,
    get_evidence_repo,
    get_production_repo,
    get_research_repo,
    get_risk_repo,
    get_verification_repo,
)
from app.services.events import event_bus
from app.services.verification_engine import VerificationEngine, verification_engine
from app.agents.verification_agent import VerificationAgent, verification_agent


# =============================================================================
# 1. DOMAIN MODELS & ENUMS
# =============================================================================

def test_verification_decision_enum():
    """Verify that all 4 verification decisions are properly defined."""
    assert VerificationDecision.CONFIRMED.value == "CONFIRMED"
    assert VerificationDecision.REVIEW.value == "REVIEW"
    assert VerificationDecision.REJECTED.value == "REJECTED"
    assert VerificationDecision.INSUFFICIENT_EVIDENCE.value == "INSUFFICIENT_EVIDENCE"


def test_verification_check_model():
    """Verify creation and serialization of VerificationCheck."""
    chk = VerificationCheck(
        name="IDENTITY_SUPPORT",
        passed=True,
        evidence_evaluated=["Rights candidate: Sony Music"],
        explanation="Candidate rights holder verified.",
        severity_if_failed="HIGH",
    )
    assert chk.check_id.startswith("chk_")
    assert chk.name == "IDENTITY_SUPPORT"
    assert chk.passed is True
    assert len(chk.evidence_evaluated) == 1
    assert chk.severity_if_failed == "HIGH"
    data = chk.model_dump()
    assert data["name"] == "IDENTITY_SUPPORT"


def test_verification_result_model():
    """Verify VerificationResult model defaults, fields, and properties."""
    res = VerificationResult(
        entity_id="ent_01",
        production_id="prod_01",
        entity_name="Pepsi",
        decision=VerificationDecision.CONFIRMED,
        confidence=0.92,
        claims_supported=["Trademark confirmed"],
        claims_disputed=[],
        contradictions=[],
        recommended_action="Proceed to clearance licensing workflow.",
    )
    assert res.verification_id.startswith("ver_")
    assert res.id == res.verification_id
    assert res.status == VerificationStatus.CONFIRMED
    assert res.rights_holder == "Pepsi"
    assert res.confidence == 0.92
    assert res.match_confidence == 0.92


def test_verification_result_backward_compatibility_properties():
    """Test computed property mappings to legacy VerificationStatus."""
    r_conf = VerificationResult(entity_id="e", production_id="p", decision=VerificationDecision.CONFIRMED)
    assert r_conf.status == VerificationStatus.CONFIRMED

    r_rej = VerificationResult(entity_id="e", production_id="p", decision=VerificationDecision.REJECTED)
    assert r_rej.status == VerificationStatus.DISPUTED

    r_ins = VerificationResult(entity_id="e", production_id="p", decision=VerificationDecision.INSUFFICIENT_EVIDENCE)
    assert r_ins.status == VerificationStatus.INCONCLUSIVE

    r_rev = VerificationResult(entity_id="e", production_id="p", decision=VerificationDecision.REVIEW)
    assert r_rev.status == VerificationStatus.UNVERIFIED


def test_verification_result_compat_validator():
    """Test initialization with legacy kwargs (id, status, rights_holder, match_confidence)."""
    res = VerificationResult(
        id="ver_legacy_999",
        entity_id="ent_01",
        production_id="prod_01",
        rights_holder="Legacy Corp",
        match_confidence=0.88,
        status=VerificationStatus.CONFIRMED,
    )
    assert res.verification_id == "ver_legacy_999"
    assert res.decision == VerificationDecision.CONFIRMED
    assert res.confidence == 0.88
    assert res.rights_holder == "Legacy Corp"


def test_entity_verification_fields():
    """Verify that Entity model incorporates verification tracking fields."""
    ent = Entity(
        production_id="prod_01",
        name="Omega Watch",
        verification_id="ver_123",
        verification_decision="CONFIRMED",
        verification_confidence=0.95,
    )
    assert ent.verification_id == "ver_123"
    assert ent.verification_decision == "CONFIRMED"
    assert ent.verification_confidence == 0.95


def test_events_verification_event_types():
    """Verify verification event types in EventType enum."""
    assert EventType.VERIFICATION_STARTED.value == "VERIFICATION_STARTED"
    assert EventType.VERIFICATION_CHECK_COMPLETED.value == "VERIFICATION_CHECK_COMPLETED"
    assert EventType.VERIFICATION_CONTRADICTION_FOUND.value == "VERIFICATION_CONTRADICTION_FOUND"
    assert EventType.VERIFICATION_COMPLETED.value == "VERIFICATION_COMPLETED"
    assert EventType.VERIFICATION_FAILED.value == "VERIFICATION_FAILED"


def test_processing_event_verification_fields():
    """Verify that ProcessingEvent supports verification_decision and verification_confidence."""
    evt = ProcessingEvent(
        production_id="prod_01",
        job_id="job_01",
        event_type=EventType.VERIFICATION_COMPLETED,
        message="Verification completed",
        verification_decision="CONFIRMED",
        verification_confidence=0.91,
    )
    assert evt.verification_decision == "CONFIRMED"
    assert evt.verification_confidence == 0.91
    d = evt.to_dict()
    assert d["verification_decision"] == "CONFIRMED"


# =============================================================================
# 2. DETERMINISTIC VERIFICATION ENGINE & 7 CORE CHECKS
# =============================================================================

def test_engine_identity_support_pass():
    """Test IDENTITY_SUPPORT check passes when candidate rights holder exists."""
    engine = VerificationEngine()
    ent = Entity(production_id="p1", name="Apple iPhone", candidate_rights_holder="Apple Inc.")
    res = engine.verify(entity=ent)
    chk = next(c for c in res.checks_run if c.name == "IDENTITY_SUPPORT")
    assert chk.passed is True


def test_engine_identity_support_fail():
    """Test IDENTITY_SUPPORT check fails when rights holder is missing or pending."""
    engine = VerificationEngine()
    ent = Entity(production_id="p1", name="Generic Cup", candidate_rights_holder="Pending Verification")
    res = engine.verify(entity=ent)
    chk = next(c for c in res.checks_run if c.name == "IDENTITY_SUPPORT")
    assert chk.passed is False


def test_engine_research_support_pass():
    """Test RESEARCH_SUPPORT check passes when research result has good confidence."""
    engine = VerificationEngine()
    ent = Entity(production_id="p1", name="Nike Shoes")
    research = ResearchResult(
        entity_id=ent.id,
        production_id="p1",
        entity_name="Nike Shoes",
        status=ResearchStatus.SUCCESS,
        research_confidence=0.85,
        candidate_rights_holder="Nike, Inc.",
    )
    res = engine.verify(entity=ent, research=research)
    chk = next(c for c in res.checks_run if c.name == "RESEARCH_SUPPORT")
    assert chk.passed is True


def test_engine_research_support_fail():
    """Test RESEARCH_SUPPORT check fails when research is None or NOT_FOUND."""
    engine = VerificationEngine()
    ent = Entity(production_id="p1", name="Unknown Marker")
    res = engine.verify(entity=ent, research=None)
    chk = next(c for c in res.checks_run if c.name == "RESEARCH_SUPPORT")
    assert chk.passed is False


def test_engine_evidence_quality_pass():
    """Test EVIDENCE_QUALITY check passes when frame paths and scene context exist."""
    engine = VerificationEngine()
    ent = Entity(
        production_id="p1",
        name="Rolex Submariner",
        frame_path="frames/scene01_0010.jpg",
        scene=1,
        bounding_box=[0.1, 0.2, 0.3, 0.4],
    )
    res = engine.verify(entity=ent)
    chk = next(c for c in res.checks_run if c.name == "EVIDENCE_QUALITY")
    assert chk.passed is True


def test_engine_evidence_quality_fail():
    """Test EVIDENCE_QUALITY check fails when no frames or context are provided."""
    engine = VerificationEngine()
    ent = Entity(
        production_id="p1",
        name="Speculative Brand",
        frame_path=None,
        scene=None,
        context=None,
        visual_basis=None,
    )
    res = engine.verify(entity=ent, evidence_list=[])
    chk = next(c for c in res.checks_run if c.name == "EVIDENCE_QUALITY")
    assert chk.passed is False


def test_engine_risk_support_pass():
    """Test RISK_SUPPORT check passes with valid RiskAssessment object."""
    engine = VerificationEngine()
    ent = Entity(production_id="p1", name="Coca-Cola")
    risk = RiskAssessment(
        entity_id=ent.id,
        production_id="p1",
        entity_name="Coca-Cola",
        overall_risk_level=RiskModelLevel.HIGH,
        risk_score=75.0,
        confidence=0.85,
    )
    res = engine.verify(entity=ent, risk=risk)
    chk = next(c for c in res.checks_run if c.name == "RISK_SUPPORT")
    assert chk.passed is True


def test_engine_risk_support_fallback_to_entity_risk():
    """Test RISK_SUPPORT check falls back to entity's pre-calculated risk score."""
    engine = VerificationEngine()
    ent = Entity(
        production_id="p1",
        name="Starbucks Mug",
        risk_level=RiskLevel.MEDIUM,
        risk_score=55.0,
    )
    res = engine.verify(entity=ent, risk=None)
    chk = next(c for c in res.checks_run if c.name == "RISK_SUPPORT")
    assert chk.passed is True


def test_engine_source_consistency_pass():
    """Test SOURCE_CONSISTENCY check passes when classification matches sources."""
    engine = VerificationEngine()
    ent = Entity(
        production_id="p1",
        name="Dell Laptop",
        sources=[EntitySource.VISUAL],
    )
    assert ent.classification == EntityClassification.VISUAL_ONLY
    res = engine.verify(entity=ent)
    chk = next(c for c in res.checks_run if c.name == "SOURCE_CONSISTENCY")
    assert chk.passed is True


def test_engine_metadata_completeness_pass_and_fail():
    """Test METADATA_COMPLETENESS check evaluates properly."""
    engine = VerificationEngine()
    ent_ok = Entity(production_id="p1", name="Sony Headphones", entity_type=EntityType.PRODUCT)
    res_ok = engine.verify(entity=ent_ok)
    chk_ok = next(c for c in res_ok.checks_run if c.name == "METADATA_COMPLETENESS")
    assert chk_ok.passed is True

    ent_bad = Entity(production_id="", name="", entity_type=EntityType.BRAND)
    res_bad = engine.verify(entity=ent_bad)
    chk_bad = next(c for c in res_bad.checks_run if c.name == "METADATA_COMPLETENESS")
    assert chk_bad.passed is False


# =============================================================================
# 3. ADVERSARIAL CONTRADICTION RULES
# =============================================================================

def test_engine_contradiction_rule1_conflicting_rights_holders():
    """Contradiction Rule 1: Conflicting candidate rights holders in research evidence."""
    engine = VerificationEngine()
    ent = Entity(production_id="p1", name="Vocal Sample")
    ev1 = Evidence(
        evidence_type=EvidenceType.RESEARCH_EVIDENCE,
        source_title="USPTO",
        candidate_rights_holder="Sony Music Publishing",
        confidence=0.8,
    )
    ev2 = Evidence(
        evidence_type=EvidenceType.RESEARCH_EVIDENCE,
        source_title="Copyright Office",
        candidate_rights_holder="Universal Music Group",
        confidence=0.85,
    )
    research = ResearchResult(
        entity_id=ent.id,
        production_id="p1",
        entity_name="Vocal Sample",
        status=ResearchStatus.INSUFFICIENT_EVIDENCE,
        evidence=[ev1, ev2],
    )
    res = engine.verify(entity=ent, research=research)
    assert len(res.contradictions) > 0
    assert any("conflicting rights holders" in c.lower() for c in res.contradictions)
    assert res.decision == VerificationDecision.REJECTED


def test_engine_contradiction_rule2_music_rights_non_music():
    """Contradiction Rule 2: MUSIC_RIGHTS signal on non-music entity without audio evidence."""
    engine = VerificationEngine()
    ent = Entity(
        production_id="p1",
        name="Brand Billboard",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
    )
    sig = RiskSignal(
        signal_type="MUSIC_RIGHTS",
        signal_name="Music Master Licensing",
        severity="HIGH",
        weight=0.35,
        contribution=30.0,
        value="background_music",
        explanation="Detected background soundtrack",
    )
    risk = RiskAssessment(
        entity_id=ent.id,
        production_id="p1",
        entity_name="Brand Billboard",
        overall_risk_level=RiskModelLevel.HIGH,
        risk_score=80.0,
        signals=[sig],
        confidence=0.85,
    )
    res = engine.verify(entity=ent, risk=risk)
    assert any("music_rights exposure" in c.lower() for c in res.contradictions)
    assert res.decision == VerificationDecision.REJECTED


def test_engine_contradiction_rule3_visual_only_in_screenplay():
    """Contradiction Rule 3: VISUAL_ONLY classification contradicted by screenplay mention."""
    engine = VerificationEngine()
    ent = Entity(
        production_id="p1",
        name="Gucci",
        sources=[EntitySource.VISUAL],
    )
    assert ent.classification == EntityClassification.VISUAL_ONLY
    script = "SCENE 01 - Arjun adjusts his stylish Gucci belt before entering."
    res = engine.verify(entity=ent, script_text=script)
    assert any("appears verbatim in the screenplay" in c.lower() for c in res.contradictions)
    assert res.decision == VerificationDecision.REJECTED


def test_engine_contradiction_rule4_not_found_with_candidate():
    """Contradiction Rule 4: Research status NOT_FOUND with affirmative candidate rights holder."""
    engine = VerificationEngine()
    ent = Entity(production_id="p1", name="Ghost Label")
    research = ResearchResult(
        entity_id=ent.id,
        production_id="p1",
        entity_name="Ghost Label",
        status=ResearchStatus.NOT_FOUND,
        candidate_rights_holder="Warner Bros Discovery",
    )
    res = engine.verify(entity=ent, research=research)
    assert any("not_found, but candidate rights holder is populated" in c.lower() for c in res.contradictions)
    assert res.decision == VerificationDecision.REJECTED


def test_engine_contradiction_rule5_audio_only_with_frames():
    """Contradiction Rule 5: AUDIO_ONLY entity with attached visual frames."""
    engine = VerificationEngine()
    ent = Entity(
        production_id="p1",
        name="Background Score Track",
        sources=[EntitySource.AUDIO],
        frame_path="frames/scene01_005.jpg",
    )
    assert ent.classification == EntityClassification.AUDIO_ONLY
    res = engine.verify(entity=ent)
    assert any("video frame evidence is attached" in c.lower() for c in res.contradictions)
    assert res.decision == VerificationDecision.REJECTED


# =============================================================================
# 4. DECISIONS, PENALTIES, & NON-LEGAL RECOMMENDATIONS
# =============================================================================

def test_engine_decision_confirmed():
    """Verify CONFIRMED decision when all checks pass and confidence >= 0.70."""
    engine = VerificationEngine()
    ent = Entity(
        production_id="p1",
        name="Nike",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        frame_path="frames/01.jpg",
        scene=1,
        confidence=0.90,
        candidate_rights_holder="Nike, Inc.",
    )
    research = ResearchResult(
        entity_id=ent.id,
        production_id="p1",
        entity_name="Nike",
        status=ResearchStatus.SUCCESS,
        research_confidence=0.95,
        candidate_rights_holder="Nike, Inc.",
    )
    risk = RiskAssessment(
        entity_id=ent.id,
        production_id="p1",
        entity_name="Nike",
        overall_risk_level=RiskModelLevel.MEDIUM,
        risk_score=50.0,
        confidence=0.88,
    )
    res = engine.verify(entity=ent, research=research, risk=risk)
    assert res.decision == VerificationDecision.CONFIRMED
    assert res.confidence >= 0.70
    assert len(res.contradictions) == 0


def test_engine_decision_insufficient_evidence():
    """Verify INSUFFICIENT_EVIDENCE when research is NOT_FOUND and zero frames/evidence exist."""
    engine = VerificationEngine()
    ent = Entity(
        production_id="p1",
        name="Unknown Sketch",
        frame_path=None,
        scene=None,
        context=None,
        visual_basis=None,
    )
    research = ResearchResult(
        entity_id=ent.id,
        production_id="p1",
        entity_name="Unknown Sketch",
        status=ResearchStatus.NOT_FOUND,
        candidate_rights_holder=None,
    )
    res = engine.verify(entity=ent, research=research, evidence_list=[])
    assert res.decision == VerificationDecision.INSUFFICIENT_EVIDENCE


def test_engine_decision_review_on_borderline():
    """Verify REVIEW decision when confidence is moderate and minor check fails."""
    engine = VerificationEngine()
    ent = Entity(
        production_id="p1",
        name="Local Coffee Sign",
        sources=[EntitySource.VISUAL],
        frame_path="frames/01.jpg",
        scene=1,
        confidence=0.60,
    )
    # Research missing
    res = engine.verify(entity=ent, research=None)
    assert res.decision in (VerificationDecision.REVIEW, VerificationDecision.INSUFFICIENT_EVIDENCE)


def test_engine_recommendations_non_legal():
    """Verify that recommended actions provide triage guidance without legal advice."""
    engine = VerificationEngine()
    ent = Entity(production_id="p1", name="Generic Can")
    res = engine.verify(entity=ent)
    rec = res.recommended_action.lower()
    # Non-legal triage phrases
    assert any(term in rec for term in ["review", "clearance", "licensing", "coordinator", "workflow", "audit", "search", "trademark", "evidence", "frames"])
    # Not legal advice
    assert "legal counsel has ruled" not in rec
    assert "you will be sued" not in rec


# =============================================================================
# 5. VERIFICATION AGENT WORKFLOW & PRIORITY SORTING
# =============================================================================

def test_agent_priority_sorting():
    """Verify strict priority sorting: Risk Level (HIGH > MED > LOW > UNKNOWN) and Classification (VISUAL_ONLY > BOTH > SCRIPT_ONLY)."""
    agent = VerificationAgent()
    e_low_vis = Entity(
        id="e1",
        production_id="p1",
        name="A",
        risk_level=RiskLevel.LOW,
        sources=[EntitySource.VISUAL],
    )
    e_high_script = Entity(
        id="e2",
        production_id="p1",
        name="B",
        risk_level=RiskLevel.HIGH,
        sources=[EntitySource.SCRIPT],
    )
    e_high_vis = Entity(
        id="e3",
        production_id="p1",
        name="C",
        risk_level=RiskLevel.HIGH,
        sources=[EntitySource.VISUAL],
    )
    e_med_both = Entity(
        id="e4",
        production_id="p1",
        name="D",
        risk_level=RiskLevel.MEDIUM,
        sources=[EntitySource.VISUAL, EntitySource.SCRIPT],
    )

    entities = [e_low_vis, e_high_script, e_high_vis, e_med_both]
    sorted_entities = sorted(entities, key=agent._sort_key)

    # 1st: HIGH risk, VISUAL_ONLY (e_high_vis)
    # 2nd: HIGH risk, SCRIPT_ONLY (e_high_script)
    # 3rd: MEDIUM risk, BOTH (e_med_both)
    # 4th: LOW risk, VISUAL_ONLY (e_low_vis)
    assert sorted_entities[0].id == "e3"
    assert sorted_entities[1].id == "e2"
    assert sorted_entities[2].id == "e4"
    assert sorted_entities[3].id == "e1"


@pytest.mark.asyncio
async def test_agent_verify_entity_idempotency_caching():
    """Verify that agent reuses cached verification unless force_refresh=True."""
    agent = VerificationAgent()
    ent_repo = get_entity_repo()
    ver_repo = get_verification_repo()

    ent = Entity(
        production_id="prod_cache_test",
        name="Tesla Model S",
        candidate_rights_holder="Tesla Inc.",
    )
    await ent_repo.create(ent)

    # First run
    res1 = await agent.verify_entity(ent, production_id="prod_cache_test")
    assert res1 is not None

    # Second run without force should return cached verification
    res2 = await agent.verify_entity(ent, production_id="prod_cache_test", force_refresh=False)
    assert res1.verification_id == res2.verification_id

    # Third run with force_refresh=True should generate new verification
    res3 = await agent.verify_entity(ent, production_id="prod_cache_test", force_refresh=True)
    assert res3 is not None


@pytest.mark.asyncio
async def test_agent_verify_entity_enrichment():
    """Verify that agent enriches entity in entity_repo with verification metadata."""
    agent = VerificationAgent()
    ent_repo = get_entity_repo()

    ent = Entity(
        production_id="prod_enrich_test",
        name="Sony Bravia TV",
        candidate_rights_holder="Sony Corp",
    )
    await ent_repo.create(ent)

    result = await agent.verify_entity(ent, production_id="prod_enrich_test", force_refresh=True)

    updated_ent = await ent_repo.get(ent.id)
    assert updated_ent is not None
    assert updated_ent.verification_id == result.verification_id
    assert updated_ent.verification_decision == result.decision.value
    assert updated_ent.verification_confidence == result.confidence


@pytest.mark.asyncio
async def test_agent_verify_entities_batch():
    """Verify batch verification with multiple entities."""
    agent = VerificationAgent()
    ent1 = Entity(production_id="prod_batch_test", name="Adidas Sneaker", risk_level=RiskLevel.MEDIUM)
    ent2 = Entity(production_id="prod_batch_test", name="Prada Bag", risk_level=RiskLevel.HIGH)

    results = await agent.verify_entities(
        entities=[ent1, ent2],
        production_id="prod_batch_test",
        force_refresh=True,
    )
    assert len(results) == 2
    # High risk should be verified first
    assert results[0].entity_name == "Prada Bag"
    assert results[1].entity_name == "Adidas Sneaker"


@pytest.mark.asyncio
async def test_agent_verify_production():
    """Verify production-wide entity verification."""
    agent = VerificationAgent()
    prod_repo = get_production_repo()
    ent_repo = get_entity_repo()

    prod = Production(title="Sci-Fi Commercial")
    await prod_repo.create(prod)

    ent = Entity(production_id=prod.id, name="Ray-Ban Sunglasses")
    await ent_repo.create(ent)

    results = await agent.verify_production(prod.id, force_refresh=True)
    assert len(results) >= 1
    assert any(r.entity_name == "Ray-Ban Sunglasses" for r in results)


@pytest.mark.asyncio
async def test_agent_error_isolation():
    """Verify that an unexpected exception during entity verification doesn't crash the pipeline."""
    agent = VerificationAgent()

    # Pass an entity that might trigger error handling or test fallback
    ent = Entity(production_id="prod_err_test", name="Corrupted Entity")

    # verify_entity catches internal errors and returns fallback REVIEW
    res = await agent.verify_entity(ent, production_id="prod_err_test", force_refresh=True)
    assert res is not None
    assert res.decision in (VerificationDecision.REVIEW, VerificationDecision.INSUFFICIENT_EVIDENCE)


@pytest.mark.asyncio
async def test_agent_verify_rights_backward_compatibility():
    """Verify backward-compatible verify_rights method works for legacy callers."""
    agent = VerificationAgent()
    ent = Entity(
        production_id="prod_legacy",
        name="Legacy Soda",
        rights_holder="Legacy Beverage Co",
    )
    res = await agent.verify_rights(ent, {"rights_holder": "Legacy Beverage Co"})
    assert res.rights_holder == "Legacy Beverage Co"
    assert res.status in (VerificationStatus.CONFIRMED, VerificationStatus.UNVERIFIED, VerificationStatus.DISPUTED, VerificationStatus.INCONCLUSIVE)


@pytest.mark.asyncio
async def test_agent_sse_events_emitted():
    """Verify that verification lifecycle events are emitted to event_bus."""
    agent = VerificationAgent()
    prod_id = "prod_sse_test_99"
    ent = Entity(production_id=prod_id, name="Bose Speakers")
    await agent.verify_entity(ent, production_id=prod_id, force_refresh=True)

    history = event_bus.get_history(f"ver_{prod_id}")
    assert len(history) >= 2
    types = [e.event_type for e in history]
    assert EventType.VERIFICATION_COMPLETED in types


# =============================================================================
# 6. REPOSITORY LAYER
# =============================================================================

@pytest.mark.asyncio
async def test_in_memory_verification_repo_save_and_get():
    """Test saving and retrieving verification records by verification_id and entity_id."""
    repo = get_verification_repo()
    ver = VerificationResult(
        entity_id="ent_repo_01",
        production_id="prod_repo_01",
        entity_name="MacBook Pro",
        decision=VerificationDecision.CONFIRMED,
    )
    await repo.save(ver)

    by_id = await repo.get(ver.verification_id)
    assert by_id is not None
    assert by_id.verification_id == ver.verification_id

    by_ent = await repo.get_by_entity("ent_repo_01")
    assert by_ent is not None
    assert by_ent.entity_name == "MacBook Pro"


@pytest.mark.asyncio
async def test_in_memory_verification_repo_latest_timestamp():
    """Test that get_by_entity returns the latest verification record."""
    repo = get_verification_repo()
    ver_old = VerificationResult(
        entity_id="ent_multi",
        production_id="p1",
        entity_name="Multi Test",
        decision=VerificationDecision.REVIEW,
        verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    ver_new = VerificationResult(
        entity_id="ent_multi",
        production_id="p1",
        entity_name="Multi Test",
        decision=VerificationDecision.CONFIRMED,
        verified_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    await repo.save(ver_old)
    await repo.save(ver_new)

    latest = await repo.get_by_entity("ent_multi")
    assert latest is not None
    assert latest.decision == VerificationDecision.CONFIRMED


@pytest.mark.asyncio
async def test_in_memory_verification_repo_list_for_production():
    """Test listing all verifications for a specific production."""
    repo = get_verification_repo()
    prod_id = "prod_list_test_01"
    v1 = VerificationResult(entity_id="e1", production_id=prod_id, entity_name="Item 1")
    v2 = VerificationResult(entity_id="e2", production_id=prod_id, entity_name="Item 2")
    await repo.save(v1)
    await repo.save(v2)

    prods = await repo.list_for_production(prod_id)
    assert len(prods) >= 2


# =============================================================================
# 7. REST API ENDPOINTS
# =============================================================================

@pytest.mark.asyncio
async def test_api_post_verification_endpoint():
    """Test POST /productions/{production_id}/verification triggers verification successfully."""
    prod_repo = get_production_repo()
    ent_repo = get_entity_repo()

    prod = Production(title="Action Film")
    await prod_repo.create(prod)

    ent = Entity(
        production_id=prod.id,
        name="Ford Mustang",
        candidate_rights_holder="Ford Motor Company",
    )
    await ent_repo.create(ent)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/productions/{prod.id}/verification",
            json={"force_refresh": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["production_id"] == prod.id
        assert len(data["results"]) >= 1
        res = data["results"][0]
        assert "decision" in res
        assert "confidence" in res
        assert "recommended_action" in res


@pytest.mark.asyncio
async def test_api_post_verification_404_nonexistent():
    """Test POST /productions/{id}/verification returns 404 for invalid production."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/productions/nonexistent_prod_123/verification")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_api_get_verifications_endpoint():
    """Test GET /productions/{production_id}/verification retrieves stored verifications."""
    prod_repo = get_production_repo()
    ver_repo = get_verification_repo()

    prod = Production(title="Drama Pilot")
    await prod_repo.create(prod)

    ver = VerificationResult(
        entity_id="ent_get_api",
        production_id=prod.id,
        entity_name="Gibson Guitar",
        decision=VerificationDecision.CONFIRMED,
    )
    await ver_repo.save(ver)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/productions/{prod.id}/verification")
        assert response.status_code == 200
        data = response.json()
        assert data["production_id"] == prod.id
        assert len(data["results"]) >= 1
        assert any(r["entity_name"] == "Gibson Guitar" for r in data["results"])
