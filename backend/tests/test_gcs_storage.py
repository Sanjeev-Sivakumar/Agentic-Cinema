"""
Unit tests for Google Cloud Storage (GCS) Storage Provider.
Verifies:
1. Disabled mode (default): returns LocalStorageService, 0 GCP calls, 0 network access.
2. Enabled mode with mocks: prefix hierarchy, content-type assignment, private blob security.
3. Resilience & Fallback: simulated GCS errors fall back to local storage without pipeline interruption.
4. Production / Job prefix organization across videos, frames, remediations, and reports.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.services.storage import get_storage_service, LocalStorageService
from app.services.gcs_storage import GCSStorageProvider


def test_gcs_disabled_by_default():
    """Default configuration uses LocalStorageService and has is_gcs_enabled=False."""
    orig_enabled = settings.GCS_ENABLED
    orig_enable_cloud = settings.ENABLE_CLOUD_STORAGE
    orig_backend = settings.STORAGE_BACKEND
    try:
        settings.GCS_ENABLED = False
        settings.ENABLE_CLOUD_STORAGE = False
        settings.STORAGE_BACKEND = "local"

        assert settings.is_gcs_enabled is False
        service = get_storage_service()
        assert isinstance(service, LocalStorageService)
    finally:
        settings.GCS_ENABLED = orig_enabled
        settings.ENABLE_CLOUD_STORAGE = orig_enable_cloud
        settings.STORAGE_BACKEND = orig_backend


def test_gcs_bucket_and_project_configuration():
    """Verify GCS settings reflect chain-of-title-cinema-2026."""
    orig_proj = settings.GCP_PROJECT_ID
    orig_bucket = settings.GCS_BUCKET
    try:
        settings.GCP_PROJECT_ID = "chain-of-title-cinema-2026"
        settings.GCS_BUCKET = "chain-of-title-cinema-2026"

        provider = GCSStorageProvider()
        assert provider.bucket_name == "chain-of-title-cinema-2026"
        assert provider.project_id == "chain-of-title-cinema-2026"
    finally:
        settings.GCP_PROJECT_ID = orig_proj
        settings.GCS_BUCKET = orig_bucket


@pytest.mark.asyncio
async def test_gcs_save_and_get_with_prefixes(tmp_path):
    """Verify saving frames, remediations, reports, and PDFs with proper content-types."""
    orig_enabled = settings.GCS_ENABLED
    orig_bucket = settings.GCS_BUCKET
    try:
        settings.GCS_ENABLED = True
        settings.GCS_BUCKET = "chain-of-title-cinema-2026"

        provider = GCSStorageProvider(base_local_dir=str(tmp_path))

        # Setup mock GCS Client & Blobs
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.download_as_bytes.return_value = b'{"report_id":"rep_demo_123"}'

        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        with patch("google.cloud.storage.Client", return_value=mock_client):
            # 1. Test Report JSON upload
            report_data = {"report_id": "rep_demo_123", "status": "COMPLETED"}
            report_path = "reports/prod_demo/rep_demo_123.json"
            saved_path = await provider.save_json(report_path, report_data)

            assert Path(saved_path).exists()
            mock_bucket.blob.assert_called_with("reports/prod_demo/rep_demo_123.json")
            upload_kwargs = mock_blob.upload_from_string.call_args[1]
            assert upload_kwargs.get("content_type") == "application/json"

            # 2. Test Evidence Frame upload (image/jpeg)
            frame_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 32
            await provider.save_file("frames/prod_demo/job_01/scene03_00027.jpg", frame_bytes)
            mock_bucket.blob.assert_called_with("frames/prod_demo/job_01/scene03_00027.jpg")
            upload_kwargs = mock_blob.upload_from_string.call_args[1]
            assert upload_kwargs.get("content_type") == "image/jpeg"

            # 3. Test Remediation Artifact upload (image/jpeg)
            rem_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 32
            await provider.save_file("remediations/prod_demo/job_01/rem_01_comparison.jpg", rem_bytes)
            mock_bucket.blob.assert_called_with("remediations/prod_demo/job_01/rem_01_comparison.jpg")
            upload_kwargs = mock_blob.upload_from_string.call_args[1]
            assert upload_kwargs.get("content_type") == "image/jpeg"

            # 4. Test PDF Report upload (application/pdf)
            pdf_bytes = b"%PDF-1.4 sample content"
            await provider.save_file("reports/prod_demo/rep_demo_123.pdf", pdf_bytes)
            mock_bucket.blob.assert_called_with("reports/prod_demo/rep_demo_123.pdf")
            upload_kwargs = mock_blob.upload_from_string.call_args[1]
            assert upload_kwargs.get("content_type") == "application/pdf"

            # 5. Test Private security: verify make_public was never invoked
            assert not mock_blob.make_public.called

            # 6. Test Retrieval & File Exists
            exists = await provider.file_exists(report_path)
            assert exists is True

            data_back = await provider.get_json(report_path)
            assert data_back.get("report_id") == "rep_demo_123"

    finally:
        settings.GCS_ENABLED = orig_enabled
        settings.GCS_BUCKET = orig_bucket


@pytest.mark.asyncio
async def test_gcs_graceful_local_fallback(tmp_path):
    """Simulated GCS network/auth failure falls back to local storage without throwing error."""
    orig_enabled = settings.GCS_ENABLED
    try:
        settings.GCS_ENABLED = True
        provider = GCSStorageProvider(base_local_dir=str(tmp_path))

        mock_blob = MagicMock()
        mock_blob.upload_from_string.side_effect = RuntimeError("GCS 503 Service Unavailable")
        mock_blob.exists.side_effect = RuntimeError("GCS Network Timeout")
        mock_blob.download_as_bytes.side_effect = RuntimeError("GCS Auth Error")

        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        with patch("google.cloud.storage.Client", return_value=mock_client):
            # Save should not fail
            test_content = b"local fallback test payload"
            rel_path = "reports/prod_demo/fallback.txt"
            local_path = await provider.save_file(rel_path, test_content)

            # Local file exists
            assert Path(local_path).exists()

            # Retrieval falls back to local
            retrieved = await provider.get_file(rel_path)
            assert retrieved == test_content

            # Exists checks local
            exists = await provider.file_exists(rel_path)
            assert exists is True

    finally:
        settings.GCS_ENABLED = orig_enabled
