from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.analysis import AnalysisJob
from app.models.entity import Entity
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.models.production import Production
from app.models.report import (
    Report,
    ReportFormat,
    ReportResult,
    ReportStatus,
)
from app.repositories import (
    get_entity_repo,
    get_evidence_repo,
    get_financial_exposure_repo,
    get_outreach_repo,
    get_remediation_repo,
    get_report_repo,
    get_research_repo,
    get_resolution_repo,
    get_risk_repo,
    get_verification_repo,
)
from app.services.events import event_bus
from app.services.report_engine import report_engine
from app.services.report_renderers import render_html_report, render_pdf_report
from app.services.report_storage import report_storage_service

class ReportAgent:
    """
    Phase 8 Clearance Intelligence Reporting Agent.
    Transforms multi-agent intelligence (Phases 1-7, 10-12) into an executive-grade,
    traceable clearance audit report across JSON, HTML, and PDF formats.
    """

    def __init__(self):
        logger.info("[ReportAgent] Initialized Phase 8 Clearance Reporting Intelligence Agent")

    def _next_version(self, current_version: str) -> str:
        """Deterministically increment report version (e.g. 1.0 -> 1.1)."""
        match = re.search(r"(\d+)\.(\d+)", current_version or "1.0")
        if match:
            major, minor = int(match.group(1)), int(match.group(2))
            return f"{major}.{minor + 1}"
        return "1.1"

    async def generate_production_report(
        self,
        production: Production,
        job: AnalysisJob,
        formats: Optional[List[ReportFormat]] = None,
        force_refresh: bool = False,
        version: Optional[str] = None,
    ) -> ReportResult:
        """
        Generate a multi-format, evidence-traceable clearance intelligence report.
        Strictly deterministic, offline, and adheres to idempotency rules.
        """
        formats = formats or [ReportFormat.JSON, ReportFormat.HTML, ReportFormat.PDF]
        formats_set = set(formats)
        report_repo = get_report_repo()

        # Idempotency check: if existing report exists and force_refresh is False
        existing_report = await report_repo.get_by_production(production.id)
        if existing_report and not force_refresh:
            # Verify if requested formats are present
            requested_names = {f.value if hasattr(f, "value") else str(f) for f in formats}
            available_formats = set(existing_report.format_paths.keys())
            if requested_names.issubset(available_formats):
                logger.info(f"[ReportAgent] Returning cached report '{existing_report.report_id}' for production {production.id}")
                return existing_report

        # Determine version
        if not version:
            version = self._next_version(existing_report.version) if existing_report else "1.0"

        # Emit REPORT_GENERATION_STARTED event
        await event_bus.publish(
            ProcessingEvent(
                production_id=production.id,
                job_id=job.job_id,
                event_type=EventType.REPORT_GENERATION_STARTED,
                stage=PipelineStage.REPORT_GENERATION,
                progress=0.05,
                message=f"Beginning clearance intelligence report generation (v{version}) for '{production.title}'",
                metadata={"formats": [f.value if hasattr(f, "value") else str(f) for f in formats]},
            )
        )

        try:
            # Gather Phase 1-7 & 10-12 repository artifacts
            entity_repo = get_entity_repo()
            evidence_repo = get_evidence_repo()
            research_repo = get_research_repo()
            risk_repo = get_risk_repo()
            verif_repo = get_verification_repo()
            resol_repo = get_resolution_repo()
            exp_repo = get_financial_exposure_repo()
            out_repo = get_outreach_repo()
            rem_repo = get_remediation_repo()

            entities = await entity_repo.list_by_production(production.id)
            evidence_list = await evidence_repo.list_by_production(production.id)
            research_results = await research_repo.list_for_production(production.id)
            risk_assessments = await risk_repo.list_for_production(production.id)
            verification_results = await verif_repo.list_for_production(production.id)
            resolution_results = await resol_repo.list_for_production(production.id)
            financial_exposures = await exp_repo.list_for_production(production.id)
            outreach_drafts = await out_repo.list_for_production(production.id)
            remediation_proposals = await rem_repo.list_for_production(production.id)

            await event_bus.publish(
                ProcessingEvent(
                    production_id=production.id,
                    job_id=job.job_id,
                    event_type=EventType.REPORT_SECTION_GENERATED,
                    stage=PipelineStage.REPORT_GENERATION,
                    progress=0.35,
                    message=f"Aggregated {len(entities)} entities, {len(evidence_list)} evidence records, and clearance resolutions",
                    report_section="AGGREGATION",
                )
            )

            # Generate consolidated ReportResult using deterministic engine
            report_result = report_engine.generate_report(
                production=production,
                job=job,
                entities=entities,
                evidence_list=evidence_list,
                research_results=research_results,
                risk_assessments=risk_assessments,
                verification_results=verification_results,
                resolution_results=resolution_results,
                financial_exposures=financial_exposures,
                outreach_drafts=outreach_drafts,
                remediation_proposals=remediation_proposals,
                version=version,
            )
            report_result.formats = formats

            await event_bus.publish(
                ProcessingEvent(
                    production_id=production.id,
                    job_id=job.job_id,
                    event_type=EventType.REPORT_SECTION_GENERATED,
                    stage=PipelineStage.REPORT_GENERATION,
                    progress=0.65,
                    message="Traceability chains built. Rendering report distribution formats",
                    report_id=report_result.report_id,
                    report_section="RENDER_PREPARATION",
                )
            )

            # Render requested formats with fault isolation
            html_content: Optional[str] = None
            pdf_bytes: Optional[bytes] = None

            if ReportFormat.HTML in formats_set:
                try:
                    html_content = render_html_report(report_result)
                except Exception as e:
                    logger.error(f"[ReportAgent] HTML rendering failed: {e}")
                    report_result.format_errors["HTML"] = str(e)
                    report_result.status = ReportStatus.PARTIAL

            if ReportFormat.PDF in formats_set:
                try:
                    pdf_bytes = render_pdf_report(report_result)
                except Exception as e:
                    logger.error(f"[ReportAgent] PDF rendering failed: {e}")
                    report_result.format_errors["PDF"] = str(e)
                    report_result.status = ReportStatus.PARTIAL

            # Persist artifacts (JSON, HTML, PDF) to storage
            report_result = await report_storage_service.save_report_artifacts(
                report=report_result,
                html_content=html_content,
                pdf_bytes=pdf_bytes,
            )

            # Persist in ReportRepository
            await report_repo.save(report_result)

            # Emit REPORT_GENERATION_COMPLETED event
            await event_bus.publish(
                ProcessingEvent(
                    production_id=production.id,
                    job_id=job.job_id,
                    event_type=EventType.REPORT_GENERATION_COMPLETED,
                    stage=PipelineStage.REPORT_GENERATION,
                    progress=1.0,
                    message=(
                        f"Pre-clearance report generated successfully ({len(report_result.all_findings)} findings, "
                        f"{len(report_result.priority_findings)} priority items, {len(report_result.visual_only_findings)} visual-only)"
                    ),
                    report_id=report_result.report_id,
                    metadata={
                        "status": report_result.status.value,
                        "formats": [f.value if hasattr(f, "value") else str(f) for f in report_result.formats],
                        "format_paths": report_result.format_paths,
                    },
                )
            )

            return report_result

        except Exception as e:
            logger.error(f"[ReportAgent] Report generation failed for production {production.id}: {e}", exc_info=True)
            await event_bus.publish(
                ProcessingEvent(
                    production_id=production.id,
                    job_id=job.job_id,
                    event_type=EventType.REPORT_GENERATION_FAILED,
                    stage=PipelineStage.REPORT_GENERATION,
                    progress=0.0,
                    message=f"Pre-clearance report generation failed: {str(e)}",
                    metadata={"error": str(e)},
                )
            )
            raise

    async def generate_report(
        self,
        production: Production,
        job: AnalysisJob,
        entities: List[Entity],
    ) -> Report:
        """
        Legacy pre-clearance intelligence audit report generator.
        Retained for 100% backward compatibility with Phase 1-7 tests and callers.
        Also executes Phase 8 production report generation and links the result.
        """
        logger.info(f"[ReportAgent] Generating backward-compatible report for production {production.id}")

        def _val(x):
            return x.value if hasattr(x, "value") else str(x)

        visual_only = [e for e in entities if _val(e.classification) == "VISUAL_ONLY"]
        script_only = [e for e in entities if _val(e.classification) == "SCRIPT_ONLY"]
        both = [e for e in entities if _val(e.classification) == "BOTH"]
        audio_only = [e for e in entities if _val(e.classification) == "AUDIO_ONLY"]

        high_risk = [e for e in entities if _val(e.risk_level) == "HIGH"]
        medium_risk = [e for e in entities if _val(e.risk_level) == "MEDIUM"]
        low_risk = [e for e in entities if _val(e.risk_level) == "LOW"]

        summary = (
            f"Pre-clearance analysis completed for '{production.title}'. "
            f"Detected {len(entities)} clearance-relevant entities across screenplay and captured footage, "
            f"including {len(visual_only)} Visual-Only findings requiring review."
        )

        entity_breakdown = [
            {
                "id": e.id,
                "name": e.name,
                "type": _val(e.entity_type),
                "classification": _val(e.classification),
                "risk_level": _val(e.risk_level),
                "risk_score": e.risk_score,
                "scene": e.scene,
                "timestamp": e.timestamp,
                "rights_holder": e.rights_holder,
            }
            for e in entities
        ]

        checklist = [
            {
                "entity_name": e.name,
                "action": "Address Visual-Only Trademark Risk" if _val(e.classification) == "VISUAL_ONLY" else "Verify License Agreement",
                "priority": _val(e.risk_level),
                "status": _val(e.resolution_status),
            }
            for e in entities
        ]

        # Generate full Phase 8 ReportResult
        report_result: Optional[ReportResult] = None
        pdf_path: Optional[str] = None
        try:
            report_result = await self.generate_production_report(
                production=production,
                job=job,
                formats=[ReportFormat.JSON, ReportFormat.HTML, ReportFormat.PDF],
            )
            pdf_path = report_result.format_paths.get("PDF")
        except Exception as e:
            logger.warning(f"[ReportAgent] Phase 8 sub-generation error during legacy call: {e}")

        return Report(
            production_id=production.id,
            job_id=job.job_id,
            title=f"Chain of Title Audit: {production.title}",
            executive_summary=summary,
            total_entities=len(entities),
            visual_only_count=len(visual_only),
            script_only_count=len(script_only),
            both_count=len(both),
            audio_only_count=len(audio_only),
            high_risk_count=len(high_risk),
            medium_risk_count=len(medium_risk),
            low_risk_count=len(low_risk),
            unresolved_count=len(high_risk) + len(medium_risk),
            entity_breakdown=entity_breakdown,
            clearance_checklist=checklist,
            pdf_path=pdf_path,
            report_result=report_result,
        )

report_agent = ReportAgent()
