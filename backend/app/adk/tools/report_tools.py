import time
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.orchestration import WorkflowSummary
from app.agents.report_agent import report_agent
from app.adk.context import WorkflowContext


async def generate_report_tool(
    context: WorkflowContext,
    formats: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    ADK tool for clearance reporting intelligence (Phase 8).
    Synthesizes upstream intelligence across Screenplay, Visual, Research, Risk, Verification,
    and Resolution into production-ready JSON, HTML, and PDF audit reports.
    """
    start_time = time.perf_counter()
    report_formats = formats or ["JSON", "HTML", "PDF"]

    try:
        from app.models.analysis import AnalysisJob
        from app.models.report import ReportFormat

        prod = await context.production_repo.get(context.production_id)
        job = await context.job_repo.get(context.job_id)
        if not job:
            job = AnalysisJob(job_id=context.job_id, production_id=context.production_id)
            await context.job_repo.save(job)

        enum_formats = []
        for f in report_formats:
            try:
                enum_formats.append(ReportFormat(f.upper()))
            except Exception:
                pass
        if not enum_formats:
            enum_formats = [ReportFormat.JSON, ReportFormat.HTML, ReportFormat.PDF]

        report = await report_agent.generate_production_report(
            production=prod,
            job=job,
            formats=enum_formats,
            force_refresh=context.force_refresh,
        )

        context.state.report_id = report.report_id

        # Populate WorkflowSummary on state
        context.state.workflow_summary = WorkflowSummary(
            detection={
                "total_entities": report.total_entities,
                "visual_only": getattr(report, "visual_only_count", len(report.visual_only_findings)),
                "both": getattr(report, "both_count", report.classification_counts.get("BOTH", 0)),
                "script_only": getattr(report, "script_only_count", report.classification_counts.get("SCRIPT_ONLY", 0)),
                "evidence_count": len(context.state.evidence_ids),
            },
            research={
                "completed": getattr(report, "researched_count", 0),
                "coverage": getattr(report, "research_coverage", 0.0),
            },
            risk={
                "high": getattr(report, "high_risk_count", report.risk_distribution.get("HIGH", 0)),
                "medium": getattr(report, "medium_risk_count", report.risk_distribution.get("MEDIUM", 0)),
                "low": getattr(report, "low_risk_count", report.risk_distribution.get("LOW", 0)),
                "unknown": report.risk_distribution.get("UNKNOWN", 0),
            },
            verification={
                "confirmed": report.verification_distribution.get("CONFIRMED", 0),
                "review": report.verification_distribution.get("REVIEW", 0),
                "rejected": report.verification_distribution.get("REJECTED", 0),
                "coverage": getattr(report, "verification_coverage", 0.0),
            },
            resolution={
                "completed": report.resolution_distribution.get("RESOLVED", 0),
                "action_required": report.resolution_distribution.get("ACTION_REQUIRED", 0),
                "human_review": report.resolution_distribution.get("HUMAN_REVIEW", 0),
                "escalated": report.resolution_distribution.get("ESCALATED", 0),
                "coverage": getattr(report, "resolution_coverage", 0.0),
            },
            reporting={
                "report_id": report.report_id,
                "findings_count": len(report.all_findings),
                "formats": report_formats,
                "format_paths": report.format_paths,
            },
        )

        duration = time.perf_counter() - start_time
        return {
            "status": "COMPLETED",
            "report_id": report.report_id,
            "formats": report_formats,
            "findings_count": len(report.all_findings),
            "format_paths": report.format_paths,
            "duration": round(duration, 3),
        }

    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"[ADK ReportTool] Report generation failed: {e}", exc_info=True)
        context.state.record_error(f"Report generation failed: {str(e)}")
        return {
            "status": "FAILED",
            "error": str(e),
            "report_id": None,
            "duration": round(duration, 3),
        }
