import argparse
import asyncio
import os
import sys
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.models.analysis import AnalysisJob
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.models.production import Production


def format_timestamp(sec: Optional[float]) -> str:
    if sec is None:
        return "00:00.00"
    mins = int(sec // 60)
    remaining = sec % 60
    return f"{mins:02d}:{remaining:05.2f}"

def render_progress_bar(percent: float, width: int = 25) -> str:
    filled = int(width * (min(100.0, max(0.0, percent)) / 100.0))
    bar = "━" * filled + " " * (width - filled)
    return f"{bar} {percent:.0f}%"

async def run_analysis(
    video_path: str,
    production_id: Optional[str] = None,
    provider: Optional[str] = None,
    frames_per_scene: Optional[int] = None,
    max_vision_frames: Optional[int] = None,
    script_text: Optional[str] = None,
):
    # Configure runtime overrides BEFORE loading services (defaults to gemini)
    settings.AI_PROVIDER = provider or getattr(settings, "AI_PROVIDER", "gemini")
    if frames_per_scene is not None:
        settings.FRAMES_PER_SCENE = frames_per_scene
    if max_vision_frames is not None:
        settings.MAX_VISION_FRAMES_PER_JOB = max_vision_frames
        settings.GEMINI_MAX_FRAMES_PER_JOB = max_vision_frames

    from app.repositories import get_job_repo, get_production_repo
    from app.agents.visual_agent import visual_agent
    from app.services import event_bus

    resolved_path = Path(video_path)
    if not resolved_path.is_absolute():
        ws_root = Path(__file__).resolve().parent.parent.parent.parent
        if (ws_root / video_path).exists():
            resolved_path = ws_root / video_path
        elif (Path(settings.LOCAL_STORAGE_DIR) / video_path).exists():
            resolved_path = Path(settings.LOCAL_STORAGE_DIR) / video_path

    print("\nCHAIN OF TITLE — PRE-CLEARANCE INTELLIGENCE")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Target Video : {resolved_path}")
    print(f"AI Provider  : {settings.AI_PROVIDER.upper()}")
    print(f"Config       : {settings.FRAMES_PER_SCENE} frames/scene, max {settings.MAX_VISION_FRAMES_PER_JOB} vision calls")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    prod_repo = get_production_repo()
    job_repo = get_job_repo()

    if not production_id:
        prod = Production(
            title=f"Analysis: {resolved_path.name}",
            footage_path=str(resolved_path),
            metadata={"cli_invocation": True},
        )
        await prod_repo.create(prod)
        production_id = prod.id

    job = AnalysisJob.create_new(production_id=production_id)
    await job_repo.create(job)

    # Live Event Handler
    findings = []

    async def cli_emit_callback(
        job: AnalysisJob,
        event_type: EventType,
        stage: Optional[PipelineStage] = None,
        progress: Optional[float] = None,
        message: str = "",
        scene_number: Optional[int] = None,
        video_timestamp: Optional[float] = None,
        entity_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        confidence: Optional[float] = None,
        risk_level: Optional[str] = None,
        risk_score: Optional[float] = None,
        frame_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        ts_str = format_timestamp(video_timestamp)
        evt_name = event_type.value if hasattr(event_type, "value") else str(event_type)

        if evt_name == "VIDEO_INGESTION_COMPLETED" and metadata:
            print(f"[1/12] Video Ingestion")
            print(f"  ✓ Video loaded: {metadata.get('width')}x{metadata.get('height')} @ {metadata.get('fps')}fps, {metadata.get('duration_seconds')}s ({metadata.get('frame_count')} frames)\n")

        elif evt_name == "SCENE_DETECTION_COMPLETED":
            count = len(metadata.get("scenes", [])) if metadata else job.scenes_detected
            print(f"[2/12] Scene Detection")
            print(f"  ✓ {job.scenes_detected} scenes detected\n")

        elif evt_name == "FRAME_EXTRACTION_COMPLETED":
            print(f"[3/12] Frame Extraction")
            print(f"  ✓ {job.frames_processed} candidate frames extracted\n")

        elif evt_name == "STAGE_STARTED" and stage == PipelineStage.OCR:
            print(f"[4/12] OCR Processing")

        elif evt_name == "OCR_COMPLETED":
            text = metadata.get("candidates", [""])[0] if metadata else ""
            if text:
                findings.append((ts_str, "OCR", f'"{text}"', confidence or 0.85))

        elif evt_name == "OBJECT_DETECTION_STARTED":
            print(f"[5/12] Object Detection (YOLO)")

        elif evt_name == "OBJECT_DETECTED":
            findings.append((ts_str, "OBJECT", message.split("Detected object: ")[-1], confidence or 0.70))

        elif evt_name == "STAGE_STARTED" and stage == PipelineStage.GEMINI_VISION:
            print(f"[6/12] Vision LLM Analysis ({settings.AI_PROVIDER.upper()})")

        elif evt_name == "ENTITY_DETECTED":
            findings.append((ts_str, "ENTITY", entity_name or "Unknown", confidence or 0.85))

        elif evt_name == "VISUAL_ONLY_DISCOVERED":
            findings.append((ts_str, "VISUAL-ONLY", f"🚨 {entity_name} (unmentioned in script)", confidence or 0.90))

    default_script = script_text or "SCENE 1: Interior coffee shop. Character drinks coffee."

    try:
        results = await visual_agent.execute_visual_pipeline(
            footage_path=str(resolved_path),
            production_id=production_id,
            job_id=job.job_id,
            job=job,
            emit_callback=cli_emit_callback,
            is_cancelled=lambda: False,
            screenplay_text=default_script,
        )

        print("\nLIVE FINDINGS SUMMARY")
        print("──────────────────────────────────────────────────")
        for ts, tag, val, conf in findings[-15:]:
            print(f"{ts}  {tag:<12}  {val} ({int(conf*100)}%)")
        print("──────────────────────────────────────────────────")
        print(f"✓ Video intelligence completed: {len(results.get('entities', []))} canonical entities detected.")
        print(f"✓ Visual-Only findings: {len(results.get('visual_only_entities', []))}\n")

    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}\n")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.analyze",
        description="Chain of Title — Real Video Intelligence Pipeline CLI",
    )
    parser.add_argument(
        "--video",
        type=str,
        default="data/storage/footage/test_video.mp4",
        help="Path to input video file (e.g. data/storage/footage/test_video.mp4)",
    )
    parser.add_argument(
        "--production-id",
        type=str,
        default=None,
        help="Production ID to attach analysis job to (creates new if omitted)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["gemini", "groq"],
        default="gemini",
        help="Vision LLM provider to use (default: gemini, optional: groq)",
    )
    parser.add_argument(
        "--frames-per-scene",
        type=int,
        default=None,
        help="Number of candidate frames to extract per scene (default: 3)",
    )
    parser.add_argument(
        "--max-vision-frames",
        type=int,
        default=None,
        help="Maximum vision frames sent to LLM for cost control (default: 8)",
    )
    parser.add_argument(
        "--script",
        type=str,
        default=None,
        help="Optional screenplay text or file path for visual-only comparison",
    )

    args = parser.parse_args()

    script_content = None
    if args.script:
        p = Path(args.script)
        if p.exists() and p.is_file():
            script_content = p.read_text(encoding="utf-8")
        else:
            script_content = args.script

    asyncio.run(
        run_analysis(
            video_path=args.video,
            production_id=args.production_id,
            provider=args.provider,
            frames_per_scene=args.frames_per_scene,
            max_vision_frames=args.max_vision_frames,
            script_text=script_content,
        )
    )

if __name__ == "__main__":
    main()
