import time
from pathlib import Path
from typing import Any, Dict, Optional
from app.core.logging import logger
from app.agents.text_agent import text_agent
from app.adk.context import WorkflowContext
from app.services.storage import materialize_asset_to_local
from app.services.screenplay_parser import screenplay_scene_parser


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
    screenplay_filename = "direct_input.txt"
    screenplay_bytes = len(screenplay_text.encode("utf-8")) if screenplay_text else 0

    prod = await context.production_repo.get(context.production_id)
    if not script and prod:
        if getattr(prod, "script_text", None):
            script = prod.script_text
            screenplay_filename = "production_metadata_script.txt"
            screenplay_bytes = len(script.encode("utf-8"))
        elif getattr(prod, "metadata", None) and prod.metadata.get("script_text"):
            script = prod.metadata["script_text"]
            screenplay_filename = "production_metadata_script.txt"
            screenplay_bytes = len(script.encode("utf-8"))
        elif getattr(prod, "script_path", None):
            raw_path = prod.script_path
            screenplay_filename = Path(raw_path).name
            try:
                mat_path = await materialize_asset_to_local(
                    path_or_uri=raw_path,
                    production_id=context.production_id,
                    category="screenplay",
                    filename=screenplay_filename,
                )
                screenplay_bytes = mat_path.stat().st_size
                try:
                    script = mat_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    script = mat_path.read_text(encoding="latin-1")
            except Exception as read_err:
                logger.error(f"[ADK ScreenplayTool] Failed to materialize screenplay '{raw_path}': {read_err}")
                duration = time.perf_counter() - start_time
                err_msg = f"Failed to retrieve screenplay asset '{raw_path}': {str(read_err)}"
                context.state.record_error(err_msg)
                return {
                    "status": "FAILED",
                    "error": err_msg,
                    "entity_ids": [],
                    "duration": round(duration, 3),
                }

    # If no screenplay text was provided or registered at all
    has_script_registered = bool(
        screenplay_text
        or (prod and (getattr(prod, "script_text", None) or getattr(prod, "script_path", None)))
    )

    if not script or not script.strip():
        duration = time.perf_counter() - start_time
        if has_script_registered:
            err_msg = f"Screenplay input for production '{context.production_id}' contains 0 characters."
            logger.error(f"[ADK] Stage 1 SCREENPLAY_PARSING failed: {err_msg}")
            context.state.record_error(err_msg)
            return {
                "status": "FAILED",
                "error": err_msg,
                "entity_ids": [],
                "duration": round(duration, 3),
            }
        else:
            logger.info(f"[ADK] Stage 1 SCREENPLAY_PARSING skipped (no screenplay registered)")
            return {
                "status": "SKIPPED",
                "message": "No screenplay text available for analysis",
                "entity_ids": [],
                "duration": round(duration, 3),
            }

    char_count = len(script)
    scenes = screenplay_scene_parser.parse_scenes(script)
    scene_count = len(scenes)

    logger.info(
        f"[ADK] Stage 1 SCREENPLAY_PARSING started (production_id={context.production_id}, "
        f"filename='{screenplay_filename}', bytes={screenplay_bytes}, characters={char_count}, scenes={scene_count})"
    )

    try:
        # Check idempotency: if force_refresh is False, check if script entities already exist
        if not context.force_refresh:
            existing = await context.entity_repo.list_by_production(context.production_id)
            script_entities = [
                e for e in existing
                if "SCRIPT" in [s.value if hasattr(s, "value") else str(s) for s in e.sources]
            ]
            if script_entities:
                ent_ids = [e.id for e in script_entities]
                for eid in ent_ids:
                    if eid not in context.state.entity_ids:
                        context.state.entity_ids.append(eid)
                    if eid not in context.state.screenplay_result_ids:
                        context.state.screenplay_result_ids.append(eid)
                duration = time.perf_counter() - start_time
                duration_ms = int(duration * 1000)
                logger.info(
                    f"[ADK] Stage 1 SCREENPLAY_PARSING completed entities={len(script_entities)} "
                    f"(source=cache, duration_ms={duration_ms})"
                )
                return {
                    "status": "COMPLETED",
                    "source": "cache",
                    "entities_count": len(script_entities),
                    "entity_ids": ent_ids,
                    "scene_count": scene_count,
                    "character_count": char_count,
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
        duration_ms = int(duration * 1000)
        logger.info(
            f"[ADK] Stage 1 SCREENPLAY_PARSING completed entities={len(entities)} "
            f"(character_count={char_count}, scenes={scene_count}, duration_ms={duration_ms})"
        )

        return {
            "status": "COMPLETED",
            "source": "live",
            "entities_count": len(entities),
            "entity_ids": [e.id for e in entities],
            "scene_count": scene_count,
            "character_count": char_count,
            "duration": round(duration, 3),
        }

    except Exception as e:
        duration = time.perf_counter() - start_time
        duration_ms = int(duration * 1000)
        logger.error(
            f"[ADK] Stage 1 SCREENPLAY_PARSING failed (production_id={context.production_id}, "
            f"duration_ms={duration_ms}, error={str(e)})",
            exc_info=True,
        )
        context.state.record_error(f"Screenplay analysis failed: {str(e)}")
        return {
            "status": "FAILED",
            "error": str(e),
            "entity_ids": [],
            "duration": round(duration, 3),
        }

