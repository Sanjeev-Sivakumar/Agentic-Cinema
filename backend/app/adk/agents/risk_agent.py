import time
from typing import Any, Dict, List, Optional
import google.adk as adk
from app.models.orchestration import AgentHandoff, AgentStatus
from app.adk.callbacks import WorkflowCallbacks
from app.adk.context import WorkflowContext
from app.adk.tools.risk_tools import assess_risk_tool


class RiskAgent:
    """
    ADK Risk Agent.
    Coordinates deterministic risk assessment across all detected entities.
    Never invents or overrides risk scores independently.
    """

    def __init__(self):
        self.adk_agent = adk.Agent(
            name="RiskAgent",
            description="Coordinates multi-factor deterministic clearance risk assessment.",
            instruction=(
                "You coordinate deterministic risk assessment. Never calculate or invent risk independently. "
                "Use the risk tool and return its structured result."
            ),
            tools=[assess_risk_tool],
        )

    async def run(
        self,
        context: WorkflowContext,
        entity_ids: Optional[List[str]] = None,
    ) -> AgentHandoff:
        start_time = time.perf_counter()
        agent_name = "Risk Agent"
        await WorkflowCallbacks.on_agent_start(context, agent_name)

        try:
            await WorkflowCallbacks.on_tool_start(context, agent_name, "assess_risk_tool")
            tool_start = time.perf_counter()

            result = await assess_risk_tool(context, entity_ids=entity_ids)

            tool_duration = time.perf_counter() - tool_start
            await WorkflowCallbacks.on_tool_complete(
                context,
                agent_name,
                "assess_risk_tool",
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
                agent="risk",
                status=agent_status,
                entity_ids=entity_ids or context.state.entity_ids,
                result_ids=result.get("risk_result_ids", []),
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
                agent="risk",
                status=AgentStatus.FAILED,
                entity_ids=entity_ids or [],
                result_ids=[],
                outputs={},
                warnings=[],
                errors=[str(e)],
                duration=round(total_duration, 3),
            )
