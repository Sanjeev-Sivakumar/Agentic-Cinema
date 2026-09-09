"""
Resolution Agent (Phase 7).

Operational triage and resolution pathway formulation agent.
Translates verified findings, risks, and evidence into clear, operational next steps:
- Prioritizes items: CRITICAL > HIGH > MEDIUM > LOW > INFO
- VISUAL_ONLY elements receive elevated review urgency
- Emits real-time SSE events over EventBus
- Maintains zero external network calls (100% offline & deterministic)
- Preserves backward-compatible formulate_resolution method
- Strictly NOT a legal decision engine
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from app.core.logging import logger
from app.models.clearance import ClearanceActionType, ClearanceRequest, ClearanceStatus
from app.models.entity import Entity, EntityClassification, RiskLevel, ResolutionStatus as EntityResolutionStatus
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.models.resolution import (
    ResolutionAction,
    ResolutionPriority,
    ResolutionResult,
    ResolutionStatus,
)
from app.models.risk import RiskAssessment
from app.models.verification import VerificationResult
from app.repositories import (
    get_entity_repo,
    get_production_repo,
    get_research_repo,
    get_resolution_repo,
    get_risk_repo,
    get_verification_repo,
)
from app.services.events import event_bus
from app.services.resolution_engine import ResolutionEngine


class ResolutionAgent:
    """
    Operational Resolution & Clearance Intelligence Agent.
    Formulates actionable next steps based on verified evidence, risk, and research.
    """

    def __init__(self):
        self._seq_counter = 0
        self._cache: Dict[str, ResolutionResult] = {}
        logger.info("[ResolutionAgent] Initialized Resolution Agent (Phase 7)")

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
        resolution_id: Optional[str] = None,
        resolution_status: Optional[str] = None,
        resolution_action: Optional[str] = None,
        resolution_priority: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProcessingEvent:
        """Publish a real-time resolution event to the EventBus."""
        self._seq_counter += 1
        active_job_id = job_id or f"res_{production_id}"

        event = ProcessingEvent(
            sequence_number=self._seq_counter,
            production_id=production_id,
            job_id=active_job_id,
            event_type=event_type,
            stage=PipelineStage.RESOLUTION,
            progress=progress,
            message=message,
            entity_id=entity_id,
            entity_name=entity_name,
            entity_type=entity_type,
            confidence=confidence,
            risk_level=risk_level,
            risk_score=risk_score,
            resolution_id=resolution_id,
            resolution_status=resolution_status,
            resolution_action=resolution_action,
            resolution_priority=resolution_priority,
            metadata=metadata or {},
        )
        await event_bus.publish(event)
        return event

    async def formulate_resolution(
        self,
        entity: Entity,
        risk: RiskAssessment,
        rights_holder: str,
    ) -> ClearanceRequest:
        """
        Legacy clearance pathway formulation (preserved for backward compatibility).
        """
        logger.info(f"[ResolutionAgent] Formulating legacy resolution for '{entity.name}' (Risk: {risk.risk_score})")

        if risk.risk_score >= 70:
            action_type = ClearanceActionType.POST_PRODUCTION_BLUR
            status = ClearanceStatus.PENDING_REVIEW
            notes = "High-risk visual finding: Recommended post-production digital blur or direct licensing agreement."
        elif risk.risk_score >= 40:
            action_type = ClearanceActionType.LICENSE_OUTREACH
            status = ClearanceStatus.IN_PROGRESS
            notes = "Moderate exposure: Outreach to rights holder for standard synchronization/display clearance."
        else:
            action_type = ClearanceActionType.FAIR_USE_ARGUMENT
            status = ClearanceStatus.APPROVED
            notes = "De minimis incidental capture eligible for fair use defense in narrative film context."

        return ClearanceRequest(
            production_id=entity.production_id,
            entity_id=entity.id,
            action_type=action_type,
            status=status,
            assigned_to="Clearance Counsel",
            rights_holder_contact=rights_holder,
            notes=notes,
        )

    def _sort_key(self, res: ResolutionResult) -> tuple:
        """
        Operational priority sorting hierarchy:
        1. Priority: CRITICAL (0) > HIGH (1) > MEDIUM (2) > LOW (3) > INFO (4)
        2. Classification: VISUAL_ONLY (0) > BOTH (1) > SCRIPT_ONLY (2) > AUDIO_ONLY (3)
        3. Risk Score descending (-risk_score)
        4. Name ascending
        """
        priority_rank = {
            ResolutionPriority.CRITICAL: 0,
            ResolutionPriority.HIGH: 1,
            ResolutionPriority.MEDIUM: 2,
            ResolutionPriority.LOW: 3,
            ResolutionPriority.INFO: 4,
        }.get(res.priority, 2)

        classification_str = res.metadata.get("classification", "VISUAL_ONLY") if res.metadata else "VISUAL_ONLY"
        classification_rank = {
            "VISUAL_ONLY": 0,
            "BOTH": 1,
            "SCRIPT_ONLY": 2,
            "AUDIO_ONLY": 3,
        }.get(classification_str.upper(), 1)

        return (priority_rank, classification_rank, -res.risk_score, res.entity_name)

    async def resolve_entity(
        self,
        entity: Entity,
        risk: Optional[RiskAssessment] = None,
        verification: Optional[VerificationResult] = None,
        research: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        force_refresh: bool = False,
    ) -> ResolutionResult:
        """
        Formulate an operational resolution recommendation for a single entity,
        enrich the entity, persist to repositories, and emit SSE events.
        """
        entity_repo = get_entity_repo()
        risk_repo = get_risk_repo()
        verification_repo = get_verification_repo()
        research_repo = get_research_repo()
        resolution_repo = get_resolution_repo()

        # Retrieve missing inputs from repositories if not supplied
        if risk is None:
            risk = await risk_repo.get_by_entity(entity.id)
        if verification is None:
            verification = await verification_repo.get_by_entity(entity.id)
        if research is None:
            res_item = await research_repo.get_by_entity(entity.id)
            if res_item:
                research = res_item.model_dump() if hasattr(res_item, "model_dump") else dict(res_item)

        # Idempotency check
        cache_key = f"{entity.id}_{risk.risk_score if risk else 0.0}_{verification.decision if verification else 'NONE'}"
        if not force_refresh and cache_key in self._cache:
            return self._cache[cache_key]

        # Deterministic resolution formulation
        result = ResolutionEngine.resolve(
            entity=entity,
            risk=risk,
            verification=verification,
            research=research,
            job_id=job_id or entity.job_id,
        )

        # Persist to repository
        await resolution_repo.save(result)

        # Enrich Entity model
        entity.resolution_id = result.resolution_id
        entity.resolution_status = result.resolution_status.value
        entity.resolution_priority = result.priority.value
        entity.resolution_action = result.recommended_action.value
        await entity_repo.update(entity)

        # Update local cache
        self._cache[cache_key] = result

        # Determine SSE Event type
        event_type = (
            EventType.RESOLUTION_ESCALATED
            if result.recommended_action == ResolutionAction.ESCALATE
            else EventType.RESOLUTION_ACTION_RECOMMENDED
        )

        await self._emit_event(
            production_id=entity.production_id,
            job_id=job_id or entity.job_id,
            event_type=event_type,
            progress=1.0,
            message=(
                f"Resolution formulated for '{entity.name}': "
                f"Status={result.resolution_status.value}, Action={result.recommended_action.value}, "
                f"Priority={result.priority.value}"
            ),
            entity_id=entity.id,
            entity_name=entity.name,
            entity_type=entity.entity_type.value if hasattr(entity.entity_type, "value") else str(entity.entity_type),
            confidence=result.confidence,
            risk_level=result.risk_level,
            risk_score=result.risk_score,
            resolution_id=result.resolution_id,
            resolution_status=result.resolution_status.value,
            resolution_action=result.recommended_action.value,
            resolution_priority=result.priority.value,
            metadata={
                "action_reason": result.action_reason,
                "replacement_suggestion": result.replacement_suggestion,
                "missing_evidence": result.missing_evidence,
                "required_information": result.required_information,
            },
        )

        return result

    async def resolve_entities(
        self,
        entities: List[Entity],
        production_id: str,
        job_id: Optional[str] = None,
        force_refresh: bool = False,
    ) -> List[ResolutionResult]:
        """
        Batch resolve all entities for a production with error isolation,
        priority sorting, and lifecycle SSE events.
        """
        if not entities:
            return []

        active_job_id = job_id or f"res_{production_id}"
        total_count = len(entities)

        # Emit RESOLUTION_STARTED
        await self._emit_event(
            production_id=production_id,
            job_id=active_job_id,
            event_type=EventType.RESOLUTION_STARTED,
            progress=0.0,
            message=f"Starting resolution formulation for {total_count} detected entities",
            metadata={"entity_count": total_count},
        )

        results: List[ResolutionResult] = []

        for idx, entity in enumerate(entities):
            progress = round((idx + 1) / total_count, 2)
            try:
                res = await self.resolve_entity(
                    entity=entity,
                    job_id=active_job_id,
                    force_refresh=force_refresh,
                )
                results.append(res)
            except Exception as e:
                logger.error(f"[ResolutionAgent] Error resolving entity '{entity.name}' ({entity.id}): {e}", exc_info=True)
                await self._emit_event(
                    production_id=production_id,
                    job_id=active_job_id,
                    event_type=EventType.RESOLUTION_FAILED,
                    progress=progress,
                    message=f"Failed to formulate resolution for entity '{entity.name}': {str(e)}",
                    entity_id=entity.id,
                    entity_name=entity.name,
                    metadata={"error": str(e)},
                )

        # Sort results according to operational priority hierarchy
        sorted_results = sorted(results, key=self._sort_key)

        # Tally metrics
        action_required_count = sum(1 for r in sorted_results if r.resolution_status == ResolutionStatus.ACTION_REQUIRED)
        human_review_count = sum(1 for r in sorted_results if r.resolution_status == ResolutionStatus.HUMAN_REVIEW)
        resolved_count = sum(1 for r in sorted_results if r.resolution_status == ResolutionStatus.RESOLVED)
        more_evidence_count = sum(1 for r in sorted_results if r.resolution_status == ResolutionStatus.MORE_EVIDENCE_REQUIRED)
        research_required_count = sum(1 for r in sorted_results if r.resolution_status == ResolutionStatus.RESEARCH_REQUIRED)
        escalated_count = sum(1 for r in sorted_results if r.recommended_action == ResolutionAction.ESCALATE)
        critical_count = sum(1 for r in sorted_results if r.priority == ResolutionPriority.CRITICAL)
        high_count = sum(1 for r in sorted_results if r.priority == ResolutionPriority.HIGH)

        # Emit RESOLUTION_COMPLETED
        await self._emit_event(
            production_id=production_id,
            job_id=active_job_id,
            event_type=EventType.RESOLUTION_COMPLETED,
            progress=1.0,
            message=(
                f"Resolution completed for {len(sorted_results)}/{total_count} entities: "
                f"{critical_count} Critical, {high_count} High priority, {action_required_count} Action Required, "
                f"{resolved_count} Resolved"
            ),
            metadata={
                "total_resolved": len(sorted_results),
                "total_entities": total_count,
                "critical_count": critical_count,
                "high_count": high_count,
                "action_required_count": action_required_count,
                "human_review_count": human_review_count,
                "resolved_count": resolved_count,
                "more_evidence_count": more_evidence_count,
                "research_required_count": research_required_count,
                "escalated_count": escalated_count,
            },
        )

        return sorted_results

    async def resolve_production(
        self,
        production_id: str,
        job_id: Optional[str] = None,
        force_refresh: bool = False,
    ) -> List[ResolutionResult]:
        """
        Formulate resolutions for all entities associated with a production.
        """
        entity_repo = get_entity_repo()
        entities = await entity_repo.list_by_production(production_id)
        return await self.resolve_entities(
            entities=entities,
            production_id=production_id,
            job_id=job_id,
            force_refresh=force_refresh,
        )


resolution_agent = ResolutionAgent()
