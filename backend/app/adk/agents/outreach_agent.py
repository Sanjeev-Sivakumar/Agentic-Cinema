"""
ADK Clearance Outreach Agent (Phase 11).
Automates drafting rights permission letters and creates DRAFTS in Gmail.
Never auto-sends without human review.
"""
import time
from typing import Any, Dict, List, Optional
import google.adk as adk
from app.models.orchestration import AgentHandoff, AgentStatus
from app.adk.callbacks import WorkflowCallbacks
from app.adk.context import WorkflowContext
from app.adk.tools.outreach_tools import draft_clearance_outreach_tool


class OutreachAgent:
    """
    ADK Clearance Outreach Agent.
    Drafts entertainment clearance requests and manages the outreach lifecycle.
    """

    def __init__(self):
        self.adk_agent = adk.Agent(
            name="OutreachAgent",
            description="Drafts formal rights permission letters and manages Gmail clearance drafts.",
            instruction=(
                "You draft formal clearance requests tailored to the scene, timecodes, and rights holder. "
                "STRICT SAFETY: Only create drafts. Never auto-send."
            ),
            tools=[draft_clearance_outreach_tool],
        )

    async def run(
        self,
        context: WorkflowContext,
        entity_ids: Optional[List[str]] = None,
    ) -> AgentHandoff:
        start_time = time.perf_counter()
        agent_name = "Outreach Agent"
        await WorkflowCallbacks.on_agent_start(context, agent_name)

        try:
            await WorkflowCallbacks.on_tool_start(context, agent_name, "draft_clearance_outreach_tool")
            tool_start = time.perf_counter()

            result = await draft_clearance_outreach_tool(context, entity_ids=entity_ids)

            tool_duration = time.perf_counter() - tool_start
            await WorkflowCallbacks.on_tool_complete(
                context,
                agent_name,
                "draft_clearance_outreach_tool",
                result,
                tool_duration,
            )

            total_duration = time.perf_counter() - start_time
            handoff = AgentHandoff(
                agent="outreach",
                status=AgentStatus.COMPLETED,
                entity_ids=entity_ids or context.state.entity_ids,
                result_ids=[d["outreach_id"] for d in result.get("drafts", [])],
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
                agent="outreach",
                status=AgentStatus.FAILED,
                entity_ids=entity_ids or [],
                result_ids=[],
                outputs={},
                warnings=[],
                errors=[str(e)],
                duration=round(total_duration, 3),
            )
