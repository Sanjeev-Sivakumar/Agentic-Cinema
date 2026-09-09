import time
from typing import Any, Dict, Optional
import google.adk as adk
from app.models.orchestration import AgentHandoff, AgentStatus
from app.adk.callbacks import WorkflowCallbacks
from app.adk.context import WorkflowContext
from app.adk.tools.visual_tools import analyze_visual_tool


class VisualAgent:
    """
    ADK Visual Agent.
    Coordinates multi-provider video analysis (Scene Detection, OCR, Object Detection, Vision analysis).
    Never invents visual evidence independently.
    """

    def __init__(self):
        self.adk_agent = adk.Agent(
            name="VisualAgent",
            description="Coordinates real video ingestion and visual detection pipelines.",
            instruction=(
                "You coordinate visual footage intelligence across Scene Detection, OCR, Object Detection, "
                "and Vision analysis. Use the visual analysis tool. Never invent visual evidence. Return structured handoff state."
            ),
            tools=[analyze_visual_tool],
        )

    async def run(
        self,
        context: WorkflowContext,
        video_path: Optional[str] = None,
    ) -> AgentHandoff:
        start_time = time.perf_counter()
        agent_name = "Visual Agent"
        await WorkflowCallbacks.on_agent_start(context, agent_name)

        try:
            await WorkflowCallbacks.on_tool_start(context, agent_name, "analyze_visual_tool")
            tool_start = time.perf_counter()

            result = await analyze_visual_tool(context, video_path=video_path)

            tool_duration = time.perf_counter() - tool_start
            await WorkflowCallbacks.on_tool_complete(
                context,
                agent_name,
                "analyze_visual_tool",
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
                agent="visual",
                status=agent_status,
                entity_ids=result.get("entity_ids", []),
                evidence_ids=result.get("evidence_ids", []),
                result_ids=result.get("evidence_ids", []),
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
                agent="visual",
                status=AgentStatus.FAILED,
                entity_ids=[],
                evidence_ids=[],
                result_ids=[],
                outputs={},
                warnings=[],
                errors=[str(e)],
                duration=round(total_duration, 3),
            )
