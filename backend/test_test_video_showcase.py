import asyncio
import os
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import cv2
from app.models.production import Production
from app.models.orchestration import WorkflowStatus, AgentStatus
from app.adk.runner import run_production_workflow
from app.repositories import (
    get_production_repo,
    get_entity_repo,
    get_evidence_repo,
    get_risk_repo,
    get_verification_repo,
    get_resolution_repo,
    get_report_repo,
    get_orchestration_repo,
)
from app.services.events import event_bus
from app.services.storage import storage_service


async def main():
    print("=" * 70)
    print("      CHAIN OF TITLE — END-TO-END TEST ON test_video.mp4")
    print("=" * 70)

    # 1. Verify video file
    video_path = "test_video.mp4"
    if not os.path.exists(video_path):
        parent_video = Path(__file__).resolve().parent.parent / "test_video.mp4"
        if parent_video.exists():
            video_path = str(parent_video)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"ERROR: Could not open video file at {video_path}")
        return

    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = total_frames / fps if fps > 0 else 0
    cap.release()

    print(f"\n[1] Video Properties:")
    print(f"    Path:       {video_path}")
    print(f"    Resolution: {int(width)}x{int(height)}")
    print(f"    FPS:        {fps:.1f}")
    print(f"    Frames:     {int(total_frames)}")
    print(f"    Duration:   {duration:.2f} seconds")

    # 2. Setup Production
    prod_id = "prod_showcase_test_video"
    prod_repo = get_production_repo()

    screenplay_text = (
        "SCENE 01 - INT. HIGH-TECH COFFEE SHOP - DAY\n"
        "Alex sits by the counter typing on an Apple MacBook.\n"
        "A cold bottle of Coca-Cola sits beside a Sony TV display.\n"
        "The barista prepares a fresh cup of Starbucks roast."
    )

    prod = Production(
        id=prod_id,
        title="Showcase Feature: The Neon Signal",
        description="Autonomous pre-clearance validation on real video footage",
        director="Jordan Vane",
        budget_tier="Studio Independent",
        footage_path=video_path,
        metadata={"script_text": screenplay_text},
    )
    await prod_repo.save(prod)
    print(f"\n[2] Bootstrapped Production:")
    print(f"    ID:    {prod.id}")
    print(f"    Title: {prod.title}")

    # 3. Subscribe to real-time events
    captured_events = []
    job_id = f"job_showcase_{int(time.time())}"

    async def event_listener():
        try:
            async for ev in event_bus.subscribe(job_id):
                captured_events.append(ev)
                print(f"    [EVENT] {ev.event_type.value:24} | {ev.message}")
                if ev.event_type.value in ("ORCHESTRATION_COMPLETED", "ORCHESTRATION_FAILED"):
                    break
        except Exception:
            pass

    listener_task = asyncio.create_task(event_listener())

    # 4. Execute Autonomous ADK Orchestration Workflow
    print(f"\n[3] Launching Autonomous ADK Orchestration (Mode: OFFLINE)...")
    start_time = time.perf_counter()

    result = await run_production_workflow(
        production_id=prod_id,
        job_id=job_id,
        screenplay_text=screenplay_text,
        video_path=video_path,
        force_refresh=True,
        mode="offline",
    )
    total_time = time.perf_counter() - start_time

    try:
        await asyncio.wait_for(listener_task, timeout=1.0)
    except asyncio.TimeoutError:
        pass

    # 5. Inspect Orchestration Results
    print(f"\n[4] Orchestration Workflow Result:")
    print(f"    Workflow ID: {result.workflow_id}")
    print(f"    Status:      {result.status.value}")
    print(f"    Duration:    {total_time:.2f}s")
    print(f"    Completed:   {', '.join(result.completed_agents)}")
    print(f"    Skipped:     {', '.join(result.skipped_agents) if result.skipped_agents else 'None'}")
    print(f"    Failed:      {', '.join(result.failed_agents) if result.failed_agents else 'None'}")

    # 6. Inspect Detected Entities & Evidence
    entity_repo = get_entity_repo()
    evidence_repo = get_evidence_repo()
    risk_repo = get_risk_repo()
    verif_repo = get_verification_repo()
    resol_repo = get_resolution_repo()
    report_repo = get_report_repo()

    entities = await entity_repo.list_by_production(prod_id)
    reports = await report_repo.list_by_production(prod_id)

    print(f"\n[5] Cross-Modal Clearance Intelligence Findings ({len(entities)} Entities Detected):")
    print("-" * 105)
    print(f"{'Entity Name':<20} | {'Type':<12} | {'Sources':<15} | {'Risk':<12} | {'Verified':<10} | {'Action':<15}")
    print("-" * 105)

    for ent in entities:
        r_assess = await risk_repo.get_by_entity(ent.id)
        risk_desc = f"{int(r_assess.risk_score)}/100 ({r_assess.risk_level.value})" if r_assess else "N/A"

        v_res = await verif_repo.get_by_entity(ent.id)
        verif_desc = v_res.status.value if v_res else "N/A"

        res_item = await resol_repo.get_by_entity(ent.id)
        action_desc = f"{res_item.recommended_action.value} ({res_item.resolution_status.value})" if res_item else "N/A"

        sources_str = ",".join([s.value if hasattr(s, "value") else str(s) for s in ent.sources])
        print(f"{ent.name:<20} | {ent.entity_type.value:<12} | {sources_str:<15} | {risk_desc:<12} | {verif_desc:<10} | {action_desc:<15}")

    print("-" * 105)

    # 7. Inspect Generated Reports & Artifacts
    print(f"\n[6] Generated Clearance Reports ({len(reports)} Report Artifacts):")
    for rep in reports:
        print(f"    Report ID:      {rep.report_id}")
        print(f"    Total Findings: {rep.total_entities}")
        print(f"    Visual Only:    {rep.visual_only_count}")
        print(f"    Both Sources:   {rep.both_count}")
        print(f"    Formats:        {list(rep.format_urls.keys())}")
        for fmt, url in rep.format_urls.items():
            print(f"      • [{fmt}]: {url}")

    print(f"\n[7] Summary KPIs:")
    if result.workflow_summary:
        ws = result.workflow_summary
        print(f"    Total Entities:       {ws.detection.get('total_entities', len(entities))}")
        print(f"    High Risk Entities:   {ws.risk.get('high', 0)}")
        print(f"    Medium Risk:          {ws.risk.get('medium', 0)}")
        print(f"    Low Risk:             {ws.risk.get('low', 0)}")
        print(f"    Human Review Needed:  {ws.resolution.get('human_review', 0)}")
        print(f"    Auto-Cleared Items:   {ws.resolution.get('cleared', 0)}")

    print(f"\n" + "=" * 70)
    print("      TEST ON test_video.mp4 COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
