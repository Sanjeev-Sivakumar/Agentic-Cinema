from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from app.agents.report_agent import report_agent
from app.models.analysis import AnalysisJob
from app.models.report import Report, ReportFormat, ReportResult
from app.repositories import (
    get_entity_repo,
    get_job_repo,
    get_production_repo,
    get_report_repo,
)
from app.services.storage import storage_service

router = APIRouter(prefix="/productions", tags=["reports"])

class GenerateReportRequest(BaseModel):
    formats: List[ReportFormat] = Field(default_factory=lambda: [ReportFormat.JSON, ReportFormat.HTML, ReportFormat.PDF])
    force_refresh: bool = False
    version: Optional[str] = None

@router.post("/{production_id}/report", response_model=ReportResult)
async def generate_production_report(
    production_id: str,
    payload: Optional[GenerateReportRequest] = None,
) -> ReportResult:
    """
    Generate or retrieve a Phase 8 multi-format clearance intelligence report.
    Returns complete evidence-traceable ReportResult with KPI matrix and findings.
    """
    payload = payload or GenerateReportRequest()
    prod_repo = get_production_repo()
    job_repo = get_job_repo()

    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    jobs = await job_repo.get_by_production(production_id)
    latest_job = jobs[-1] if jobs else None
    if not latest_job:
        latest_job = AnalysisJob(production_id=production_id, job_id=f"job_placeholder_{production_id}")

    report_result = await report_agent.generate_production_report(
        production=production,
        job=latest_job,
        formats=payload.formats,
        force_refresh=payload.force_refresh,
        version=payload.version,
    )
    return report_result

@router.get("/{production_id}/report/result", response_model=ReportResult)
async def get_production_report_result(production_id: str) -> ReportResult:
    """
    Fetch the latest Phase 8 ReportResult for a production.
    If no report has been generated yet, automatically generates one.
    """
    report_repo = get_report_repo()
    report = await report_repo.get_by_production(production_id)
    if report:
        return report

    # Generate if not yet cached
    prod_repo = get_production_repo()
    job_repo = get_job_repo()
    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    jobs = await job_repo.get_by_production(production_id)
    latest_job = jobs[-1] if jobs else None
    if not latest_job:
        latest_job = AnalysisJob(production_id=production_id, job_id=f"job_placeholder_{production_id}")

    return await report_agent.generate_production_report(
        production=production,
        job=latest_job,
        formats=[ReportFormat.JSON, ReportFormat.HTML, ReportFormat.PDF],
        force_refresh=False,
    )

@router.get("/{production_id}/report", response_model=Report)
async def get_production_report(production_id: str) -> Report:
    """
    Get or generate the comprehensive pre-clearance intelligence audit report.
    Maintains 100% backward compatibility with Phase 1-7 tests while including
    the full Phase 8 report_result.
    """
    prod_repo = get_production_repo()
    job_repo = get_job_repo()
    entity_repo = get_entity_repo()

    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    jobs = await job_repo.get_by_production(production_id)
    latest_job = jobs[-1] if jobs else None
    entities = await entity_repo.list_by_production(production_id)

    if not latest_job:
        latest_job = AnalysisJob(production_id=production_id, job_id=f"job_placeholder_{production_id}")

    report = await report_agent.generate_report(
        production=production,
        job=latest_job,
        entities=entities,
    )
    return report

@router.get("/{production_id}/report/html", response_class=HTMLResponse)
async def get_latest_report_html(production_id: str) -> HTMLResponse:
    """Retrieve the latest HTML clearance report."""
    report = await get_production_report_result(production_id)
    html_path = report.format_paths.get("HTML")
    if not html_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HTML format not available for this report",
        )

    rel_path = storage_service.to_relative_path(html_path)
    file_bytes = await storage_service.get_file(rel_path)
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report HTML file not found on disk",
        )
    return HTMLResponse(content=file_bytes.decode("utf-8"), status_code=200)

@router.get("/{production_id}/report/pdf")
async def get_latest_report_pdf(production_id: str) -> Response:
    """Retrieve and stream the latest PDF clearance report."""
    report = await get_production_report_result(production_id)
    pdf_path = report.format_paths.get("PDF")
    if not pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF format not available for this report",
        )

    rel_path = storage_service.to_relative_path(pdf_path)
    file_bytes = await storage_service.get_file(rel_path)
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report PDF file not found on disk",
        )

    headers = {
        "Content-Disposition": f'inline; filename="clearance_report_{production_id}.pdf"',
        "Content-Type": "application/pdf",
    }
    return Response(content=file_bytes, media_type="application/pdf", headers=headers)

@router.get("/{production_id}/report/{report_id}/html", response_class=HTMLResponse)
async def get_report_html_by_id(production_id: str, report_id: str) -> HTMLResponse:
    """Retrieve specific report HTML by report ID."""
    report_repo = get_report_repo()
    report = await report_repo.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

    html_path = report.format_paths.get("HTML")
    if not html_path:
        raise HTTPException(status_code=404, detail="HTML format not generated for this report")

    rel_path = storage_service.to_relative_path(html_path)
    file_bytes = await storage_service.get_file(rel_path)
    if not file_bytes:
        raise HTTPException(status_code=404, detail="HTML artifact file missing from storage")

    return HTMLResponse(content=file_bytes.decode("utf-8"))

@router.get("/{production_id}/report/{report_id}/pdf")
async def get_report_pdf_by_id(production_id: str, report_id: str) -> Response:
    """Retrieve specific report PDF by report ID."""
    report_repo = get_report_repo()
    report = await report_repo.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

    pdf_path = report.format_paths.get("PDF")
    if not pdf_path:
        raise HTTPException(status_code=404, detail="PDF format not generated for this report")

    rel_path = storage_service.to_relative_path(pdf_path)
    file_bytes = await storage_service.get_file(rel_path)
    if not file_bytes:
        raise HTTPException(status_code=404, detail="PDF artifact file missing from storage")

    headers = {
        "Content-Disposition": f'inline; filename="clearance_report_{report_id}.pdf"',
        "Content-Type": "application/pdf",
    }
    return Response(content=file_bytes, media_type="application/pdf", headers=headers)
