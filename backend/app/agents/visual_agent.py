import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.models.analysis import AnalysisJob
from app.models.entity import Entity, EntityClassification, EntitySource
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.models.evidence import Evidence, EvidenceType
from app.models.video import (
    ExtractedFrame,
    FrameRanking,
    OCRResult,
    ObjectDetection,
    ObjectDetectionResult,
    RankedFrame,
    Scene,
    VideoMetadata,
)
from app.services import (
    deduplication_service,
    entity_service,
    frame_extraction_service,
    frame_ranking_service,
    get_vision_provider,
    ocr_service,
    object_detection_service,
    scene_detection_service,
    screenplay_comparison_service,
    storage_service,
    video_service,
)
from app.services.video import VideoDurationLimitExceededError, VideoReadError

class VisualAgent:
    """
    ADK Visual Agent for Chain of Title.
    Coordinates the real video intelligence pipeline:
    Video Ingestion -> Scene Detection -> Candidate Frame Extraction -> OCR -> Object Detection ->
    Frame Ranking -> Vision LLM Analysis (Groq / Gemini) -> Entity Extraction -> Deduplication -> Screenplay Comparison.
    """

    def __init__(self):
        logger.info("[VisualAgent] Initialized ADK Visual Agent with multi-provider vision pipeline")

    def _resolve_footage_path(self, footage_path: str) -> str:
        """Resolve footage path against local storage and workspace without guessing fallback."""
        p = Path(footage_path)
        if p.is_absolute() and p.exists():
            return str(p)
        if p.exists():
            return str(p.resolve())

        storage_p = Path(settings.LOCAL_STORAGE_DIR) / footage_path
        if storage_p.exists():
            return str(storage_p.resolve())

        ws_root = Path(__file__).resolve().parent.parent.parent.parent
        ws_p = ws_root / footage_path
        if ws_p.exists():
            return str(ws_p.resolve())

        return footage_path

    async def execute_visual_pipeline(
        self,
        footage_path: str,
        production_id: str,
        job_id: str,
        job: AnalysisJob,
        emit_callback: Callable[..., Any],
        is_cancelled: Callable[[], bool],
        screenplay_text: Optional[str] = None,
        screenplay_entities: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute full deterministic video intelligence pipeline, emitting real-time events and progress.
        """
        resolved_path = self._resolve_footage_path(footage_path)
        results: Dict[str, Any] = {
            "metadata": None,
            "scenes": [],
            "extracted_frames": [],
            "ocr_results": {},
            "object_results": {},
            "ranked_frames": [],
            "vision_results": [],
            "entities": [],
            "visual_only_entities": [],
            "evidence": [],
            "status": "SUCCESS",
        }

        # Stage weights for progress calculation
        w_ingest = settings.STAGE_WEIGHTS.get(PipelineStage.VIDEO_INGESTION.value, 0.08) * 100
        w_scene = settings.STAGE_WEIGHTS.get(PipelineStage.SCENE_DETECTION.value, 0.10) * 100
        w_ocr = settings.STAGE_WEIGHTS.get(PipelineStage.OCR.value, 0.12) * 100
        w_obj = settings.STAGE_WEIGHTS.get(PipelineStage.OBJECT_DETECTION.value, 0.12) * 100
        w_vis = settings.STAGE_WEIGHTS.get(PipelineStage.GEMINI_VISION.value, 0.18) * 100
        w_merge = settings.STAGE_WEIGHTS.get(PipelineStage.ENTITY_MERGE.value, 0.10) * 100

        base_prog = settings.STAGE_WEIGHTS.get(PipelineStage.SCREENPLAY_EXTRACTION.value, 0.08) * 100

        # =========================================================================
        # 1. Video Ingestion
        # =========================================================================
        if is_cancelled():
            return results

        await emit_callback(
            job=job,
            event_type=EventType.VIDEO_INGESTION_STARTED,
            stage=PipelineStage.VIDEO_INGESTION,
            progress=round(base_prog, 1),
            message="Ingesting video container stream headers...",
        )

        logger.info(
            f"[ADK] Stage 2 VIDEO_INGESTION started (production_id={production_id}, "
            f"filename='{Path(resolved_path).name}', resolved_path='{resolved_path}')"
        )

        try:
            metadata: VideoMetadata = video_service.inspect_video(resolved_path)
            results["metadata"] = metadata
        except (FileNotFoundError, VideoReadError, VideoDurationLimitExceededError) as e:
            logger.error(f"[ADK] Stage 2 VIDEO_INGESTION failed: {e}")
            await emit_callback(
                job=job,
                event_type=EventType.ANALYSIS_FAILED,
                stage=PipelineStage.VIDEO_INGESTION,
                message=f"VIDEO_READ_ERROR: {e}",
                metadata={"error": str(e)},
            )
            results["status"] = "FAILED"
            results["error"] = str(e)
            raise

        await emit_callback(
            job=job,
            event_type=EventType.VIDEO_METADATA_EXTRACTED,
            stage=PipelineStage.VIDEO_INGESTION,
            progress=round(base_prog + (w_ingest * 0.7), 1),
            message=f"Metadata extracted: {metadata.width}x{metadata.height} @ {metadata.fps}fps, {metadata.duration_seconds}s ({metadata.frame_count} frames, codec: {metadata.codec})",
            metadata=metadata.model_dump(),
        )

        base_prog += w_ingest
        await emit_callback(
            job=job,
            event_type=EventType.VIDEO_INGESTION_COMPLETED,
            stage=PipelineStage.VIDEO_INGESTION,
            progress=round(base_prog, 1),
            message=f"Video ingestion completed successfully ({metadata.filename})",
            metadata=metadata.model_dump(),
        )

        # =========================================================================
        # 2. Scene Detection
        # =========================================================================
        if is_cancelled():
            return results

        await emit_callback(
            job=job,
            event_type=EventType.SCENE_DETECTION_STARTED,
            stage=PipelineStage.SCENE_DETECTION,
            progress=round(base_prog, 1),
            message="Detecting scene cut boundaries using PySceneDetect and adaptive visual difference...",
        )

        scenes: List[Scene] = scene_detection_service.detect_scenes(
            video_path=resolved_path,
            production_id=production_id,
            job_id=job_id,
            metadata=metadata,
        )
        results["scenes"] = scenes
        job.scenes_detected = len(scenes)

        for idx, scene in enumerate(scenes):
            if is_cancelled():
                return results
            scene_prog = base_prog + (w_scene * ((idx + 1) / max(1, len(scenes))))
            await emit_callback(
                job=job,
                event_type=EventType.SCENE_DETECTED,
                stage=PipelineStage.SCENE_DETECTION,
                progress=round(scene_prog, 1),
                scene_number=scene.scene_number,
                video_timestamp=scene.start_time,
                message=f"Scene {scene.scene_number:02d} detected: {scene.start_time}s - {scene.end_time}s ({scene.duration_seconds}s duration, frames {scene.start_frame}-{scene.end_frame})",
                metadata=scene.model_dump(),
            )

        base_prog += w_scene
        await emit_callback(
            job=job,
            event_type=EventType.SCENE_DETECTION_COMPLETED,
            stage=PipelineStage.SCENE_DETECTION,
            progress=round(base_prog, 1),
            message=f"Scene detection completed: {len(scenes)} distinct scenes identified",
        )

        # =========================================================================
        # 3. Candidate Frame Extraction
        # =========================================================================
        if is_cancelled():
            return results

        await emit_callback(
            job=job,
            event_type=EventType.FRAME_EXTRACTION_STARTED,
            stage=PipelineStage.VIDEO_INGESTION,
            progress=round(base_prog, 1),
            message=f"Extracting candidate frames ({settings.FRAMES_PER_SCENE} per scene: start, middle, end)...",
        )

        extracted_frames: List[ExtractedFrame] = await frame_extraction_service.extract_scene_frames(
            video_path=resolved_path,
            scenes=scenes,
            production_id=production_id,
            job_id=job_id,
            metadata=metadata,
        )
        results["extracted_frames"] = extracted_frames
        job.frames_processed = len(extracted_frames)

        for idx, frame in enumerate(extracted_frames):
            if is_cancelled():
                return results
            web_frame_url = storage_service.get_url(frame.local_path)
            await emit_callback(
                job=job,
                event_type=EventType.FRAME_EXTRACTED,
                scene_number=frame.scene_number,
                video_timestamp=frame.video_timestamp,
                frame_path=web_frame_url,
                message=f"Extracted candidate frame at {frame.video_timestamp}s (Scene {frame.scene_number:02d}, position: {frame.position_in_scene})",
            )

        await emit_callback(
            job=job,
            event_type=EventType.FRAME_EXTRACTION_COMPLETED,
            stage=PipelineStage.VIDEO_INGESTION,
            message=f"Extracted {len(extracted_frames)} candidate frames across {len(scenes)} scenes",
        )

        # =========================================================================
        # 4. Local OCR Processing (Concurrent Frame Processing)
        # =========================================================================
        if is_cancelled():
            return results

        await emit_callback(
            job=job,
            event_type=EventType.OCR_STARTED,
            stage=PipelineStage.OCR,
            progress=round(base_prog, 1),
            message="Running fast concurrent local OCR on candidate frames...",
        )

        async def _process_single_frame_ocr(frame: ExtractedFrame):
            try:
                hits = await asyncio.to_thread(ocr_service.process_frame, frame.local_path, frame)
                return frame, hits
            except Exception as e:
                logger.warning(f"[VisualAgent] OCR_ERROR on frame {frame.frame_id}: {e}")
                return frame, []

        ocr_tasks = [_process_single_frame_ocr(f) for f in extracted_frames]
        ocr_results_list = await asyncio.gather(*ocr_tasks)

        ocr_map: Dict[str, List[OCRResult]] = {}
        for idx, (frame, ocr_hits) in enumerate(ocr_results_list):
            ocr_map[frame.frame_id] = ocr_hits
            ocr_prog = base_prog + (w_ocr * ((idx + 1) / max(1, len(extracted_frames))))

            if ocr_hits:
                top_hit = ocr_hits[0]
                await emit_callback(
                    job=job,
                    event_type=EventType.OCR_COMPLETED,
                    stage=PipelineStage.OCR,
                    progress=round(ocr_prog, 1),
                    scene_number=frame.scene_number,
                    video_timestamp=frame.video_timestamp,
                    frame_path=storage_service.get_url(frame.local_path),
                    confidence=top_hit.confidence,
                    message=f"OCR detected text at {frame.video_timestamp}s: '{top_hit.text}' (conf: {top_hit.confidence:.2f})",
                    metadata={
                        "frame_id": frame.frame_id,
                        "text_count": len(ocr_hits),
                        "candidates": [r.text for r in ocr_hits],
                        "bounding_boxes": [r.bounding_box for r in ocr_hits],
                    },
                )

        results["ocr_results"] = ocr_map
        base_prog += w_ocr
        await emit_callback(
            job=job,
            event_type=EventType.STAGE_COMPLETED,
            stage=PipelineStage.OCR,
            progress=round(base_prog, 1),
            message=f"Local OCR completed: processed {len(extracted_frames)} frames ({sum(len(v) for v in ocr_map.values())} text regions found)",
        )

        # =========================================================================
        # 5. Local Object Detection (YOLOv8n Concurrent Processing)
        # =========================================================================
        if is_cancelled():
            return results

        await emit_callback(
            job=job,
            event_type=EventType.OBJECT_DETECTION_STARTED,
            stage=PipelineStage.OBJECT_DETECTION,
            progress=round(base_prog, 1),
            message=f"Running fast candidate object detection (YOLOv8n, threshold: {settings.YOLO_CONFIDENCE_THRESHOLD})...",
        )

        async def _process_single_frame_yolo(frame: ExtractedFrame):
            try:
                hits = await asyncio.to_thread(object_detection_service.detect_objects, frame.local_path, frame)
                return frame, hits
            except Exception as e:
                logger.warning(f"[VisualAgent] OBJECT_DETECTION_ERROR on frame {frame.frame_id}: {e}")
                return frame, []

        yolo_tasks = [_process_single_frame_yolo(f) for f in extracted_frames]
        yolo_results_list = await asyncio.gather(*yolo_tasks)

        obj_map: Dict[str, List[ObjectDetection]] = {}
        for idx, (frame, obj_hits) in enumerate(yolo_results_list):
            obj_map[frame.frame_id] = obj_hits
            obj_prog = base_prog + (w_obj * ((idx + 1) / max(1, len(extracted_frames))))

            for hit in obj_hits:
                if hit.confidence >= settings.YOLO_CONFIDENCE_THRESHOLD:
                    await emit_callback(
                        job=job,
                        event_type=EventType.OBJECT_DETECTED,
                        stage=PipelineStage.OBJECT_DETECTION,
                        progress=round(obj_prog, 1),
                        scene_number=frame.scene_number,
                        video_timestamp=frame.video_timestamp,
                        frame_path=storage_service.get_url(frame.local_path),
                        confidence=hit.confidence,
                        message=f"Detected object: {hit.label} ({int(hit.confidence*100)}% conf) at {frame.video_timestamp}s",
                        metadata=hit.model_dump(),
                    )

        results["object_results"] = obj_map
        base_prog += w_obj
        await emit_callback(
            job=job,
            event_type=EventType.OBJECT_DETECTION_COMPLETED,
            stage=PipelineStage.OBJECT_DETECTION,
            progress=round(base_prog, 1),
            message=f"Object detection completed: processed {len(extracted_frames)} frames ({sum(len(v) for v in obj_map.values())} objects detected)",
        )

        # =========================================================================
        # 6. Local Frame Ranking (Cost Control & Quality Prioritization)
        # =========================================================================
        if is_cancelled():
            return results

        ranked_all: List[RankedFrame] = []
        for frame in extracted_frames:
            f_ocr = ocr_map.get(frame.frame_id, [])
            f_obj = obj_map.get(frame.frame_id, [])
            ranking = frame_ranking_service.rank_frame(frame, f_ocr, f_obj)
            ranked_all.append(ranking)

            await emit_callback(
                job=job,
                event_type=EventType.FRAME_RANKED,
                scene_number=frame.scene_number,
                video_timestamp=frame.video_timestamp,
                frame_path=storage_service.get_url(frame.local_path),
                message=f"Frame at {frame.video_timestamp}s ranked (Score: {ranking.score:.1f})",
                metadata=ranking.model_dump(),
            )

        # Select highest-value frames for Vision LLM
        selected_vision_frames: List[RankedFrame] = frame_ranking_service.select_vision_frames(ranked_all)
        results["ranked_frames"] = selected_vision_frames

        for ranked in selected_vision_frames:
            web_frame_url = storage_service.get_url(ranked.frame_path)
            await emit_callback(
                job=job,
                event_type=EventType.FRAME_SELECTED_FOR_VISION,
                scene_number=ranked.scene_number,
                video_timestamp=ranked.video_timestamp,
                frame_path=web_frame_url,
                message=f"Frame at {ranked.video_timestamp}s selected for Vision LLM (Score: {ranked.score:.1f}) - {', '.join(ranked.reasons[:2])}",
                metadata=ranked.model_dump(),
            )

        # =========================================================================
        # 7. Vision LLM Inspection (Groq / Gemini via VisionProvider abstraction)
        # =========================================================================
        if is_cancelled():
            return results

        vision_provider = get_vision_provider()
        provider_name = vision_provider.provider_name.upper()

        await emit_callback(
            job=job,
            event_type=EventType.STAGE_STARTED,
            stage=PipelineStage.GEMINI_VISION,
            progress=round(base_prog, 1),
            message=f"Initiating {provider_name} multimodal vision inspection on top-ranked frames...",
            metadata={"provider": vision_provider.provider_name},
        )

        raw_entities: List[Entity] = []
        vision_semaphore = asyncio.Semaphore(5)

        async def _inspect_frame(idx: int, ranked: RankedFrame):
            if is_cancelled():
                return []

            web_frame_url = storage_service.get_url(ranked.frame_path)
            vis_prog = base_prog + (w_vis * ((idx + 1) / max(1, len(selected_vision_frames))))

            await emit_callback(
                job=job,
                event_type=EventType.VISION_ANALYSIS_STARTED,
                stage=PipelineStage.GEMINI_VISION,
                progress=round(vis_prog, 1),
                scene_number=ranked.scene_number,
                video_timestamp=ranked.video_timestamp,
                frame_path=web_frame_url,
                message=f"{provider_name} inspecting candidate frame at {ranked.video_timestamp}s (Scene {ranked.scene_number:02d})...",
            )

            f_ocr = ocr_map.get(ranked.frame_id, [])
            f_obj = obj_map.get(ranked.frame_id, [])

            context = {
                "timestamp": ranked.video_timestamp,
                "scene_number": ranked.scene_number,
                "ocr_hints": ", ".join([r.text for r in f_ocr[:6]]),
                "obj_hints": ", ".join([(o.label or o.class_name) for o in f_obj[:6]]),
                "ocr_results": f_ocr,
                "object_results": f_obj,
                "screenplay_text": screenplay_text,
                "screenplay_entities": screenplay_entities or [],
            }

            async with vision_semaphore:
                try:
                    vision_output = await vision_provider.analyze_frame(
                        frame_path=ranked.frame_path,
                        context=context,
                    )
                except Exception as e:
                    logger.warning(f"[VisualAgent] VISION_PROVIDER_ERROR on frame {ranked.frame_id}: {e}")
                    vision_output = {"status": "ERROR", "entities": [], "error": str(e)}

            await emit_callback(
                job=job,
                event_type=EventType.VISION_ANALYSIS_COMPLETED,
                stage=PipelineStage.GEMINI_VISION,
                progress=round(vis_prog, 1),
                scene_number=ranked.scene_number,
                video_timestamp=ranked.video_timestamp,
                frame_path=web_frame_url,
                message=f"{provider_name} inspection completed for frame at {ranked.video_timestamp}s ({vision_output.get('latency_ms', 0)}ms, {len(vision_output.get('entities', []))} entities)",
                metadata=vision_output,
            )

            # Convert vision entity candidates into Entity domain models (filtering non-clearance noise)
            frame_entities: List[Entity] = []
            from app.services.clearance_filter import is_clearance_relevant
            for d in vision_output.get("entities", []):
                if not is_clearance_relevant(d):
                    logger.debug(f"[VisualAgent] Filtered non-clearance detection candidate: '{d.get('name')}'")
                    continue

                ent = entity_service.create_entity_from_detection(
                    detection=d,
                    production_id=production_id,
                    job_id=job_id,
                    scene_number=ranked.scene_number,
                    timestamp=ranked.video_timestamp,
                    frame_path=web_frame_url,
                )
                if not is_clearance_relevant(ent):
                    continue
                frame_entities.append(ent)

                await emit_callback(
                    job=job,
                    event_type=EventType.ENTITY_DETECTED,
                    entity_id=ent.id,
                    entity_name=ent.name,
                    entity_type=ent.entity_type.value,
                    confidence=ent.confidence,
                    risk_level=ent.risk_level.value,
                    risk_score=ent.risk_score,
                    scene_number=ent.scene,
                    video_timestamp=ent.timestamp,
                    frame_path=ent.frame_path,
                    message=f"Potential clearance-relevant entity detected: '{ent.name}' ({ent.entity_type.value}, {int(ent.confidence*100)}% conf)",
                )

            return frame_entities

        frame_tasks = [_inspect_frame(idx, r) for idx, r in enumerate(selected_vision_frames)]
        all_inspections = await asyncio.gather(*frame_tasks, return_exceptions=True)
        for item in all_inspections:
            if isinstance(item, list):
                raw_entities.extend(item)
            elif isinstance(item, Exception):
                logger.error(f"[VisualAgent] Vision frame inspection task error: {item}")

        base_prog += w_vis
        await emit_callback(
            job=job,
            event_type=EventType.STAGE_COMPLETED,
            stage=PipelineStage.GEMINI_VISION,
            progress=round(base_prog, 1),
            message=f"{provider_name} vision inspection complete: {len(raw_entities)} visual entity occurrences extracted",
        )

        # =========================================================================
        # 8. Entity Deduplication
        # =========================================================================
        if is_cancelled():
            return results

        canonical_entities, merged_pairs = deduplication_service.deduplicate_entities(raw_entities)
        for canon, duplicate in merged_pairs:
            await emit_callback(
                job=job,
                event_type=EventType.ENTITY_DEDUPLICATED,
                entity_id=canon.id,
                entity_name=canon.name,
                scene_number=duplicate.scene,
                video_timestamp=duplicate.timestamp,
                message=f"Deduplicated '{duplicate.name}' (Scene {duplicate.scene}) into canonical '{canon.name}' (appearance #{canon.appearances})",
            )

        results["entities"] = canonical_entities
        job.entities_detected = len(canonical_entities)

        logger.info(
            f"[ADK] Stage 3 VISUAL_PERCEPTION completed detections={len(raw_entities)} "
            f"canonical_entities={len(canonical_entities)} (ranked_frames={len(selected_vision_frames)})"
        )

        # =========================================================================
        # 9. Screenplay Comparison (VISUAL-ONLY FINDINGS)
        # =========================================================================
        if is_cancelled():
            return results

        if screenplay_text is not None:
            await emit_callback(
                job=job,
                event_type=EventType.STAGE_STARTED,
                stage=PipelineStage.ENTITY_MERGE,
                progress=round(base_prog, 1),
                message="Cross-referencing detected footage entities with screenplay script tokens...",
            )

            all_compared, visual_only_findings = screenplay_comparison_service.compare_against_screenplay(
                footage_entities=canonical_entities,
                screenplay_text=screenplay_text,
            )
            results["entities"] = all_compared
            results["visual_only_entities"] = visual_only_findings
            job.visual_only_count = len(visual_only_findings)

            # Signature Visual-Only Event Emission
            for v_ent in visual_only_findings:
                await emit_callback(
                    job=job,
                    event_type=EventType.VISUAL_ONLY_DISCOVERED,
                    entity_id=v_ent.id,
                    entity_name=v_ent.name,
                    entity_type=v_ent.entity_type.value,
                    confidence=v_ent.confidence,
                    risk_level=v_ent.risk_level.value,
                    risk_score=v_ent.risk_score,
                    scene_number=v_ent.scene,
                    video_timestamp=v_ent.timestamp,
                    frame_path=v_ent.frame_path,
                    message=f"🚨 VISUAL-ONLY FINDING: '{v_ent.name}' detected in footage but absent from screenplay (Scene {v_ent.scene or 1}, {v_ent.timestamp or 0.0}s)",
                )

            base_prog += w_merge
            await emit_callback(
                job=job,
                event_type=EventType.STAGE_COMPLETED,
                stage=PipelineStage.ENTITY_MERGE,
                progress=round(base_prog, 1),
                message=f"Screenplay cross-referencing complete: {len(visual_only_findings)} visual-only findings isolated",
            )

        return results

visual_agent = VisualAgent()
