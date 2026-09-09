"""
Chain of Title — Unified Solution Launcher
Starts both the FastAPI Backend and Vite Frontend concurrently with single-command simplicity.
"""

import os
import sys
import subprocess
import threading
import time
import signal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"

def stream_process_output(proc, prefix, color_code):
    """Stream subprocess stdout/stderr with a colored tag prefix."""
    try:
        for line in iter(proc.stdout.readline, ''):
            if not line:
                break
            clean = line.rstrip()
            if clean:
                print(f"\033[{color_code}m[{prefix}]\033[0m {clean}")
    except Exception:
        pass

def main():
    print("=" * 80)
    print("       CHAIN OF TITLE: AGENTIC PRE-CLEARANCE INTELLIGENCE SYSTEM")
    print("=" * 80)
    print(f"Project Directory : {BASE_DIR}")
    print(f"Backend Server    : http://localhost:8000  (API & Static Media)")
    print(f"Frontend UI       : http://localhost:5173  (Command Center & Frame Inspector)")
    print(f"Active Vision     : Gemini 3.5 Flash Lite")
    print(f"Active Research   : Parallel Search API (Live USPTO / Trademarks)")
    print(f"Report Directory  : {BASE_DIR / 'reports'}")
    print("=" * 80)
    print("Starting services... (Press Ctrl+C to stop both)\n")

    # Ensure reports and storage folders exist
    (BASE_DIR / "reports").mkdir(exist_ok=True)
    (BASE_DIR / "data" / "storage" / "frames").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "data" / "storage" / "reports").mkdir(parents=True, exist_ok=True)

    # 1. Start Backend FastAPI Server
    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
    ]

    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(BACKEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    t_backend = threading.Thread(
        target=stream_process_output,
        args=(backend_proc, "Backend", "36"),  # Cyan
        daemon=True,
    )
    t_backend.start()

    time.sleep(1.5)

    # 2. Start Frontend Vite Dev Server
    # On Windows, npm is npm.cmd
    npm_bin = "npm.cmd" if sys.platform.startswith("win") else "npm"

    frontend_cmd = [npm_bin, "run", "dev"]

    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=str(FRONTEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    t_frontend = threading.Thread(
        target=stream_process_output,
        args=(frontend_proc, "Frontend", "33"),  # Amber
        daemon=True,
    )
    t_frontend.start()

    print("\n\033[32m✔ Both Backend and Frontend services launched successfully!\033[0m")
    print("\033[1;37m👉 Open your browser at: http://localhost:5173\033[0m\n")

    def handle_signal(sig, frame):
        print("\nStopping Chain of Title services...")
        backend_proc.terminate()
        frontend_proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print("Backend terminated unexpectedly.")
                break
            if frontend_proc.poll() is not None:
                print("Frontend terminated unexpectedly.")
                break
    except KeyboardInterrupt:
        handle_signal(None, None)

if __name__ == "__main__":
    main()
