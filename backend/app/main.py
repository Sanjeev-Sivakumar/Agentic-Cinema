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

import json
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from app.ui import get_judge_ui_html

@app.get("/download/sample-video", tags=["download"])
@app.get("/download/test_video1.mp4", tags=["download"])
@app.get("/download/video", tags=["download"])
async def download_sample_video():
    """Download the official benchmark sample video (test_video1.mp4) as a real file attachment."""
    candidates = [
        Path(settings.BASE_DIR) / "test_video1.mp4",
        Path("/app/test_video1.mp4"),
        Path("/app/backend/test_video1.mp4"),
        Path("test_video1.mp4"),
        Path("backend/test_video1.mp4"),
        Path(__file__).resolve().parent.parent.parent / "test_video1.mp4",
        Path(__file__).resolve().parent.parent / "test_video1.mp4",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return FileResponse(
                path=str(c.resolve()),
                media_type="video/mp4",
                filename="test_video1.mp4",
                headers={
                    "Content-Disposition": 'attachment; filename="test_video1.mp4"',
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=3600",
                },
            )
    raise HTTPException(status_code=404, detail="Sample video test_video1.mp4 not found on server.")


@app.get("/download/sample-script", tags=["download"])
@app.get("/download/benchmark-script", tags=["download"])
@app.get("/download/script", tags=["download"])
async def download_sample_script():
    """Download the official benchmark screenplay (Artificial Intelligence.txt)."""
    candidates = [
        Path(settings.BASE_DIR) / "Artificial Intelligence.txt",
        Path("/app/Artificial Intelligence.txt"),
        Path("/app/backend/Artificial Intelligence.txt"),
        Path("Artificial Intelligence.txt"),
        Path("backend/Artificial Intelligence.txt"),
        Path(__file__).resolve().parent.parent.parent / "Artificial Intelligence.txt",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return FileResponse(
                path=str(c.resolve()),
                media_type="text/plain; charset=utf-8",
                filename="Artificial Intelligence.txt",
                headers={
                    "Content-Disposition": 'attachment; filename="Artificial Intelligence.txt"',
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=3600",
                },
            )
    raise HTTPException(status_code=404, detail="Sample screenplay not found on server.")

@app.get("/benchmark/report", tags=["benchmark"])
@app.get("/benchmark-report", tags=["benchmark"])
async def get_root_benchmark_report():
    """Return pre-computed benchmark clearance report for instantaneous demonstration."""
    candidates = [
        Path("reports/rep_8cf8d48bb5a7.json"),
        Path("data/storage/reports/prod_d13bf22452/rep_83543fdf985f.json"),
        Path("data/storage/reports/test_video_e2e/rep_6f5d2e5435a0.json"),
        Path(settings.BASE_DIR) / "data" / "storage" / "reports" / "prod_d13bf22452" / "rep_83543fdf985f.json",
        Path(settings.BASE_DIR) / "reports" / "rep_83543fdf985f.json",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            try:
                with open(c, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["production_id"] = data.get("production_id") or "prod_d13bf22452"
                    return data
            except Exception as e:
                logger.warning(f"Failed to load benchmark report from {c}: {e}")

    rep_dir = Path("data/storage/reports")
    if rep_dir.exists():
        for r_file in rep_dir.glob("*/*.json"):
            try:
                with open(r_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("all_findings"):
                        return data
            except Exception:
                continue

    return JSONResponse(status_code=404, content={"detail": "Benchmark report not found."})

@app.get("/", response_class=HTMLResponse, tags=["ui"])
async def root_judge_ui():
    """Serve the interactive judge clearance evaluation UI."""
    return HTMLResponse(
        content=get_judge_ui_html(),
        status_code=200,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )



