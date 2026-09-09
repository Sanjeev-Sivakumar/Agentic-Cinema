"""
Verification suite for Phase 13.2 — GCS Upload/Download & Prefix Architecture.
Verifies all 5 production prefix structures, byte-exact data integrity, private ACLs,
and graceful local fallback.
"""
import os
import json
import pytest
from unittest.mock import MagicMock, patch
from app.core.config import settings
from app.services.gcs_storage import GCSStorageProvider


@pytest.fixture
def clean_local_storage(tmp_path):
    """Temporary local storage directory for test isolation."""
    return str(tmp_path / "gcs_local_test")


@pytest.mark.asyncio
async def test_gcs_all_five_production_prefixes_upload_download(clean_local_storage):
    """
    Verify upload and download across all 5 standard production prefix hierarchies:
    1. footage/{production_id}/...
    2. frames/{production_id}/{job_id}/...
    3. remediations/{production_id}/{job_id}/...
    4. reports/{production_id}/...
    5. scripts/{production_id}/...
    """
    orig_enabled = settings.GCS_ENABLED
    orig_bucket = settings.GCS_BUCKET
    orig_project = settings.GCP_PROJECT_ID

    try:
        settings.GCS_ENABLED = True
        settings.GCS_BUCKET = "chain-of-title-cinema-2026"
        settings.GCP_PROJECT_ID = "chain-of-title-cinema-2026"

        provider = GCSStorageProvider(base_local_dir=clean_local_storage)

        # In-memory mock storage representing GCS bucket
        gcs_blob_store = {}

        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        def create_mock_blob(blob_name):
            mock_blob = MagicMock()
            mock_blob.name = blob_name

            def upload_from_string(data, content_type=None):
                gcs_blob_store[blob_name] = {
                    "data": data,
                    "content_type": content_type,
                    "is_public": False,
                }

            def exists():
                return blob_name in gcs_blob_store

            def download_as_bytes():
                if blob_name in gcs_blob_store:
                    return gcs_blob_store[blob_name]["data"]
                raise Exception("Blob not found")

            mock_blob.upload_from_string.side_effect = upload_from_string
            mock_blob.exists.side_effect = exists
            mock_blob.download_as_bytes.side_effect = download_as_bytes
            return mock_blob

        mock_bucket.blob.side_effect = create_mock_blob

        with patch("google.cloud.storage.Client", return_value=mock_client):
            test_cases = [
                (
                    "footage/prod_demo_01/raw_footage.mp4",
                    b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00",
                    "video/mp4",
                ),
                (
                    "frames/prod_demo_01/job_101/frame_0001.jpg",
                    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00",
                    "image/jpeg",
                ),
                (
                    "remediations/prod_demo_01/job_101/rem_9ec41.jpg",
                    b"\xff\xd8\xff\xe0\x00\x10JFIF_REMEDIATED",
                    "image/jpeg",
                ),
                (
                    "reports/prod_demo_01/rep_764ba.json",
                    json.dumps({"report_id": "rep_764ba", "status": "COMPLETED"}).encode("utf-8"),
                    "application/json",
                ),
                (
                    "scripts/prod_demo_01/screenplay.pdf",
                    b"%PDF-1.4 sample screenplay document",
                    "application/pdf",
                ),
            ]

            for path, data, expected_mime in test_cases:
                # 1. Save file
                saved_path = await provider.save_file(path, data)
                assert saved_path is not None

                # 2. Verify stored in GCS mock store
                clean_key = path
                assert clean_key in gcs_blob_store
                assert gcs_blob_store[clean_key]["data"] == data
                assert gcs_blob_store[clean_key]["content_type"] == expected_mime
                assert gcs_blob_store[clean_key]["is_public"] is False

                # 3. Verify file_exists
                exists = await provider.file_exists(path)
                assert exists is True

                # 4. Download and verify byte-for-byte exact equality
                downloaded_data = await provider.get_file(path)
                assert downloaded_data == data

    finally:
        settings.GCS_ENABLED = orig_enabled
        settings.GCS_BUCKET = orig_bucket
        settings.GCP_PROJECT_ID = orig_project


@pytest.mark.asyncio
async def test_gcs_private_acl_enforcement(clean_local_storage):
    """Verify that blobs remain private and no make_public methods are called."""
    orig_enabled = settings.GCS_ENABLED
    try:
        settings.GCS_ENABLED = True
        provider = GCSStorageProvider(base_local_dir=clean_local_storage)

        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        with patch("google.cloud.storage.Client", return_value=mock_client):
            await provider.save_file("reports/prod_01/rep.json", b'{"private": true}')

            # Assert upload was performed
            assert mock_blob.upload_from_string.called

            # Assert make_public was NEVER called
            assert not hasattr(mock_blob, "make_public") or not mock_blob.make_public.called
            assert not mock_blob.acl.all().grant_read.called
    finally:
        settings.GCS_ENABLED = orig_enabled


@pytest.mark.asyncio
async def test_gcs_json_serialization_roundtrip(clean_local_storage):
    """Verify save_json and get_json serialize and deserialize complex clearance data accurately."""
    orig_enabled = settings.GCS_ENABLED
    try:
        settings.GCS_ENABLED = True
        provider = GCSStorageProvider(base_local_dir=clean_local_storage)

        stored_blobs = {}
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        def get_blob(name):
            b = MagicMock()
            b.upload_from_string.side_effect = lambda d, content_type=None: stored_blobs.update({name: d})
            b.exists.side_effect = lambda: name in stored_blobs
            b.download_as_bytes.side_effect = lambda: stored_blobs.get(name)
            return b

        mock_bucket.blob.side_effect = get_blob

        with patch("google.cloud.storage.Client", return_value=mock_client):
            clearance_payload = {
                "production_id": "prod_demo",
                "entities": [
                    {
                        "name": "Cadbury Dairy Milk",
                        "risk_score": 64,
                        "rights_holder": "CADBURY UK LIMITED",
                        "statutory_reference": "15 U.S.C. § 1117(c)",
                    }
                ],
                "verified": True,
            }

            await provider.save_json("reports/prod_demo/clearance.json", clearance_payload)
            retrieved = await provider.get_json("reports/prod_demo/clearance.json")

            assert retrieved == clearance_payload
            assert retrieved["entities"][0]["rights_holder"] == "CADBURY UK LIMITED"
    finally:
        settings.GCS_ENABLED = orig_enabled


@pytest.mark.asyncio
async def test_gcs_unauthenticated_graceful_fallback(clean_local_storage):
    """
    Verify that in unauthenticated or offline environments, GCSStorageProvider
    gracefully catches errors, logs warnings, and safely preserves local disk storage.
    """
    orig_enabled = settings.GCS_ENABLED
    try:
        settings.GCS_ENABLED = True
        provider = GCSStorageProvider(base_local_dir=clean_local_storage)

        # Force storage.Client to raise DefaultCredentialsError
        from google.auth.exceptions import DefaultCredentialsError

        with patch("google.cloud.storage.Client", side_effect=DefaultCredentialsError("No credentials")):
            data = b"Offline safe clearance payload"
            path = "footage/prod_01/clip.mp4"

            # Must succeed locally without throwing
            saved_local_path = await provider.save_file(path, data)
            assert os.path.exists(saved_local_path)

            # Must retrieve from local fallback
            retrieved = await provider.get_file(path)
            assert retrieved == data
    finally:
        settings.GCS_ENABLED = orig_enabled


@pytest.mark.asyncio
async def test_gcs_blob_not_found_local_cache_fallback(clean_local_storage):
    """Verify that when a blob is not found on GCS, local cache is returned."""
    orig_enabled = settings.GCS_ENABLED
    try:
        settings.GCS_ENABLED = True
        provider = GCSStorageProvider(base_local_dir=clean_local_storage)

        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False  # Blob does not exist on GCS
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        with patch("google.cloud.storage.Client", return_value=mock_client):
            local_only_data = b"Local cached document"
            await provider._local.save_file("reports/prod_01/local_doc.pdf", local_only_data)

            # Retrieve through GCS provider
            result = await provider.get_file("reports/prod_01/local_doc.pdf")
            assert result == local_only_data
    finally:
        settings.GCS_ENABLED = orig_enabled
