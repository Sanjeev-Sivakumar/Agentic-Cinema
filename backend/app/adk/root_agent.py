import asyncio
import time
from typing import Any, Dict, List, Optional
import google.adk as adk
from app.core.logging import logger
from app.models.orchestration import (
    AgentHandoff,
    AgentStatus,
    WorkflowStatus,
    OrchestrationResult,
)
from app.services.storage import cleanup_production_temp
from app.adk.context import WorkflowContext
from app.adk.callbacks import WorkflowCallbacks
from app.adk.tools.entity_tools import merge_entities_tool
from app.adk.tools.exposure_tools import calculate_financial_exposure_tool
from app.adk.agents.screenplay_agent import ScreenplayAgent
from app.adk.agents.visual_agent import VisualAgent
from app.adk.agents.research_agent import ResearchAgent
from app.adk.agents.risk_agent import RiskAgent
from app.adk.agents.verification_agent import VerificationAgent
from app.adk.agents.resolution_agent import ResolutionAgent
from app.adk.agents.outreach_agent import OutreachAgent
from app.adk.agents.remediation_agent import RemediationAgent
from app.adk.agents.report_agent import ReportAgent


class RootOrchestrator:
    """
    Google ADK Root Agent for Chain of Title.
    Autonomous clearance workflow orchestrator coordinating specialized agents across
    the dependency graph:
      [Screenplay Agent]  ||  [Visual Agent]   (Parallel)
                \\            //
              [Entity Merge Tool]              (Synchronization)
                      ||
              [Research Agent]                 (Corroboration)
                      ||
                [Risk Agent]                   (Deterministic Assessment)
                      ||
            [Verification Agent]               (Adversarial Verification)
                      ||
             [Resolution Agent]                (Operational Actions & Human Review)
                      ||
       [Financial Exposure + Outreach + Remediation] (Phase 10-12 Execution)
                      ||
               [Report Agent]                  (Final Traceable Synthesis)
    """

    def __init__(self):
        self.screenplay_agent = ScreenplayAgent()
        self.visual_agent = VisualAgent()
        self.research_agent = ResearchAgent()
        self.risk_agent = RiskAgent()
        self.verification_agent = VerificationAgent()
        self.resolution_agent = ResolutionAgent()
        self.outreach_agent = OutreachAgent()
        self.remediation_agent = RemediationAgent()
        self.report_agent = ReportAgent()

        # Instantiate Google ADK Root Agent
        self.adk_agent = adk.Agent(
            name="RootAgent",
            description="Autonomous clearance orchestrator coordinating specialized clearance agents.",
            instruction=(
                "You are the Root Clearance Orchestrator. Coordinate specialized agents across the clearance graph. "
                "Respect dependencies, enable parallel execution where possible, handle failures gracefully, "
                "uphold terminal HUMAN_REVIEW boundaries, and produce a fully traceable audit report."
            ),
            sub_agents=[
                self.screenplay_agent.adk_agent,
                self.visual_agent.adk_agent,
                self.research_agent.adk_agent,
                self.risk_agent.adk_agent,
                self.verification_agent.adk_agent,
                self.resolution_agent.adk_agent,
                self.outreach_agent.adk_agent,
                self.remediation_agent.adk_agent,
                self.report_agent.adk_agent,
            ],
        )

    async def orchestrate(
        self,
        context: WorkflowContext,
        screenplay_text: Optional[str] = None,
        video_path: Optional[str] = None,
    ) -> OrchestrationResult:
        """
        Execute full autonomous agent orchestration according to the dependency DAG.
        """
        await WorkflowCallbacks.on_orchestration_start(context)

        try:
            # =========================================================================
            # STAGE 1 & 2: PARALLEL DELEGATION (SCREENPLAY + VISUAL)
            # =========================================================================
            # Execute screenplay and visual agents concurrently using asyncio.gather
            screenplay_coro = self.screenplay_agent.run(context, screenplay_text=screenplay_text)
            visual_coro = self.visual_agent.run(context, video_path=video_path)

            results = await asyncio.gather(screenplay_coro, visual_coro, return_exceptions=True)

            # Handle screenplay handoff
            if isinstance(results[0], Exception):
                logger.error(f"[RootOrchestrator] Screenplay branch crashed: {results[0]}", exc_info=True)
                screenplay_handoff = AgentHandoff(
                    agent="screenplay",
                    status=AgentStatus.FAILED,
                    errors=[str(results[0])],
                )
            else:
                screenplay_handoff = results[0]

            # Handle visual handoff
            if isinstance(results[1], Exception):
                logger.error(f"[RootOrchestrator] Visual branch crashed: {results[1]}", exc_info=True)
                visual_handoff = AgentHandoff(
                    agent="visual",
                    status=AgentStatus.FAILED,
                    errors=[str(results[1])],
                )
            else:
                visual_handoff = results[1]

            context.state.update_agent_status("screenplay", screenplay_handoff.status, duration=screenplay_handoff.duration)
            context.state.update_agent_status("visual", visual_handoff.status, duration=visual_handoff.duration)

            for err in screenplay_handoff.errors:
                context.state.record_error(f"[Screenplay] {err}")
            for err in visual_handoff.errors:
                context.state.record_error(f"[Visual] {err}")

            # Check if all active input branches failed
            both_failed = (
                screenplay_handoff.status == AgentStatus.FAILED and visual_handoff.status == AgentStatus.FAILED
            )
            if both_failed:
                error_msg = "Both Screenplay and Visual ingestion branches failed. Aborting orchestration."
                logger.error(f"[RootOrchestrator] {error_msg}")
                await self.report_agent.run(context)
                await WorkflowCallbacks.on_orchestration_fail(context, error_msg)
                return context.state.to_orchestration_result()

            # =========================================================================
            # STAGE 3: ENTITY MERGE (Synchronization Barrier)
            # =========================================================================
            await WorkflowCallbacks.on_tool_start(context, "ROOT AGENT", "merge_entities_tool")
            merge_start = time.perf_counter()
            merge_result = await merge_entities_tool(context)
            merge_duration = time.perf_counter() - merge_start
            await WorkflowCallbacks.on_tool_complete(
                context, "ROOT AGENT", "merge_entities_tool", merge_result, merge_duration
            )

            if merge_result.get("status") == "FAILED":
                context.state.record_error(f"Entity merge failed: {merge_result.get('error')}")

            # Re-read entities from repository to ensure all branches are synchronized
            all_entities = await context.entity_repo.list_by_production(context.production_id)
            context.state.entity_ids = [e.id for e in all_entities]

            # If no entities at all were found, check if this was due to branch failures
            if not all_entities:
                has_branch_failure = (
                    screenplay_handoff.status == AgentStatus.FAILED or visual_handoff.status == AgentStatus.FAILED
                )
                if has_branch_failure:
                    error_msg = "No entities detected and one or more input branches failed. Marking workflow as FAILED."
                    logger.error(f"[RootOrchestrator] {error_msg}")
                    context.state.record_error(error_msg)
                    await self.report_agent.run(context)
                    await WorkflowCallbacks.on_orchestration_fail(context, error_msg)
                    return context.state.to_orchestration_result()

                logger.warning("[RootOrchestrator] No clearance entities detected across inputs. Generating clean report.")
                context.state.record_warning("No clearance entities detected from screenplay or video footage.")
                context.state.research_status = AgentStatus.SKIPPED
                context.state.risk_status = AgentStatus.SKIPPED
                context.state.verification_status = AgentStatus.SKIPPED
                context.state.resolution_status = AgentStatus.SKIPPED
                context.state.exposure_status = AgentStatus.SKIPPED
                context.state.outreach_status = AgentStatus.SKIPPED
                context.state.remediation_status = AgentStatus.SKIPPED

                # Generate report with zero entities
                await self.report_agent.run(context)
                await WorkflowCallbacks.on_orchestration_complete(context, WorkflowStatus.COMPLETED)
                return context.state.to_orchestration_result()

            # =========================================================================
            # STAGE 4: RESEARCH AGENT (Depends on Entity Merge)
            # =========================================================================
            research_handoff = await self.research_agent.run(context, entity_ids=context.state.entity_ids)
            context.state.update_agent_status("research", research_handoff.status, duration=research_handoff.duration)
            for err in research_handoff.errors:
                context.state.record_error(err)

            # Failure isolation: if research failed, do not abort workflow.
            # Downstream Risk & Resolution will handle un-researched entities.
            research_failed = research_handoff.status == AgentStatus.FAILED
            if research_failed:
                context.state.record_warning("Research stage failed or encountered errors; continuing with detection triage.")

            # =========================================================================
            # STAGE 5: RISK AGENT (Depends on Detection + Research)
            # =========================================================================
            risk_handoff = await self.risk_agent.run(context, entity_ids=context.state.entity_ids)
            context.state.update_agent_status("risk", risk_handoff.status, duration=risk_handoff.duration)
            for err in risk_handoff.errors:
                context.state.record_error(err)
            risk_failed = risk_handoff.status == AgentStatus.FAILED

            # =========================================================================
            # STAGE 6: VERIFICATION AGENT (Depends on Evidence + Risk)
            # =========================================================================
            if risk_failed:
                context.state.verification_status = AgentStatus.BLOCKED
                context.state.record_warning("Verification blocked due to upstream risk assessment failure.")
            else:
                verification_handoff = await self.verification_agent.run(context, entity_ids=context.state.entity_ids)
                context.state.update_agent_status("verification", verification_handoff.status, duration=verification_handoff.duration)
                for err in verification_handoff.errors:
                    context.state.record_error(err)

            # =========================================================================
            # STAGE 7: RESOLUTION AGENT (Depends on Verification)
            # =========================================================================
            if risk_failed:
                context.state.resolution_status = AgentStatus.BLOCKED
            else:
                resolution_handoff = await self.resolution_agent.run(context, entity_ids=context.state.entity_ids)
                context.state.update_agent_status("resolution", resolution_handoff.status, duration=resolution_handoff.duration)
                for err in resolution_handoff.errors:
                    context.state.record_error(err)

            # =========================================================================
            # STAGE 7B: FINANCIAL EXPOSURE (Phase 10: Statutory & Market Exposure)
            # =========================================================================
            try:
                exp_start = time.perf_counter()
                exp_res = await calculate_financial_exposure_tool(context, entity_ids=context.state.entity_ids)
                exp_duration = time.perf_counter() - exp_start
                context.state.update_agent_status("exposure", AgentStatus.COMPLETED, duration=exp_duration)
            except Exception as e:
                logger.warning(f"[RootOrchestrator] Financial exposure calculation encountered error: {e}")
                context.state.update_agent_status("exposure", AgentStatus.FAILED)
                context.state.record_warning(f"Financial exposure calculation error: {e}")

            # =========================================================================
            # STAGE 7C: CLEARANCE OUTREACH AGENT (Phase 11: Permission Request Drafts)
            # =========================================================================
            outreach_handoff = await self.outreach_agent.run(context, entity_ids=context.state.entity_ids)
            context.state.update_agent_status("outreach", outreach_handoff.status, duration=outreach_handoff.duration)
            for err in outreach_handoff.errors:
                context.state.record_warning(f"Outreach draft error: {err}")

            # =========================================================================
            # STAGE 7D: VISUAL REMEDIATION AGENT (Phase 12: Optical Cleanup Proposals)
            # =========================================================================
            remediation_handoff = await self.remediation_agent.run(context, entity_ids=context.state.entity_ids)
            context.state.update_agent_status("remediation", remediation_handoff.status, duration=remediation_handoff.duration)
            for err in remediation_handoff.errors:
                context.state.record_warning(f"Remediation proposal error: {err}")

            # =========================================================================
            # STAGE 8: REPORT AGENT (Synthesizes all available upstream findings)
            # =========================================================================
            report_handoff = await self.report_agent.run(context)
            context.state.update_agent_status("report", report_handoff.status, duration=report_handoff.duration)
            for err in report_handoff.errors:
                context.state.record_error(err)

            # Determine final workflow status:
            # PARTIAL if any non-critical stage failed but report generated; FAILED if report failed; COMPLETED otherwise
            has_failures = bool(context.state.get_failed_agents()) or bool(context.state.get_blocked_agents())
            if report_handoff.status == AgentStatus.FAILED:
                final_status = WorkflowStatus.FAILED
            elif has_failures:
                final_status = WorkflowStatus.PARTIAL
            else:
                final_status = WorkflowStatus.COMPLETED

            await WorkflowCallbacks.on_orchestration_complete(context, final_status)
            return context.state.to_orchestration_result()

        except Exception as e:
            logger.error(f"[RootOrchestrator] Fatal error during orchestration: {e}", exc_info=True)
            await WorkflowCallbacks.on_orchestration_fail(context, str(e))
            return context.state.to_orchestration_result()

        finally:
            # Clean up temporary materialization directory for this production
            try:
                cleanup_production_temp(context.production_id)
            except Exception as ce:
                logger.warning(f"[RootOrchestrator] Temp cleanup warning for {context.production_id}: {ce}")
