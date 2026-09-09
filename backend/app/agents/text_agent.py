from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.entity import Entity, EntitySource, EntityType
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.services.clearance_filter import is_clearance_relevant
from app.services.entity_normalization import deduplicate_screenplay_entities
from app.services.events import event_bus
from app.services.screenplay_parser import ScreenplaySceneParser, screenplay_scene_parser
from app.services.screenplay_provider import ScreenplayExtractionProvider, get_screenplay_provider

class TextAgent:
    """
    Screenplay Intelligence Agent (Phase 3).
    Parses screenplay text, segments scenes, extracts clearance-relevant entities,
    filters generic noise, deduplicates across scenes, tags source='SCRIPT',
    and publishes real-time ProcessingEvents to the EventBus.
    """

    def __init__(
        self,
        scene_parser: Optional[ScreenplaySceneParser] = None,
        provider: Optional[ScreenplayExtractionProvider] = None,
    ):
        self.scene_parser = scene_parser or screenplay_scene_parser
        self.provider = provider
        self._seq_counter = 0
        logger.info("[TextAgent] Initialized Screenplay Intelligence Agent")

    async def _emit_event(
        self,
        production_id: str,
        job_id: Optional[str],
        event_type: EventType,
        progress: float,
        message: str,
        scene_number: Optional[int] = None,
        entity_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProcessingEvent:
        """Publish a real-time screenplay lifecycle event to the EventBus."""
        self._seq_counter += 1
        active_job_id = job_id or f"script_analysis_{production_id}"

        event = ProcessingEvent(
            sequence_number=self._seq_counter,
            production_id=production_id,
            job_id=active_job_id,
            event_type=event_type,
            stage=PipelineStage.SCREENPLAY_EXTRACTION,
            progress=round(progress, 1),
            message=message,
            scene_number=scene_number,
            entity_name=entity_name,
            entity_type=entity_type,
            confidence=confidence,
            metadata=metadata or {},
        )
        try:
            await event_bus.publish(event)
        except Exception as e:
            logger.warning(f"[TextAgent] Failed to publish event: {e}")

        return event

    def _map_entity_type(self, raw_type: str) -> EntityType:
        """Safely convert raw string entity type to EntityType enum."""
        norm = (raw_type or "brand").upper().strip()
        type_mapping = {
            "BRAND": EntityType.BRAND,
            "TRADEMARK": EntityType.TRADEMARK,
            "PRODUCT": EntityType.PRODUCT,
            "COMPANY": EntityType.COMPANY,
            "PUBLIC_FIGURE": EntityType.PUBLIC_FIGURE,
            "PERSON": EntityType.PERSON,
            "MUSIC": EntityType.MUSIC,
            "ARTIST": EntityType.MUSIC,
            "ARTWORK": EntityType.ARTWORK,
            "POSTER": EntityType.POSTER,
            "BOOK": EntityType.BOOK,
            "FILM": EntityType.FILM,
            "MOVIE": EntityType.FILM,
            "TV": EntityType.TV_SHOW,
            "TV_SHOW": EntityType.TV_SHOW,
            "FILM_TV": EntityType.FILM_TV,
            "LOCATION": EntityType.LOCATION,
            "SIGNAGE": EntityType.SIGNAGE,
            "VEHICLE": EntityType.VEHICLE,
        }
        return type_mapping.get(norm, EntityType.OTHER)

    async def analyze_screenplay(
        self,
        screenplay_text: str,
        production_id: str,
        job_id: Optional[str] = None,
    ) -> List[Entity]:
        """
        Execute full screenplay pre-clearance intelligence pipeline:
        1. Validates input
        2. Segments scenes
        3. Invokes extraction provider
        4. Filters non-clearance noise
        5. Normalizes and deduplicates entities
        6. Constructs canonical Entity domain records with sources=[SCRIPT]
        7. Publishes real-time SSE events
        """
        clean_text = (screenplay_text or "").strip()
        logger.info(
            f"[TextAgent] Starting screenplay analysis for production '{production_id}' "
            f"({len(clean_text)} chars)"
        )

        # 1. Emit Analysis Started
        await self._emit_event(
            production_id=production_id,
            job_id=job_id,
            event_type=EventType.SCREENPLAY_ANALYSIS_STARTED,
            progress=0.0,
            message=f"Starting screenplay analysis ({len(clean_text)} characters)",
        )

        if not clean_text:
            logger.info("[TextAgent] Screenplay text is empty; returning 0 entities")
            await self._emit_event(
                production_id=production_id,
                job_id=job_id,
                event_type=EventType.SCREENPLAY_ANALYSIS_COMPLETED,
                progress=100.0,
                message="Screenplay analysis completed: 0 entities found (empty screenplay)",
                metadata={"scene_count": 0, "entity_count": 0},
            )
            return []

        try:
            # 2. Scene Parsing
            scenes = self.scene_parser.parse_scenes(clean_text)
            total_scenes = len(scenes)

            for s in scenes:
                await self._emit_event(
                    production_id=production_id,
                    job_id=job_id,
                    event_type=EventType.SCREENPLAY_SCENE_DETECTED,
                    progress=round((s.scene_number / max(1, total_scenes)) * 25.0, 1),
                    message=f"Scene {s.scene_number} detected: {s.heading}",
                    scene_number=s.scene_number,
                    metadata={"heading": s.heading, "start_line": s.start_line, "end_line": s.end_line},
                )

            # 3. Screenplay Extraction via Provider
            active_provider = self.provider or get_screenplay_provider()
            logger.info(f"[TextAgent] Using extraction provider: {active_provider.provider_name.upper()}")

            raw_entities = await active_provider.extract_entities(clean_text, scenes=scenes)

            # 4. Clearance Filtering
            valid_candidates: List[Dict[str, Any]] = []
            for candidate in raw_entities:
                if not isinstance(candidate, dict):
                    continue

                # Filter generic noise (e.g. generic characters, furniture, ordinary props)
                if not is_clearance_relevant(candidate):
                    logger.debug(f"[TextAgent] Filtered non-clearance candidate: '{candidate.get('name')}'")
                    continue

                valid_candidates.append(candidate)

                # Emit detection event
                await self._emit_event(
                    production_id=production_id,
                    job_id=job_id,
                    event_type=EventType.SCREENPLAY_ENTITY_EXTRACTED,
                    progress=round(30.0 + (len(valid_candidates) / max(1, len(raw_entities) + 1)) * 40.0, 1),
                    message=f"Screenplay entity identified: '{candidate.get('name')}' ({candidate.get('entity_type')}) in Scene {candidate.get('scene', 1)}",
                    scene_number=candidate.get("scene", 1),
                    entity_name=candidate.get("name"),
                    entity_type=candidate.get("entity_type"),
                    confidence=candidate.get("confidence", 0.90),
                    metadata=candidate,
                )

            # 5. Normalization and Deduplication
            deduplicated_records = deduplicate_screenplay_entities(valid_candidates)

            # 6. Convert to Entity Domain Models
            entities: List[Entity] = []
            for item in deduplicated_records:
                enum_type = self._map_entity_type(item.get("entity_type", "brand"))

                entity = Entity(
                    production_id=production_id,
                    job_id=job_id,
                    name=item["name"],
                    entity_type=enum_type,
                    sources=[EntitySource.SCRIPT],
                    confidence=float(item.get("confidence", 0.90)),
                    scene=int(item.get("scene", 1)),
                    appearances=int(item.get("metadata", {}).get("occurrences", 1)),
                    context=item.get("context"),
                    clearance_type=enum_type.value,
                    metadata=item.get("metadata", {}),
                )
                entities.append(entity)

            # 7. Emit Completed Event
            await self._emit_event(
                production_id=production_id,
                job_id=job_id,
                event_type=EventType.SCREENPLAY_ANALYSIS_COMPLETED,
                progress=100.0,
                message=f"Screenplay analysis completed: {len(entities)} clearance-relevant entities across {total_scenes} scenes",
                metadata={"scene_count": total_scenes, "entity_count": len(entities)},
            )

            logger.info(
                f"[TextAgent] Successfully completed screenplay analysis for production '{production_id}': "
                f"{len(entities)} entities extracted"
            )
            return entities

        except Exception as err:
            logger.error(f"[TextAgent] Screenplay analysis error: {err}")
            await self._emit_event(
                production_id=production_id,
                job_id=job_id,
                event_type=EventType.SCREENPLAY_ANALYSIS_FAILED,
                progress=100.0,
                message=f"Screenplay analysis failed: {err}",
                metadata={"error": str(err)},
            )
            raise

    async def extract_entities(self, script_text: str, production_id: str) -> List[Entity]:
        """Backward-compatible wrapper for extract_entities."""
        return await self.analyze_screenplay(script_text, production_id)

text_agent = TextAgent()
