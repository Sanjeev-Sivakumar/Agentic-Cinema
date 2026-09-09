"""
Automated unit test suite for Phase 8 — Reporting Intelligence.
Tests domain models, deterministic report generation engine, 7-stage traceability,
prioritization hierarchy, dynamic coverage & distribution aggregation,
HTML & PDF renderers (with NumberedCanvas page stamping), ReportStorageService,
InMemoryReportRepository, ReportAgent execution, idempotency caching,
version auto-incrementing, fault isolation, SSE event bus emissions,
and FastAPI REST endpoints.

STRICT ZERO-NETWORK CONSTRAINT: 0 external API calls (0 Gemini, 0 Groq, 0 Parallel, 0 cloud).
"""

import asyncio
from datetime import datetime, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.report_agent import ReportAgent, report_agent
from app.main import app
from app.models.analysis import AnalysisJob
from app.models.entity import (
    Entity,
    EntityClassification,
    EntitySource,
    EntityType,
    RiskLevel,
    VerificationStatus,
)
from app.models.events import EventType, PipelineStage
from app.models.evidence import Evidence, EvidenceType
from app.models.production import Production
from app.models.report import (
    DEFAULT_LEGAL_DISCLAIMER,
    Report,
    ReportFinding,
    ReportFormat,
    ReportResult,
    ReportSeverity,
    ReportStatus,
)
from app.models.research import ResearchResult
from app.models.resolution import (
    ResolutionAction,
    ResolutionPriority,
    ResolutionResult,
    ResolutionStatus,
)
from app.models.risk import RiskAssessment, RiskCategory, RiskFactor
from app.models.verification import VerificationDecision, VerificationResult
from app.repositories import (
    get_entity_repo,
    get_evidence_repo,
    get_production_repo,
    get_report_repo,
    get_research_repo,
    get_resolution_repo,
    get_risk_repo,
    get_verification_repo,
)
from app.repositories.local.in_memory import InMemoryReportRepository
from app.services.events import event_bus
from app.services.report_engine import ReportEngine, report_engine
from app.services.report_renderers import render_html_report, render_pdf_report
from app.services.report_storage import ReportStorageService, report_storage_service


# =============================================================================
# 1. DOMAIN MODELS & ENUMS
# =============================================================================

def test_report_status_enum():
    """Verify all Phase 8 report status enum values."""
    assert ReportStatus.GENERATING.value == "GENERATING"
    assert ReportStatus.COMPLETED.value == "COMPLETED"
    assert ReportStatus.PARTIAL.value == "PARTIAL"
    assert ReportStatus.FAILED.value == "FAILED"


def test_report_format_enum():
    """Verify all Phase 8 supported report formats."""
    assert ReportFormat.JSON.value == "JSON"
    assert ReportFormat.HTML.value == "HTML"
    assert ReportFormat.PDF.value == "PDF"


def test_report_severity_enum():
    """Verify all report severity enum values."""
    assert ReportSeverity.CRITICAL.value == "CRITICAL"
    assert ReportSeverity.HIGH.value == "HIGH"
    assert ReportSeverity.MEDIUM.value == "MEDIUM"
    assert ReportSeverity.LOW.value == "LOW"
    assert ReportSeverity.INFO.value == "INFO"


def test_report_finding_model():
    """Verify ReportFinding initialization, evidence snippets, and chain."""
    finding = ReportFinding(
        entity_id="ent_001",
        entity_name="Acme Quantum Drive",
        entity_type="PROP",
        classification="VISUAL_ONLY",
        risk_level="HIGH",
        risk_score=0.88,
        risk_factors=["UNSCRIPTED_TRADEMARK", "PROMINENT_CENTRAL_FRAMING"],
        scene_number=4,
        timestamp_start=14.2,
        rights_holder="Acme Industries LLC",
        verification_decision="VERIFIED",
        resolution_action="LICENSE_REQUIRED",
        resolution_priority="CRITICAL",
        resolution_owner="Legal Dept",
        evidence_count=2,
        evidence_snippets=[{"type": "OCR", "text": "ACME"}],
    )
    assert finding.entity_id == "ent_001"
    assert finding.entity_name == "Acme Quantum Drive"
    assert finding.classification == "VISUAL_ONLY"
    assert finding.risk_score == 0.88
    assert finding.evidence_count == 2
    assert len(finding.evidence_snippets) == 1


def test_report_result_properties_and_backward_compatibility():
    """Verify ReportResult properties computed dynamically for backward compatibility."""
    result = ReportResult(
        production_id="prod_test_01",
        job_id="job_test_01",
        production_title="Cyberpunk 2099",
        version="1.0",
        total_entities=10,
        classification_counts={"VISUAL_ONLY": 3, "SCRIPT_ONLY": 4, "BOTH": 3, "AUDIO_ONLY": 0},
        risk_distribution={"HIGH": 2, "MEDIUM": 5, "LOW": 3},
        format_paths={"PDF": "data/storage/reports/prod_test_01/rep_01.pdf"},
    )
    assert result.id == result.report_id
    assert "Cyberpunk 2099" in result.title
    assert result.visual_only_count == 3
    assert result.script_only_count == 4
    assert result.both_count == 3
    assert result.audio_only_count == 0
    assert result.high_risk_count == 2
    assert result.medium_risk_count == 5
    assert result.low_risk_count == 3
    assert result.pdf_path == "data/storage/reports/prod_test_01/rep_01.pdf"
    assert "LEGAL DISCLAIMER" in result.disclaimer


def test_legacy_report_model_compatibility():
    """Verify legacy Report model instantiates and stores report_result."""
    legacy = Report(
        production_id="p1",
        job_id="j1",
        total_entities=5,
        visual_only_count=2,
        high_risk_count=1,
    )
    assert legacy.total_entities == 5
    assert legacy.visual_only_count == 2
    assert legacy.report_result is None


# =============================================================================
# 2. DETERMINISTIC REPORT GENERATION ENGINE
# =============================================================================

def test_engine_zero_entities():
    """Verify report engine handles zero entities without division by zero."""
    engine = ReportEngine()
    prod = Production(id="p_zero", title="Empty Production")
    job = AnalysisJob(production_id="p_zero", job_id="j_zero")

    res = engine.generate_report(
        production=prod,
        job=job,
        entities=[],
        evidence_list=[],
        research_results=[],
        risk_assessments=[],
        verification_results=[],
        resolution_results=[],
    )

    assert res.total_entities == 0
    assert res.researched_count == 0
    assert res.verified_count == 0
    assert res.resolved_count == 0
    assert res.research_coverage == 0.0
    assert res.verification_coverage == 0.0
    assert res.resolution_coverage == 0.0
    assert len(res.all_findings) == 0
    assert len(res.priority_findings) == 0
    assert len(res.visual_only_findings) == 0
    assert res.status == ReportStatus.COMPLETED


def test_engine_coverage_calculations():
    """Verify coverage percentages calculate correctly."""
    engine = ReportEngine()
    prod = Production(id="p_cov", title="Coverage Test")
    job = AnalysisJob(production_id="p_cov", job_id="j_cov")

    e1 = Entity(id="e1", production_id="p_cov", name="Apple iPhone", sources=[EntitySource.VISUAL])
    e2 = Entity(id="e2", production_id="p_cov", name="Nike Cap", sources=[EntitySource.VISUAL, EntitySource.SCRIPT])
    e3 = Entity(id="e3", production_id="p_cov", name="Ferrari Car", sources=[EntitySource.SCRIPT])
    e4 = Entity(id="e4", production_id="p_cov", name="Rolex Watch", sources=[EntitySource.VISUAL])

    # 2 researched, 3 verified, 4 resolved
    r1 = ResearchResult(id="r1", entity_id="e1", production_id="p_cov", entity_name="Apple iPhone", rights_holder="Apple Inc")
    r2 = ResearchResult(id="r2", entity_id="e2", production_id="p_cov", entity_name="Nike Cap", rights_holder="Nike Inc")

    v1 = VerificationResult(id="v1", entity_id="e1", production_id="p_cov", decision=VerificationDecision.CONFIRMED, confidence=0.95)
    v2 = VerificationResult(id="v2", entity_id="e2", production_id="p_cov", decision=VerificationDecision.REJECTED, confidence=0.88)
    v3 = VerificationResult(id="v3", entity_id="e3", production_id="p_cov", decision=VerificationDecision.CONFIRMED, confidence=0.92)

    res1 = ResolutionResult(id="res1", resolution_id="res1", entity_id="e1", production_id="p_cov", entity_name="Apple iPhone", entity_type="PROP", risk_level="HIGH", risk_score=0.85, resolution_status=ResolutionStatus.ACTION_REQUIRED, recommended_action=ResolutionAction.REQUEST_LICENSE_INFORMATION, priority=ResolutionPriority.HIGH, action_reason="Logo", supporting_evidence_ids=[], missing_evidence=[], required_information=[], confidence=0.9, resolver="Rule")
    res2 = ResolutionResult(id="res2", resolution_id="res2", entity_id="e2", production_id="p_cov", entity_name="Nike Cap", entity_type="WARDROBE", risk_level="MEDIUM", risk_score=0.55, resolution_status=ResolutionStatus.ACTION_REQUIRED, recommended_action=ResolutionAction.CONSIDER_REPLACEMENT, priority=ResolutionPriority.CRITICAL, action_reason="Contradiction", supporting_evidence_ids=[], missing_evidence=[], required_information=[], confidence=0.85, resolver="Rule")
    res3 = ResolutionResult(id="res3", resolution_id="res3", entity_id="e3", production_id="p_cov", entity_name="Ferrari Car", entity_type="VEHICLE", risk_level="LOW", risk_score=0.20, resolution_status=ResolutionStatus.RESOLVED, recommended_action=ResolutionAction.NO_ACTION, priority=ResolutionPriority.LOW, action_reason="Script only", supporting_evidence_ids=[], missing_evidence=[], required_information=[], confidence=0.95, resolver="Rule")
    res4 = ResolutionResult(id="res4", resolution_id="res4", entity_id="e4", production_id="p_cov", entity_name="Rolex Watch", entity_type="PROP", risk_level="HIGH", risk_score=0.80, resolution_status=ResolutionStatus.ACTION_REQUIRED, recommended_action=ResolutionAction.REQUEST_LICENSE_INFORMATION, priority=ResolutionPriority.HIGH, action_reason="Visual unscripted", supporting_evidence_ids=[], missing_evidence=[], required_information=[], confidence=0.9, resolver="Rule")

    res = engine.generate_report(
        production=prod,
        job=job,
        entities=[e1, e2, e3, e4],
        evidence_list=[],
        research_results=[r1, r2],
        risk_assessments=[],
        verification_results=[v1, v2, v3],
        resolution_results=[res1, res2, res3, res4],
    )

    assert res.total_entities == 4
    assert res.researched_count == 2
    assert res.verified_count == 3
    assert res.resolved_count == 4
    assert res.research_coverage == 0.50
    assert res.verification_coverage == 0.75
    assert res.resolution_coverage == 1.0


def test_engine_finding_prioritization_hierarchy():
    """
    Verify deterministic prioritization hierarchy:
    Resolution Priority: CRITICAL > HIGH > MEDIUM > LOW
    Risk Level: HIGH > MEDIUM > LOW
    Risk Score: Descending
    Classification: VISUAL_ONLY > BOTH > SCRIPT_ONLY
    """
    engine = ReportEngine()
    prod = Production(id="p_prio", title="Prioritization")
    job = AnalysisJob(production_id="p_prio", job_id="j_prio")

    # Item A: Critical resolution priority
    e_a = Entity(id="ea", production_id="p_prio", name="A_Crit", sources=[EntitySource.VISUAL, EntitySource.SCRIPT], risk_level=RiskLevel.MEDIUM, risk_score=0.6)
    res_a = ResolutionResult(id="ra", resolution_id="ra", entity_id="ea", production_id="p_prio", entity_name="A_Crit", entity_type="PROP", risk_level="MEDIUM", risk_score=0.6, resolution_status=ResolutionStatus.ACTION_REQUIRED, recommended_action=ResolutionAction.ESCALATE, priority=ResolutionPriority.CRITICAL, action_reason="", supporting_evidence_ids=[], missing_evidence=[], required_information=[], confidence=0.9, resolver="Rule")

    # Item B: High resolution priority, High risk score 0.95
    e_b = Entity(id="eb", production_id="p_prio", name="B_HighRisk95", sources=[EntitySource.VISUAL], risk_level=RiskLevel.HIGH, risk_score=0.95)
    res_b = ResolutionResult(id="rb", resolution_id="rb", entity_id="eb", production_id="p_prio", entity_name="B_HighRisk95", entity_type="PROP", risk_level="HIGH", risk_score=0.95, resolution_status=ResolutionStatus.ACTION_REQUIRED, recommended_action=ResolutionAction.REQUEST_LICENSE_INFORMATION, priority=ResolutionPriority.HIGH, action_reason="", supporting_evidence_ids=[], missing_evidence=[], required_information=[], confidence=0.9, resolver="Rule")

    # Item C: High resolution priority, High risk score 0.80
    e_c = Entity(id="ec", production_id="p_prio", name="C_HighRisk80", sources=[EntitySource.VISUAL], risk_level=RiskLevel.HIGH, risk_score=0.80)
    res_c = ResolutionResult(id="rc", resolution_id="rc", entity_id="ec", production_id="p_prio", entity_name="C_HighRisk80", entity_type="PROP", risk_level="HIGH", risk_score=0.80, resolution_status=ResolutionStatus.ACTION_REQUIRED, recommended_action=ResolutionAction.REQUEST_LICENSE_INFORMATION, priority=ResolutionPriority.HIGH, action_reason="", supporting_evidence_ids=[], missing_evidence=[], required_information=[], confidence=0.9, resolver="Rule")

    # Item D: Low priority
    e_d = Entity(id="ed", production_id="p_prio", name="D_Low", sources=[EntitySource.SCRIPT], risk_level=RiskLevel.LOW, risk_score=0.1)
    res_d = ResolutionResult(id="rd", resolution_id="rd", entity_id="ed", production_id="p_prio", entity_name="D_Low", entity_type="PROP", risk_level="LOW", risk_score=0.1, resolution_status=ResolutionStatus.RESOLVED, recommended_action=ResolutionAction.NO_ACTION, priority=ResolutionPriority.LOW, action_reason="", supporting_evidence_ids=[], missing_evidence=[], required_information=[], confidence=0.9, resolver="Rule")

    report = engine.generate_report(
        production=prod,
        job=job,
        entities=[e_d, e_c, e_b, e_a],  # unsorted input
        evidence_list=[],
        research_results=[],
        risk_assessments=[],
        verification_results=[],
        resolution_results=[res_a, res_b, res_c, res_d],
    )

    names = [f.entity_name for f in report.all_findings]
    # Expect ea (CRITICAL) first, then eb (HIGH prio, 0.95), then ec (HIGH prio, 0.80), then ed (LOW)
    assert names == ["A_Crit", "B_HighRisk95", "C_HighRisk80", "D_Low"]


def test_engine_visual_only_and_priority_spotlights():
    """Verify visual-only entities and priority findings are properly isolated."""
    engine = ReportEngine()
    prod = Production(id="p_spot", title="Spotlight Test")
    job = AnalysisJob(production_id="p_spot", job_id="j_spot")

    e_vis = Entity(id="e_vis", production_id="p_spot", name="Incidental Poster", sources=[EntitySource.VISUAL], risk_level=RiskLevel.MEDIUM, risk_score=0.5)
    e_scr = Entity(id="e_scr", production_id="p_spot", name="Dialogue Brand", sources=[EntitySource.SCRIPT], risk_level=RiskLevel.LOW, risk_score=0.2)
    e_high = Entity(id="e_high", production_id="p_spot", name="Hero Watch", sources=[EntitySource.VISUAL, EntitySource.SCRIPT], risk_level=RiskLevel.HIGH, risk_score=0.85)

    rep = engine.generate_report(
        production=prod,
        job=job,
        entities=[e_vis, e_scr, e_high],
        evidence_list=[],
        research_results=[],
        risk_assessments=[],
        verification_results=[],
        resolution_results=[],
    )

    # Visual-only spotlight should contain only e_vis
    assert len(rep.visual_only_findings) == 1
    assert rep.visual_only_findings[0].entity_id == "e_vis"

    # Priority findings should contain e_vis (visual-only) and e_high (HIGH risk)
    prio_ids = {f.entity_id for f in rep.priority_findings}
    assert "e_vis" in prio_ids
    assert "e_high" in prio_ids
    assert "e_scr" not in prio_ids


def test_engine_7_stage_evidence_chain():
    """Verify the 7-stage traceability evidence chain is populated for each finding."""
    engine = ReportEngine()
    prod = Production(id="p_trace", title="Trace Test")
    job = AnalysisJob(production_id="p_trace", job_id="j_trace")

    ent = Entity(id="e_tr", production_id="p_trace", name="Sony TV", sources=[EntitySource.VISUAL], scene=2, timestamp=24.5)
    ev1 = Evidence(id="ev1", production_id="p_trace", entity_id="e_tr", evidence_type=EvidenceType.OCR_DETECTION, text_content="SONY", timestamp=24.5, frame_path="frames/f1.jpg")
    ev2 = Evidence(id="ev2", production_id="p_trace", entity_id="e_tr", evidence_type=EvidenceType.OBJECT_BOUNDING_BOX, confidence=0.92, timestamp=24.5)
    res_intel = ResearchResult(id="res1", entity_id="e_tr", production_id="p_trace", entity_name="Sony TV", rights_holder="Sony Corp", summary="Consumer Electronics")
    rk = RiskAssessment(
        id="rk1",
        entity_id="e_tr",
        production_id="p_trace",
        risk_score=0.82,
        risk_level=RiskLevel.HIGH,
        factors=[
            RiskFactor(
                category=RiskCategory.TRADEMARK_INFRINGEMENT,
                description="Visual unscripted logo",
                severity="HIGH",
            )
        ],
    )
    vr = VerificationResult(id="vr1", entity_id="e_tr", production_id="p_trace", decision=VerificationDecision.CONFIRMED, confidence=0.95, notes="Clear logo visible")
    res = ResolutionResult(id="resol1", resolution_id="resol1", entity_id="e_tr", production_id="p_trace", entity_name="Sony TV", entity_type="PROP", risk_level="HIGH", risk_score=0.82, resolution_status=ResolutionStatus.ACTION_REQUIRED, recommended_action=ResolutionAction.REQUEST_LICENSE_INFORMATION, priority=ResolutionPriority.HIGH, action_reason="Prominent logo", supporting_evidence_ids=["ev1"], missing_evidence=[], required_information=[], confidence=0.9, resolver="Rule")

    rep = engine.generate_report(
        production=prod,
        job=job,
        entities=[ent],
        evidence_list=[ev1, ev2],
        research_results=[res_intel],
        risk_assessments=[rk],
        verification_results=[vr],
        resolution_results=[res],
    )

    f = rep.all_findings[0]
    chain = f.evidence_chain
    assert "stage_1_detection" in chain
    assert chain["stage_1_detection"]["name"] == "Sony TV"
    assert "stage_2_visual_evidence" in chain
    assert "stage_4_research" in chain
    assert chain["stage_4_research"]["rights_holder"] == "Sony Corp"
    assert "stage_5_risk" in chain
    assert chain["stage_5_risk"]["level"] == "HIGH"
    assert "stage_6_verification" in chain
    assert chain["stage_6_verification"]["decision"] == "CONFIRMED"
    assert "stage_7_resolution" in chain
    assert chain["stage_7_resolution"]["action"] == "REQUEST_LICENSE_INFORMATION"


# =============================================================================
# 3. REPORT RENDERERS (HTML & PDF)
# =============================================================================

def test_html_renderer_output():
    """Verify HTML renderer generates valid HTML containing title, disclaimer, and tables."""
    result = ReportResult(
        production_id="prod_html",
        job_id="job_html",
        production_title="Blade Runner 2099",
        total_entities=1,
        classification_counts={"VISUAL_ONLY": 1},
        risk_distribution={"HIGH": 1},
        priority_findings=[
            ReportFinding(
                entity_id="e_html_1",
                entity_name="Atari Neon Sign",
                entity_type="SIGNAGE",
                classification="VISUAL_ONLY",
                risk_level="HIGH",
                risk_score=0.9,
                verification_decision="VERIFIED",
                resolution_action="LICENSE_REQUIRED",
            )
        ],
        all_findings=[
            ReportFinding(
                entity_id="e_html_1",
                entity_name="Atari Neon Sign",
                entity_type="SIGNAGE",
                classification="VISUAL_ONLY",
                risk_level="HIGH",
                risk_score=0.9,
                verification_decision="VERIFIED",
                resolution_action="LICENSE_REQUIRED",
            )
        ],
    )
    html_out = render_html_report(result)
    assert "<!DOCTYPE html>" in html_out
    assert "Blade Runner 2099" in html_out
    assert "Atari Neon Sign" in html_out
    assert "VISUAL-ONLY" in html_out or "VISUAL_ONLY" in html_out
    assert "Non-Legal Advice Notice" in html_out
    assert "LEGAL DISCLAIMER" in html_out
    import html
    assert html.escape(result.disclaimer) in html_out


def test_html_renderer_escaping():
    """Verify HTML renderer escapes XSS / special characters properly."""
    result = ReportResult(
        production_id="prod_esc",
        job_id="job_esc",
        production_title="<script>alert('xss')</script>",
        all_findings=[
            ReportFinding(
                entity_id="e_xss",
                entity_name="Brand & Co <Dangerous>",
                entity_type="PROP",
                classification="SCRIPT_ONLY",
                risk_level="LOW",
                risk_score=0.1,
            )
        ],
    )
    html_out = render_html_report(result)
    assert "<script>alert('xss')</script>" not in html_out
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html_out or "&lt;script&gt;" in html_out
    assert "Brand &amp; Co &lt;Dangerous&gt;" in html_out


def test_pdf_renderer_output():
    """Verify PDF renderer produces valid PDF bytes with PDF magic header."""
    result = ReportResult(
        production_id="prod_pdf",
        job_id="job_pdf",
        production_title="The Matrix Clearance",
        total_entities=1,
        classification_counts={"VISUAL_ONLY": 1},
        risk_distribution={"HIGH": 1},
        all_findings=[
            ReportFinding(
                entity_id="e_pdf",
                entity_name="Nokia 8110",
                entity_type="PROP",
                classification="VISUAL_ONLY",
                risk_level="HIGH",
                risk_score=0.85,
                verification_decision="VERIFIED",
                resolution_action="LICENSE_REQUIRED",
                resolution_priority="HIGH",
                resolution_owner="Legal",
            )
        ],
        priority_findings=[
            ReportFinding(
                entity_id="e_pdf",
                entity_name="Nokia 8110",
                entity_type="PROP",
                classification="VISUAL_ONLY",
                risk_level="HIGH",
                risk_score=0.85,
                verification_decision="VERIFIED",
                resolution_action="LICENSE_REQUIRED",
                resolution_priority="HIGH",
                resolution_owner="Legal",
            )
        ],
    )
    pdf_bytes = render_pdf_report(result)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")


def test_pdf_renderer_multi_page():
    """Verify PDF renderer handles multi-page tables and page count stamping."""
    findings = [
        ReportFinding(
            entity_id=f"ent_{i:02d}",
            entity_name=f"Prop Item #{i}",
            entity_type="PROP",
            classification="BOTH" if i % 2 == 0 else "VISUAL_ONLY",
            risk_level="HIGH" if i % 3 == 0 else "LOW",
            risk_score=0.8 if i % 3 == 0 else 0.2,
            verification_decision="VERIFIED",
            resolution_action="LICENSE_REQUIRED" if i % 3 == 0 else "CLEARED",
            scene_number=i % 5 + 1,
            timestamp_start=float(i * 10),
        )
        for i in range(35)
    ]
    result = ReportResult(
        production_id="prod_multi",
        job_id="job_multi",
        production_title="Multi-Page Film Audit",
        total_entities=len(findings),
        all_findings=findings,
        priority_findings=findings[:10],
    )
    pdf_bytes = render_pdf_report(result)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF")


# =============================================================================
# 4. STORAGE & REPOSITORY LAYER
# =============================================================================

@pytest.mark.asyncio
async def test_in_memory_report_repository():
    """Verify InMemoryReportRepository CRUD and sorting operations."""
    repo = InMemoryReportRepository()
    r1 = ReportResult(production_id="prod_repo", job_id="j1", version="1.0")
    await asyncio.sleep(0.01)
    r2 = ReportResult(production_id="prod_repo", job_id="j2", version="1.1")

    await repo.create(r1)
    await repo.create(r2)

    # Fetch by ID
    fetched = await repo.get(r1.report_id)
    assert fetched is not None
    assert fetched.version == "1.0"

    # Fetch latest by production
    latest = await repo.get_by_production("prod_repo")
    assert latest is not None
    assert latest.version == "1.1"

    # List by production
    all_reports = await repo.list_by_production("prod_repo")
    assert len(all_reports) == 2
    assert all_reports[0].version == "1.1"  # Most recent first

    # Delete
    deleted = await repo.delete(r1.report_id)
    assert deleted is True
    assert await repo.get(r1.report_id) is None


@pytest.mark.asyncio
async def test_report_storage_service():
    """Verify ReportStorageService saves JSON, HTML, and PDF files to storage."""
    service = ReportStorageService()
    report = ReportResult(
        production_id="prod_stor_test",
        job_id="j_stor",
        total_entities=1,
    )
    html_doc = "<html><body>Test HTML Report</body></html>"
    pdf_doc = b"%PDF-1.4 test bytes"

    updated = await service.save_report_artifacts(
        report=report,
        html_content=html_doc,
        pdf_bytes=pdf_doc,
    )

    assert "JSON" in updated.format_paths
    assert "HTML" in updated.format_paths
    assert "PDF" in updated.format_paths
    assert "JSON" in updated.format_urls
    assert "HTML" in updated.format_urls
    assert "PDF" in updated.format_urls


# =============================================================================
# 5. REPORT AGENT WORKFLOW & IDEMPOTENCY
# =============================================================================

@pytest.mark.asyncio
async def test_report_agent_generate_production_report():
    """Verify ReportAgent generates full multi-format report and emits events."""
    prod_repo = get_production_repo()
    prod = Production(id="prod_agent_full", title="Agent Full Test")
    await prod_repo.create(prod)
    job = AnalysisJob(production_id=prod.id, job_id="job_agent_full")

    # Add an entity
    ent_repo = get_entity_repo()
    ent = Entity(id="ent_ag", production_id=prod.id, name="Tesla Model 3", classification=EntityClassification.VISUAL_ONLY)
    await ent_repo.create(ent)

    # Listen to events
    received_events = []
    queue = asyncio.Queue()
    async with event_bus._lock:
        event_bus._subscribers[job.job_id].add(queue)

    res = await report_agent.generate_production_report(
        production=prod,
        job=job,
        formats=[ReportFormat.JSON, ReportFormat.HTML, ReportFormat.PDF],
        force_refresh=True,
    )

    assert res.production_id == prod.id
    assert res.total_entities == 1
    assert res.status == ReportStatus.COMPLETED
    assert "JSON" in res.format_paths
    assert "HTML" in res.format_paths
    assert "PDF" in res.format_paths

    # Drain events
    while not queue.empty():
        received_events.append(await queue.get())

    event_types = [e.event_type for e in received_events]
    assert EventType.REPORT_GENERATION_STARTED in event_types
    assert EventType.REPORT_GENERATION_COMPLETED in event_types


@pytest.mark.asyncio
async def test_report_agent_idempotency_and_force_refresh():
    """Verify idempotency returns cached report unless force_refresh=True."""
    prod_repo = get_production_repo()
    prod = Production(id="prod_idemp", title="Idempotency Test")
    await prod_repo.create(prod)
    job = AnalysisJob(production_id=prod.id, job_id="job_idemp")

    # First run: generates v1.0
    r1 = await report_agent.generate_production_report(
        production=prod,
        job=job,
        force_refresh=False,
    )
    assert r1.version == "1.0"

    # Second run with force_refresh=False: returns exact cached r1
    r2 = await report_agent.generate_production_report(
        production=prod,
        job=job,
        force_refresh=False,
    )
    assert r2.report_id == r1.report_id
    assert r2.version == "1.0"

    # Third run with force_refresh=True: increments version to 1.1
    r3 = await report_agent.generate_production_report(
        production=prod,
        job=job,
        force_refresh=True,
    )
    assert r3.report_id != r1.report_id
    assert r3.version == "1.1"


@pytest.mark.asyncio
async def test_report_agent_fault_isolation():
    """Verify fault isolation: PDF failure marks report PARTIAL without crashing."""
    agent = ReportAgent()
    prod = Production(id="prod_fault", title="Fault Test")
    job = AnalysisJob(production_id=prod.id, job_id="job_fault")

    # Patch PDF renderer to raise Exception
    from unittest.mock import patch
    with patch("app.agents.report_agent.render_pdf_report", side_effect=RuntimeError("Simulated PDF Engine Error")):
        res = await agent.generate_production_report(
            production=prod,
            job=job,
            formats=[ReportFormat.JSON, ReportFormat.HTML, ReportFormat.PDF],
            force_refresh=True,
        )

    # Report is marked PARTIAL, HTML and JSON are preserved
    assert res.status == ReportStatus.PARTIAL
    assert "PDF" in res.format_errors
    assert "HTML" in res.format_paths
    assert "JSON" in res.format_paths


@pytest.mark.asyncio
async def test_report_agent_legacy_generate_report_method():
    """Verify backward-compatible generate_report returns legacy Report model."""
    prod = Production(id="prod_leg", title="Legacy Call")
    job = AnalysisJob(production_id=prod.id, job_id="job_leg")
    ent = Entity(id="e_leg", production_id=prod.id, name="Ray-Ban Sunglasses", classification=EntityClassification.VISUAL_ONLY, risk_level=RiskLevel.HIGH)

    legacy_report = await report_agent.generate_report(
        production=prod,
        job=job,
        entities=[ent],
    )

    assert isinstance(legacy_report, Report)
    assert legacy_report.total_entities == 1
    assert legacy_report.visual_only_count == 1
    assert legacy_report.high_risk_count == 1
    assert legacy_report.report_result is not None


# =============================================================================
# 6. REST API ENDPOINTS
# =============================================================================

@pytest.mark.asyncio
async def test_api_report_endpoints():
    """Verify POST, GET, HTML, and PDF endpoints work via FastAPI HTTP test client."""
    prod_repo = get_production_repo()
    prod = Production(id="prod_api_test", title="API Test Movie")
    await prod_repo.create(prod)

    ent_repo = get_entity_repo()
    await ent_repo.create(Entity(id="e_api", production_id=prod.id, name="Rolex Submariner", classification=EntityClassification.VISUAL_ONLY, risk_level=RiskLevel.HIGH))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. POST /productions/{id}/report
        post_res = await client.post(
            f"/productions/{prod.id}/report",
            json={"formats": ["JSON", "HTML", "PDF"], "force_refresh": True},
        )
        assert post_res.status_code == 200
        post_data = post_res.json()
        assert post_data["production_id"] == prod.id
        assert post_data["total_entities"] == 1
        rep_id = post_data["report_id"]

        # 2. GET /productions/{id}/report/result
        get_res = await client.get(f"/productions/{prod.id}/report/result")
        assert get_res.status_code == 200
        assert get_res.json()["report_id"] == rep_id

        # 3. GET /productions/{id}/report (legacy format)
        legacy_res = await client.get(f"/productions/{prod.id}/report")
        assert legacy_res.status_code == 200
        assert legacy_res.json()["total_entities"] == 1
        assert legacy_res.json()["visual_only_count"] == 1

        # 4. GET /productions/{id}/report/html
        html_res = await client.get(f"/productions/{prod.id}/report/html")
        assert html_res.status_code == 200
        assert "text/html" in html_res.headers["content-type"]
        assert "<!DOCTYPE html>" in html_res.text

        # 5. GET /productions/{id}/report/pdf
        pdf_res = await client.get(f"/productions/{prod.id}/report/pdf")
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert pdf_res.content.startswith(b"%PDF")

        # 6. GET 404 for unknown production
        bad_res = await client.get("/productions/non_existent_prod_999/report")
        assert bad_res.status_code == 404

        # 7. GET /productions/{id}/report/{report_id}/html
        id_html_res = await client.get(f"/productions/{prod.id}/report/{rep_id}/html")
        assert id_html_res.status_code == 200
        assert "<!DOCTYPE html>" in id_html_res.text

        # 8. GET /productions/{id}/report/{report_id}/pdf
        id_pdf_res = await client.get(f"/productions/{prod.id}/report/{rep_id}/pdf")
        assert id_pdf_res.status_code == 200
        assert id_pdf_res.content.startswith(b"%PDF")


# =============================================================================
# 7. ADVANCED EDGE-CASE & SCALE TESTS
# =============================================================================

def test_engine_large_scale_100_entities():
    """Verify report engine performance and determinism with 100 entities."""
    engine = ReportEngine()
    prod = Production(id="p_scale", title="100 Entity Mega Film")
    job = AnalysisJob(production_id="p_scale", job_id="j_scale")

    entities = [
        Entity(
            id=f"ent_{i:03d}",
            production_id="p_scale",
            name=f"Entity Brand #{i}",
            sources=[EntitySource.VISUAL] if i % 3 == 0 else ([EntitySource.SCRIPT] if i % 3 == 1 else [EntitySource.VISUAL, EntitySource.SCRIPT]),
            risk_level=RiskLevel.HIGH if i % 5 == 0 else (RiskLevel.MEDIUM if i % 5 == 1 else RiskLevel.LOW),
            risk_score=float(i % 100) / 100.0,
            scene=i % 10 + 1,
            timestamp=float(i * 3.5),
        )
        for i in range(100)
    ]

    report = engine.generate_report(
        production=prod,
        job=job,
        entities=entities,
    )

    assert report.total_entities == 100
    assert len(report.all_findings) == 100
    assert report.classification_counts["VISUAL_ONLY"] == 34
    assert report.classification_counts["SCRIPT_ONLY"] == 33
    assert report.classification_counts["BOTH"] == 33
    assert report.generation_duration_ms > 0.0


def test_engine_all_classifications_distribution():
    """Verify distinct classification counts across all sources."""
    engine = ReportEngine()
    prod = Production(id="p_cls_dist", title="Class Dist")
    job = AnalysisJob(production_id="p_cls_dist", job_id="j_cls_dist")

    e_vis = Entity(id="ev", production_id="p_cls_dist", name="Vis", sources=[EntitySource.VISUAL])
    e_scr = Entity(id="es", production_id="p_cls_dist", name="Scr", sources=[EntitySource.SCRIPT])
    e_both = Entity(id="eb", production_id="p_cls_dist", name="Both", sources=[EntitySource.VISUAL, EntitySource.SCRIPT])
    e_aud = Entity(id="ea", production_id="p_cls_dist", name="Aud", sources=[EntitySource.AUDIO])

    rep = engine.generate_report(
        production=prod,
        job=job,
        entities=[e_vis, e_scr, e_both, e_aud],
    )

    assert rep.classification_counts.get("VISUAL_ONLY") == 1
    assert rep.classification_counts.get("SCRIPT_ONLY") == 1
    assert rep.classification_counts.get("BOTH") == 1
    assert rep.classification_counts.get("AUDIO_ONLY") == 1


def test_engine_all_risk_levels_distribution():
    """Verify all 4 risk levels are tallied correctly."""
    engine = ReportEngine()
    prod = Production(id="p_risk_dist", title="Risk Dist")
    job = AnalysisJob(production_id="p_risk_dist", job_id="j_risk_dist")

    e_high = Entity(id="eh", production_id="p_risk_dist", name="High", risk_level=RiskLevel.HIGH, risk_score=0.9)
    e_med = Entity(id="em", production_id="p_risk_dist", name="Med", risk_level=RiskLevel.MEDIUM, risk_score=0.5)
    e_low = Entity(id="el", production_id="p_risk_dist", name="Low", risk_level=RiskLevel.LOW, risk_score=0.1)
    e_unk = Entity(id="eu", production_id="p_risk_dist", name="Unk", risk_level=RiskLevel.UNKNOWN, risk_score=0.0)

    rep = engine.generate_report(
        production=prod,
        job=job,
        entities=[e_high, e_med, e_low, e_unk],
    )

    assert rep.risk_distribution.get("HIGH") == 1
    assert rep.risk_distribution.get("MEDIUM") == 1
    assert rep.risk_distribution.get("LOW") == 1
    assert rep.risk_distribution.get("UNKNOWN") == 1


def test_engine_dynamic_executive_summary_accuracy():
    """Verify numbers in executive summary match dynamic calculation outputs."""
    engine = ReportEngine()
    prod = Production(id="p_exec", title="Executive Narrative Test")
    job = AnalysisJob(production_id="p_exec", job_id="j_exec")

    e1 = Entity(id="e1", production_id="p_exec", name="Billboard", sources=[EntitySource.VISUAL], risk_level=RiskLevel.HIGH, risk_score=0.9)
    e2 = Entity(id="e2", production_id="p_exec", name="Script Name", sources=[EntitySource.SCRIPT], risk_level=RiskLevel.LOW, risk_score=0.1)

    rep = engine.generate_report(
        production=prod,
        job=job,
        entities=[e1, e2],
    )

    summary = rep.executive_summary
    assert "Executive Narrative Test" in summary
    assert "2 clearance-relevant entities" in summary
    assert "1 Visual-Only" in summary
    assert "1 HIGH risk" in summary
    assert "1 LOW risk" in summary


def test_engine_custom_version_propagation():
    """Verify custom version propagates directly into ReportResult."""
    engine = ReportEngine()
    prod = Production(id="p_ver", title="Version Test")
    job = AnalysisJob(production_id="p_ver", job_id="j_ver")

    rep = engine.generate_report(
        production=prod,
        job=job,
        entities=[],
        version="3.5",
    )
    assert rep.version == "3.5"
    assert "v3.5" in rep.title


def test_html_renderer_structure_and_meta():
    """Verify HTML report includes mobile viewport, UTF-8 charset, and styling tokens."""
    rep = ReportResult(production_id="p_html_meta", job_id="j_meta")
    html_str = render_html_report(rep)
    assert '<meta charset="UTF-8">' in html_str
    assert '<meta name="viewport"' in html_str
    assert "Executive Clearance Summary" in html_str
    assert "Chain of Title Intelligence System" in html_str


def test_pdf_renderer_special_unicode_strings():
    """Verify PDF rendering doesn't crash on international text or symbols."""
    finding = ReportFinding(
        entity_id="e_uni",
        entity_name="Café München & Tokyo (東京)",
        entity_type="LOCATION",
        classification="VISUAL_ONLY",
        risk_level="HIGH",
        risk_score=0.85,
        resolution_action="LICENSE_REQUIRED",
        rights_holder="München Holding GmbH",
    )
    rep = ReportResult(
        production_id="p_uni",
        job_id="j_uni",
        production_title="Global Cinema World",
        total_entities=1,
        all_findings=[finding],
    )
    pdf_bytes = render_pdf_report(rep)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_in_memory_report_repository_isolation():
    """Verify separate productions don't bleed report results."""
    repo = InMemoryReportRepository()
    r_prod_a = ReportResult(production_id="prod_A", job_id="jA", version="1.0")
    r_prod_b = ReportResult(production_id="prod_B", job_id="jB", version="1.0")

    await repo.create(r_prod_a)
    await repo.create(r_prod_b)

    list_a = await repo.list_by_production("prod_A")
    list_b = await repo.list_by_production("prod_B")

    assert len(list_a) == 1
    assert list_a[0].production_id == "prod_A"
    assert len(list_b) == 1
    assert list_b[0].production_id == "prod_B"


@pytest.mark.asyncio
async def test_in_memory_report_repository_delete_missing():
    """Verify deleting a non-existent report returns False."""
    repo = InMemoryReportRepository()
    deleted = await repo.delete("rep_non_existent_xyz")
    assert deleted is False


def test_report_agent_next_version_incrementer():
    """Verify deterministic version math across integer increments."""
    agent = ReportAgent()
    assert agent._next_version("1.0") == "1.1"
    assert agent._next_version("1.9") == "1.10"
    assert agent._next_version("2.14") == "2.15"
    assert agent._next_version("invalid") == "1.1"


@pytest.mark.asyncio
async def test_report_agent_single_format_request():
    """Verify requesting only HTML generates only HTML without crashing."""
    prod = Production(id="p_single_fmt", title="Single Fmt")
    job = AnalysisJob(production_id=prod.id, job_id="j_single_fmt")

    res = await report_agent.generate_production_report(
        production=prod,
        job=job,
        formats=[ReportFormat.HTML],
        force_refresh=True,
    )
    assert "HTML" in res.format_paths
    assert "PDF" not in res.format_paths


def test_report_result_json_serialization():
    """Verify ReportResult serializes cleanly to JSON dictionary and back."""
    rep = ReportResult(
        production_id="p_json_ser",
        job_id="j_ser",
        total_entities=3,
        classification_counts={"VISUAL_ONLY": 2, "SCRIPT_ONLY": 1},
        risk_distribution={"HIGH": 1, "LOW": 2},
    )
    d = rep.model_dump(mode="json")
    assert d["production_id"] == "p_json_ser"
    assert d["total_entities"] == 3

    rebuilt = ReportResult.model_validate(d)
    assert rebuilt.production_id == "p_json_ser"
    assert rebuilt.total_entities == 3
    assert rebuilt.classification_counts["VISUAL_ONLY"] == 2
