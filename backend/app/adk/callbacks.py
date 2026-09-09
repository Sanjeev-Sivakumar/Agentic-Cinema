from datetime import datetime, timezone
from typing import Any, Dict, Optional
from app.core.logging import logger
from app.models.events import EventType, PipelineStage, ProcessingEvent
from app.models.orchestration import AgentHandoff, AgentStatus, WorkflowStatus
from app.adk.context import WorkflowContext


class WorkflowCallbacks:
    """
    EventBus-integrated callback handler for the Google ADK Root Agent and specialized agents.
    Dispatches SSE telemetry events for orchestration lifecycle and tool execution.
    """

    @staticmethod
    async def on_orchestration_start(context: WorkflowContext) -> None:
        context.state.workflow_status = WorkflowStatus.RUNNING
        context.state.started_at = datetime.now(timezone.utc)
        logger.info(f"[ADK Root] Orchestration started for workflow {context.workflow_id} (Production: {context.production_id})")

        event = ProcessingEvent(
            production_id=context.production_id,
            job_id=context.job_id,
            event_type=EventType.ORCHESTRATION_STARTED,
            progress=0.0,
            message=f"Autonomous Clearance Orchestrator started (Mode: {context.execution_mode.upper()})",
            workflow_id=context.workflow_id,
            agent_name="ROOT AGENT",
            agent_status=WorkflowStatus.RUNNING.value,
            metadata={"execution_mode": context.execution_mode, "force_refresh": context.force_refresh},
        )
        await context.bus.publish(event)

    @staticmethod
    async def on_agent_start(context: WorkflowContext, agent_name: str) -> None:
        context.state.current_agent = agent_name
        context.state.update_agent_status(agent_name, AgentStatus.RUNNING)
        logger.info(f"[ADK Agent] Started {agent_name} in workflow {context.workflow_id}")

        event = ProcessingEvent(
            production_id=context.production_id,
            job_id=context.job_id,
            event_type=EventType.AGENT_STARTED,
            progress=0.0,
            message=f"{agent_name} agent invoked by Root Orchestrator",
            workflow_id=context.workflow_id,
            agent_name=agent_name,
            agent_status=AgentStatus.RUNNING.value,
        )
        await context.bus.publish(event)

    @staticmethod
    async def on_agent_complete(
        context: WorkflowContext,
        agent_name: str,
        handoff: AgentHandoff,
    ) -> None:
        context.state.update_agent_status(
            agent_name=agent_name,
            status=handoff.status,
            duration=handoff.duration,
            outputs=handoff.outputs,
        )
        for w in handoff.warnings:
            context.state.record_warning(w)
        for e in handoff.errors:
            context.state.record_error(e)

        logger.info(f"[ADK Agent] Completed {agent_name} in {handoff.duration:.2f}s with status {handoff.status.value}")

        event = ProcessingEvent(
            production_id=context.production_id,
            job_id=context.job_id,
            event_type=EventType.AGENT_COMPLETED,
            progress=0.0,
            message=f"{agent_name} agent completed in {handoff.duration:.2f}s ({handoff.status.value})",
            workflow_id=context.workflow_id,
            agent_name=agent_name,
            agent_status=handoff.status.value,
            duration_seconds=handoff.duration,
            metadata=handoff.outputs,
        )
        await context.bus.publish(event)

    @staticmethod
    async def on_agent_fail(
        context: WorkflowContext,
        agent_name: str,
        error: str,
        duration: float = 0.0,
    ) -> None:
        context.state.update_agent_status(agent_name, AgentStatus.FAILED, duration=duration)
        context.state.record_error(f"{agent_name} failed: {error}")
        logger.error(f"[ADK Agent] Failed {agent_name} in workflow {context.workflow_id}: {error}")

        event = ProcessingEvent(
            production_id=context.production_id,
            job_id=context.job_id,
            event_type=EventType.AGENT_FAILED,
            progress=0.0,
            message=f"{agent_name} agent failed: {error}",
            workflow_id=context.workflow_id,
            agent_name=agent_name,
            agent_status=AgentStatus.FAILED.value,
            duration_seconds=duration,
            metadata={"error": error},
        )
        await context.bus.publish(event)

    @staticmethod
    async def on_tool_start(
        context: WorkflowContext,
        agent_name: str,
        tool_name: str,
        args: Optional[Dict[str, Any]] = None,
    ) -> None:
        logger.debug(f"[ADK Tool] {agent_name} invoking tool {tool_name}")
        event = ProcessingEvent(
            production_id=context.production_id,
            job_id=context.job_id,
            event_type=EventType.TOOL_STARTED,
            progress=0.0,
            message=f"Tool '{tool_name}' invoked by {agent_name}",
            workflow_id=context.workflow_id,
            agent_name=agent_name,
            tool_name=tool_name,
            metadata=args or {},
        )
        await context.bus.publish(event)

    @staticmethod
    async def on_tool_complete(
        context: WorkflowContext,
        agent_name: str,
        tool_name: str,
        result: Dict[str, Any],
        duration: float = 0.0,
    ) -> None:
        logger.debug(f"[ADK Tool] {agent_name} completed tool {tool_name} in {duration:.2f}s")
        event = ProcessingEvent(
            production_id=context.production_id,
            job_id=context.job_id,
            event_type=EventType.TOOL_COMPLETED,
            progress=0.0,
            message=f"Tool '{tool_name}' completed in {duration:.2f}s",
            workflow_id=context.workflow_id,
            agent_name=agent_name,
            tool_name=tool_name,
            duration_seconds=duration,
            metadata=result,
        )
        await context.bus.publish(event)

    @staticmethod
    async def on_orchestration_complete(
        context: WorkflowContext,
        status: WorkflowStatus = WorkflowStatus.COMPLETED,
    ) -> None:
        context.state.workflow_status = status
        context.state.completed_at = datetime.now(timezone.utc)
        total_duration = (context.state.completed_at - context.state.started_at).total_seconds()
        logger.info(f"[ADK Root] Orchestration completed ({status.value}) in {total_duration:.2f}s")

        event = ProcessingEvent(
            production_id=context.production_id,
            job_id=context.job_id,
            event_type=EventType.ORCHESTRATION_COMPLETED,
            progress=100.0,
            message=f"Autonomous clearance orchestration finished with status: {status.value}",
            workflow_id=context.workflow_id,
            agent_name="ROOT AGENT",
            agent_status=status.value,
            duration_seconds=round(total_duration, 3),
            report_id=context.state.report_id,
        )
        await context.bus.publish(event)

    @staticmethod
    async def on_orchestration_fail(context: WorkflowContext, error: str) -> None:
        context.state.workflow_status = WorkflowStatus.FAILED
        context.state.completed_at = datetime.now(timezone.utc)
        context.state.record_error(f"Root orchestration failed: {error}")
        total_duration = (context.state.completed_at - context.state.started_at).total_seconds()
        logger.error(f"[ADK Root] Orchestration failed in {total_duration:.2f}s: {error}")

        event = ProcessingEvent(
            production_id=context.production_id,
            job_id=context.job_id,
            event_type=EventType.ORCHESTRATION_FAILED,
            progress=0.0,
            message=f"Autonomous clearance orchestration failed: {error}",
            workflow_id=context.workflow_id,
            agent_name="ROOT AGENT",
            agent_status=WorkflowStatus.FAILED.value,
            duration_seconds=round(total_duration, 3),
            metadata={"error": error},
        )
        await context.bus.publish(event)

    @staticmethod
    async def emit_event(
        context: WorkflowContext,
        event_type: EventType,
        stage: Optional[PipelineStage] = None,
        payload: Optional[Dict[str, Any]] = None,
        message: str = "",
    ) -> None:
        event = ProcessingEvent(
            production_id=context.production_id,
            job_id=context.job_id,
            event_type=event_type,
            stage=stage,
            progress=0.0,
            message=message,
            workflow_id=context.workflow_id,
            metadata=payload or {},
        )
        await context.bus.publish(event)

