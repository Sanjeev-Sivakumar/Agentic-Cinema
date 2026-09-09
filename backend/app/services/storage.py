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
