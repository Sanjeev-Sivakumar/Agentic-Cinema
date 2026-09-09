import time
from typing import Any, Dict, List, Optional
import google.adk as adk
from app.models.orchestration import AgentHandoff, AgentStatus
from app.adk.callbacks import WorkflowCallbacks
from app.adk.context import WorkflowContext
from app.adk.tools.verification_tools import verify_entities_tool


class VerificationAgent:
    """
    ADK Verification Agent.
    Adversarially challenges evidence backing research and risk classifications.
    Never makes legal determinations.
    """

    def __init__(self):
        self.adk_agent = adk.Agent(
            name="VerificationAgent",
            description="Challenges whether findings are grounded in real evidence and checks contradictions.",
            instruction=(
                "You challenge whether existing evidence supports the research and risk assessment. "
                "Never make a legal determination."
            ),
            tools=[verify_entities_tool],
        )

    async def run(
        self,
        context: WorkflowContext,
        entity_ids: Optional[List[str]] = None,
    ) -> AgentHandoff:
        start_time = time.perf_counter()
        agent_name = "Verification Agent"
        await WorkflowCallbacks.on_agent_start(context, agent_name)

        try:
            await WorkflowCallbacks.on_tool_start(context, agent_name, "verify_entities_tool")
            tool_start = time.perf_counter()

            result = await verify_entities_tool(context, entity_ids=entity_ids)

            tool_duration = time.perf_counter() - tool_start
            await WorkflowCallbacks.on_tool_complete(
                context,
                agent_name,
                "verify_entities_tool",
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
                agent="verification",
                status=agent_status,
                entity_ids=entity_ids or context.state.entity_ids,
                result_ids=result.get("verification_result_ids", []),
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
                agent="verification",
                status=AgentStatus.FAILED,
                entity_ids=entity_ids or [],
                result_ids=[],
                outputs={},
                warnings=[],
                errors=[str(e)],
                duration=round(total_duration, 3),
            )
