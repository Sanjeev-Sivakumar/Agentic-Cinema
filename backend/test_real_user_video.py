import asyncio
from app.agents.root_agent import root_agent
from app.models.production import Production
from app.repositories import get_production_repo, get_job_repo, get_entity_repo
from app.models.analysis import AnalysisJob

async def main():
    prod_repo = get_production_repo()
    job_repo = get_job_repo()
    entity_repo = get_entity_repo()

    prod = Production(
        title="User Provided Test Video Showcase",
        description="Testing with real test_video.mp4",
        director="Alex Rivera",
        budget_tier="Studio Feature",
        footage_path="footage/test_video.mp4",
        script_text="SCENE 01 - INT. OFFICE - DAY\nAn agent reviews visual clearance contracts.",
    )
    await prod_repo.create(prod)

    job = AnalysisJob(
        production_id=prod.id,
        created_by="system_test",
    )
    await job_repo.create(job)

    print(f"Starting real pipeline on test_video.mp4 for prod: {prod.id}, job: {job.job_id}")

    captured_events = []
    async def listen():
        async for evt in root_agent.bus.subscribe(prod.id):
            captured_events.append(evt)
            print(f"[EVENT #{evt.sequence_number}] {evt.event_type.value} - {evt.message}")
            if evt.event_type.value in ("ANALYSIS_COMPLETED", "ANALYSIS_FAILED"):
                break

    listener_task = asyncio.create_task(listen())
    job_task = asyncio.create_task(root_agent.execute_pipeline(prod.id, job.job_id))

    await asyncio.gather(listener_task, job_task)

    final_entities = await entity_repo.list_by_production(prod.id)
    print("\n--- FINAL CANONICAL ENTITIES ---")
    for e in final_entities:
        print(f"• [{e.classification.value}] {e.name} ({e.entity_type.value}) - Risk: {e.risk_score} ({e.risk_level.value}) - Frame: {e.frame_path}")

    print(f"\nTotal events emitted: {len(captured_events)}")

if __name__ == "__main__":
    asyncio.run(main())
