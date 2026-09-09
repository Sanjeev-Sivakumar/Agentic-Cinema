import argparse
import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path so app imports resolve cleanly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.models.production import Production
from app.models.orchestration import AgentStatus
from app.adk.runner import run_production_workflow
from app.repositories import (
    get_production_repo,
    get_orchestration_repo,
    get_entity_repo,
    get_risk_repo,
    get_verification_repo,
    get_resolution_repo,
    get_report_repo,
    get_financial_exposure_repo,
    get_outreach_repo,
    get_remediation_repo,
)


async def cmd_orchestrate_run(args):
    prod_repo = get_production_repo()
    prod_id = args.production_id

    script_text = getattr(args, "script_text", None) or "SCENE 01 - INT. COFFEE SHOP - DAY\nArjun sits at a corner table sipping black coffee in front of a Sony TV reviewing his clearance notes."
    video_path = getattr(args, "video_path", "test_video.mp4")

    # Resolve video path across workspace root and backend directory
    v_cand = Path(video_path)
    if not v_cand.exists():
        if (Path.cwd() / video_path).exists():
            video_path = str((Path.cwd() / video_path).resolve())
        elif (Path.cwd().parent / video_path).exists():
            video_path = str((Path.cwd().parent / video_path).resolve())
        elif (Path(__file__).resolve().parent.parent.parent / video_path).exists():
            video_path = str((Path(__file__).resolve().parent.parent.parent / video_path).resolve())

    # If production doesn't exist, bootstrap a sample production for convenience
    existing_prod = await prod_repo.get(prod_id)
    if not existing_prod:
        prod = Production(
            id=prod_id,
            title="Demo Feature: Clearance Benchmark",
            description="Autonomous pre-clearance validation scene",
            footage_path=video_path,
            metadata={"script_text": script_text},
        )
        await prod_repo.save(prod)
    else:
        existing_prod.footage_path = video_path
        if not existing_prod.metadata:
            existing_prod.metadata = {}
        existing_prod.metadata["script_text"] = script_text
        await prod_repo.save(existing_prod)

    # Configure research provider for the run
    import os
    has_parallel = bool(getattr(settings, "PARALLEL_API_KEY", "") or os.getenv("PARALLEL_API_KEY", ""))
    explicit_res_prov = getattr(args, "research_provider", None)
    if explicit_res_prov:
        settings.RESEARCH_PROVIDER = explicit_res_prov
    elif args.mode == "live" and has_parallel:
        settings.RESEARCH_PROVIDER = "parallel"
    elif args.mode == "offline":
        settings.RESEARCH_PROVIDER = "local"

    print(f"Launching autonomous clearance orchestration for production '{prod_id}'...")
    print(f"Video Path: {video_path}")
    print(f"Mode: {args.mode.upper()} | Research Provider: {settings.RESEARCH_PROVIDER.upper()} | Force Refresh: {args.force_refresh}\n")

    result = await run_production_workflow(
        production_id=prod_id,
        job_id=args.job_id,
        screenplay_text=script_text,
        video_path=video_path,
        force_refresh=args.force_refresh,
        mode=args.mode,
    )

    await display_status(result, prod_id=prod_id)


async def cmd_orchestrate_status(args):
    orch_repo = get_orchestration_repo()
    latest = await orch_repo.get_latest_for_production(args.production_id)
    if not latest:
        print(f"No orchestration results found for production '{args.production_id}'")
        return

    await display_status(latest, prod_id=args.production_id)


async def display_status(result, prod_id: str = None):
    print("=" * 105)
    print("                              CHAIN OF TITLE — ORCHESTRATION RESULT")
    print("=" * 105)
    print(f"Workflow ID: {result.workflow_id}")
    print(f"Status:      {result.status.value}")
    print(f"Duration:    {result.duration:.2f}s\n")

    stages = [
        ("Screenplay", "screenplay" in result.completed_agents),
        ("Visual", "visual" in result.completed_agents),
        ("Entity Merge", "screenplay" in result.completed_agents or "visual" in result.completed_agents),
        ("Research", "research" in result.completed_agents),
        ("Risk", "risk" in result.completed_agents),
        ("Verification", "verification" in result.completed_agents),
        ("Resolution", "resolution" in result.completed_agents),
        ("Financial Exposure", "financial_exposure" in result.completed_agents),
        ("Clearance Outreach", "clearance_outreach" in result.completed_agents),
        ("Visual Remediation", "visual_remediation" in result.completed_agents),
        ("Report", "report" in result.completed_agents),
    ]

    print("Pipeline Execution Stages:")
    stage_str = "  " + "  |  ".join([f"{'✓' if c else '✗'} {lbl}" for lbl, c in stages])
    print(stage_str)

    # Detailed entities table
    p_id = prod_id or getattr(result, "production_id", None)
    if p_id:
        entity_repo = get_entity_repo()
        risk_repo = get_risk_repo()
        verif_repo = get_verification_repo()
        resol_repo = get_resolution_repo()
        report_repo = get_report_repo()
        fe_repo = get_financial_exposure_repo()
        outreach_repo = get_outreach_repo()
        remed_repo = get_remediation_repo()

        entities = await entity_repo.list_by_production(p_id)
        if entities:
            print(f"\nDetected Clearance Entities ({len(entities)} Total):")
            print("-" * 125)
            print(f"{'Entity Name':<20} | {'Type':<10} | {'Sources':<12} | {'Risk':<12} | {'Verification':<12} | {'Action':<15} | {'Financial Exp.':<18} | {'Outreach':<10} | {'Remediation':<12}")
            print("-" * 125)
            for ent in entities:
                r_assess = await risk_repo.get_by_entity(ent.id)
                risk_desc = f"{int(r_assess.risk_score)}/100 ({r_assess.risk_level.value})" if r_assess else "N/A"

                v_res = await verif_repo.get_by_entity(ent.id)
                verif_desc = v_res.status.value if v_res else "N/A"

                res_item = await resol_repo.get_by_entity(ent.id)
                action_desc = f"{res_item.recommended_action.value}" if res_item else "N/A"

                fe_item = await fe_repo.get_by_entity(ent.id)
                if fe_item and fe_item.status.value == "ESTIMATED":
                    fe_desc = f"${fe_item.estimated_low:,.0f} - ${fe_item.estimated_high:,.0f}"
                elif fe_item:
                    fe_desc = fe_item.status.value
                else:
                    fe_desc = "N/A"

                drafts = await outreach_repo.list_by_entity(ent.id)
                outreach_desc = f"{len(drafts)} draft(s)" if drafts else "None"

                proposals = await remed_repo.list_by_entity(ent.id)
                remed_desc = f"{len(proposals)} proposal(s)" if proposals else "None"

                sources_str = ",".join([s.value if hasattr(s, "value") else str(s) for s in ent.sources])
                print(f"{ent.name:<20} | {ent.entity_type.value:<10} | {sources_str:<12} | {risk_desc:<12} | {verif_desc:<12} | {action_desc:<15} | {fe_desc:<18} | {outreach_desc:<10} | {remed_desc:<12}")
            print("-" * 125)

        reports = await report_repo.list_by_production(p_id)
        if reports:
            latest_rep = reports[0]
            print(f"\nGenerated Clearance Reports (Report ID: {latest_rep.report_id}):")
            for fmt, path_url in latest_rep.format_urls.items():
                print(f"  • [{fmt}]: {path_url}")

    summary = result.workflow_summary
    if summary:
        print(f"\nSummary KPIs:")
        print(f"  Entities: {summary.detection.get('total_entities', len(result.entity_ids))} | High Risk: {summary.risk.get('high', 0)} | Medium Risk: {summary.risk.get('medium', 0)} | Low Risk: {summary.risk.get('low', 0)}")
        print(f"  Verified: {summary.verification.get('verified', 0)} | Human Review: {summary.resolution.get('human_review', 0)} | Cleared: {summary.resolution.get('cleared', 0)}")

    print("=" * 105 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Chain of Title CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # orchestrate command
    orch_parser = subparsers.add_parser("orchestrate", help="Orchestration management")
    orch_sub = orch_parser.add_subparsers(dest="subcommand", help="Orchestration subcommands")

    # orchestrate run
    run_parser = orch_sub.add_parser("run", help="Run autonomous clearance orchestration")
    run_parser.add_argument("--production-id", default="prod_demo", help="Production ID")
    run_parser.add_argument("--job-id", default=None, help="Optional Job ID")
    run_parser.add_argument("--video-path", default="test_video.mp4", help="Video footage path")
    from app.core.config import settings
    has_gemini = bool(getattr(settings, "GEMINI_API_KEY", "") and getattr(settings, "AI_PROVIDER", "gemini").lower() == "gemini")
    default_mode = "live" if has_gemini else "offline"
    run_parser.add_argument("--mode", default=default_mode, choices=["offline", "live"], help="Execution mode (live or offline)")
    run_parser.add_argument("--research-provider", default=None, choices=["local", "parallel"], help="Research provider (local or parallel)")
    run_parser.add_argument("--force-refresh", action="store_true", help="Force refresh all stages")

    # orchestrate status
    status_parser = orch_sub.add_parser("status", help="Get latest orchestration status")
    status_parser.add_argument("--production-id", default="prod_demo", help="Production ID")

    args = parser.parse_args()

    if args.command == "orchestrate":
        if args.subcommand == "run":
            asyncio.run(cmd_orchestrate_run(args))
        elif args.subcommand == "status":
            asyncio.run(cmd_orchestrate_status(args))
        else:
            orch_parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
