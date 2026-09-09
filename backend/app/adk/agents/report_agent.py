import time
from typing import Any, Dict, List, Optional
import google.adk as adk
from app.models.orchestration import AgentHandoff, AgentStatus
from app.adk.callbacks import WorkflowCallbacks
from app.adk.context import WorkflowContext
from app.adk.tools.report_tools import generate_report_tool


class ReportAgent:
    """
    ADK Report Agent.
    Synthesizes upstream intelligence across all agents into comprehensive audit reports.
    Never invents metrics or statistics.
    """

    def __init__(self):
        self.adk_agent = adk.Agent(
            name="ReportAgent",
            description="Compiles multi-format JSON, HTML, and PDF clearance audit reports.",
            instruction=(
                "You compile existing intelligence into a traceable report. "
                "Never invent findings or statistics."
            ),
            tools=[generate_report_tool],
        )

    async def run(
        self,
        context: WorkflowContext,
        formats: Optional[List[str]] = None,
    ) -> AgentHandoff:
        start_time = time.perf_counter()
        agent_name = "Report Agent"
        await WorkflowCallbacks.on_agent_start(context, agent_name)

        try:
            await WorkflowCallbacks.on_tool_start(context, agent_name, "generate_report_tool")
            tool_start = time.perf_counter()

            result = await generate_report_tool(context, formats=formats)

            tool_duration = time.perf_counter() - tool_start
            await WorkflowCallbacks.on_tool_complete(
                context,
                agent_name,
                "generate_report_tool",
                result,
                tool_duration,
            )

            total_duration = time.perf_counter() - start_time
            status_str = result.get("status", "COMPLETED")
            if status_str == "FAILED":
                agent_status = AgentStatus.FAILED
            elif status_str == "SKIPPED":
                agent_status = AgentStatus.SKIPPED
            else:
                agent_status = AgentStatus.COMPLETED

            report_id = result.get("report_id")
            handoff = AgentHandoff(
                agent="report",
                status=agent_status,
                entity_ids=context.state.entity_ids,
                evidence_ids=context.state.evidence_ids,
                result_ids=[report_id] if report_id else [],
                outputs=result,
                warnings=[],
                errors=[result["error"]] if "error" in result else [],
                duration=round(total_duration, 3),
            )
            await WorkflowCallbacks.on_agent_complete(context, agent_name, handoff)
            return handoff

        except Exception as e:
            total_duration = time.perf_counter() - start_time
            await WorkflowCallbacks.on_agent_fail(context, agent_name, str(e), duration=total_duration)
            return AgentHandoff(
                agent="report",
                status=AgentStatus.FAILED,
                entity_ids=context.state.entity_ids,
                evidence_ids=[],
                result_ids=[],
                outputs={},
                warnings=[],
                errors=[str(e)],
                duration=round(total_duration, 3),
            )
