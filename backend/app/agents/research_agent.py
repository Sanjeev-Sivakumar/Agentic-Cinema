from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.entity import Entity, EntityClassification
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.models.research import ResearchResult, ResearchStatus
from app.repositories import (
    get_entity_repo,
    get_evidence_repo,
    get_research_repo,
)
from app.services.events import event_bus
from app.services.research_provider import (
    ResearchProvider,
    get_research_provider,
    query_builder,
)

class ResearchAgent:
    """
    Research Intelligence Agent (Phase 4).
    Coordinates factual rights-holder discovery, trademark checks, and evidence gathering
    for detected entities (prioritizing VISUAL_ONLY > BOTH > SCRIPT_ONLY).
    """

    def __init__(self, provider: Optional[ResearchProvider] = None):
        self.provider = provider
        self.query_builder = query_builder
        self._seq_counter = 0
        logger.info("[ResearchAgent] Initialized Research Intelligence Agent")

    async def _emit_event(
        self,
        production_id: str,
        job_id: Optional[str],
        event_type: EventType,
        progress: float,
        message: str,
        entity_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProcessingEvent:
        """Publish a real-time research lifecycle event to the EventBus."""
        self._seq_counter += 1
        active_job_id = job_id or f"research_{production_id}"

        event = ProcessingEvent(
            sequence_number=self._seq_counter,
            production_id=production_id,
            job_id=active_job_id,
            event_type=event_type,
            stage=PipelineStage.PARALLEL_RESEARCH,
            progress=round(progress, 1),
            message=message,
            entity_name=entity_name,
            entity_type=entity_type,
            confidence=confidence,
            metadata=metadata or {},
        )
        try:
            await event_bus.publish(event)
        except Exception as e:
            logger.warning(f"[ResearchAgent] Failed to publish event: {e}")

        return event

    def _get_classification_priority(self, classification: EntityClassification) -> int:
        """
        Research target priority ordering:
        1. VISUAL_ONLY (0 - highest priority)
        2. BOTH (1)
        3. SCRIPT_ONLY (2)
        4. Other (3)
        """
        if classification == EntityClassification.VISUAL_ONLY:
            return 0
        elif classification == EntityClassification.BOTH:
            return 1
        elif classification == EntityClassification.SCRIPT_ONLY:
            return 2
        return 3

    async def research_entity(
        self,
        entity: Entity,
        job_id: Optional[str] = None,
        force_refresh: bool = False,
        provider: Optional[ResearchProvider] = None,
    ) -> ResearchResult:
        """
        Conduct factual research on a single entity.
        Supports idempotency: reuses cached results unless force_refresh=True.
        Enriches entity in entity_repo with research metadata without altering detection signals.
        """
        production_id = entity.production_id or "global"
        research_repo = get_research_repo()
        entity_repo = get_entity_repo()
        evidence_repo = get_evidence_repo()

        # 1. Check idempotency cache
        if not force_refresh:
            cached = await research_repo.get_by_entity(entity.id)
            if cached:
                logger.info(f"[ResearchAgent] Reusing cached research for entity '{entity.name}' ({entity.id})")
                return cached

        # 2. Build Query & Emit Event
        active_provider = provider or self.provider or get_research_provider()

        query_str = self.query_builder.build_query(
            entity_name=entity.name,
            entity_type=entity.entity_type.value,
            context=entity.context,
        )

        await self._emit_event(
            production_id=production_id,
            job_id=job_id,
            event_type=EventType.RESEARCH_QUERY_BUILT,
            progress=0.0,
            message=f"Constructed research query for '{entity.name}': {query_str}",
            entity_name=entity.name,
            entity_type=entity.entity_type.value,
            metadata={"query": query_str, "provider": active_provider.provider_name},
        )

        # 3. Execute Provider
        try:
            result = await active_provider.research_entity(
                entity_name=entity.name,
                entity_type=entity.entity_type.value,
                context=entity.context,
                production_id=production_id,
                job_id=job_id,
                entity_id=entity.id,
                force_refresh=force_refresh,
            )
        except Exception as prov_err:
            logger.error(f"[ResearchAgent] Provider execution failed for '{entity.name}': {prov_err}")
            result = ResearchResult(
                production_id=production_id,
                job_id=job_id,
                entity_id=entity.id,
                entity_name=entity.name,
                entity_type=entity.entity_type.value,
                status=ResearchStatus.API_ERROR,
                candidate_rights_holder=None,
                identity_confidence=0.0,
                research_confidence=0.0,
                evidence=[],
                query=query_str,
                provider=active_provider.provider_name,
                notes=str(prov_err),
            )

        # 4. Emit Result Received Event
        await self._emit_event(
            production_id=production_id,
            job_id=job_id,
            event_type=EventType.RESEARCH_RESULT_RECEIVED,
            progress=50.0,
            message=f"Research result for '{entity.name}': {result.status.value} (Candidate: {result.candidate_rights_holder or 'None'})",
            entity_name=entity.name,
            entity_type=entity.entity_type.value,
            confidence=result.research_confidence,
            metadata={
                "status": result.status.value,
                "candidate_rights_holder": result.candidate_rights_holder,
                "evidence_count": len(result.evidence),
            },
        )

        # 5. Persist Evidence & Emit Found Events
        for evi in result.evidence:
            evi.entity_id = entity.id
            evi.production_id = production_id
            evi.job_id = job_id
            await evidence_repo.create(evi)
            if evi.id not in entity.evidence_ids:
                entity.evidence_ids.append(evi.id)

            await self._emit_event(
                production_id=production_id,
                job_id=job_id,
                event_type=EventType.RESEARCH_EVIDENCE_FOUND,
                progress=75.0,
                message=f"Evidence found for '{entity.name}': {evi.claim[:80]}",
                entity_name=entity.name,
                entity_type=entity.entity_type.value,
                confidence=evi.confidence,
                metadata={"claim": evi.claim, "source_type": evi.source_type},
            )

        # 6. Enrich Entity without altering original detection signals
        entity.research_status = result.status.value
        entity.candidate_rights_holder = result.candidate_rights_holder
        if result.candidate_rights_holder and not entity.rights_holder:
            entity.rights_holder = result.candidate_rights_holder
        entity.research_confidence = result.research_confidence
        await entity_repo.update(entity)

        # 7. Save to Research Repository
        await research_repo.save(result)

        return result

    async def research_entities(
        self,
        entities: List[Entity],
        production_id: str,
        job_id: Optional[str] = None,
        force_refresh: bool = False,
        provider: Optional[ResearchProvider] = None,
    ) -> List[ResearchResult]:
        """
        Research multiple entities according to operational triage priority:
        VISUAL_ONLY > BOTH > SCRIPT_ONLY.
        Provides intra-batch deduplication, failure isolation, and event telemetry.
        """
        if not entities:
            logger.info(f"[ResearchAgent] No entities provided for research in production {production_id}")
            return []

        # 1. Sort entities according to strict clearance priority hierarchy
        sorted_entities = sorted(
            entities,
            key=lambda e: (
                self._get_classification_priority(e.classification),
                -(e.risk_score or 0.0),
                e.name.lower(),
            ),
        )

        total_count = len(sorted_entities)
        await self._emit_event(
            production_id=production_id,
            job_id=job_id,
            event_type=EventType.RESEARCH_STARTED,
            progress=0.0,
            message=f"Starting clearance research across {total_count} sorted candidate entities",
            metadata={"total_entities": total_count},
        )

        results: List[ResearchResult] = []
        name_to_result_cache: Dict[str, ResearchResult] = {}

        # 2. Iterate and execute research with fault isolation
        for idx, ent in enumerate(sorted_entities, start=1):
            norm_name = ent.name.lower().strip()
            calc_progress = round((idx / total_count) * 100.0, 1)

            try:
                # Deduplication within batch: if same entity already researched, share result
                if not force_refresh and norm_name in name_to_result_cache:
                    cached_result = name_to_result_cache[norm_name]
                    logger.info(f"[ResearchAgent] Sharing batch research for duplicate entity '{ent.name}'")
                    # Enrich this specific entity instance
                    ent.research_status = cached_result.status.value
                    ent.candidate_rights_holder = cached_result.candidate_rights_holder
                    ent.research_confidence = cached_result.research_confidence
                    await get_entity_repo().update(ent)
                    results.append(cached_result)
                    continue

                # Execute individual entity research
                res = await self.research_entity(
                    entity=ent,
                    job_id=job_id,
                    force_refresh=force_refresh,
                    provider=provider,
                )

                name_to_result_cache[norm_name] = res
                results.append(res)

            except Exception as ent_err:
                logger.error(f"[ResearchAgent] Error researching entity '{ent.name}': {ent_err}")
                # Fault isolation: record failure result, continue pipeline
                fail_res = ResearchResult(
                    production_id=production_id,
                    job_id=job_id,
                    entity_id=ent.id,
                    entity_name=ent.name,
                    entity_type=ent.entity_type.value,
                    status=ResearchStatus.API_ERROR,
                    candidate_rights_holder=None,
                    identity_confidence=0.0,
                    research_confidence=0.0,
                    evidence=[],
                    notes=f"Failed with exception: {ent_err}",
                )
                results.append(fail_res)

        # 3. Emit Completion Event
        success_count = sum(1 for r in results if r.status == ResearchStatus.SUCCESS)
        await self._emit_event(
            production_id=production_id,
            job_id=job_id,
            event_type=EventType.RESEARCH_COMPLETED,
            progress=100.0,
            message=f"Research completed: {success_count}/{total_count} entities resolved with candidate rights holders",
            metadata={"total": total_count, "success": success_count},
        )

        return results

research_agent = ResearchAgent()
