from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "Chain of Title"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    BASE_DIR: Path = BASE_DIR
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: Union[str, List[str]] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
    ]

    # AI & Intelligence Keys
    AI_PROVIDER: str = "gemini"  # "gemini" (primary/default) or "groq" (optional)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_VISION_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_SCREENPLAY_MODEL: str = "gemini-3.5-flash-lite"
    SCREENPLAY_PROVIDER: str = "local"  # "local" (default/deterministic) or "gemini"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "qwen/qwen3.6-27b"
    PARALLEL_API_KEY: str = ""
    RESEARCH_PROVIDER: str = "parallel"  # "parallel" (live Parallel Search API) or "local"
    ADK_MODE: str = "offline"  # "offline" (default/deterministic) or "live"

    # Storage & Database Architecture
    STORAGE_BACKEND: str = "local"  # "local" or "gcs"
    DATABASE_BACKEND: str = "local"  # "local" or "firestore"
    LOCAL_STORAGE_DIR: str = str(BASE_DIR / "data" / "storage")

    # Video Pipeline & Sampling Settings (Optimized for speed & quota safety)
    FRAME_SAMPLING_MODE: str = "scene"  # "scene", "interval", "all"
    FRAMES_PER_SCENE: int = 1
    MAX_FRAMES_PER_SCENE: int = 2
    VISION_FRAMES_PER_SCENE: int = 1
    GEMINI_FRAMES_PER_SCENE: int = 1
    MAX_VISION_FRAMES_PER_JOB: int = 6
    MAX_VIDEO_DURATION_SECONDS: int = 300
    YOLO_CONFIDENCE_THRESHOLD: float = 0.45
    OBJECT_CONFIDENCE_THRESHOLD: float = 0.45
    GEMINI_MAX_FRAMES_PER_JOB: int = 6

    # Stage Progress Weights (total sum = 1.0)
    STAGE_WEIGHTS: Dict[str, float] = {
        "Screenplay Extraction": 0.08,
        "Video Ingestion": 0.08,
        "Scene Detection": 0.10,
        "OCR": 0.12,
        "Object Detection": 0.12,
        "Gemini Vision": 0.18,
        "Entity Merge": 0.10,
        "Parallel Research": 0.08,
        "Risk Assessment": 0.06,
        "Verification": 0.04,
        "Resolution": 0.02,
        "Report Generation": 0.02,
    }

    # Cloud Configuration (Future demo / cloud deployment)
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    FIRESTORE_DATABASE: str = "(default)"
    GCS_BUCKET: str = "chain-of-title-cinema-2026"
    GCS_ENABLED: bool = False
    ENABLE_FIRESTORE: bool = False
    ENABLE_CLOUD_STORAGE: bool = False

    # Google Cloud Pub/Sub Configuration
    GCP_PROJECT_ID: str = "chain-of-title-cinema-2026"
    PUBSUB_TOPIC: str = "chain-of-title-events"
    PUBSUB_ENABLED: bool = False

    # Container & Cloud Run Runtime
    PORT: Optional[int] = None

    def get_cors_origins(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return self.CORS_ORIGINS

    @property
    def effective_port(self) -> int:
        return self.PORT or self.API_PORT or 8000

    @property
    def is_local_storage(self) -> bool:
        return not self.is_gcs_enabled

    @property
    def is_gcs_enabled(self) -> bool:
        return bool(self.GCS_ENABLED or self.ENABLE_CLOUD_STORAGE or self.STORAGE_BACKEND.lower() == "gcs")

    @property
    def is_pubsub_enabled(self) -> bool:
        return bool(self.PUBSUB_ENABLED)

    @property
    def is_local_database(self) -> bool:
        return self.DATABASE_BACKEND.lower() == "local" and not self.ENABLE_FIRESTORE

    @property
    def is_firestore_enabled(self) -> bool:
        return bool(self.ENABLE_FIRESTORE or self.DATABASE_BACKEND.lower() == "firestore")

    @property
    def effective_gcp_project_id(self) -> str:
        return self.GCP_PROJECT_ID or self.GOOGLE_CLOUD_PROJECT or "chain-of-title-cinema-2026"

    @property
    def effective_gcs_bucket(self) -> str:
        return self.GCS_BUCKET or "chain-of-title-cinema-2026"

    @property
    def pubsub_topic_path(self) -> str:
        return f"projects/{self.effective_gcp_project_id}/topics/{self.PUBSUB_TOPIC}"

settings = Settings()
