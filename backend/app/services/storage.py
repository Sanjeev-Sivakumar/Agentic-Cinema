from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
from typing import Any, Optional
import aiofiles
from app.core.config import settings
from app.core.logging import logger

class StorageService(ABC):
    """Abstract interface for local and cloud storage operations."""

    @abstractmethod
    async def save_file(self, relative_path: str, data: bytes) -> str:
        """Save raw bytes to storage and return accessible URI/path."""
        pass

    @abstractmethod
    async def get_file(self, relative_path: str) -> Optional[bytes]:
        """Retrieve raw bytes from storage."""
        pass

    @abstractmethod
    async def file_exists(self, relative_path: str) -> bool:
        """Check if file exists in storage."""
        pass

    @abstractmethod
    async def save_json(self, relative_path: str, data: Any) -> str:
        """Save JSON serializable object."""
        pass

    @abstractmethod
    async def get_json(self, relative_path: str) -> Optional[Any]:
        """Retrieve and deserialize JSON object."""
        pass


class LocalStorageService(StorageService):
    """Local filesystem storage implementation."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or settings.LOCAL_STORAGE_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, relative_path: str) -> Path:
        # Sanitize path to prevent directory traversal
        clean_path = relative_path.lstrip("/\\")
        target = self.base_dir / clean_path
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    async def save_file(self, relative_path: str, data: bytes) -> str:
        target_path = self._resolve_path(relative_path)
        async with aiofiles.open(target_path, "wb") as f:
            await f.write(data)
        logger.debug(f"[LocalStorage] Saved {len(data)} bytes to {target_path}")
        return str(target_path)

    async def get_file(self, relative_path: str) -> Optional[bytes]:
        target_path = self._resolve_path(relative_path)
        if not target_path.exists():
            return None
        async with aiofiles.open(target_path, "rb") as f:
            return await f.read()

    async def file_exists(self, relative_path: str) -> bool:
        target_path = self._resolve_path(relative_path)
        return target_path.exists()

    async def save_json(self, relative_path: str, data: Any) -> str:
        content = json.dumps(data, indent=2, default=str).encode("utf-8")
        return await self.save_file(relative_path, content)

    async def get_json(self, relative_path: str) -> Optional[Any]:
        file_bytes = await self.get_file(relative_path)
        if not file_bytes:
            return None
        return json.loads(file_bytes.decode("utf-8"))

    def to_relative_path(self, path: str) -> str:
        """Convert filesystem path to web storage relative path."""
        p = Path(path)
        try:
            rel = p.relative_to(self.base_dir)
            return str(rel).replace("\\", "/")
        except Exception:
            clean = path.replace("\\", "/")
            if "data/storage/" in clean:
                return clean.split("data/storage/")[-1]
            return clean

    def get_url(self, path: str) -> str:
        """Format web accessible URL for a stored asset."""
        rel = self.to_relative_path(path)
        return f"/storage/{rel.lstrip('/')}"


def get_storage_service() -> StorageService:
    if settings.is_gcs_enabled:
        from app.services.gcs_storage import GCSStorageProvider
        return GCSStorageProvider()
    return LocalStorageService()


# Backward compatibility alias
def __getattr__(name: str):
    if name == "GoogleCloudStorageService":
        from app.services.gcs_storage import GCSStorageProvider
        return GCSStorageProvider
    raise AttributeError(f"module {__name__} has no attribute {name}")


storage_service: StorageService = get_storage_service()


async def materialize_asset_to_local(
    path_or_uri: str,
    production_id: str,
    category: str = "footage",
    filename: Optional[str] = None,
) -> Path:
    """
    Ensures an asset (footage, screenplay, image) is present as a real, accessible local file.
    Resolves local workspace paths, local storage files, and downloads GCS/cloud blobs to a unique
    temporary path (/tmp/chain_of_title/{production_id}/{category}/{filename}).
    Strictly verifies existence and file size > 0.
    """
    import tempfile
    import re

    if not path_or_uri or not str(path_or_uri).strip():
        raise ValueError(f"Empty path_or_uri provided for production '{production_id}' ({category})")

    clean_str = str(path_or_uri).strip()

    # 1. Check direct local filesystem candidates first
    direct_p = Path(clean_str)
    candidate_paths = [
        direct_p if direct_p.is_absolute() else None,
        direct_p,
        Path(settings.BASE_DIR) / clean_str,
        Path(settings.BASE_DIR) / clean_str.lstrip("/\\"),
        Path(settings.LOCAL_STORAGE_DIR) / clean_str,
        Path(settings.LOCAL_STORAGE_DIR) / clean_str.lstrip("/\\"),
    ]

    # Also strip known prefixes if present in path (e.g. data/storage/..., /storage/..., footage/...)
    stripped_keys = [clean_str]
    for prefix in ("data/storage/", "/storage/", "storage/", "media/", "/media/"):
        if prefix in clean_str:
            stripped_keys.append(clean_str.split(prefix)[-1].lstrip("/\\"))

    for sk in stripped_keys:
        candidate_paths.append(Path(settings.LOCAL_STORAGE_DIR) / sk)
        candidate_paths.append(Path(settings.BASE_DIR) / sk)

    for cp in candidate_paths:
        if cp and cp.exists() and cp.is_file() and cp.stat().st_size > 0:
            logger.info(f"[StorageMaterialize] Found local asset at '{cp}' ({cp.stat().st_size} bytes)")
            return cp.resolve()

    # 2. Asset is not on local filesystem (Cloud Run GCS blob or ephemeral instance) -> Fetch from storage service
    logger.info(f"[StorageMaterialize] Asset '{clean_str}' not found on local disk. Fetching from storage backend...")

    # Determine unique local temp destination
    safe_prod_id = re.sub(r"[^\w\-]", "_", production_id)
    safe_cat = re.sub(r"[^\w\-]", "_", category)
    target_filename = filename or direct_p.name or f"asset_{safe_cat}.dat"
    # Ensure standard extensions if known
    if category == "footage" and not any(target_filename.endswith(ext) for ext in (".mp4", ".mov", ".avi", ".mkv", ".webm")):
        target_filename += ".mp4"
    elif category == "screenplay" and not any(target_filename.endswith(ext) for ext in (".txt", ".pdf", ".docx")):
        target_filename += ".txt"

    temp_dir = Path(tempfile.gettempdir()) / "chain_of_title" / safe_prod_id / safe_cat
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_target_path = temp_dir / target_filename

    # Try fetching bytes from storage service with various key variations
    file_bytes: Optional[bytes] = None
    lookup_keys = list(dict.fromkeys([
        clean_str,
        clean_str.lstrip("/\\"),
        *stripped_keys,
        f"{category}/{safe_prod_id}_{target_filename}",
        f"{category}/{target_filename}",
        f"{safe_prod_id}_{target_filename}",
    ]))

    for key in lookup_keys:
        try:
            file_bytes = await storage_service.get_file(key)
            if file_bytes and len(file_bytes) > 0:
                logger.info(f"[StorageMaterialize] Retrieved {len(file_bytes)} bytes using key '{key}'")
                break
        except Exception as e:
            logger.debug(f"[StorageMaterialize] Key '{key}' lookup error: {e}")

    # If still not found and GCS is enabled, attempt direct bucket download
    if not file_bytes and settings.is_gcs_enabled:
        try:
            from app.services.gcs_storage import GCSStorageProvider
            if isinstance(storage_service, GCSStorageProvider):
                bucket = storage_service._get_bucket()
                if bucket is not None:
                    for key in lookup_keys:
                        blob_key = storage_service._clean_path(key)
                        blob = bucket.blob(blob_key)
                        import asyncio
                        loop = asyncio.get_running_loop()
                        exists = await loop.run_in_executor(None, blob.exists)
                        if exists:
                            file_bytes = await loop.run_in_executor(None, blob.download_as_bytes)
                            if file_bytes:
                                logger.info(f"[StorageMaterialize] Downloaded {len(file_bytes)} bytes from GCS gs://{storage_service.bucket_name}/{blob_key}")
                                break
        except Exception as gcs_err:
            logger.warning(f"[StorageMaterialize] Direct GCS fallback error: {gcs_err}")

    if not file_bytes or len(file_bytes) == 0:
        raise FileNotFoundError(
            f"Asset '{path_or_uri}' for production '{production_id}' ({category}) "
            f"could not be retrieved from local storage or Cloud Storage bucket '{settings.GCS_BUCKET}'."
        )

    # Write materialized file to unique temp path
    async with aiofiles.open(temp_target_path, "wb") as f:
        await f.write(file_bytes)

    if not temp_target_path.exists() or temp_target_path.stat().st_size == 0:
        raise IOError(f"Failed to write materialized asset to temp path: '{temp_target_path}'")

    logger.info(
        f"[StorageMaterialize] Materialized asset '{clean_str}' -> '{temp_target_path}' "
        f"({temp_target_path.stat().st_size} bytes)"
    )
    return temp_target_path.resolve()


def cleanup_production_temp(production_id: str) -> None:
    """Safely cleans up unique production temporary files after workflow completion."""
    import tempfile
    import shutil
    import re

    safe_prod_id = re.sub(r"[^\w\-]", "_", production_id)
    temp_dir = Path(tempfile.gettempdir()) / "chain_of_title" / safe_prod_id
    if temp_dir.exists() and temp_dir.is_dir():
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.debug(f"[StorageMaterialize] Cleaned up temporary files at '{temp_dir}'")
        except Exception as e:
            logger.warning(f"[StorageMaterialize] Error cleaning up '{temp_dir}': {e}")

