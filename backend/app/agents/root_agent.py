import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from app.core.config import settings
from app.core.logging import logger
from app.models.analysis import AnalysisJob, JobStatus, StageStatus
from app.models.entity import Entity, EntityClassification, EntitySource
from app.models.evidence import Evidence, EvidenceType
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.models.production import Production
from app.services import (
    event_bus,
    screenplay_comparison_service,
    storage_service,
)
from app.agents.visual_agent import visual_agent
from app.agents.text_agent import text_agent
from app.agents.research_agent import research_agent
from app.agents.risk_agent import risk_agent
from app.agents.verification_agent import verification_agent
from app.agents.resolution_agent import resolution_agent
from app.agents.report_agent import report_agent
from app.repositories import (
    get_production_repo,
    get_job_repo,
    get_entity_repo,
    get_evidence_repo,
    get_risk_repo,
    get_verification_repo,
    get_clearance_repo,
)

class RootAgent:
    """
    Google ADK Root Agent for Chain of Title.
    Orchestrates the specialized agent modules across the 12-stage pre-clearance pipeline.
    Emits real-time ProcessingEvents through the EventBus and maintains Job state.
    """

    def __init__(self):
        self.bus = event_bus
        self.production_repo = get_production_repo()
        self.job_repo = get_job_repo()
        self.entity_repo = get_entity_repo()
        self.evidence_repo = get_evidence_repo()
        self.risk_repo = get_risk_repo()
        self.verification_repo = get_verification_repo()
        self.clearance_repo = get_clearance_repo()
        self._cancelled_jobs: Set[str] = set()
        self._seq_counter: int = 0

    def cancel_job(self, job_id: str) -> bool:
        """Flag job for cooperative cancellation."""
        self._cancelled_jobs.add(job_id)
        logger.info(f"[RootAgent] Marked job {job_id} for cancellation")
        return True

    def is_cancelled(self, job_id: str) -> bool:
        return job_id in self._cancelled_jobs

    async def emit_event(
        self,
        job: AnalysisJob,
        event_type: EventType,
        stage: Optional[PipelineStage] = None,
        progress: Optional[float] = None,
        message: str = "",
        scene_number: Optional[int] = None,
        video_timestamp: Optional[float] = None,
        entity_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        confidence: Optional[float] = None,
        risk_level: Optional[str] = None,
        risk_score: Optional[float] = None,
        frame_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProcessingEvent:
        if progress is not None:
            job.progress = round(progress, 1)

        self._seq_counter += 1

        event = ProcessingEvent(
            sequence_number=self._seq_counter,
            production_id=job.production_id,
            job_id=job.job_id,
            event_type=event_type,
            stage=stage,
            progress=job.progress,
            message=message,
            scene_number=scene_number,
            video_timestamp=video_timestamp,
            entity_id=entity_id,
            entity_name=entity_name,
            entity_type=entity_type,
            confidence=confidence,
            risk_level=risk_level,
            risk_score=risk_score,
            frame_path=frame_path,
            metadata=metadata or {},
        )

        # Update stage state on job
        if stage and stage.value in job.stages:
            stage_state = job.stages[stage.value]
            stage_state.latest_event = message
            if event_type == EventType.STAGE_STARTED:
                stage_state.status = StageStatus.RUNNING
                stage_state.started_at = datetime.now(timezone.utc)
            elif event_type == EventType.STAGE_COMPLETED:
                stage_state.status = StageStatus.COMPLETED
                stage_state.completed_at = datetime.now(timezone.utc)
                stage_state.progress = 100.0
                if stage_state.started_at and stage_state.completed_at:
                    delta = stage_state.completed_at - stage_state.started_at
                    stage_state.duration_ms = int(delta.total_seconds() * 1000)
            elif event_type == EventType.ANALYSIS_FAILED:
                stage_state.status = StageStatus.FAILED

        if stage:
            job.current_stage = stage.value

        await self.job_repo.update(job)
        await self.bus.publish(event)
        return event

    async def execute_pipeline(self, production_id: str, job_id: str) -> AnalysisJob:
        """
        Main execution loop for the real analysis pipeline.
        Orchestrates deterministic video intelligence services, multimodal Gemini inspection,
        and agentic risk evaluation.
        """
        job = await self.job_repo.get(job_id)
        if not job:
            raise ValueError(f"Analysis job {job_id} not found")

        production = await self.production_repo.get(production_id)
        if not production:
            raise ValueError(f"Production {production_id} not found")

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        await self.job_repo.update(job)

        await self.emit_event(
            job=job,
            event_type=EventType.ANALYSIS_STARTED,
            progress=0.0,
            message=f"Starting Chain of Title pre-clearance analysis for '{production.title}'",
        )

        accumulated_progress = 0.0

        try:
            # Check cancellation
            if self.is_cancelled(job_id):
                return await self._handle_cancellation(job)

            # =========================================================================
            # Stage 1: Screenplay Extraction
            # =========================================================================
            await self.emit_event(
                job=job,
                event_type=EventType.STAGE_STARTED,
                stage=PipelineStage.SCREENPLAY_EXTRACTION,
                message="Parsing screenplay text tokens and narrative entity references...",
            )

            script_text = ""
            if production.script_path and Path(production.script_path).exists():
                try:
                    script_text = Path(production.script_path).read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"[RootAgent] Could not read script from path: {e}")

            if not script_text:
                script_text = "SCENE 01 - INT. COFFEE SHOP - DAY\nArjun enters a bustling coffee shop and orders an iced Americano."

            accumulated_progress += settings.STAGE_WEIGHTS.get(PipelineStage.SCREENPLAY_EXTRACTION.value, 0.08) * 100
            await self.emit_event(
                job=job,
                event_type=EventType.STAGE_COMPLETED,
                stage=PipelineStage.SCREENPLAY_EXTRACTION,
                progress=accumulated_progress,
                message=f"Screenplay parsed successfully ({len(script_text)} characters)",
            )

            # =========================================================================
            # Stages 2 - 6: Visual Pipeline (Ingestion -> Scene Detection -> Frame Extraction -> OCR -> YOLO -> Gemini)
            # =========================================================================
            footage_path = production.footage_path or "demo_data/sample_footage.mp4"

            # Execute real visual pipeline through VisualAgent
            visual_results = await visual_agent.execute_visual_pipeline(
                footage_path=footage_path,
                production_id=production_id,
                job_id=job_id,
                job=job,
                emit_callback=self.emit_event,
                is_cancelled=lambda: self.is_cancelled(job_id),
            )

            if self.is_cancelled(job_id):
                return await self._handle_cancellation(job)

            raw_visual_entities: List[Entity] = visual_results.get("entities", [])

            # Update accumulated progress after visual pipeline
            visual_weight = sum([
                settings.STAGE_WEIGHTS.get(PipelineStage.VIDEO_INGESTION.value, 0.08),
                settings.STAGE_WEIGHTS.get(PipelineStage.SCENE_DETECTION.value, 0.10),
                settings.STAGE_WEIGHTS.get(PipelineStage.OCR.value, 0.12),
                settings.STAGE_WEIGHTS.get(PipelineStage.OBJECT_DETECTION.value, 0.12),
                settings.STAGE_WEIGHTS.get(PipelineStage.GEMINI_VISION.value, 0.18),
            ]) * 100
            accumulated_progress += visual_weight
            job.progress = accumulated_progress
            await self.job_repo.update(job)

            # =========================================================================
            # Stage 7: Entity Merge & Screenplay Comparison (VISUAL-ONLY FINDINGS)
            # =========================================================================
            if self.is_cancelled(job_id):
                return await self._handle_cancellation(job)

            await self.emit_event(
                job=job,
                event_type=EventType.STAGE_STARTED,
                stage=PipelineStage.ENTITY_MERGE,
                message="Cross-referencing detected footage entities with screenplay script tokens...",
            )

            # Compare against screenplay
            updated_entities, visual_only_findings = screenplay_comparison_service.compare_against_screenplay(
                footage_entities=raw_visual_entities,
                screenplay_text=script_text,
            )

            job.visual_only_count = len(visual_only_findings)

            # Emit VISUAL_ONLY_DISCOVERED events
            for v_ent in visual_only_findings:
                await self.emit_event(
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
                    message=f"🚨 VISUAL-ONLY FINDING: '{v_ent.name}' detected in footage but unmentioned in screenplay (Scene {v_ent.scene or 1}, {v_ent.timestamp or 0.0}s)",
                )

            # Persist canonical entities
            for ent in updated_entities:
                await self.entity_repo.create(ent)
                # Create evidence record
                if ent.frame_path:
                    evi = Evidence(
                        production_id=production_id,
                        entity_id=ent.id,
                        job_id=job_id,
                        evidence_type=EvidenceType.VIDEO_FRAME,
                        timestamp=ent.timestamp,
                        scene_number=ent.scene,
                        frame_path=ent.frame_path,
                        confidence=ent.confidence,
                    )
                    await self.evidence_repo.create(evi)

            accumulated_progress += settings.STAGE_WEIGHTS.get(PipelineStage.ENTITY_MERGE.value, 0.10) * 100
            await self.emit_event(
                job=job,
                event_type=EventType.STAGE_COMPLETED,
                stage=PipelineStage.ENTITY_MERGE,
                progress=accumulated_progress,
                message=f"Entity merge complete: {len(updated_entities)} canonical entities ({len(visual_only_findings)} Visual-Only)",
            )

            # =========================================================================
            # Stage 8: Parallel Research
            # =========================================================================
            if self.is_cancelled(job_id):
                return await self._handle_cancellation(job)

            await self.emit_event(
                job=job,
                event_type=EventType.STAGE_STARTED,
                stage=PipelineStage.PARALLEL_RESEARCH,
                message="Researching corporate rights holders and trademark registries via Parallel API...",
            )

            research_records = {}
            for ent in updated_entities:
                res = await research_agent.research_entity(ent, job_id=job.job_id)
                research_records[ent.id] = res
                rights_holder = getattr(res, "candidate_rights_holder", None) or (res.get("rights_holder") if hasattr(res, "get") else None)
                if rights_holder:
                    ent.rights_holder = rights_holder
                await self.entity_repo.update(ent)

                res_meta = res.model_dump() if hasattr(res, "model_dump") else res
                await self.emit_event(
                    job=job,
                    event_type=EventType.RESEARCH_COMPLETED,
                    entity_id=ent.id,
                    entity_name=ent.name,
                    video_timestamp=ent.timestamp,
                    message=f"Research completed for '{ent.name}': Owner identified as '{ent.rights_holder}'",
                    metadata=res_meta,
                )

            job.research_completed = len(updated_entities)
            accumulated_progress += settings.STAGE_WEIGHTS.get(PipelineStage.PARALLEL_RESEARCH.value, 0.08) * 100
            await self.emit_event(
                job=job,
                event_type=EventType.STAGE_COMPLETED,
                stage=PipelineStage.PARALLEL_RESEARCH,
                progress=accumulated_progress,
                message="Parallel research queries completed across all detected entities",
            )

            # =========================================================================
            # Stage 9: Risk Assessment
            # =========================================================================
            if self.is_cancelled(job_id):
                return await self._handle_cancellation(job)

            await self.emit_event(
                job=job,
                event_type=EventType.STAGE_STARTED,
                stage=PipelineStage.RISK_ASSESSMENT,
                message="Evaluating trademark exposure, fair use defensibility, and liability scores...",
            )

            risk_records = {}
            for ent in updated_entities:
                risk_res = await risk_agent.assess_risk(ent)
                risk_records[ent.id] = risk_res
                ent.risk_level = risk_res.overall_risk_level
                ent.risk_score = risk_res.risk_score
                await self.risk_repo.create(risk_res)
                await self.entity_repo.update(ent)

                await self.emit_event(
                    job=job,
                    event_type=EventType.RISK_CALCULATED,
                    entity_id=ent.id,
                    entity_name=ent.name,
                    risk_level=ent.risk_level.value,
                    risk_score=ent.risk_score,
                    video_timestamp=ent.timestamp,
                    message=f"Risk calculated for '{ent.name}': {ent.risk_level.value} ({ent.risk_score:.0f}/100)",
                    metadata=risk_res.model_dump(),
                )

            accumulated_progress += settings.STAGE_WEIGHTS.get(PipelineStage.RISK_ASSESSMENT.value, 0.06) * 100
            await self.emit_event(
                job=job,
                event_type=EventType.STAGE_COMPLETED,
                stage=PipelineStage.RISK_ASSESSMENT,
                progress=accumulated_progress,
                message="Multi-factor risk assessment completed",
            )

            # =========================================================================
            # Stage 10: Rights Verification
            # =========================================================================
            if self.is_cancelled(job_id):
                return await self._handle_cancellation(job)

            await self.emit_event(
                job=job,
                event_type=EventType.STAGE_STARTED,
                stage=PipelineStage.VERIFICATION,
                message="Verifying chain of title against official registry databases...",
            )

            for ent in updated_entities:
                ver_res = await verification_agent.verify_rights(ent, research_records.get(ent.id, {}))
                ent.verification_status = ver_res.status
                await self.verification_repo.create(ver_res)
                await self.entity_repo.update(ent)

                await self.emit_event(
                    job=job,
                    event_type=EventType.VERIFICATION_COMPLETED,
                    entity_id=ent.id,
                    entity_name=ent.name,
                    video_timestamp=ent.timestamp,
                    message=f"Rights verified for '{ent.name}': {ver_res.status.value} ({ver_res.rights_holder})",
                    metadata=ver_res.model_dump(),
                )

            job.verification_completed = len(updated_entities)
            accumulated_progress += settings.STAGE_WEIGHTS.get(PipelineStage.VERIFICATION.value, 0.04) * 100
            await self.emit_event(
                job=job,
                event_type=EventType.STAGE_COMPLETED,
                stage=PipelineStage.VERIFICATION,
                progress=accumulated_progress,
                message="Chain of title verification completed",
            )

            # =========================================================================
            # Stage 11: Resolution Pathways
            # =========================================================================
            if self.is_cancelled(job_id):
                return await self._handle_cancellation(job)

            await self.emit_event(
                job=job,
                event_type=EventType.STAGE_STARTED,
                stage=PipelineStage.RESOLUTION,
                message="Formulating actionable remediation pathways and legal recommendations...",
            )

            for ent in updated_entities:
                clr_req = await resolution_agent.formulate_resolution(
                    entity=ent,
                    risk=risk_records.get(ent.id),
                    rights_holder=ent.rights_holder or "Pending Verification",
                )
                await self.clearance_repo.create(clr_req)

                try:
                    await resolution_agent.resolve_entity(
                        entity=ent,
                        risk=risk_records.get(ent.id),
                        job_id=job.job_id,
                    )
                except Exception as ex:
                    logger.warning(f"[RootAgent] Phase 7 resolution formulation error for '{ent.name}': {ex}")

                await self.entity_repo.update(ent)

                await self.emit_event(
                    job=job,
                    event_type=EventType.RESOLUTION_COMPLETED,
                    entity_id=ent.id,
                    entity_name=ent.name,
                    video_timestamp=ent.timestamp,
                    message=f"Resolution pathway formulated for '{ent.name}': {ent.resolution_action or clr_req.action_type.value}",
                    metadata=clr_req.model_dump(),
                )

            accumulated_progress += settings.STAGE_WEIGHTS.get(PipelineStage.RESOLUTION.value, 0.02) * 100
            await self.emit_event(
                job=job,
                event_type=EventType.STAGE_COMPLETED,
                stage=PipelineStage.RESOLUTION,
                progress=accumulated_progress,
                message="Clearance resolution pathways established",
            )

            # =========================================================================
            # Stage 12: Report Generation
            # =========================================================================
            if self.is_cancelled(job_id):
                return await self._handle_cancellation(job)

            await self.emit_event(
                job=job,
                event_type=EventType.STAGE_STARTED,
                stage=PipelineStage.REPORT_GENERATION,
                message="Compiling final pre-clearance intelligence audit certificate and checklist...",
            )

            rep = await report_agent.generate_report(
                production=production,
                job=job,
                entities=updated_entities,
            )

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.progress = 100.0
            await self.job_repo.update(job)

            await self.emit_event(
                job=job,
                event_type=EventType.REPORT_GENERATED,
                stage=PipelineStage.REPORT_GENERATION,
                progress=100.0,
                message=f"Pre-clearance audit report generated ({len(updated_entities)} total entities, {len(visual_only_findings)} visual-only)",
                metadata=rep.model_dump(),
            )

            await self.emit_event(
                job=job,
                event_type=EventType.ANALYSIS_COMPLETED,
                progress=100.0,
                message="Chain of Title real video pre-clearance intelligence analysis completed successfully",
            )
            return job

        except Exception as e:
            logger.error(f"[RootAgent] Pipeline error: {e}", exc_info=True)
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now(timezone.utc)
            await self.job_repo.update(job)

            await self.emit_event(
                job=job,
                event_type=EventType.ANALYSIS_FAILED,
                progress=job.progress,
                message=f"Analysis pipeline failed: {str(e)}",
            )
            return job
        finally:
            if job_id in self._cancelled_jobs:
                self._cancelled_jobs.remove(job_id)

    async def _handle_cancellation(self, job: AnalysisJob) -> AnalysisJob:
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        await self.job_repo.update(job)

        await self.emit_event(
            job=job,
            event_type=EventType.ANALYSIS_CANCELLED,
            progress=job.progress,
            message=f"Analysis job {job.job_id} cancelled by user request.",
        )
        logger.info(f"[RootAgent] Job {job.job_id} successfully cancelled")
        return job

root_agent = RootAgent()
