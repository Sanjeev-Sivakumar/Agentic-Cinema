@echo off
REM Chain of Title - Command Line Autonomous Clearance Runner
REM Runs the full multi-agent pipeline in CMD without frontend
REM Usage:
REM   run_cli.bat
REM   run_cli.bat test_video1.mp4
REM   run_cli.bat test_video.mp4

python run_cli.py %*
