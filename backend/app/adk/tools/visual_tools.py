import time
from pathlib import Path
from typing import Any, Dict, Optional
from app.core.logging import logger
from app.models.analysis import AnalysisJob
from app.agents.visual_agent import visual_agent
from app.adk.context import WorkflowContext


async def analyze_visual_tool(
    context: WorkflowContext,
    video_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    ADK tool for video visual intelligence.
    Coordinates real multi-provider video analysis (Scene Detection, OCR, YOLO, Gemini Vision),
    extracts visual entities & evidence, persists records, and updates workflow state.
    """
    start_time = time.perf_counter()
    v_path = video_path

    if not v_path:
        prod = await context.production_repo.get(context.production_id)
        if prod:
            v_path = (
                getattr(prod, "footage_path", None)
                or getattr(prod, "video_path", None)
                or (getattr(prod, "metadata", None) and prod.metadata.get("video_path"))
                or (getattr(prod, "metadata", None) and prod.metadata.get("footage_path"))
            )

    if not v_path:
        duration = time.perf_counter() - start_time
        return {
            "status": "SKIPPED",
            "message": "No video footage available for analysis",
            "entity_ids": [],
            "evidence_ids": [],
            "duration": round(duration, 3),
        }

    try:
        # Check idempotency: if force_refresh is False, check if visual entities already exist
        if not context.force_refresh:
            existing_entities = await context.entity_repo.list_by_production(context.production_id)
            existing_evidence = await context.evidence_repo.list_by_production(context.production_id)
            vis_entities = [
                e for e in existing_entities
                if "VISUAL" in [s.value if hasattr(s, "value") else str(s) for s in e.sources]
            ]
            if vis_entities:
                ent_ids = [e.id for e in vis_entities]
                evi_ids = [evi.id for evi in existing_evidence]
                for eid in ent_ids:
                    if eid not in context.state.entity_ids:
                        context.state.entity_ids.append(eid)
                for evid in evi_ids:
                    if evid not in context.state.evidence_ids:
                        context.state.evidence_ids.append(evid)
                duration = time.perf_counter() - start_time
                return {
                    "status": "COMPLETED",
                    "source": "cache",
                    "entities_count": len(vis_entities),
                    "evidence_count": len(existing_evidence),
                    "entity_ids": ent_ids,
                    "evidence_ids": evi_ids,
                    "duration": round(duration, 3),
                }

        # Get or create analysis job
        job = await context.job_repo.get(context.job_id)
        if not job:
            job = AnalysisJob(
                job_id=context.job_id,
                production_id=context.production_id,
            )
            await context.job_repo.save(job)

        async def _noop_emit(*args, **kwargs):
            pass

        orig_provider = getattr(context.settings, "AI_PROVIDER", "gemini")
        if getattr(context, "mode", "offline") == "offline":
            context.settings.AI_PROVIDER = "local"

        # Retrieve screenplay context and existing script entities if available
        script_text = None
        prod = await context.production_repo.get(context.production_id)
        if prod:
            if getattr(prod, "script_text", None):
                script_text = prod.script_text
            elif getattr(prod, "metadata", None) and prod.metadata.get("script_text"):
                script_text = prod.metadata["script_text"]
            elif getattr(prod, "script_path", None):
                candidates = [
                    Path(prod.script_path),
                    Path(context.settings.LOCAL_STORAGE_DIR) / prod.script_path,
                    Path(context.settings.BASE_DIR) / prod.script_path,
                ]
                for c in candidates:
                    if c.exists() and c.is_file():
                        try:
                            script_text = c.read_text(encoding="utf-8")
                            break
                        except Exception:
                            pass

        existing_entities = await context.entity_repo.list_by_production(context.production_id)
        script_entities = [
            e.name for e in existing_entities
            if "SCRIPT" in [s.value if hasattr(s, "value") else str(s) for s in e.sources]
        ]

        try:
            results = await visual_agent.execute_visual_pipeline(
                footage_path=v_path,
                production_id=context.production_id,
                job_id=context.job_id,
                job=job,
                emit_callback=_noop_emit,
                is_cancelled=lambda: False,
                screenplay_text=script_text,
                screenplay_entities=script_entities,
            )
        finally:
            if getattr(context, "mode", "offline") == "offline":
                context.settings.AI_PROVIDER = orig_provider

        entities = results.get("entities", [])
        evidence = results.get("evidence", [])

        # Persist to repositories
        for ent in entities:
            await context.entity_repo.save(ent)
            if ent.id not in context.state.entity_ids:
                context.state.entity_ids.append(ent.id)

        for evi in evidence:
            await context.evidence_repo.save(evi)
            if evi.id not in context.state.evidence_ids:
                context.state.evidence_ids.append(evi.id)

        duration = time.perf_counter() - start_time
        return {
            "status": "COMPLETED",
            "source": "live",
            "entities_count": len(entities),
            "evidence_count": len(evidence),
            "entity_ids": [e.id for e in entities],
            "evidence_ids": [evi.id for evi in evidence],
            "duration": round(duration, 3),
        }

    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"[ADK VisualTool] Video analysis failed: {e}", exc_info=True)
        context.state.record_error(f"Visual analysis failed: {str(e)}")
        return {
            "status": "FAILED",
            "error": str(e),
            "entity_ids": [],
            "evidence_ids": [],
            "duration": round(duration, 3),
        }
