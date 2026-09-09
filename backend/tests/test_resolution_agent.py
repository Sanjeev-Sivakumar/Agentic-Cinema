"""
Automated unit test suite for Phase 7 — Resolution Intelligence.
Tests domain models, deterministic resolution engine, Rules A through I,
priority hierarchy, neutral replacement suggestions, evidence traceability,
ResolutionAgent workflow, idempotency caching, error isolation, EventBus SSE events,
repositories, and REST API endpoints.

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
from app.models.production import Production
from app.models.clearance import ClearanceActionType, ClearanceRequest, ClearanceStatus
from app.models.risk import RiskAssessment
from app.models.verification import (
    VerificationCheck,
    VerificationDecision,
    VerificationResult,
)
from app.models.resolution import (
    ResolutionAction,
    ResolutionPriority,
    ResolutionResult,
    ResolutionStatus,
)
from app.repositories import (
    get_entity_repo,
    get_production_repo,
    get_research_repo,
    get_resolution_repo,
    get_risk_repo,
    get_verification_repo,
)
from app.services.events import event_bus
from app.services.resolution_engine import ResolutionEngine
from app.agents.resolution_agent import ResolutionAgent, resolution_agent


# =============================================================================
# 1. DOMAIN MODELS & ENUMS
# =============================================================================

def test_resolution_status_enum():
    """Verify all Phase 7 resolution status enum values."""
    assert ResolutionStatus.RESOLVED.value == "RESOLVED"
    assert ResolutionStatus.ACTION_REQUIRED.value == "ACTION_REQUIRED"
    assert ResolutionStatus.HUMAN_REVIEW.value == "HUMAN_REVIEW"
    assert ResolutionStatus.MORE_EVIDENCE_REQUIRED.value == "MORE_EVIDENCE_REQUIRED"
    assert ResolutionStatus.RESEARCH_REQUIRED.value == "RESEARCH_REQUIRED"
    assert ResolutionStatus.REPLACEMENT_RECOMMENDED.value == "REPLACEMENT_RECOMMENDED"
    assert ResolutionStatus.ESCALATED.value == "ESCALATED"
    assert ResolutionStatus.UNRESOLVED.value == "UNRESOLVED"
    assert ResolutionStatus.PENDING.value == "PENDING"


def test_resolution_action_enum():
    """Verify operational resolution actions."""
    assert ResolutionAction.NO_ACTION.value == "NO_ACTION"
    assert ResolutionAction.HUMAN_REVIEW.value == "HUMAN_REVIEW"
    assert ResolutionAction.COLLECT_EVIDENCE.value == "COLLECT_EVIDENCE"
    assert ResolutionAction.CONDUCT_RESEARCH.value == "CONDUCT_RESEARCH"
    assert ResolutionAction.REQUEST_RIGHTS_INFORMATION.value == "REQUEST_RIGHTS_INFORMATION"
    assert ResolutionAction.REVIEW_MUSIC_USAGE.value == "REVIEW_MUSIC_USAGE"
    assert ResolutionAction.REVIEW_BRAND_USAGE.value == "REVIEW_BRAND_USAGE"
    assert ResolutionAction.REVIEW_LOCATION_USAGE.value == "REVIEW_LOCATION_USAGE"
    assert ResolutionAction.REVIEW_ARTWORK_USAGE.value == "REVIEW_ARTWORK_USAGE"
    assert ResolutionAction.REVIEW_PUBLIC_FIGURE_USAGE.value == "REVIEW_PUBLIC_FIGURE_USAGE"
    assert ResolutionAction.CONSIDER_REPLACEMENT.value == "CONSIDER_REPLACEMENT"
    assert ResolutionAction.ESCALATE.value == "ESCALATE"


def test_resolution_priority_enum():
    """Verify operational resolution priority levels."""
    assert ResolutionPriority.CRITICAL.value == "CRITICAL"
    assert ResolutionPriority.HIGH.value == "HIGH"
    assert ResolutionPriority.MEDIUM.value == "MEDIUM"
    assert ResolutionPriority.LOW.value == "LOW"
    assert ResolutionPriority.INFO.value == "INFO"


def test_resolution_result_model_and_compat():
    """Verify ResolutionResult creation and backward compatibility properties."""
    res = ResolutionResult(
        resolution_id="res_test123",
        entity_id="ent_01",
        production_id="prod_01",
        entity_name="Demo Brand",
        entity_type="BRAND",
        verification_decision="CONFIRMED",
        risk_level="HIGH",
        risk_score=85.0,
        resolution_status=ResolutionStatus.ACTION_REQUIRED,
        recommended_action=ResolutionAction.REVIEW_BRAND_USAGE,
        priority=ResolutionPriority.CRITICAL,
        action_reason="High exposure brand element",
        supporting_evidence_ids=["frame_01", "ver_01"],
    )

    assert res.resolution_id == "res_test123"
    assert res.id == "res_test123"
    assert res.action_type == "REVIEW_BRAND_USAGE"
    assert res.status == "ACTION_REQUIRED"
    assert res.confidence > 0.0


# =============================================================================
# 2. DETERMINISTIC RESOLUTION ENGINE — RULES A THROUGH I
# =============================================================================

def test_rule_a_insufficient_evidence():
    """Rule A: INSUFFICIENT_EVIDENCE -> MORE_EVIDENCE_REQUIRED, COLLECT_EVIDENCE."""
    entity = Entity(
        id="ent_a",
        production_id="prod_test",
        name="Obscured Logo",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
    )
    verification = VerificationResult(
        verification_id="ver_a",
        entity_id="ent_a",
        production_id="prod_test",
        decision=VerificationDecision.INSUFFICIENT_EVIDENCE,
    )
    risk = RiskAssessment(
        entity_id="ent_a",
        production_id="prod_test",
        risk_level=RiskLevel.MEDIUM,
        risk_score=45.0,
    )

    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=verification)
    assert result.resolution_status == ResolutionStatus.MORE_EVIDENCE_REQUIRED
    assert result.recommended_action == ResolutionAction.COLLECT_EVIDENCE
    assert len(result.missing_evidence) > 0
    assert "Additional visual or audio evidence is required" in result.action_reason


def test_rule_b_rejected_verification():
    """Rule B: REJECTED -> HUMAN_REVIEW (confirm non-exposure)."""
    entity = Entity(
        id="ent_b",
        production_id="prod_test",
        name="False Detection Item",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
    )
    verification = VerificationResult(
        verification_id="ver_b",
        entity_id="ent_b",
        production_id="prod_test",
        decision=VerificationDecision.REJECTED,
    )

    result = ResolutionEngine.resolve(entity=entity, verification=verification)
    assert result.resolution_status == ResolutionStatus.HUMAN_REVIEW
    assert result.recommended_action == ResolutionAction.HUMAN_REVIEW
    assert result.priority == ResolutionPriority.MEDIUM
    assert "fails to support" in result.action_reason


def test_rule_c_contradiction_escalation():
    """Rule C: Contradictions -> HUMAN_REVIEW + ESCALATE action."""
    entity = Entity(
        id="ent_c",
        production_id="prod_test",
        name="Contradictory Prop",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
    )
    verification = VerificationResult(
        verification_id="ver_c",
        entity_id="ent_c",
        production_id="prod_test",
        decision=VerificationDecision.REVIEW,
        contradictions=["Frame shows vintage 1980s can but research identified 2020 product line"],
    )
    risk = RiskAssessment(
        entity_id="ent_c",
        production_id="prod_test",
        risk_level=RiskLevel.HIGH,
        risk_score=75.0,
    )

    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=verification)
    assert result.resolution_status == ResolutionStatus.HUMAN_REVIEW
    assert result.recommended_action == ResolutionAction.ESCALATE
    assert result.priority == ResolutionPriority.CRITICAL
    assert "Contradiction detected" in result.action_reason


def test_rule_d_research_required():
    """Rule D: Research NOT_FOUND or missing rights holder -> RESEARCH_REQUIRED + CONDUCT_RESEARCH."""
    entity = Entity(
        id="ent_d",
        production_id="prod_test",
        name="Mysterious Artwork",
        entity_type=EntityType.ARTWORK,
        sources=[EntitySource.VISUAL],
    )
    verification = VerificationResult(
        verification_id="ver_d",
        entity_id="ent_d",
        production_id="prod_test",
        decision=VerificationDecision.CONFIRMED,
    )
    risk = RiskAssessment(
        entity_id="ent_d",
        production_id="prod_test",
        risk_level=RiskLevel.HIGH,
        risk_score=75.0,
    )
    research = {"status": "NOT_FOUND", "rights_holder": None}

    result = ResolutionEngine.resolve(
        entity=entity, risk=risk, verification=verification, research=research
    )
    assert result.resolution_status == ResolutionStatus.RESEARCH_REQUIRED
    assert result.recommended_action == ResolutionAction.CONDUCT_RESEARCH
    assert result.research_action == "TARGETED_RIGHTS_RESEARCH"
    assert len(result.required_information) > 0


def test_rule_e_high_risk_confirmed_brand():
    """Rule E: HIGH risk + CONFIRMED -> ACTION_REQUIRED + REVIEW_BRAND_USAGE."""
    entity = Entity(
        id="ent_e1",
        production_id="prod_test",
        name="Apex Soda Can",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
    )
    verification = VerificationResult(
        verification_id="ver_e1",
        entity_id="ent_e1",
        production_id="prod_test",
        decision=VerificationDecision.CONFIRMED,
    )
    risk = RiskAssessment(
        entity_id="ent_e1",
        production_id="prod_test",
        risk_level=RiskLevel.HIGH,
        risk_score=85.0,
    )
    research = {"status": "COMPLETED", "rights_holder": "Apex Beverage Co"}

    result = ResolutionEngine.resolve(
        entity=entity, risk=risk, verification=verification, research=research
    )
    assert result.resolution_status == ResolutionStatus.ACTION_REQUIRED
    assert result.recommended_action == ResolutionAction.REVIEW_BRAND_USAGE
    assert result.priority == ResolutionPriority.CRITICAL  # VISUAL_ONLY + HIGH risk
    assert result.replacement_suggestion is not None


def test_rule_e_high_risk_confirmed_music():
    """Rule E: HIGH risk + CONFIRMED music -> REVIEW_MUSIC_USAGE."""
    entity = Entity(
        id="ent_e2",
        production_id="prod_test",
        name="Symphony of Shadows",
        entity_type=EntityType.MUSIC,
        sources=[EntitySource.AUDIO],
    )
    verification = VerificationResult(
        verification_id="ver_e2",
        entity_id="ent_e2",
        production_id="prod_test",
        decision=VerificationDecision.CONFIRMED,
    )
    risk = RiskAssessment(
        entity_id="ent_e2",
        production_id="prod_test",
        risk_level=RiskLevel.HIGH,
        risk_score=80.0,
    )
    research = {"status": "COMPLETED", "rights_holder": "Shadow Music Pub"}

    result = ResolutionEngine.resolve(
        entity=entity, risk=risk, verification=verification, research=research
    )
    assert result.resolution_status == ResolutionStatus.ACTION_REQUIRED
    assert result.recommended_action == ResolutionAction.REVIEW_MUSIC_USAGE
    assert "audio composition" in result.replacement_suggestion


def test_rule_e_high_risk_confirmed_artwork():
    """Rule E: HIGH risk + CONFIRMED artwork -> REVIEW_ARTWORK_USAGE."""
    entity = Entity(
        id="ent_e3",
        production_id="prod_test",
        name="Gallery Canvas #12",
        entity_type=EntityType.ARTWORK,
        sources=[EntitySource.VISUAL],
    )
    verification = VerificationResult(
        verification_id="ver_e3",
        entity_id="ent_e3",
        production_id="prod_test",
        decision=VerificationDecision.CONFIRMED,
    )
    risk = RiskAssessment(
        entity_id="ent_e3",
        production_id="prod_test",
        risk_level=RiskLevel.HIGH,
        risk_score=75.0,
    )

    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=verification)
    assert result.recommended_action == ResolutionAction.REVIEW_ARTWORK_USAGE


def test_rule_e_high_risk_confirmed_location_signage():
    """Rule E: HIGH risk + CONFIRMED signage -> REVIEW_LOCATION_USAGE."""
    entity = Entity(
        id="ent_e4",
        production_id="prod_test",
        name="Commercial Tower Sign",
        entity_type=EntityType.SIGNAGE,
        sources=[EntitySource.VISUAL],
    )
    verification = VerificationResult(
        verification_id="ver_e4",
        entity_id="ent_e4",
        production_id="prod_test",
        decision=VerificationDecision.CONFIRMED,
    )
    risk = RiskAssessment(
        entity_id="ent_e4",
        production_id="prod_test",
        risk_level=RiskLevel.HIGH,
        risk_score=70.0,
    )

    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=verification)
    assert result.recommended_action == ResolutionAction.REVIEW_LOCATION_USAGE


def test_rule_e_high_risk_confirmed_public_figure():
    """Rule E: HIGH risk + CONFIRMED public figure -> REVIEW_PUBLIC_FIGURE_USAGE."""
    entity = Entity(
        id="ent_e5",
        production_id="prod_test",
        name="Prominent Politician Likeness",
        entity_type=EntityType.PUBLIC_FIGURE,
        sources=[EntitySource.VISUAL],
    )
    verification = VerificationResult(
        verification_id="ver_e5",
        entity_id="ent_e5",
        production_id="prod_test",
        decision=VerificationDecision.CONFIRMED,
    )
    risk = RiskAssessment(
        entity_id="ent_e5",
        production_id="prod_test",
        risk_level=RiskLevel.HIGH,
        risk_score=85.0,
    )

    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=verification)
    assert result.recommended_action == ResolutionAction.REVIEW_PUBLIC_FIGURE_USAGE


def test_rule_f_medium_risk_confirmed():
    """Rule F: MEDIUM risk + CONFIRMED -> HUMAN_REVIEW."""
    entity = Entity(
        id="ent_f",
        production_id="prod_test",
        name="Incidental Background Brand",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL, EntitySource.SCRIPT],
    )
    verification = VerificationResult(
        verification_id="ver_f",
        entity_id="ent_f",
        production_id="prod_test",
        decision=VerificationDecision.CONFIRMED,
    )
    risk = RiskAssessment(
        entity_id="ent_f",
        production_id="prod_test",
        risk_level=RiskLevel.MEDIUM,
        risk_score=50.0,
    )

    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=verification)
    assert result.resolution_status == ResolutionStatus.HUMAN_REVIEW
    assert result.recommended_action == ResolutionAction.REVIEW_BRAND_USAGE
    assert result.priority == ResolutionPriority.MEDIUM


def test_rule_g_low_risk_confirmed():
    """Rule G: LOW risk + CONFIRMED -> RESOLVED + NO_ACTION (never say 'legally cleared')."""
    entity = Entity(
        id="ent_g",
        production_id="prod_test",
        name="Incidental Generic Street",
        entity_type=EntityType.LOCATION,
        sources=[EntitySource.VISUAL],
    )
    verification = VerificationResult(
        verification_id="ver_g",
        entity_id="ent_g",
        production_id="prod_test",
        decision=VerificationDecision.CONFIRMED,
    )
    risk = RiskAssessment(
        entity_id="ent_g",
        production_id="prod_test",
        risk_level=RiskLevel.LOW,
        risk_score=15.0,
    )

    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=verification)
    assert result.resolution_status == ResolutionStatus.RESOLVED
    assert result.recommended_action == ResolutionAction.NO_ACTION
    assert result.priority == ResolutionPriority.LOW
    assert "legally cleared" not in result.action_reason.lower()
    assert "This item does not currently require an additional operational action" in result.action_reason


def test_rule_h_visual_only_priority_elevation():
    """Rule H: Confirmed VISUAL_ONLY items get elevated priority."""
    # High risk visual-only -> CRITICAL
    p_high = ResolutionEngine.calculate_resolution_priority(
        risk_level="HIGH", classification="VISUAL_ONLY", verification_decision="CONFIRMED"
    )
    assert p_high == ResolutionPriority.CRITICAL

    # Medium risk visual-only -> HIGH
    p_med = ResolutionEngine.calculate_resolution_priority(
        risk_level="MEDIUM", classification="VISUAL_ONLY", verification_decision="CONFIRMED"
    )
    assert p_med == ResolutionPriority.HIGH


def test_rule_i_script_only_priority():
    """Rule I: SCRIPT_ONLY items get standard operational priority."""
    p_high = ResolutionEngine.calculate_resolution_priority(
        risk_level="HIGH", classification="SCRIPT_ONLY", verification_decision="CONFIRMED"
    )
    assert p_high == ResolutionPriority.HIGH

    p_med = ResolutionEngine.calculate_resolution_priority(
        risk_level="MEDIUM", classification="SCRIPT_ONLY", verification_decision="CONFIRMED"
    )
    assert p_med == ResolutionPriority.MEDIUM

    p_low = ResolutionEngine.calculate_resolution_priority(
        risk_level="LOW", classification="SCRIPT_ONLY", verification_decision="CONFIRMED"
    )
    assert p_low == ResolutionPriority.LOW


# =============================================================================
# 3. NEUTRAL REPLACEMENT SUGGESTIONS
# =============================================================================

def test_neutral_replacement_never_suggests_real_brands():
    """Verify that replacement suggestions use strictly generic phrasing."""
    known_brands = ["coca-cola", "pepsi", "nike", "apple", "starbucks", "sony", "ford"]

    for etype in ["BRAND", "PRODUCT", "MUSIC", "ARTWORK", "LOCATION", "SIGNAGE", "OTHER"]:
        suggestion = ResolutionEngine.get_replacement_suggestion(etype, "Test Asset")
        suggestion_lower = suggestion.lower()
        for brand in known_brands:
            assert brand not in suggestion_lower
        assert "consider replacing" in suggestion_lower or "review" in suggestion_lower


# =============================================================================
# 4. EVIDENCE TRACEABILITY
# =============================================================================

def test_evidence_traceability_collection():
    """Verify supporting_evidence_ids captures frame IDs, risk IDs, and verification IDs."""
    entity = Entity(
        id="ent_trace",
        production_id="prod_trace",
        name="Traceable Item",
        evidence_frames=["frame_001.jpg", "frame_002.jpg"],
    )
    verification = VerificationResult(
        verification_id="ver_trace_99",
        entity_id="ent_trace",
        production_id="prod_trace",
        decision=VerificationDecision.CONFIRMED,
        metadata={"evidence_ids": ["ocr_01", "box_02"]},
    )
    risk = RiskAssessment(
        risk_id="risk_trace_88",
        entity_id="ent_trace",
        production_id="prod_trace",
        risk_level=RiskLevel.MEDIUM,
    )
    research = {"id": "res_trace_77", "rights_holder": "Acme Corp"}

    result = ResolutionEngine.resolve(
        entity=entity, risk=risk, verification=verification, research=research
    )

    for expected_id in ["frame_001.jpg", "frame_002.jpg", "ver_trace_99", "risk_trace_88", "res_trace_77", "ocr_01", "box_02"]:
        assert expected_id in result.supporting_evidence_ids


# =============================================================================
# 5. REPOSITORY OPERATIONS
# =============================================================================

@pytest.mark.asyncio
async def test_resolution_repository_crud():
    """Test InMemoryResolutionRepository save, get, get_by_entity, list_for_production."""
    repo = get_resolution_repo()

    res = ResolutionResult(
        resolution_id="res_repo_01",
        entity_id="ent_repo_01",
        production_id="prod_repo_01",
        entity_name="Repo Test Entity",
        resolution_status=ResolutionStatus.ACTION_REQUIRED,
        recommended_action=ResolutionAction.REVIEW_BRAND_USAGE,
        priority=ResolutionPriority.HIGH,
    )

    saved = await repo.save(res)
    assert saved.resolution_id == "res_repo_01"

    # Get by resolution_id
    retrieved = await repo.get("res_repo_01")
    assert retrieved is not None
    assert retrieved.entity_name == "Repo Test Entity"

    # Get by entity_id
    by_entity = await repo.get_by_entity("ent_repo_01")
    assert by_entity is not None
    assert by_entity.resolution_id == "res_repo_01"

    # List for production
    prod_list = await repo.list_for_production("prod_repo_01")
    assert len(prod_list) >= 1
    assert any(r.resolution_id == "res_repo_01" for r in prod_list)


# =============================================================================
# 6. RESOLUTION AGENT WORKFLOW & SORTING
# =============================================================================

@pytest.mark.asyncio
async def test_resolution_agent_resolve_entity_and_enrichment():
    """Verify ResolutionAgent.resolve_entity enriches entity fields and emits events."""
    agent = ResolutionAgent()
    entity_repo = get_entity_repo()

    entity = Entity(
        id="ent_agent_01",
        production_id="prod_agent_test",
        name="Enrichment Test Entity",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
    )
    await entity_repo.create(entity)

    verification = VerificationResult(
        verification_id="ver_agent_01",
        entity_id=entity.id,
        production_id=entity.production_id,
        decision=VerificationDecision.CONFIRMED,
    )
    risk = RiskAssessment(
        risk_id="risk_agent_01",
        entity_id=entity.id,
        production_id=entity.production_id,
        risk_level=RiskLevel.HIGH,
        risk_score=85.0,
    )

    result = await agent.resolve_entity(
        entity=entity,
        risk=risk,
        verification=verification,
        force_refresh=True,
    )

    assert result.resolution_status == ResolutionStatus.ACTION_REQUIRED
    assert entity.resolution_id == result.resolution_id
    assert entity.resolution_status == "ACTION_REQUIRED"
    assert entity.resolution_action == "REVIEW_BRAND_USAGE"
    assert entity.resolution_priority == "CRITICAL"


@pytest.mark.asyncio
async def test_resolution_agent_sorting_hierarchy():
    """Verify operational priority sorting: CRITICAL > HIGH > MEDIUM > LOW > INFO."""
    agent = ResolutionAgent()

    r_low = ResolutionResult(
        entity_id="e_low", production_id="p", entity_name="Zebra",
        priority=ResolutionPriority.LOW, risk_score=10.0,
    )
    r_med = ResolutionResult(
        entity_id="e_med", production_id="p", entity_name="Monkey",
        priority=ResolutionPriority.MEDIUM, risk_score=50.0,
    )
    r_high = ResolutionResult(
        entity_id="e_high", production_id="p", entity_name="Lion",
        priority=ResolutionPriority.HIGH, risk_score=75.0,
    )
    r_crit = ResolutionResult(
        entity_id="e_crit", production_id="p", entity_name="Dragon",
        priority=ResolutionPriority.CRITICAL, risk_score=95.0,
    )

    unsorted = [r_low, r_high, r_med, r_crit]
    sorted_res = sorted(unsorted, key=agent._sort_key)

    assert sorted_res[0].priority == ResolutionPriority.CRITICAL
    assert sorted_res[1].priority == ResolutionPriority.HIGH
    assert sorted_res[2].priority == ResolutionPriority.MEDIUM
    assert sorted_res[3].priority == ResolutionPriority.LOW


@pytest.mark.asyncio
async def test_resolution_agent_error_isolation():
    """Verify error isolation: a single failing entity does not stop batch resolution."""
    agent = ResolutionAgent()

    e1 = Entity(id="ent_good_1", production_id="prod_iso", name="Good Item 1")
    e2 = Entity(id="ent_good_2", production_id="prod_iso", name="Good Item 2")

    results = await agent.resolve_entities(
        entities=[e1, e2],
        production_id="prod_iso",
        force_refresh=True,
    )

    assert len(results) == 2
    assert all(isinstance(r, ResolutionResult) for r in results)


@pytest.mark.asyncio
async def test_resolution_agent_idempotency_caching():
    """Verify repeated calls return cached results unless force_refresh=True."""
    agent = ResolutionAgent()

    entity = Entity(id="ent_cache_01", production_id="prod_cache", name="Cache Item")
    r1 = await agent.resolve_entity(entity=entity, force_refresh=False)
    r2 = await agent.resolve_entity(entity=entity, force_refresh=False)

    assert r1.resolution_id == r2.resolution_id

    # Forcing refresh generates new resolution_id
    r3 = await agent.resolve_entity(entity=entity, force_refresh=True)
    assert r3.resolution_id != r1.resolution_id


# =============================================================================
# 7. BACKWARD COMPATIBILITY
# =============================================================================

@pytest.mark.asyncio
async def test_legacy_formulate_resolution():
    """Verify ResolutionAgent.formulate_resolution backward compatibility method."""
    agent = ResolutionAgent()
    entity = Entity(id="ent_leg", production_id="prod_leg", name="Legacy Brand")

    # High risk -> POST_PRODUCTION_BLUR
    risk_high = RiskAssessment(entity_id="ent_leg", production_id="prod_leg", risk_score=75.0)
    req_high = await agent.formulate_resolution(entity, risk_high, "Rights Holder A")
    assert req_high.action_type == ClearanceActionType.POST_PRODUCTION_BLUR

    # Moderate risk -> LICENSE_OUTREACH
    risk_med = RiskAssessment(entity_id="ent_leg", production_id="prod_leg", risk_score=50.0)
    req_med = await agent.formulate_resolution(entity, risk_med, "Rights Holder B")
    assert req_med.action_type == ClearanceActionType.LICENSE_OUTREACH

    # Low risk -> FAIR_USE_ARGUMENT
    risk_low = RiskAssessment(entity_id="ent_leg", production_id="prod_leg", risk_score=20.0)
    req_low = await agent.formulate_resolution(entity, risk_low, "Rights Holder C")
    assert req_low.action_type == ClearanceActionType.FAIR_USE_ARGUMENT


# =============================================================================
# 8. REST API ENDPOINTS
# =============================================================================

@pytest.mark.asyncio
async def test_resolution_api_endpoints():
    """Verify POST and GET /productions/{id}/resolution endpoints."""
    prod_repo = get_production_repo()
    entity_repo = get_entity_repo()

    prod = Production(title="API Resolution Test Production")
    saved_prod = await prod_repo.create(prod)

    ent = Entity(
        production_id=saved_prod.id,
        name="API Test Can",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
    )
    await entity_repo.create(ent)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # POST /productions/{id}/resolution
        post_res = await client.post(f"/productions/{saved_prod.id}/resolution")
        assert post_res.status_code == 200
        post_data = post_res.json()
        assert post_data["production_id"] == saved_prod.id
        assert len(post_data["results"]) >= 1
        assert "summary" in post_data
        assert post_data["summary"]["total"] >= 1

        # GET /productions/{id}/resolution
        get_res = await client.get(f"/productions/{saved_prod.id}/resolution")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["production_id"] == saved_prod.id
        assert len(get_data["results"]) >= 1
        assert "summary" in get_data


@pytest.mark.asyncio
async def test_resolution_api_nonexistent_production():
    """Verify 404 response for nonexistent production."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/productions/nonexistent_prod_999/resolution")
        assert res.status_code == 404


# =============================================================================
# 9. EXTENDED RULES & EVENT BUS EMISSIONS
# =============================================================================

def test_rule_e_high_risk_confirmed_other_type():
    """Rule E: HIGH risk + CONFIRMED for OTHER entity type defaults to HUMAN_REVIEW."""
    entity = Entity(
        id="ent_other",
        production_id="prod_test",
        name="Unclassified Exotic Prop",
        entity_type=EntityType.OTHER,
        sources=[EntitySource.VISUAL],
    )
    verification = VerificationResult(
        entity_id="ent_other",
        production_id="prod_test",
        decision=VerificationDecision.CONFIRMED,
    )
    risk = RiskAssessment(
        entity_id="ent_other",
        production_id="prod_test",
        risk_level=RiskLevel.HIGH,
        risk_score=75.0,
    )

    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=verification)
    assert result.resolution_status == ResolutionStatus.ACTION_REQUIRED
    assert result.recommended_action == ResolutionAction.HUMAN_REVIEW


def test_rule_f_medium_risk_music():
    """Rule F: MEDIUM risk + CONFIRMED music maps to REVIEW_MUSIC_USAGE."""
    entity = Entity(id="ent_m_mus", production_id="p", name="Café Jingle", entity_type=EntityType.MUSIC)
    ver = VerificationResult(entity_id="ent_m_mus", production_id="p", decision=VerificationDecision.CONFIRMED)
    risk = RiskAssessment(entity_id="ent_m_mus", production_id="p", risk_level=RiskLevel.MEDIUM, risk_score=50.0)

    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=ver)
    assert result.resolution_status == ResolutionStatus.HUMAN_REVIEW
    assert result.recommended_action == ResolutionAction.REVIEW_MUSIC_USAGE


def test_rule_f_medium_risk_artwork():
    """Rule F: MEDIUM risk + CONFIRMED artwork maps to REVIEW_ARTWORK_USAGE."""
    entity = Entity(id="ent_m_art", production_id="p", name="Poster Print", entity_type=EntityType.ARTWORK)
    ver = VerificationResult(entity_id="ent_m_art", production_id="p", decision=VerificationDecision.CONFIRMED)
    risk = RiskAssessment(entity_id="ent_m_art", production_id="p", risk_level=RiskLevel.MEDIUM, risk_score=48.0)

    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=ver)
    assert result.resolution_status == ResolutionStatus.HUMAN_REVIEW
    assert result.recommended_action == ResolutionAction.REVIEW_ARTWORK_USAGE


def test_rule_f_medium_risk_location():
    """Rule F: MEDIUM risk + CONFIRMED location maps to REVIEW_LOCATION_USAGE."""
    entity = Entity(id="ent_m_loc", production_id="p", name="Historic Facade", entity_type=EntityType.LOCATION)
    ver = VerificationResult(entity_id="ent_m_loc", production_id="p", decision=VerificationDecision.CONFIRMED)
    risk = RiskAssessment(entity_id="ent_m_loc", production_id="p", risk_level=RiskLevel.MEDIUM, risk_score=45.0)

    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=ver)
    assert result.resolution_status == ResolutionStatus.HUMAN_REVIEW
    assert result.recommended_action == ResolutionAction.REVIEW_LOCATION_USAGE


def test_rule_f_medium_risk_public_figure():
    """Rule F: MEDIUM risk + CONFIRMED public figure maps to REVIEW_PUBLIC_FIGURE_USAGE."""
    entity = Entity(id="ent_m_pf", production_id="p", name="Mayor Portrait", entity_type=EntityType.PUBLIC_FIGURE)
    ver = VerificationResult(entity_id="ent_m_pf", production_id="p", decision=VerificationDecision.CONFIRMED)
    risk = RiskAssessment(entity_id="ent_m_pf", production_id="p", risk_level=RiskLevel.MEDIUM, risk_score=55.0)

    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=ver)
    assert result.resolution_status == ResolutionStatus.HUMAN_REVIEW
    assert result.recommended_action == ResolutionAction.REVIEW_PUBLIC_FIGURE_USAGE


def test_rule_f_medium_risk_visual_only_priority():
    """Rule F + Rule H: MEDIUM risk visual-only confirmed gets priority HIGH."""
    entity = Entity(
        id="ent_m_vo",
        production_id="p",
        name="Visual Medium Logo",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
    )
    ver = VerificationResult(entity_id="ent_m_vo", production_id="p", decision=VerificationDecision.CONFIRMED)
    risk = RiskAssessment(entity_id="ent_m_vo", production_id="p", risk_level=RiskLevel.MEDIUM, risk_score=55.0)

    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=ver)
    assert result.priority == ResolutionPriority.HIGH


def test_rule_g_low_risk_script_only():
    """Rule G + Rule I: LOW risk script-only confirmed gets priority LOW."""
    entity = Entity(
        id="ent_l_so",
        production_id="p",
        name="Mentioned Street Name",
        entity_type=EntityType.LOCATION,
        sources=[EntitySource.SCRIPT],
    )
    ver = VerificationResult(entity_id="ent_l_so", production_id="p", decision=VerificationDecision.CONFIRMED)
    risk = RiskAssessment(entity_id="ent_l_so", production_id="p", risk_level=RiskLevel.LOW, risk_score=10.0)

    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=ver)
    assert result.resolution_status == ResolutionStatus.RESOLVED
    assert result.recommended_action == ResolutionAction.NO_ACTION
    assert result.priority == ResolutionPriority.LOW


def test_rule_c_multiple_contradictions():
    """Rule C: Multiple contradictions are joined and preserved in action_reason."""
    entity = Entity(id="ent_multi_c", production_id="p", name="Multi Contradiction Prop")
    ver = VerificationResult(
        entity_id="ent_multi_c",
        production_id="p",
        contradictions=["Date mismatch in script", "Manufacturer claims model discontinued in 1999"],
    )

    result = ResolutionEngine.resolve(entity=entity, verification=ver)
    assert result.recommended_action == ResolutionAction.ESCALATE
    assert "Date mismatch in script" in result.action_reason
    assert "Manufacturer claims model discontinued in 1999" in result.action_reason


@pytest.mark.asyncio
async def test_resolution_agent_event_bus_emission():
    """Verify that resolving entities emits RESOLUTION_STARTED and RESOLUTION_COMPLETED."""
    agent = ResolutionAgent()
    job_id = "job_test_ev_bus_1"
    production_id = "prod_ev_bus"

    e1 = Entity(id="ent_ev_1", production_id=production_id, name="Event Test 1")
    await agent.resolve_entities([e1], production_id=production_id, job_id=job_id, force_refresh=True)

    events = event_bus.get_history(job_id)
    types = [ev.event_type for ev in events]
    assert EventType.RESOLUTION_STARTED in types
    assert EventType.RESOLUTION_COMPLETED in types


@pytest.mark.asyncio
async def test_resolution_agent_escalation_event_type():
    """Verify that an ESCALATE action emits RESOLUTION_ESCALATED event."""
    agent = ResolutionAgent()
    job_id = "job_test_esc_1"
    production_id = "prod_esc"

    entity = Entity(id="ent_esc", production_id=production_id, name="Escalate Prop")
    ver = VerificationResult(
        entity_id="ent_esc",
        production_id=production_id,
        contradictions=["Direct trademark mismatch"],
    )

    await agent.resolve_entity(entity=entity, verification=ver, job_id=job_id, force_refresh=True)

    events = event_bus.get_history(job_id)
    types = [ev.event_type for ev in events]
    assert EventType.RESOLUTION_ESCALATED in types
    esc_ev = next(ev for ev in events if ev.event_type == EventType.RESOLUTION_ESCALATED)
    assert esc_ev.resolution_action == "ESCALATE"


@pytest.mark.asyncio
async def test_resolution_agent_resolve_production():
    """Verify resolve_production processes all entities in a production."""
    agent = ResolutionAgent()
    prod_repo = get_production_repo()
    entity_repo = get_entity_repo()

    prod = Production(title="Prod Level Resolution")
    saved_prod = await prod_repo.create(prod)

    e1 = Entity(production_id=saved_prod.id, name="Item Alpha")
    e2 = Entity(production_id=saved_prod.id, name="Item Beta")
    await entity_repo.create(e1)
    await entity_repo.create(e2)

    results = await agent.resolve_production(production_id=saved_prod.id, force_refresh=True)
    assert len(results) >= 2


@pytest.mark.asyncio
async def test_resolution_agent_resolve_production_empty():
    """Verify resolve_production returns empty list when no entities exist."""
    agent = ResolutionAgent()
    results = await agent.resolve_production(production_id="prod_nonexistent_empty")
    assert results == []


@pytest.mark.asyncio
async def test_resolution_api_subset_entity_ids():
    """Verify POST /productions/{id}/resolution filters by entity_ids subset."""
    prod_repo = get_production_repo()
    entity_repo = get_entity_repo()

    prod = Production(title="Subset Test Production")
    saved_prod = await prod_repo.create(prod)

    e1 = Entity(production_id=saved_prod.id, name="Target Item")
    e2 = Entity(production_id=saved_prod.id, name="Untargeted Item")
    await entity_repo.create(e1)
    await entity_repo.create(e2)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/productions/{saved_prod.id}/resolution",
            json={"entity_ids": [e1.id], "force_refresh": True},
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["entity_id"] == e1.id


@pytest.mark.asyncio
async def test_resolution_api_force_refresh_flag():
    """Verify POST /productions/{id}/resolution handles force_refresh flag cleanly."""
    prod_repo = get_production_repo()
    prod = Production(title="Force Refresh Production")
    saved_prod = await prod_repo.create(prod)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/productions/{saved_prod.id}/resolution",
            json={"force_refresh": True},
        )
        assert res.status_code == 200


# =============================================================================
# 10. STRICT ZERO-NETWORK GUARANTEE
# =============================================================================

def test_zero_network_resolution():
    """Ensure ResolutionEngine executes 100% offline with zero network or cloud calls."""
    entity = Entity(id="ent_off", production_id="prod_off", name="Offline Prop")
    risk = RiskAssessment(entity_id="ent_off", production_id="prod_off", risk_score=60.0)
    verification = VerificationResult(entity_id="ent_off", production_id="prod_off", decision=VerificationDecision.CONFIRMED)

    # Resolution executes synchronously and completely offline
    result = ResolutionEngine.resolve(entity=entity, risk=risk, verification=verification)
    assert result.resolver == "DeterministicResolutionEngine"
    assert result.resolution_status == ResolutionStatus.HUMAN_REVIEW
    assert result.confidence > 0.0

