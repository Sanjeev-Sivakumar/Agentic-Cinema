"""
ADK Visual Remediation Agent (Phase 12).
Generates proposed optical cleanups and side-by-side review assets.
Never modifies original footage.
"""
import time
from typing import Any, Dict, List, Optional
import google.adk as adk
from app.models.orchestration import AgentHandoff, AgentStatus
from app.adk.callbacks import WorkflowCallbacks
from app.adk.context import WorkflowContext
from app.adk.tools.remediation_tools import generate_visual_remediation_tool


class RemediationAgent:
    """
    ADK Visual Remediation Agent.
    Generates proposed optical cleanups and side-by-side review assets for VISUAL_ONLY entities.
    """

    def __init__(self):
        self.adk_agent = adk.Agent(
            name="RemediationAgent",
            description="Generates non-destructive optical cleanup proposals for unscripted or high-risk visual entities.",
            instruction=(
                "You generate visual remediation proposals (Gaussian blur, neutral replacement, AI inpainting) "
                "for visual entities. Always preserve original footage and flag outputs for human review."
            ),
            tools=[generate_visual_remediation_tool],
        )

    async def run(
        self,
        context: WorkflowContext,
        entity_ids: Optional[List[str]] = None,
    ) -> AgentHandoff:
        start_time = time.perf_counter()
        agent_name = "Remediation Agent"
        await WorkflowCallbacks.on_agent_start(context, agent_name)

        try:
            await WorkflowCallbacks.on_tool_start(context, agent_name, "generate_visual_remediation_tool")
            tool_start = time.perf_counter()

            result = await generate_visual_remediation_tool(context, entity_ids=entity_ids)

            tool_duration = time.perf_counter() - tool_start
            await WorkflowCallbacks.on_tool_complete(
                context,
                agent_name,
                "generate_visual_remediation_tool",
                result,
                tool_duration,
            )

            total_duration = time.perf_counter() - start_time
            handoff = AgentHandoff(
                agent="remediation",
                status=AgentStatus.COMPLETED,
                entity_ids=entity_ids or context.state.entity_ids,
                result_ids=[p["remediation_id"] for p in result.get("proposals", [])],
                outputs=result,
                warnings=[],
                errors=[],
                duration=round(total_duration, 3),
            )
            await WorkflowCallbacks.on_agent_complete(context, agent_name, handoff)
            return handoff

        except Exception as e:
            total_duration = time.perf_counter() - start_time
            await WorkflowCallbacks.on_agent_fail(context, agent_name, str(e), duration=total_duration)
            return AgentHandoff(
                agent="remediation",
                status=AgentStatus.FAILED,
                entity_ids=entity_ids or [],
                result_ids=[],
                outputs={},
                warnings=[],
                errors=[str(e)],
                duration=round(total_duration, 3),
            )
