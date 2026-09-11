import difflib
import re
import time
from pathlib import Path
from typing import Any, Dict, List
from app.core.logging import logger
from app.models.entity import Entity, EntityClassification, EntitySource
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.services.screenplay_comparison import screenplay_comparison_service
from app.services.clearance_filter import is_clearance_relevant
from app.services.entity_normalization import entity_normalization_service
from app.services.storage import materialize_asset_to_local
from app.adk.context import WorkflowContext


def _entity_similarity(name1: str, name2: str) -> float:
    """Compute fuzzy matching score between two entity candidate names."""
    n1 = entity_normalization_service.clean_text(name1).lower()
    n2 = entity_normalization_service.clean_text(name2).lower()
    if n1 == n2:
        return 1.0

    s1 = entity_normalization_service.simplify_for_matching(name1)
    s2 = entity_normalization_service.simplify_for_matching(name2)
    if s1 and s1 == s2:
        return 1.0

    # Check canonical mapping
    c1 = entity_normalization_service.normalize_ocr_candidate(name1)
    c2 = entity_normalization_service.normalize_ocr_candidate(name2)
    if c1 and c2 and c1.get("matched_canonical") and c1.get("matched_canonical") == c2.get("matched_canonical"):
        return 1.0

    # Substring inclusion for distinctive names
    if len(s1) >= 4 and len(s2) >= 4:
        if s1 in s2 or s2 in s1:
            return 0.92

    return difflib.SequenceMatcher(None, s1, s2).ratio()


async def merge_entities_tool(
    context: WorkflowContext,
) -> Dict[str, Any]:
    """
    ADK tool for entity reconciliation, cross-modal unification, and screenplay comparison.
    Unifies entities detected across screenplay extraction and visual footage,
    eliminates duplicate records, identifies VISUAL_ONLY, BOTH, and SCRIPT_ONLY classifications,
    and publishes VISUAL_ONLY_DISCOVERED events.
    """
    start_time = time.perf_counter()
    try:
        raw_entities: List[Entity] = await context.entity_repo.list_by_production(context.production_id)
        logger.info(
            f"[ADK] Stage 4 ENTITY_MERGE started (production_id={context.production_id}, "
            f"raw_entities_count={len(raw_entities)})"
        )
        if not raw_entities:
            duration = time.perf_counter() - start_time
            logger.info(
                f"[ADK] Stage 4 ENTITY_MERGE completed entities=0 (duration_ms={int(duration * 1000)})"
            )
            return {
                "status": "COMPLETED",
                "total_entities": 0,
                "visual_only_count": 0,
                "both_count": 0,
                "script_only_count": 0,
                "entity_ids": [],
                "duration": round(duration, 3),
            }

        # Step 1: Purge non-clearance noise from entity repository
        active_entities: List[Entity] = []
        for ent in raw_entities:
            if not is_clearance_relevant(ent):
                logger.info(f"[ADK EntityMerge] Purging non-clearance artifact '{ent.name}' ({ent.id})")
                await context.entity_repo.delete(ent.id)
                continue

            # Canonical normalization if OCR corruption
            norm_res = entity_normalization_service.normalize_ocr_candidate(ent.name, confidence=ent.confidence)
            if norm_res and norm_res.get("is_normalized"):
                ent.name = norm_res["name"]
                if norm_res.get("entity_type"):
                    from app.models.entity import EntityType
                    t_val = norm_res["entity_type"].upper()
                    if hasattr(EntityType, t_val):
                        ent.entity_type = getattr(EntityType, t_val)
                await context.entity_repo.update(ent)

            active_entities.append(ent)

        # Step 2: Cross-modal entity unification (merge visual & script records of the same entity)
        merged_canonical: List[Entity] = []
        entities_to_delete: List[str] = []

        for ent in active_entities:
            if ent.id in entities_to_delete:
                continue

            target_canon = None
            for canon in merged_canonical:
                sim = _entity_similarity(ent.name, canon.name)
                is_type_compatible = (
                    canon.entity_type == ent.entity_type
                    or "brand" in (canon.entity_type.value.lower(), ent.entity_type.value.lower())
                )
                if sim >= 0.85 and is_type_compatible:
                    target_canon = canon
                    break

            if target_canon:
                # Merge duplicate entity into target canonical
                logger.info(f"[ADK EntityMerge] Unifying cross-modal duplicate '{ent.name}' ({ent.id}) into '{target_canon.name}' ({target_canon.id})")
                for s in ent.sources:
                    if s not in target_canon.sources:
                        target_canon.sources.append(s)

                target_canon.appearances += ent.appearances
                if ent.timestamp is not None:
                    if target_canon.first_seen_timestamp is None or ent.timestamp < target_canon.first_seen_timestamp:
                        target_canon.first_seen_timestamp = ent.timestamp
                    if target_canon.last_seen_timestamp is None or ent.timestamp > target_canon.last_seen_timestamp:
                        target_canon.last_seen_timestamp = ent.timestamp
                    if target_canon.timestamp is None:
                        target_canon.timestamp = ent.timestamp

                if ent.scene is not None and target_canon.scene is None:
                    target_canon.scene = ent.scene

                if ent.frame_path and not target_canon.frame_path:
                    target_canon.frame_path = ent.frame_path

                if ent.bounding_box and not target_canon.bounding_box:
                    target_canon.bounding_box = ent.bounding_box

                for ef in (ent.evidence_ids + ent.evidence_frames):
                    if ef not in target_canon.evidence_ids:
                        target_canon.evidence_ids.append(ef)
                    if ef not in target_canon.evidence_frames:
                        target_canon.evidence_frames.append(ef)

                target_canon.confidence = max(target_canon.confidence, ent.confidence)
                target_canon.risk_score = max(target_canon.risk_score, ent.risk_score)

                # Persist updated canonical entity and mark duplicate for deletion
                await context.entity_repo.update(target_canon)
                await context.entity_repo.delete(ent.id)
                entities_to_delete.append(ent.id)
            else:
                merged_canonical.append(ent)

        # Step 3: Fetch screenplay text if available and compare remaining footage entities
        script_text = ""
        prod = await context.production_repo.get(context.production_id)
        if prod:
            if getattr(prod, "script_text", None):
                script_text = prod.script_text
            elif getattr(prod, "metadata", None) and prod.metadata.get("script_text"):
                script_text = prod.metadata["script_text"]
            elif getattr(prod, "script_path", None):
                try:
                    mat_path = await materialize_asset_to_local(
                        path_or_uri=prod.script_path,
                        production_id=context.production_id,
                        category="screenplay",
                    )
                    script_text = mat_path.read_text(encoding="utf-8")
                except Exception as read_err:
                    logger.debug(f"[ADK EntityMerge] Could not read script for comparison: {read_err}")

        footage_entities = [
            e for e in merged_canonical
            if EntitySource.VISUAL in e.sources
        ]

        if footage_entities and script_text:
            updated_entities, visual_only_findings = screenplay_comparison_service.compare_against_screenplay(
                footage_entities=footage_entities,
                screenplay_text=script_text,
            )

            # Persist updated classifications
            for ue in updated_entities:
                await context.entity_repo.update(ue)

            # Emit VISUAL_ONLY_DISCOVERED events for unscripted discoveries
            for v_ent in visual_only_findings:
                event = ProcessingEvent(
                    production_id=context.production_id,
                    job_id=context.job_id,
                    event_type=EventType.VISUAL_ONLY_DISCOVERED,
                    stage=PipelineStage.ENTITY_MERGE,
                    progress=50.0,
                    message=f"[ADK Entity Merge] Visual-only exposure discovered: '{v_ent.name}' not found in screenplay!",
                    entity_id=v_ent.id,
                    entity_name=v_ent.name,
                    entity_type=v_ent.entity_type.value if hasattr(v_ent.entity_type, "value") else str(v_ent.entity_type),
                    confidence=v_ent.confidence,
                    workflow_id=context.workflow_id,
                    agent_name="Entity Merge",
                )
                await context.bus.publish(event)

        # Step 4: Refresh entity list
        refreshed_entities = await context.entity_repo.list_by_production(context.production_id)
        context.state.entity_ids = [e.id for e in refreshed_entities]

        visual_only_count = sum(
            1 for e in refreshed_entities
            if (e.classification == EntityClassification.VISUAL_ONLY or getattr(e.classification, "value", "") == "VISUAL_ONLY")
        )
        both_count = sum(
            1 for e in refreshed_entities
            if (e.classification == EntityClassification.BOTH or getattr(e.classification, "value", "") == "BOTH")
        )
        script_only_count = sum(
            1 for e in refreshed_entities
            if (e.classification == EntityClassification.SCRIPT_ONLY or getattr(e.classification, "value", "") == "SCRIPT_ONLY")
        )

        duration = time.perf_counter() - start_time
        duration_ms = int(duration * 1000)
        logger.info(
            f"[ADK] Stage 4 ENTITY_MERGE completed entities={len(refreshed_entities)} "
            f"(both={both_count}, visual_only={visual_only_count}, script_only={script_only_count}, duration_ms={duration_ms})"
        )
        return {
            "status": "COMPLETED",
            "total_entities": len(refreshed_entities),
            "visual_only_count": visual_only_count,
            "both_count": both_count,
            "script_only_count": script_only_count,
            "entity_ids": context.state.entity_ids,
            "duration": round(duration, 3),
        }

    except Exception as e:
        duration = time.perf_counter() - start_time
        duration_ms = int(duration * 1000)
        logger.error(f"[ADK] Stage 4 ENTITY_MERGE failed: {e} (duration_ms={duration_ms})", exc_info=True)
        context.state.record_error(f"Entity merge failed: {str(e)}")
        return {
            "status": "FAILED",
            "error": str(e),
            "entity_ids": context.state.entity_ids,
            "duration": round(duration, 3),
        }
