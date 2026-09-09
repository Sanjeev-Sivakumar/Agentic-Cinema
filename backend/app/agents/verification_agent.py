"""
Verification Agent (Phase 6).

Adversarial evidence-checking agent that verifies whether available evidence
substantiates research findings and risk assessment scores.
Prioritizes entities by Risk Level (HIGH > MEDIUM > LOW > UNKNOWN) and
Classification (VISUAL_ONLY > BOTH > SCRIPT_ONLY).

Streams real-time SSE events and enriches entities with verification metadata.
Does NOT provide legal advice.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.entity import Entity, EntityClassification, RiskLevel, VerificationStatus
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.models.research import ResearchResult
from app.models.risk import RiskAssessment
from app.models.verification import VerificationCheck, VerificationDecision, VerificationResult
from app.repositories import (
    get_entity_repo,
    get_evidence_repo,
    get_production_repo,
    get_research_repo,
    get_risk_repo,
    get_verification_repo,
)
from app.services.events import event_bus
from app.services.verification_engine import verification_engine


class VerificationAgent:
    """
    Adversarial verification agent executing deterministic evidence checks,
    contradiction detection, and explainable recommendations.
    """

    def __init__(self):
        self._seq_counter = 0
        logger.info("[VerificationAgent] Initialized Verification Agent (Phase 6)")

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
        verification_decision: Optional[str] = None,
        verification_confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProcessingEvent:
        """Publish a real-time verification event to the EventBus."""
        self._seq_counter += 1
        active_job_id = job_id or f"ver_{production_id}"

        event = ProcessingEvent(
            sequence_number=self._seq_counter,
            production_id=production_id,
            job_id=active_job_id,
            event_type=event_type,
            stage=PipelineStage.VERIFICATION,
            progress=progress,
            message=message,
            entity_id=entity_id,
            entity_name=entity_name,
            entity_type=entity_type,
            confidence=confidence,
            risk_level=risk_level,
            risk_score=risk_score,
            verification_decision=verification_decision,
            verification_confidence=verification_confidence,
            metadata=metadata or {},
        )
        await event_bus.publish(event)
        return event

    def _sort_key(self, entity: Entity):
        """
        Priority sorting hierarchy:
        1. Risk Level: HIGH > MEDIUM > LOW > UNKNOWN
        2. Classification: VISUAL_ONLY > BOTH > SCRIPT_ONLY > AUDIO_ONLY
        3. Entity confidence descending
        4. Name ascending
        """
        risk_rank = {
            RiskLevel.HIGH: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.LOW: 2,
            RiskLevel.UNKNOWN: 3,
        }.get(entity.risk_level, 4)

        class_rank = {
            EntityClassification.VISUAL_ONLY: 0,
            EntityClassification.BOTH: 1,
            EntityClassification.SCRIPT_ONLY: 2,
            EntityClassification.AUDIO_ONLY: 3,
        }.get(entity.classification, 4)

        return (risk_rank, class_rank, -entity.confidence, entity.name.lower())

    async def verify_entity(
        self,
        entity: Entity,
        production_id: Optional[str] = None,
        job_id: Optional[str] = None,
        force_refresh: bool = False,
        force: bool = False,
        script_text: Optional[str] = None,
    ) -> VerificationResult:
        """
        Perform adversarial verification on a single entity.
        Supports idempotency: reuses cached verification unless force_refresh=True or force=True.
        Enriches entity in entity_repo with verification_id, verification_decision, verification_confidence.
        """
        is_force = force_refresh or force
        prod_id = production_id or entity.production_id or "default"
        ver_repo = get_verification_repo()
        entity_repo = get_entity_repo()
        research_repo = get_research_repo()
        risk_repo = get_risk_repo()
        evidence_repo = get_evidence_repo()

        # 1. Idempotency Cache Check
        if not is_force:
            cached = await ver_repo.get_by_entity(entity.id)
            if cached:
                logger.info(f"[VerificationAgent] Returning cached verification for '{entity.name}' ({cached.verification_id})")
                return cached

        try:
            # 2. Gather Evidence Records
            research = await research_repo.get_by_entity(entity.id)
            risk = await risk_repo.get_by_entity(entity.id)
            evidence_list = await evidence_repo.list_by_entity(entity.id)

            # Retrieve script if not passed
            if not script_text and prod_id:
                prod_repo = get_production_repo()
                prod = await prod_repo.get(prod_id)
                if prod and prod.script_path and Path(prod.script_path).exists():
                    try:
                        script_text = Path(prod.script_path).read_text(encoding="utf-8")
                    except Exception as e:
                        logger.warning(f"[VerificationAgent] Could not read script: {e}")

            # 3. Execute Deterministic Verification Engine
            result = verification_engine.verify(
                entity=entity,
                research=research,
                risk=risk,
                evidence_list=evidence_list,
                script_text=script_text,
            )

            # 4. Emit Contradiction Event if detected
            if result.contradictions:
                await self._emit_event(
                    production_id=prod_id,
                    job_id=job_id,
                    event_type=EventType.VERIFICATION_CONTRADICTION_FOUND,
                    progress=50.0,
                    message=f"Contradiction found for '{entity.name}': {'; '.join(result.contradictions)}",
                    entity_id=entity.id,
                    entity_name=entity.name,
                    verification_decision=result.decision.value,
                    verification_confidence=result.confidence,
                    metadata={"contradictions": result.contradictions},
                )

            # 5. Emit Verification Check Completed
            await self._emit_event(
                production_id=prod_id,
                job_id=job_id,
                event_type=EventType.VERIFICATION_CHECK_COMPLETED,
                progress=80.0,
                message=f"Checks evaluated for '{entity.name}': {len(result.checks_run)} checks, {len(result.claims_supported)} claims supported",
                entity_id=entity.id,
                entity_name=entity.name,
                verification_decision=result.decision.value,
                verification_confidence=result.confidence,
                metadata={
                    "checks": [c.model_dump() for c in result.checks_run],
                    "claims_supported": result.claims_supported,
                    "claims_disputed": result.claims_disputed,
                },
            )

            # 6. Enrich Entity
            entity.verification_id = result.verification_id
            entity.verification_decision = result.decision.value
            entity.verification_confidence = result.confidence
            entity.verification_status = result.status
            await entity_repo.update(entity)

            # 7. Persist to Verification Repository
            await ver_repo.save(result)

            # 8. Emit Verification Completed Event
            await self._emit_event(
                production_id=prod_id,
                job_id=job_id,
                event_type=EventType.VERIFICATION_COMPLETED,
                progress=100.0,
                message=f"Verification completed for '{entity.name}': {result.decision.value} (Confidence: {result.confidence:.2f})",
                entity_id=entity.id,
                entity_name=entity.name,
                verification_decision=result.decision.value,
                verification_confidence=result.confidence,
                metadata=result.model_dump(),
            )

            return result

        except Exception as e:
            logger.error(f"[VerificationAgent] Verification error for entity '{entity.name}': {e}", exc_info=True)
            await self._emit_event(
                production_id=prod_id,
                job_id=job_id,
                event_type=EventType.VERIFICATION_FAILED,
                progress=0.0,
                message=f"Verification failed for '{entity.name}': {str(e)}",
                entity_id=entity.id,
                entity_name=entity.name,
                metadata={"error": str(e)},
            )
            # Fault isolation fallback
            fallback_res = VerificationResult(
                entity_id=entity.id,
                production_id=prod_id,
                entity_name=entity.name,
                decision=VerificationDecision.REVIEW,
                confidence=0.30,
                recommended_action=f"System check error during verification of '{entity.name}'. Manual review required.",
                notes=f"Verification error fallback: {str(e)}",
            )
            await ver_repo.save(fallback_res)
            return fallback_res

    async def verify_entities(
        self,
        entities: List[Entity],
        production_id: Optional[str] = None,
        job_id: Optional[str] = None,
        force_refresh: bool = False,
        force: bool = False,
    ) -> List[VerificationResult]:
        """
        Batch verify entities in strict priority order (HIGH > MEDIUM > LOW > UNKNOWN, VISUAL_ONLY > BOTH > SCRIPT_ONLY).
        Emits progress and handles error isolation.
        """
        is_force = force_refresh or force
        prod_id = production_id or (entities[0].production_id if entities else "default")
        if not entities:
            logger.info("[VerificationAgent] No entities provided for verification")
            return []

        sorted_entities = sorted(entities, key=self._sort_key)
        total = len(sorted_entities)

        await self._emit_event(
            production_id=prod_id,
            job_id=job_id,
            event_type=EventType.VERIFICATION_STARTED,
            progress=0.0,
            message=f"Starting verification pipeline for {total} entities (Prioritizing High Risk & Visual-Only)",
            metadata={"entity_count": total},
        )

        # Pre-read script if available
        script_text = None
        if prod_id:
            prod_repo = get_production_repo()
            prod = await prod_repo.get(prod_id)
            if prod and prod.script_path and Path(prod.script_path).exists():
                try:
                    script_text = Path(prod.script_path).read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"[VerificationAgent] Could not read script: {e}")

        results: List[VerificationResult] = []
        for idx, ent in enumerate(sorted_entities):
            res = await self.verify_entity(
                entity=ent,
                production_id=prod_id,
                job_id=job_id,
                force_refresh=is_force,
                script_text=script_text,
            )
            results.append(res)

        return results

    async def verify_production(
        self,
        production_id: str,
        job_id: Optional[str] = None,
        entity_ids: Optional[List[str]] = None,
        force_refresh: bool = False,
        force: bool = False,
    ) -> List[VerificationResult]:
        """Verify entities for an entire production."""
        entity_repo = get_entity_repo()
        all_entities = await entity_repo.list_by_production(production_id)

        if entity_ids:
            target_ids = set(entity_ids)
            target_entities = [e for e in all_entities if e.id in target_ids]
        else:
            target_entities = all_entities

        return await self.verify_entities(
            entities=target_entities,
            production_id=production_id,
            job_id=job_id,
            force_refresh=force_refresh or force,
        )

    async def verify_rights(self, entity: Entity, research_data: Dict[str, Any]) -> VerificationResult:
        """
        Backward-compatible method for pipeline integration.
        """
        rights_holder = research_data.get("rights_holder", entity.rights_holder or "Pending Verification")
        logger.info(f"[VerificationAgent] Backward-compatible verify_rights for '{entity.name}' -> {rights_holder}")

        # Run verification engine
        result = await self.verify_entity(
            entity=entity,
            production_id=entity.production_id,
            force_refresh=True,
        )
        return result


verification_agent = VerificationAgent()
