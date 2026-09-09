import time
from typing import Any, Dict, Optional
import google.adk as adk
from app.models.orchestration import AgentHandoff, AgentStatus
from app.adk.callbacks import WorkflowCallbacks
from app.adk.context import WorkflowContext
from app.adk.tools.screenplay_tools import analyze_screenplay_tool


class ScreenplayAgent:
    """
    ADK Screenplay Agent.
    Coordinates screenplay parsing and clearance-relevant entity extraction.
    Never invents entities or dialogue independently.
    """

    def __init__(self):
        self.adk_agent = adk.Agent(
            name="ScreenplayAgent",
            description="Extracts clearance-relevant entities and scene metadata from screenplay text.",
            instruction=(
                "You coordinate screenplay script intelligence. Parse scenes and extract entities "
                "using the screenplay analysis tool. Never invent dialogue or entities. Return structured handoff state."
            ),
            tools=[analyze_screenplay_tool],
        )

    async def run(
        self,
        context: WorkflowContext,
        screenplay_text: Optional[str] = None,
    ) -> AgentHandoff:
        start_time = time.perf_counter()
        agent_name = "Screenplay Agent"
        await WorkflowCallbacks.on_agent_start(context, agent_name)

        try:
            await WorkflowCallbacks.on_tool_start(context, agent_name, "analyze_screenplay_tool")
            tool_start = time.perf_counter()

            result = await analyze_screenplay_tool(context, screenplay_text=screenplay_text)

            tool_duration = time.perf_counter() - tool_start
            await WorkflowCallbacks.on_tool_complete(
                context,
                agent_name,
                "analyze_screenplay_tool",
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

            handoff = AgentHandoff(
                agent="screenplay",
                status=agent_status,
                entity_ids=result.get("entity_ids", []),
                result_ids=result.get("entity_ids", []),
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
                agent="screenplay",
                status=AgentStatus.FAILED,
                entity_ids=[],
                result_ids=[],
                outputs={},
                warnings=[],
                errors=[str(e)],
                duration=round(total_duration, 3),
            )
