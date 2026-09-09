from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.logging import logger
from app.api import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure local directories exist
    storage_dir = Path(settings.LOCAL_STORAGE_DIR)
    storage_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"[Chain of Title] Backend started in '{settings.APP_ENV}' mode (Storage: {settings.STORAGE_BACKEND}, DB: {settings.DATABASE_BACKEND})")
    yield
    logger.info("[Chain of Title] Backend shutting down gracefully")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Agentic Pre-Clearance Intelligence System for Film, Advertising, and Media Productions",
    lifespan=lifespan,
)

# Configure CORS
origins = settings.get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint
@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "HEALTHY",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "storage_backend": settings.STORAGE_BACKEND,
        "database_backend": settings.DATABASE_BACKEND,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

# Mount local storage directory for static assets (frames, footage)
storage_dir = Path(settings.LOCAL_STORAGE_DIR)
storage_dir.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=str(storage_dir)), name="storage")

# Mount base directory for direct video playback (e.g. test_video1.mp4)
app.mount("/media", StaticFiles(directory=str(settings.BASE_DIR)), name="media")

# Mount reports directory in project folder
reports_dir = Path(settings.BASE_DIR) / "reports"
reports_dir.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(reports_dir)), name="reports")

# Register all API routes
app.include_router(api_router)

from fastapi.responses import HTMLResponse
from app.ui import get_judge_ui_html

@app.get("/", response_class=HTMLResponse, tags=["ui"])
async def root_judge_ui():
    """Serve the interactive judge clearance evaluation UI."""
    return HTMLResponse(content=get_judge_ui_html(), status_code=200)


