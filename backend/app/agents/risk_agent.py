"""
Risk Assessment Intelligence Agent (Phase 5).

Provides deterministic product triage classification (LOW / MEDIUM / HIGH / UNKNOWN),
computes explainable risk signals, enriches entities, and streams real-time SSE events.
NOT a legal decision engine.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.entity import Entity, EntityClassification, RiskLevel
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.models.research import ResearchResult
from app.models.risk import RiskAssessment
from app.repositories import (
    get_entity_repo,
    get_production_repo,
    get_research_repo,
    get_risk_repo,
)
from app.services.events import event_bus
from app.services.risk_scoring import calculate_risk

class RiskAssessmentAgent:
    """
    Multi-factor deterministic Risk Assessment Agent.
    Evaluates visual prominence, commercial context, music rights, visual-only status,
    research confidence, entity type, duration, and screen position.
    """

    def __init__(self):
        self._seq_counter = 0
        logger.info("[RiskAssessmentAgent] Initialized Risk Assessment Intelligence Agent")

    async def _emit_event(
        self,
        production_id: str,
        job_id: Optional[str],
        event_type: EventType,
        progress: float,
        message: str,
        entity_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        confidence: Optional[float] = None,
        risk_level: Optional[str] = None,
        risk_score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProcessingEvent:
        """Publish a real-time risk lifecycle event to the EventBus."""
        self._seq_counter += 1
        active_job_id = job_id or f"risk_{production_id}"

        event = ProcessingEvent(
            sequence_number=self._seq_counter,
            production_id=production_id,
            job_id=active_job_id,
            event_type=event_type,
            stage=PipelineStage.RISK_ASSESSMENT,
            progress=round(progress, 1),
            message=message,
            entity_id=entity_id,
            entity_name=entity_name,
            entity_type=entity_type,
            confidence=confidence,
            risk_level=risk_level,
            risk_score=risk_score,
            metadata=metadata or {},
        )
        try:
            await event_bus.publish(event)
        except Exception as e:
            logger.warning(f"[RiskAssessmentAgent] Failed to publish event: {e}")

        return event

    def _get_classification_priority(self, classification: EntityClassification) -> int:
        """
        Risk assessment target priority ordering:
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

    async def assess_entity(
        self,
        entity: Entity,
        production_id: Optional[str] = None,
        job_id: Optional[str] = None,
        research_result: Optional[ResearchResult] = None,
        force_refresh: bool = False,
        force: bool = False,
    ) -> RiskAssessment:
        """
        Perform deterministic risk triage assessment on a single entity.
        Supports idempotency: reuses cached assessment unless force_refresh=True or force=True.
        Enriches entity in entity_repo with risk_id, risk_level, risk_score, risk_confidence.
        """
        is_force = force_refresh or force
        prod_id = production_id or entity.production_id or "default"
        risk_repo = get_risk_repo()
        entity_repo = get_entity_repo()
        research_repo = get_research_repo()

        # 1. Check idempotency cache
        if not is_force:
            cached_risk = await risk_repo.get_by_entity(entity.id)
            if cached_risk:
                logger.info(f"[RiskAssessmentAgent] Returning cached assessment for '{entity.name}' ({cached_risk.risk_id})")
                return cached_risk


        # 2. Retrieve research if not provided
        res_result = research_result
        if res_result is None:
            res_result = await research_repo.get_by_entity(entity.id)

        # 3. Calculate deterministic signals & score
        assessment = calculate_risk(
            entity=entity,
            research_result=res_result,
            production_id=prod_id,
            job_id=job_id,
        )

        # 4. Emit signal calculated event
        top_signals = [s for s in assessment.signals if s.contribution > 0]
        signal_summary = ", ".join([f"{s.signal_name}(+{s.contribution:.0f})" for s in top_signals]) or "NONE"
        await self._emit_event(
            production_id=prod_id,
            job_id=job_id,
            event_type=EventType.RISK_SIGNAL_CALCULATED,
            progress=50.0,
            message=f"Risk signals evaluated for '{entity.name}': {signal_summary} (Score: {assessment.risk_score:.0f}/100)",
            entity_id=entity.id,
            entity_name=entity.name,
            entity_type=entity.entity_type.value if hasattr(entity.entity_type, "value") else str(entity.entity_type),
            confidence=assessment.confidence,
            risk_level=assessment.risk_level.value,
            risk_score=assessment.risk_score,
            metadata={
                "signals": [s.model_dump() for s in assessment.signals],
                "signal_summary": signal_summary,
                "top_signal": top_signals[0].signal_name if top_signals else None,
                "contribution": top_signals[0].contribution if top_signals else 0.0,
            },
        )

        # 5. Enrich Entity without overwriting prior detection/research fields
        entity.risk_id = assessment.risk_id
        entity.risk_level = assessment.risk_level
        entity.risk_score = assessment.risk_score
        entity.risk_confidence = assessment.confidence
        await entity_repo.update(entity)

        # 6. Save assessment to repository
        await risk_repo.save(assessment)

        return assessment

    async def assess_entities(
        self,
        entities: List[Entity],
        production_id: Optional[str] = None,
        job_id: Optional[str] = None,
        force_refresh: bool = False,
        force: bool = False,
    ) -> List[RiskAssessment]:
        """
        Batch assess entities with:
        - Strict target prioritization: VISUAL_ONLY > BOTH > SCRIPT_ONLY
        - Fault isolation (failure on 1 entity does not abort entire batch)
        - Meaningful progress tracking
        """
        is_force = force_refresh or force
        prod_id = production_id or (entities[0].production_id if entities else "default")
        if not entities:
            logger.info("[RiskAssessmentAgent] No entities provided for risk assessment")
            await self._emit_event(
                production_id=prod_id,
                job_id=job_id,
                event_type=EventType.RISK_ASSESSMENT_COMPLETED,
                progress=100.0,
                message="Risk assessment completed: 0 entities to assess",
                metadata={"entity_count": 0},
            )
            return []

        # 1. Sort by Priority (VISUAL_ONLY first, then BOTH, then SCRIPT_ONLY; then -confidence, then name)
        sorted_entities = sorted(
            entities,
            key=lambda e: (
                self._get_classification_priority(e.classification),
                -e.confidence,
                e.name,
            ),
        )

        total_count = len(sorted_entities)
        logger.info(
            f"[RiskAssessmentAgent] Starting batch risk assessment for {total_count} entities "
            f"(Priority order: {[f'{e.name}({e.classification.value if hasattr(e.classification, 'value') else e.classification})' for e in sorted_entities[:5]]})"
        )

        # 2. Emit Started Event
        await self._emit_event(
            production_id=prod_id,
            job_id=job_id,
            event_type=EventType.RISK_ASSESSMENT_STARTED,
            progress=0.0,
            message=f"Starting multi-factor triage risk assessment for {total_count} entities",
            metadata={"entity_count": total_count},
        )

        assessments: List[RiskAssessment] = []
        for idx, ent in enumerate(sorted_entities):
            pct = round(((idx + 1) / total_count) * 100.0, 1)
            try:
                assessment = await self.assess_entity(
                    entity=ent,
                    production_id=prod_id,
                    job_id=job_id,
                    force_refresh=is_force,
                )
                assessments.append(assessment)
            except Exception as ent_err:
                logger.error(f"[RiskAssessmentAgent] Failed assessing entity '{ent.name}': {ent_err}", exc_info=True)
                await self._emit_event(
                    production_id=prod_id,
                    job_id=job_id,
                    event_type=EventType.RISK_ASSESSMENT_FAILED,
                    progress=pct,
                    message=f"Risk assessment failed for entity '{ent.name}': {ent_err}",
                    entity_id=ent.id,
                    entity_name=ent.name,
                    metadata={"error": str(ent_err)},
                )

        # 3. Emit Completion Event
        await self._emit_event(
            production_id=prod_id,
            job_id=job_id,
            event_type=EventType.RISK_ASSESSMENT_COMPLETED,
            progress=100.0,
            message=f"Risk assessment completed for {len(assessments)}/{total_count} entities",
            metadata={
                "total_assessed": len(assessments),
                "total_requested": total_count,
                "high_risk_count": len([a for a in assessments if a.risk_level == RiskLevel.HIGH]),
                "medium_risk_count": len([a for a in assessments if a.risk_level == RiskLevel.MEDIUM]),
                "low_risk_count": len([a for a in assessments if a.risk_level == RiskLevel.LOW]),
                "unknown_risk_count": len([a for a in assessments if a.risk_level == RiskLevel.UNKNOWN]),
            },
        )

        return assessments

    async def assess_production(
        self,
        production_id: str,
        entity_ids: Optional[List[str]] = None,
        job_id: Optional[str] = None,
        force_refresh: bool = False,
        force: bool = False,
    ) -> List[RiskAssessment]:
        """
        Assess risk for entities within a production.
        If entity_ids is specified, filters to those entities; otherwise assesses all production entities.
        """
        is_force = force_refresh or force
        prod_repo = get_production_repo()
        production = await prod_repo.get(production_id)
        if not production:
            raise ValueError(f"Production '{production_id}' not found")

        entity_repo = get_entity_repo()
        all_entities = await entity_repo.list_by_production(production_id)

        if entity_ids:
            target_set = set(entity_ids)
            target_entities = [e for e in all_entities if e.id in target_set]
        else:
            target_entities = all_entities

        return await self.assess_entities(
            entities=target_entities,
            production_id=production_id,
            job_id=job_id,
            force_refresh=is_force,
        )


    async def assess_risk(self, entity_or_prod: Any, entity_id_or_context: Any = "") -> RiskAssessment:
        """Backward compatibility wrapper supporting both (entity, context) and (production_id, entity_id)."""
        if isinstance(entity_or_prod, Entity):
            return await self.assess_entity(entity=entity_or_prod)
        prod_id = str(entity_or_prod)
        ent_id = str(entity_id_or_context)
        entity_repo = get_entity_repo()
        entity = await entity_repo.get(ent_id)
        if not entity:
            raise ValueError(f"Entity '{ent_id}' not found")
        return await self.assess_entity(entity=entity, production_id=prod_id)


# Global singleton instance
risk_agent = RiskAssessmentAgent()
RiskAgent = RiskAssessmentAgent  # Type alias for backward compatibility
