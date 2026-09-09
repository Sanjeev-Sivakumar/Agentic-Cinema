#!/usr/bin/env python
"""
Chain of Title — Command-Line (CMD) Autonomous Clearance Runner
Run directly from the command prompt:
    python run_cli.py
    python run_cli.py test_video1.mp4
    python run_cli.py test_video.mp4
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
backend_dir = BASE_DIR / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Change cwd to backend so relative paths and storage dirs resolve uniformly
os.chdir(str(backend_dir))

from cli.main import main

if __name__ == "__main__":
    # If called with no arguments, default to test_video1.mp4 (Cadbury Showcase)
    if len(sys.argv) == 1:
        print("=" * 90)
        print("       CHAIN OF TITLE: AGENTIC PRE-CLEARANCE INTELLIGENCE SYSTEM (CMD MODE)")
        print("=" * 90)
        print("No video specified. Defaulting to: test_video1.mp4 (Cadbury Dairy Milk & Sony Showcase)")
        print("AI Vision Provider     : Google Gemini Multimodal Vision")
        print("AI Research Provider   : Parallel Search API (Live USPTO / Corporate Trademarks)")
        print(f"Reports Output Folder  : {BASE_DIR / 'reports'}\n")
        sys.argv = [
            sys.argv[0],
            "orchestrate",
            "run",
            "--video-path",
            str(BASE_DIR / "test_video1.mp4"),
            "--force-refresh",
        ]
    elif len(sys.argv) == 2 and not sys.argv[1].startswith("-") and sys.argv[1].endswith((".mp4", ".mov", ".mkv", ".avi")):
        video_arg = sys.argv[1]
        resolved = (BASE_DIR / video_arg) if (BASE_DIR / video_arg).exists() else Path(video_arg)
        sys.argv = [
            sys.argv[0],
            "orchestrate",
            "run",
            "--video-path",
            str(resolved),
            "--force-refresh",
        ]

    main()

