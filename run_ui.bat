@echo off
REM Chain of Title — Embedded Web App Launcher
REM Starts ONLY the FastAPI server serving the embedded web UI at http://127.0.0.1:8000

echo Starting Chain of Title UI at http://127.0.0.1:8000 ...
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
