"""
Google Cloud Storage (GCS) Provider for Chain of Title.
Stores footage, evidence frames, visual remediation proposals, and clearance reports
under organized production/job prefixes in Google Cloud Storage:
  Bucket: chain-of-title-cinema-2026 (or GCS_BUCKET)
  Project: chain-of-title-cinema-2026 (or GCP_PROJECT_ID)

Resilience & Security Guarantees:
- Completely optional: When GCS_ENABLED=false (default), uses LocalStorageService with zero GCP dependencies.
- Dual persistence & local fallback: Writes to both GCS and local disk; on any GCS network or auth failure,
  gracefully logs a warning and falls back to local storage without breaking the pipeline.
- Private bucket security: No public ACLs or public URLs are generated.
- ₹0 / Free-tier safe: Standard 5GB/month storage free tier.
"""
import asyncio
import json
import mimetypes
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings
from app.core.logging import logger
from app.services.storage import StorageService, LocalStorageService


class GCSStorageProvider(StorageService):
    """
    Production-grade Google Cloud Storage provider with automatic local fallback.
    Organizes assets under production/job prefixes:
      - footage/{production_id}/{filename}
      - frames/{production_id}/{job_id}/{filename}
      - remediations/{production_id}/{job_id}/{filename}
      - reports/{production_id}/{filename}
      - scripts/{production_id}/{filename}
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        project_id: Optional[str] = None,
        base_local_dir: Optional[str] = None,
    ):
        self.bucket_name = bucket_name or settings.GCS_BUCKET
        self.project_id = project_id or settings.effective_gcp_project_id
        self._local = LocalStorageService(base_dir=base_local_dir)
        self._client: Optional[Any] = None
        self._bucket: Optional[Any] = None
        self._init_failed: bool = False

    def _get_bucket(self) -> Optional[Any]:
        """Lazy-initialize the official Google Cloud Storage client and bucket."""
        if not settings.is_gcs_enabled:
            return None

        if self._bucket is not None:
            return self._bucket

        if self._init_failed:
            return None

        try:
            from google.cloud import storage
            self._client = storage.Client(project=self.project_id)
            self._bucket = self._client.bucket(self.bucket_name)
            logger.info(f"[GCSStorage] Initialized GCS client for bucket 'gs://{self.bucket_name}' (Project: {self.project_id})")
            return self._bucket
        except Exception as e:
            self._init_failed = True
            logger.warning(
                f"[GCSStorage] Failed to initialize Google Cloud Storage client: {e}. "
                f"Falling back to local storage."
            )
            return None

    def _clean_path(self, relative_path: str) -> str:
        """Sanitize relative path to clean forward-slash blob path."""
        p = str(relative_path).replace("\\", "/")
        if "data/storage/" in p:
            p = p.split("data/storage/")[-1]
        elif "/storage/" in p:
            p = p.split("/storage/")[-1]
        elif "storage/" in p:
            p = p.split("storage/")[-1]
        return p.lstrip("/")

    def _detect_content_type(self, path: str) -> str:
        """Determine content MIME type for GCS blob."""
        mime, _ = mimetypes.guess_type(path)
        if mime:
            return mime
        if path.endswith(".json"):
            return "application/json"
        if path.endswith(".pdf"):
            return "application/pdf"
        if path.endswith(".html"):
            return "text/html"
        if path.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        if path.endswith(".png"):
            return "image/png"
        if path.endswith(".mp4"):
            return "video/mp4"
        return "application/octet-stream"

    async def save_file(self, relative_path: str, data: bytes) -> str:
        """
        Save file to local storage and upload to Google Cloud Storage if enabled.
        Returns local filesystem path or GCS URI.
        """
        clean_path = self._clean_path(relative_path)

        # 1. Always write to local storage first for fast local caching & zero-failure guarantee
        local_path = await self._local.save_file(clean_path, data)

        # 2. Upload to GCS if enabled
        if settings.is_gcs_enabled:
            bucket = self._get_bucket()
            if bucket is not None:
                try:
                    content_type = self._detect_content_type(clean_path)
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        None,
                        lambda: bucket.blob(clean_path).upload_from_string(
                            data,
                            content_type=content_type,
                        )
                    )
                    logger.debug(f"[GCSStorage] Uploaded {len(data)} bytes to gs://{self.bucket_name}/{clean_path}")
                except Exception as e:
                    logger.warning(
                        f"[GCSStorage] Failed to upload to gs://{self.bucket_name}/{clean_path}: {e}. "
                        f"Local copy at '{local_path}' remains preserved."
                    )

        return str(local_path)

    async def get_file(self, relative_path: str) -> Optional[bytes]:
        """
        Retrieve raw file bytes from GCS (if enabled) or local cache.
        """
        clean_path = self._clean_path(relative_path)

        if settings.is_gcs_enabled:
            bucket = self._get_bucket()
            if bucket is not None:
                try:
                    blob = bucket.blob(clean_path)
                    loop = asyncio.get_running_loop()
                    exists = await loop.run_in_executor(None, blob.exists)
                    if exists:
                        data = await loop.run_in_executor(None, blob.download_as_bytes)
                        return data
                except Exception as e:
                    logger.warning(f"[GCSStorage] Failed to download from gs://{self.bucket_name}/{clean_path}: {e}. Checking local cache.")

        # Local fallback
        return await self._local.get_file(clean_path)

    async def file_exists(self, relative_path: str) -> bool:
        """Check if file exists in GCS or local storage."""
        clean_path = self._clean_path(relative_path)

        if settings.is_gcs_enabled:
            bucket = self._get_bucket()
            if bucket is not None:
                try:
                    blob = bucket.blob(clean_path)
                    loop = asyncio.get_running_loop()
                    exists = await loop.run_in_executor(None, blob.exists)
                    if exists:
                        return True
                except Exception as e:
                    logger.warning(f"[GCSStorage] Failed to check existence of gs://{self.bucket_name}/{clean_path}: {e}")

        return await self._local.file_exists(clean_path)

    async def save_json(self, relative_path: str, data: Any) -> str:
        """Save JSON serializable object to storage."""
        content = json.dumps(data, indent=2, default=str).encode("utf-8")
        return await self.save_file(relative_path, content)

    async def get_json(self, relative_path: str) -> Optional[Any]:
        """Retrieve and deserialize JSON object from storage."""
        file_bytes = await self.get_file(relative_path)
        if not file_bytes:
            return None
        return json.loads(file_bytes.decode("utf-8"))

    def to_relative_path(self, path: str) -> str:
        """Convert filesystem or GCS path to web relative path."""
        return self._local.to_relative_path(path)

    def get_url(self, path: str) -> str:
        """Format web accessible URL for a stored asset."""
        return self._local.get_url(path)


# Backward compatibility alias
GoogleCloudStorageService = GCSStorageProvider
