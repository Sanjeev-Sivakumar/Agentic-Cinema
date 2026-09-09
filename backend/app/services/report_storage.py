import json
from pathlib import Path
from typing import Optional
from app.core.logging import logger
from app.models.report import ReportFormat, ReportResult
from app.services.storage import storage_service

class ReportStorageService:
    """
    Manages filesystem persistence and retrieval of multi-format clearance reports.
    """

    def __init__(self):
        logger.info("[ReportStorage] Initialized Report Storage Service")

    async def save_report_artifacts(
        self,
        report: ReportResult,
        html_content: Optional[str] = None,
        pdf_bytes: Optional[bytes] = None,
    ) -> ReportResult:
        """
        Persist JSON, HTML, and PDF artifacts for a generated report.
        Updates format_paths and format_urls in-place on the report object.
        """
        prod_id = report.production_id
        rep_id = report.report_id
        base_rel = f"reports/{prod_id}/{rep_id}"

        # 1. JSON serialization
        try:
            json_rel = f"{base_rel}.json"
            json_data = report.model_dump(mode="json")
            json_path = await storage_service.save_json(json_rel, json_data)
            report.format_paths["JSON"] = json_path
            report.format_urls["JSON"] = storage_service.get_url(json_path)
            logger.debug(f"[ReportStorage] Stored JSON report at {json_path}")
        except Exception as e:
            logger.error(f"[ReportStorage] Failed saving JSON report: {e}")
            report.format_errors["JSON"] = str(e)

        # 2. HTML document
        if html_content:
            try:
                html_rel = f"{base_rel}.html"
                html_path = await storage_service.save_file(html_rel, html_content.encode("utf-8"))
                report.format_paths["HTML"] = html_path
                report.format_urls["HTML"] = storage_service.get_url(html_path)
                logger.debug(f"[ReportStorage] Stored HTML report at {html_path}")
            except Exception as e:
                logger.error(f"[ReportStorage] Failed saving HTML report: {e}")
                report.format_errors["HTML"] = str(e)

        # 3. PDF document
        if pdf_bytes:
            try:
                pdf_rel = f"{base_rel}.pdf"
                pdf_path = await storage_service.save_file(pdf_rel, pdf_bytes)
                report.format_paths["PDF"] = pdf_path
                report.format_urls["PDF"] = storage_service.get_url(pdf_path)
                logger.debug(f"[ReportStorage] Stored PDF report at {pdf_path}")
            except Exception as e:
                logger.error(f"[ReportStorage] Failed saving PDF report: {e}")
                report.format_errors["PDF"] = str(e)

        # 4. Mirror export directly into project-level reports directory (BASE_DIR / "reports")
        try:
            from app.core.config import settings
            project_reports_dir = Path(settings.BASE_DIR) / "reports"
            project_reports_dir.mkdir(parents=True, exist_ok=True)

            # Project JSON export
            proj_json_path = project_reports_dir / f"{rep_id}.json"
            with open(proj_json_path, "w", encoding="utf-8") as f:
                json.dump(report.model_dump(mode="json"), f, indent=2, default=str)

            # Project HTML export & latest preview
            if html_content:
                proj_html_path = project_reports_dir / f"{rep_id}.html"
                with open(proj_html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                latest_html = project_reports_dir / "latest_clearance_report.html"
                with open(latest_html, "w", encoding="utf-8") as f:
                    f.write(html_content)

            # Project PDF export & latest preview
            if pdf_bytes:
                proj_pdf_path = project_reports_dir / f"{rep_id}.pdf"
                with open(proj_pdf_path, "wb") as f:
                    f.write(pdf_bytes)
                latest_pdf = project_reports_dir / "latest_clearance_report.pdf"
                with open(latest_pdf, "wb") as f:
                    f.write(pdf_bytes)

            logger.info(f"[ReportStorage] Exported project clearance report to {project_reports_dir} ({rep_id})")
        except Exception as e:
            logger.warning(f"[ReportStorage] Could not mirror report to project folder: {e}")

        return report


report_storage_service = ReportStorageService()
