import time
from pathlib import Path
from typing import Any, Dict, Optional
from app.core.logging import logger
from app.agents.text_agent import text_agent
from app.adk.context import WorkflowContext


async def analyze_screenplay_tool(
    context: WorkflowContext,
    screenplay_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    ADK tool for screenplay analysis.
    Consumes screenplay text or production screenplay asset, executes TextAgent parsing & entity extraction,
    persists entities, and updates workflow state.
    """
    start_time = time.perf_counter()
    script = screenplay_text

    if not script:
        prod = await context.production_repo.get(context.production_id)
        if prod:
            if getattr(prod, "script_text", None):
                script = prod.script_text
            elif getattr(prod, "metadata", None) and prod.metadata.get("script_text"):
                script = prod.metadata["script_text"]
            elif getattr(prod, "script_path", None):
                from app.core.config import settings
                candidates = [
                    Path(prod.script_path),
                    Path(settings.LOCAL_STORAGE_DIR) / prod.script_path,
                    Path(settings.BASE_DIR) / prod.script_path,
                ]
                for c in candidates:
                    if c.exists() and c.is_file():
                        try:
                            script = c.read_text(encoding="utf-8")
                            break
                        except Exception as e:
                            logger.warning(f"[ADK ScreenplayTool] Could not read '{c}': {e}")

    if not script or not script.strip():
        duration = time.perf_counter() - start_time
        return {
            "status": "SKIPPED",
            "message": "No screenplay text available for analysis",
            "entity_ids": [],
            "duration": round(duration, 3),
        }

    try:
        # Check idempotency: if force_refresh is False, check if script entities already exist
        if not context.force_refresh:
            existing = await context.entity_repo.list_by_production(context.production_id)
            script_entities = [e for e in existing if "SCRIPT" in [s.value if hasattr(s, "value") else str(s) for s in e.sources]]
            if script_entities:
                ent_ids = [e.id for e in script_entities]
                for eid in ent_ids:
                    if eid not in context.state.entity_ids:
                        context.state.entity_ids.append(eid)
                    if eid not in context.state.screenplay_result_ids:
                        context.state.screenplay_result_ids.append(eid)
                duration = time.perf_counter() - start_time
                return {
                    "status": "COMPLETED",
                    "source": "cache",
                    "entities_count": len(script_entities),
                    "entity_ids": ent_ids,
                    "duration": round(duration, 3),
                }

        entities = await text_agent.analyze_screenplay(
            screenplay_text=script,
            production_id=context.production_id,
            job_id=context.job_id,
        )

        for ent in entities:
            await context.entity_repo.save(ent)
            if ent.id not in context.state.entity_ids:
                context.state.entity_ids.append(ent.id)
            if ent.id not in context.state.screenplay_result_ids:
                context.state.screenplay_result_ids.append(ent.id)

        duration = time.perf_counter() - start_time
        return {
            "status": "COMPLETED",
            "source": "live",
            "entities_count": len(entities),
            "entity_ids": [e.id for e in entities],
            "duration": round(duration, 3),
        }

    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"[ADK ScreenplayTool] Screenplay analysis failed: {e}", exc_info=True)
        context.state.record_error(f"Screenplay analysis failed: {str(e)}")
        return {
            "status": "FAILED",
            "error": str(e),
            "entity_ids": [],
            "duration": round(duration, 3),
        }
