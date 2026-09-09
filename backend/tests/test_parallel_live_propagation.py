"""
Unit and integration tests for Parallel Research Intelligence, force-refresh cache bypass,
8-stage lineage propagation, and Phase 8 JSON/HTML/PDF report generation.
"""
from datetime import datetime, timezone
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.models.analysis import AnalysisJob
from app.models.entity import Entity, EntityClassification, EntityType, RiskLevel
from app.models.evidence import Evidence, EvidenceType
from app.models.production import Production
from app.models.report import ReportFormat
from app.models.research import ResearchResult, ResearchStatus
from app.models.resolution import ResolutionAction, ResolutionPriority, ResolutionResult, ResolutionStatus
from app.models.risk import RiskAssessment
from app.models.verification import VerificationDecision, VerificationResult
from app.services.report_engine import report_engine
from app.services.report_renderers import render_html_report, render_pdf_report
from app.services.research_provider.parallel_provider import ParallelResearchProvider, _load_cache, _save_cache
from app.services.research_provider.local_provider import LocalResearchProvider


@pytest.mark.asyncio
async def test_parallel_force_refresh_bypasses_cache():
    """Test that force_refresh=True completely bypasses disk cache and dispatches live API call."""
    provider = ParallelResearchProvider(api_key="test_dummy_key")

    mock_live_response = {
        "search_id": "search_12345",
        "results": [
            {
                "title": "Cadbury - Trademark of Mondelez International",
                "url": "https://trademarks.justia.com/cadbury",
                "excerpts": ["Cadbury is a registered trademark owned by Mondelez International."],
            },
            {
                "title": "Mondelez Corporate Holdings: Cadbury Dairy Milk",
                "url": "https://www.mondelezinternational.com/brand/cadbury",
                "excerpts": ["Cadbury Dairy Milk confectionery brand produced by Mondelez."],
            },
        ],
    }

    # 1. Populate disk cache with stale fixture
    cache = _load_cache()
    cache["cadbury"] = {
        "candidate_rights_holder": "Stale Cached Holder",
        "evidence": [],
    }
    _save_cache(cache)

    # 2. Call with force_refresh=False -> Should HIT disk cache
    res_cached = await provider.research_entity(
        entity_name="Cadbury",
        entity_type="brand",
        force_refresh=False,
    )
    assert res_cached.status == ResearchStatus.SUCCESS
    assert res_cached.candidate_rights_holder == "Stale Cached Holder"
    assert res_cached.metadata.get("cache_status") == "CACHE HIT"

    # 3. Call with force_refresh=True -> Should bypass disk cache and make live HTTP call
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_live_response
        mock_post.return_value = mock_resp

        res_live = await provider.research_entity(
            entity_name="Cadbury",
            entity_type="brand",
            force_refresh=True,
        )

        assert mock_post.called
        assert res_live.status == ResearchStatus.SUCCESS
        assert "Mondelez" in res_live.candidate_rights_holder
        assert res_live.metadata.get("cache_status") == "LIVE API"
        assert res_live.metadata.get("is_live") is True
        assert len(res_live.evidence) == 2
        assert res_live.evidence[0].source_url == "https://trademarks.justia.com/cadbury"
        assert "Mondelez" in res_live.evidence[0].excerpt


@pytest.mark.asyncio
async def test_parallel_evidence_propagation_to_report():
    """Test that Parallel search evidence, URLs, and rights holder propagate to JSON, HTML, and PDF."""
    now = datetime.now(timezone.utc)
    production = Production(
        id="prod_test_parallel",
        title="Parallel Intelligence Showcase",
    )
    job = AnalysisJob(job_id="job_parallel_1", production_id="prod_test_parallel")

    entity_cadbury = Entity(
        id="ent_cadbury",
        production_id="prod_test_parallel",
        name="Cadbury Dairy Milk",
        entity_type=EntityType.BRAND,
        classification=EntityClassification.BOTH,
        scene=1,
        timestamp=2.5,
    )
    entity_sony = Entity(
        id="ent_sony",
        production_id="prod_test_parallel",
        name="Sony Bravia TV",
        entity_type=EntityType.BRAND,
        classification=EntityClassification.VISUAL_ONLY,
        scene=2,
        timestamp=5.0,
    )

    cadbury_evidence = [
        Evidence(
            production_id="prod_test_parallel",
            entity_id="ent_cadbury",
            evidence_type=EvidenceType.RESEARCH_EVIDENCE,
            entity_name="Cadbury Dairy Milk",
            claim="Parallel search identified: Cadbury - Trademark of Mondelez International",
            source_title="Cadbury - Trademark of Mondelez International",
            source_url="https://trademarks.justia.com/cadbury",
            excerpt="Cadbury is a registered trademark owned by Mondelez International.",
            source_type="parallel_api",
            candidate_rights_holder="Mondelez International",
            confidence=0.96,
            retrieved_at=now,
            provider="parallel",
        )
    ]
    sony_evidence = [
        Evidence(
            production_id="prod_test_parallel",
            entity_id="ent_sony",
            evidence_type=EvidenceType.RESEARCH_EVIDENCE,
            entity_name="Sony Bravia TV",
            claim="Parallel search identified: Sony Corporation Trademark Registry",
            source_title="Sony Corporation Trademark Registry",
            source_url="https://trademarks.justia.com/sony-corporation",
            excerpt="Sony and Bravia are registered marks of Sony Group Corporation.",
            source_type="parallel_api",
            candidate_rights_holder="Sony Group Corporation",
            confidence=0.98,
            retrieved_at=now,
            provider="parallel",
        )
    ]

    cadbury_research = ResearchResult(
        production_id="prod_test_parallel",
        job_id="job_parallel_1",
        entity_id="ent_cadbury",
        entity_name="Cadbury Dairy Milk",
        entity_type="brand",
        status=ResearchStatus.SUCCESS,
        candidate_rights_holder="Mondelez International",
        identity_confidence=0.96,
        research_confidence=0.94,
        evidence=cadbury_evidence,
        query='"Cadbury Dairy Milk" corporate rights holder trademark status',
        provider="parallel",
        retrieved_at=now,
        notes="Verified via Parallel Search API",
        metadata={"source_type": "parallel_api", "is_live": True, "cache_status": "LIVE API", "found": True},
    )

    sony_research = ResearchResult(
        production_id="prod_test_parallel",
        job_id="job_parallel_1",
        entity_id="ent_sony",
        entity_name="Sony Bravia TV",
        entity_type="brand",
        status=ResearchStatus.SUCCESS,
        candidate_rights_holder="Sony Group Corporation",
        identity_confidence=0.98,
        research_confidence=0.96,
        evidence=sony_evidence,
        query='"Sony Bravia TV" corporate rights holder trademark status',
        provider="parallel",
        retrieved_at=now,
        notes="Verified via Parallel Search API",
        metadata={"source_type": "parallel_api", "is_live": True, "cache_status": "LIVE API", "found": True},
    )

    from app.models.risk import RiskCategory, RiskFactor

    risk_cadbury = RiskAssessment(
        entity_id="ent_cadbury",
        production_id="prod_test_parallel",
        risk_level=RiskLevel.MEDIUM,
        risk_score=55.0,
        factors=[RiskFactor(category=RiskCategory.TRADEMARK_INFRINGEMENT, description="Commercial Product Placement", severity="MEDIUM")],
        explanation="Prominent branded chocolate bar in dialogue scene.",
    )
    risk_sony = RiskAssessment(
        entity_id="ent_sony",
        production_id="prod_test_parallel",
        risk_level=RiskLevel.HIGH,
        risk_score=85.0,
        factors=[RiskFactor(category=RiskCategory.TRADEMARK_INFRINGEMENT, description="Visual-Only Surprise Liability", severity="HIGH")],
        explanation="Unscripted television logo appearing in background footage.",
    )

    verif_cadbury = VerificationResult(
        entity_id="ent_cadbury",
        production_id="prod_test_parallel",
        decision=VerificationDecision.CONFIRMED,
        confidence=0.95,
        reasoning="Corroborated by both script mention and live trademark registry.",
    )
    verif_sony = VerificationResult(
        entity_id="ent_sony",
        production_id="prod_test_parallel",
        decision=VerificationDecision.REVIEW,
        confidence=0.90,
        reasoning="Visual-only detection confirmed against Sony trademark registry.",
    )

    resol_cadbury = ResolutionResult(
        entity_id="ent_cadbury",
        production_id="prod_test_parallel",
        recommended_action=ResolutionAction.NO_ACTION,
        resolution_status=ResolutionStatus.RESOLVED,
        priority=ResolutionPriority.MEDIUM,
        resolver="Clearance Counsel",
        action_reason="Incidental consumption under narrative context.",
    )
    resol_sony = ResolutionResult(
        entity_id="ent_sony",
        production_id="prod_test_parallel",
        recommended_action=ResolutionAction.CONSIDER_REPLACEMENT,
        resolution_status=ResolutionStatus.ACTION_REQUIRED,
        priority=ResolutionPriority.HIGH,
        resolver="VFX Lead",
        action_reason="Unscripted logo requires digital removal or licensing agreement.",
    )

    # 1. Generate Report Result via Engine
    report_result = report_engine.generate_report(
        production=production,
        job=job,
        entities=[entity_cadbury, entity_sony],
        evidence_list=cadbury_evidence + sony_evidence,
        research_results=[cadbury_research, sony_research],
        risk_assessments=[risk_cadbury, risk_sony],
        verification_results=[verif_cadbury, verif_sony],
        resolution_results=[resol_cadbury, resol_sony],
    )

    # 2. Validate JSON structure & Parallel Research Intelligence
    json_dict = report_result.model_dump(mode="json")
    assert "parallel_research_intelligence" in json_dict
    assert len(json_dict["parallel_research_intelligence"]) == 2

    cadbury_intel = next(i for i in json_dict["parallel_research_intelligence"] if i["entity_name"] == "Cadbury Dairy Milk")
    assert cadbury_intel["candidate_rights_holder"] == "Mondelez International"
    assert cadbury_intel["research_provider"] == "Parallel Search API"
    assert cadbury_intel["cache_status"] == "LIVE API"
    assert len(cadbury_intel["results"]) == 1
    assert cadbury_intel["results"][0]["url"] == "https://trademarks.justia.com/cadbury"
    assert "Mondelez" in cadbury_intel["results"][0]["excerpt"]

    # 3. Validate Lineage preservation in findings
    finding_cadbury = next(f for f in report_result.all_findings if f.entity_name == "Cadbury Dairy Milk")
    stage_4 = finding_cadbury.evidence_chain["stage_4_research"]
    assert stage_4["provider"] == "Parallel Search API"
    assert stage_4["candidate_rights_holder"] == "Mondelez International"
    assert len(stage_4["evidence"]) == 1

    # 4. Validate Coverage calculations
    assert report_result.research_coverage == 1.0  # 2/2 usable research records
    assert report_result.verification_coverage == 1.0
    assert report_result.resolution_coverage == 1.0
    assert "2/2 (100.0%) factual research evidence coverage" in report_result.executive_summary

    # 5. Validate HTML Rendering contains Parallel section, URLs, and badges
    html_output = render_html_report(report_result)
    assert "PARALLEL RESEARCH INTELLIGENCE & RIGHTS-HOLDER EVIDENCE" in html_output
    assert "https://trademarks.justia.com/cadbury" in html_output
    assert "https://trademarks.justia.com/sony-corporation" in html_output
    assert "Mondelez International" in html_output
    assert "Sony Group Corporation" in html_output
    assert "LIVE API" in html_output
    assert "8-Stage Lineage" in html_output

    # 6. Validate PDF Rendering generates valid PDF bytes with Parallel section
    pdf_bytes = render_pdf_report(report_result)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


@pytest.mark.asyncio
async def test_offline_mode_zero_external_requests():
    """Test that offline mode uses deterministic LocalResearchProvider without network requests."""
    local_prov = LocalResearchProvider()
    result = await local_prov.research_entity(
        entity_name="Coca-Cola",
        entity_type="brand",
        force_refresh=False,
    )
    assert result.status == ResearchStatus.SUCCESS
    assert result.candidate_rights_holder == "The Coca-Cola Company"
    assert result.provider == "local"
    assert result.metadata.get("source_type") == "local_fixture"
