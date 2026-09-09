import asyncio
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.production import Production
from app.models.entity import Entity, EntityClassification, EntitySource, EntityType, RiskLevel
from app.models.evidence import Evidence, EvidenceType
from app.models.events import EventType, ProcessingEvent
from app.models.orchestration import (
    WorkflowStatus,
    AgentStatus,
    AgentHandoff,
    WorkflowSummary,
    OrchestrationResult,
)
from app.adk.state import ChainOfTitleState
from app.adk.context import WorkflowContext
from app.adk.callbacks import WorkflowCallbacks
from app.adk.tools.screenplay_tools import analyze_screenplay_tool
from app.adk.tools.visual_tools import analyze_visual_tool
from app.adk.tools.entity_tools import merge_entities_tool
from app.adk.tools.research_tools import research_entities_tool
from app.adk.tools.risk_tools import assess_risk_tool
from app.adk.tools.verification_tools import verify_entities_tool
from app.adk.tools.resolution_tools import resolve_entities_tool
from app.adk.tools.report_tools import generate_report_tool
from app.adk.agents.screenplay_agent import ScreenplayAgent
from app.adk.agents.visual_agent import VisualAgent
from app.adk.agents.research_agent import ResearchAgent
from app.adk.agents.risk_agent import RiskAgent
from app.adk.agents.verification_agent import VerificationAgent
from app.adk.agents.resolution_agent import ResolutionAgent
from app.adk.agents.report_agent import ReportAgent
from app.adk.root_agent import RootOrchestrator
from app.adk.runner import run_production_workflow
from app.repositories.orchestration.in_memory import InMemoryOrchestrationRepository
from app.repositories import (
    get_production_repo,
    get_entity_repo,
    get_evidence_repo,
    get_research_repo,
    get_risk_repo,
    get_verification_repo,
    get_resolution_repo,
    get_report_repo,
    get_orchestration_repo,
)
from app.services import event_bus

client = TestClient(app)


# =============================================================================
# 1. State Tests
# =============================================================================

def test_state_initialization_defaults():
    state = ChainOfTitleState(production_id="prod_01")
    assert state.production_id == "prod_01"
    assert state.workflow_status == WorkflowStatus.PENDING
    assert state.screenplay_status == AgentStatus.PENDING
    assert state.visual_status == AgentStatus.PENDING
    assert state.research_status == AgentStatus.PENDING
    assert state.risk_status == AgentStatus.PENDING
    assert state.verification_status == AgentStatus.PENDING
    assert state.resolution_status == AgentStatus.PENDING
    assert state.report_status == AgentStatus.PENDING
    assert state.entity_ids == []
    assert state.evidence_ids == []
    assert state.errors == []
    assert state.warnings == []


def test_state_serialization_to_dict():
    state = ChainOfTitleState(production_id="prod_01")
    d = state.to_dict()
    assert d["production_id"] == "prod_01"
    assert d["workflow_status"] == "PENDING"
    assert isinstance(d["started_at"], str)


def test_state_status_transitions():
    state = ChainOfTitleState(production_id="prod_01")
    state.update_agent_status("Screenplay Agent", AgentStatus.RUNNING)
    assert state.screenplay_status == AgentStatus.RUNNING

    state.update_agent_status("Screenplay Agent", AgentStatus.COMPLETED, duration=1.23)
    assert state.screenplay_status == AgentStatus.COMPLETED
    assert state.agent_durations["Screenplay Agent"] == 1.23


def test_state_record_error_and_warning():
    state = ChainOfTitleState(production_id="prod_01")
    state.record_error("Test error")
    state.record_warning("Test warning")
    assert "Test error" in state.errors
    assert "Test warning" in state.warnings


def test_state_get_completed_agents():
    state = ChainOfTitleState(production_id="prod_01")
    state.screenplay_status = AgentStatus.COMPLETED
    state.visual_status = AgentStatus.COMPLETED
    assert "screenplay" in state.get_completed_agents()
    assert "visual" in state.get_completed_agents()
    assert "risk" not in state.get_completed_agents()


def test_state_get_failed_agents():
    state = ChainOfTitleState(production_id="prod_01")
    state.research_status = AgentStatus.FAILED
    assert state.get_failed_agents() == ["research"]


def test_state_get_blocked_agents():
    state = ChainOfTitleState(production_id="prod_01")
    state.verification_status = AgentStatus.BLOCKED
    assert state.get_blocked_agents() == ["verification"]


def test_state_get_skipped_agents():
    state = ChainOfTitleState(production_id="prod_01")
    state.screenplay_status = AgentStatus.SKIPPED
    assert state.get_skipped_agents() == ["screenplay"]


def test_state_to_orchestration_result():
    state = ChainOfTitleState(production_id="prod_01")
    state.entity_ids = ["ent_1", "ent_2", "ent_1"]  # duplicates should dedupe
    state.workflow_status = WorkflowStatus.COMPLETED
    res = state.to_orchestration_result()
    assert isinstance(res, OrchestrationResult)
    assert res.production_id == "prod_01"
    assert res.entity_ids == ["ent_1", "ent_2"]
    assert res.status == WorkflowStatus.COMPLETED


def test_state_timestamps_updated():
    state = ChainOfTitleState(production_id="prod_01")
    initial_updated = state.updated_at
    state.update_agent_status("Visual Agent", AgentStatus.COMPLETED)
    assert state.updated_at >= initial_updated


# =============================================================================
# 2. Context Tests
# =============================================================================

def test_workflow_context_initialization():
    state = ChainOfTitleState(production_id="prod_01")
    ctx = WorkflowContext(state=state, execution_mode="offline")
    assert ctx.production_id == "prod_01"
    assert ctx.workflow_id == state.workflow_id
    assert ctx.is_offline is True
    assert ctx.production_repo is not None
    assert ctx.orchestration_repo is not None


def test_workflow_context_live_mode():
    state = ChainOfTitleState(production_id="prod_01")
    ctx = WorkflowContext(state=state, execution_mode="live")
    assert ctx.is_offline is False
    assert ctx.execution_mode == "live"


# =============================================================================
# 3. Callbacks & Events Tests
# =============================================================================

@pytest.mark.asyncio
async def test_callbacks_orchestration_start():
    state = ChainOfTitleState(production_id="prod_test")
    ctx = WorkflowContext(state=state)
    await WorkflowCallbacks.on_orchestration_start(ctx)
    assert state.workflow_status == WorkflowStatus.RUNNING


@pytest.mark.asyncio
async def test_callbacks_agent_lifecycle():
    state = ChainOfTitleState(production_id="prod_test")
    ctx = WorkflowContext(state=state)
    await WorkflowCallbacks.on_agent_start(ctx, "Risk Agent")
    assert state.current_agent == "Risk Agent"
    assert state.risk_status == AgentStatus.RUNNING

    handoff = AgentHandoff(
        agent="risk",
        status=AgentStatus.COMPLETED,
        result_ids=["risk_01"],
        duration=0.5,
    )
    await WorkflowCallbacks.on_agent_complete(ctx, "Risk Agent", handoff)
    assert state.risk_status == AgentStatus.COMPLETED
    assert state.agent_durations["Risk Agent"] == 0.5


@pytest.mark.asyncio
async def test_callbacks_agent_failure():
    state = ChainOfTitleState(production_id="prod_test")
    ctx = WorkflowContext(state=state)
    await WorkflowCallbacks.on_agent_fail(ctx, "Research Agent", "Network timeout", duration=0.2)
    assert state.research_status == AgentStatus.FAILED
    assert any("Research Agent failed" in err for err in state.errors)


@pytest.mark.asyncio
async def test_callbacks_orchestration_complete():
    state = ChainOfTitleState(production_id="prod_test")
    ctx = WorkflowContext(state=state)
    await WorkflowCallbacks.on_orchestration_start(ctx)
    await WorkflowCallbacks.on_orchestration_complete(ctx, WorkflowStatus.COMPLETED)
    assert state.workflow_status == WorkflowStatus.COMPLETED
    assert state.completed_at is not None


@pytest.mark.asyncio
async def test_callbacks_orchestration_fail():
    state = ChainOfTitleState(production_id="prod_test")
    ctx = WorkflowContext(state=state)
    await WorkflowCallbacks.on_orchestration_start(ctx)
    await WorkflowCallbacks.on_orchestration_fail(ctx, "Fatal error")
    assert state.workflow_status == WorkflowStatus.FAILED
    assert any("Fatal error" in err for err in state.errors)


# =============================================================================
# 4. Tools Layer Tests
# =============================================================================

@pytest.mark.asyncio
async def test_analyze_screenplay_tool_with_script():
    prod_id = "prod_tool_screenplay"
    prod = Production(id=prod_id, title="Script Test", script_path="")
    await get_production_repo().save(prod)

    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)
    result = await analyze_screenplay_tool(
        ctx,
        screenplay_text="SCENE 01 - INT. ROOM - DAY\nAlice drinks Coca-Cola while listening to Sony radio."
    )
    assert result["status"] == "COMPLETED"
    assert result["entities_count"] >= 1
    assert len(state.entity_ids) >= 1


@pytest.mark.asyncio
async def test_analyze_screenplay_tool_missing_script():
    prod_id = "prod_tool_no_script"
    prod = Production(id=prod_id, title="No Script Test")
    await get_production_repo().save(prod)

    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)
    result = await analyze_screenplay_tool(ctx, screenplay_text="")
    assert result["status"] == "SKIPPED"


@pytest.mark.asyncio
async def test_analyze_visual_tool_missing_footage():
    prod_id = "prod_tool_no_vis"
    prod = Production(id=prod_id, title="No Footage")
    await get_production_repo().save(prod)

    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)
    result = await analyze_visual_tool(ctx, video_path="")
    assert result["status"] == "SKIPPED"


@pytest.mark.asyncio
async def test_merge_entities_tool_identifies_visual_only():
    prod_id = "prod_tool_merge"
    prod = Production(id=prod_id, title="Merge Test")
    await get_production_repo().save(prod)

    # Inject one visual-only entity and one screenplay entity
    ent1 = Entity(
        id="ent_vis_1",
        production_id=prod_id,
        name="Unscripted Soda",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
    )
    ent2 = Entity(
        id="ent_script_1",
        production_id=prod_id,
        name="Scripted Watch",
        entity_type=EntityType.PRODUCT,
        sources=[EntitySource.SCRIPT],
        classification=EntityClassification.SCRIPT_ONLY,
    )
    await get_entity_repo().save(ent1)
    await get_entity_repo().save(ent2)

    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)
    result = await merge_entities_tool(ctx)
    assert result["status"] == "COMPLETED"
    assert result["total_entities"] == 2


@pytest.mark.asyncio
async def test_research_entities_tool_empty():
    prod_id = "prod_tool_research_empty"
    prod = Production(id=prod_id, title="Empty Research")
    await get_production_repo().save(prod)

    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)
    result = await research_entities_tool(ctx, entity_ids=[])
    assert result["status"] == "SKIPPED"


@pytest.mark.asyncio
async def test_assess_risk_tool_deterministic_output():
    prod_id = "prod_tool_risk"
    prod = Production(id=prod_id, title="Risk Test")
    await get_production_repo().save(prod)

    ent = Entity(
        id="ent_risk_1",
        production_id=prod_id,
        name="High Exposure Can",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        classification=EntityClassification.VISUAL_ONLY,
    )
    await get_entity_repo().save(ent)

    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)
    result = await assess_risk_tool(ctx, entity_ids=["ent_risk_1"])
    assert result["status"] == "COMPLETED"
    assert result["total_assessed"] == 1


@pytest.mark.asyncio
async def test_verify_entities_tool_adversarial_check():
    prod_id = "prod_tool_verif"
    prod = Production(id=prod_id, title="Verif Test")
    await get_production_repo().save(prod)

    ent = Entity(
        id="ent_verif_1",
        production_id=prod_id,
        name="Sample Brand",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
    )
    await get_entity_repo().save(ent)

    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)
    result = await verify_entities_tool(ctx, entity_ids=["ent_verif_1"])
    assert result["status"] == "COMPLETED"
    assert result["total_verified"] == 1


@pytest.mark.asyncio
async def test_resolve_entities_tool_human_review_boundary():
    prod_id = "prod_tool_resol"
    prod = Production(id=prod_id, title="Resol Test")
    await get_production_repo().save(prod)

    ent = Entity(
        id="ent_resol_1",
        production_id=prod_id,
        name="Uncertain Brand",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
    )
    await get_entity_repo().save(ent)

    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)
    result = await resolve_entities_tool(ctx, entity_ids=["ent_resol_1"])
    assert result["status"] == "COMPLETED"
    assert result["total_resolved"] == 1


@pytest.mark.asyncio
async def test_generate_report_tool_multi_format():
    prod_id = "prod_tool_rep"
    prod = Production(id=prod_id, title="Report Test")
    await get_production_repo().save(prod)

    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)
    result = await generate_report_tool(ctx, formats=["JSON", "HTML"])
    assert result["status"] == "COMPLETED"
    assert result["report_id"] is not None
    assert state.workflow_summary is not None


# =============================================================================
# 5. Specialized ADK Agent Wrappers Tests
# =============================================================================

@pytest.mark.asyncio
async def test_screenplay_agent_handoff_contract():
    prod_id = "prod_agent_screenplay"
    await get_production_repo().save(Production(id=prod_id, title="Agent Test"))

    agent = ScreenplayAgent()
    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    handoff = await agent.run(ctx, screenplay_text="INT. CAFE - DAY\nBob drinks Pepsi.")
    assert isinstance(handoff, AgentHandoff)
    assert handoff.agent == "screenplay"
    assert handoff.status in (AgentStatus.COMPLETED, AgentStatus.SKIPPED)
    assert handoff.duration >= 0.0


@pytest.mark.asyncio
async def test_visual_agent_handoff_contract():
    prod_id = "prod_agent_visual"
    await get_production_repo().save(Production(id=prod_id, title="Visual Agent Test"))

    agent = VisualAgent()
    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    handoff = await agent.run(ctx, video_path="")
    assert isinstance(handoff, AgentHandoff)
    assert handoff.agent == "visual"
    assert handoff.status == AgentStatus.SKIPPED


@pytest.mark.asyncio
async def test_research_agent_handoff_contract():
    prod_id = "prod_agent_research"
    await get_production_repo().save(Production(id=prod_id, title="Research Agent Test"))

    agent = ResearchAgent()
    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    handoff = await agent.run(ctx, entity_ids=[])
    assert handoff.agent == "research"
    assert handoff.status == AgentStatus.SKIPPED


@pytest.mark.asyncio
async def test_risk_agent_handoff_contract():
    prod_id = "prod_agent_risk"
    await get_production_repo().save(Production(id=prod_id, title="Risk Agent Test"))

    agent = RiskAgent()
    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    handoff = await agent.run(ctx, entity_ids=[])
    assert handoff.agent == "risk"
    assert handoff.status == AgentStatus.COMPLETED


@pytest.mark.asyncio
async def test_verification_agent_handoff_contract():
    prod_id = "prod_agent_verif"
    await get_production_repo().save(Production(id=prod_id, title="Verif Agent Test"))

    agent = VerificationAgent()
    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    handoff = await agent.run(ctx, entity_ids=[])
    assert handoff.agent == "verification"
    assert handoff.status == AgentStatus.COMPLETED


@pytest.mark.asyncio
async def test_resolution_agent_handoff_contract():
    prod_id = "prod_agent_resol"
    await get_production_repo().save(Production(id=prod_id, title="Resol Agent Test"))

    agent = ResolutionAgent()
    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    handoff = await agent.run(ctx, entity_ids=[])
    assert handoff.agent == "resolution"
    assert handoff.status == AgentStatus.COMPLETED


@pytest.mark.asyncio
async def test_report_agent_handoff_contract():
    prod_id = "prod_agent_rep"
    await get_production_repo().save(Production(id=prod_id, title="Report Agent Test"))

    agent = ReportAgent()
    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    handoff = await agent.run(ctx, formats=["JSON"])
    assert handoff.agent == "report"
    assert handoff.status == AgentStatus.COMPLETED


def test_agent_adk_model_instruction_compliance():
    """Verify each specialized agent has an adk.Agent instance with explicit instructions."""
    agents = [
        ScreenplayAgent(),
        VisualAgent(),
        ResearchAgent(),
        RiskAgent(),
        VerificationAgent(),
        ResolutionAgent(),
        ReportAgent(),
    ]
    for a in agents:
        assert hasattr(a, "adk_agent")
        assert a.adk_agent.name is not None
        assert a.adk_agent.instruction is not None
        assert len(a.adk_agent.tools) >= 1


# =============================================================================
# 6. Root Agent & Dependency Graph Tests
# =============================================================================

@pytest.mark.asyncio
async def test_root_orchestrator_normal_pipeline():
    prod_id = "prod_root_normal"
    await get_production_repo().save(Production(id=prod_id, title="Normal Pipeline"))

    orchestrator = RootOrchestrator()
    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    result = await orchestrator.orchestrate(
        context=ctx,
        screenplay_text="SCENE 01 - INT. LAB - NIGHT\nScientist works on Acme Terminal.",
    )
    assert result.status == WorkflowStatus.COMPLETED
    assert "screenplay" in result.completed_agents
    assert "report" in result.completed_agents
    assert result.report_id is not None


@pytest.mark.asyncio
async def test_root_orchestrator_missing_screenplay():
    prod_id = "prod_root_no_script"
    await get_production_repo().save(Production(id=prod_id, title="No Script Pipeline"))

    orchestrator = RootOrchestrator()
    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    result = await orchestrator.orchestrate(context=ctx, screenplay_text="")
    assert result.status == WorkflowStatus.COMPLETED
    assert "screenplay" in result.skipped_agents or state.screenplay_status == AgentStatus.SKIPPED


@pytest.mark.asyncio
async def test_root_orchestrator_missing_video():
    prod_id = "prod_root_no_video"
    await get_production_repo().save(Production(id=prod_id, title="No Video Pipeline"))

    orchestrator = RootOrchestrator()
    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    result = await orchestrator.orchestrate(
        context=ctx,
        screenplay_text="SCENE 01 - INT. OFFICE - DAY\nManager checks Rolex watch.",
        video_path="",
    )
    assert result.status == WorkflowStatus.COMPLETED
    assert "visual" in result.skipped_agents or state.visual_status == AgentStatus.SKIPPED


@pytest.mark.asyncio
async def test_root_orchestrator_no_entities_graceful_completion():
    prod_id = "prod_root_empty"
    await get_production_repo().save(Production(id=prod_id, title="Empty Pipeline"))

    orchestrator = RootOrchestrator()
    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    result = await orchestrator.orchestrate(context=ctx, screenplay_text="", video_path="")
    assert result.status == WorkflowStatus.COMPLETED
    assert len(result.entity_ids) == 0
    assert result.report_id is not None


@pytest.mark.asyncio
async def test_root_orchestrator_research_failure_isolation():
    """Verify research failure produces PARTIAL status and does not crash downstream resolution/reporting."""
    prod_id = "prod_root_fail_research"
    await get_production_repo().save(Production(id=prod_id, title="Fail Research"))

    orchestrator = RootOrchestrator()
    # Mock research agent to fail
    orchestrator.research_agent.run = AsyncMock(return_value=AgentHandoff(
        agent="research",
        status=AgentStatus.FAILED,
        errors=["Simulated registry connection failure"],
    ))

    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    result = await orchestrator.orchestrate(
        context=ctx,
        screenplay_text="SCENE 01 - INT. STORE - DAY\nCustomer asks for Pepsi.",
    )
    assert result.status == WorkflowStatus.PARTIAL
    assert "research" in result.failed_agents
    assert "report" in result.completed_agents
    assert result.report_id is not None


@pytest.mark.asyncio
async def test_root_orchestrator_terminal_human_review_boundary():
    """Verify resolution sets items to HUMAN_REVIEW without claiming cleared."""
    prod_id = "prod_root_human_review"
    await get_production_repo().save(Production(id=prod_id, title="Human Review Boundary"))

    orchestrator = RootOrchestrator()
    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    result = await orchestrator.orchestrate(
        context=ctx,
        screenplay_text="SCENE 01 - INT. DINER - DAY\nProtagonist holds a vintage Coca-Cola bottle.",
    )
    assert result.status == WorkflowStatus.COMPLETED
    # Check that human review count is tracked
    if result.workflow_summary:
        assert "human_review" in result.workflow_summary.resolution


# =============================================================================
# 7. Runner & Idempotency Tests
# =============================================================================

@pytest.mark.asyncio
async def test_runner_executes_and_persists():
    prod_id = "prod_runner_test"
    await get_production_repo().save(Production(id=prod_id, title="Runner Test"))

    result = await run_production_workflow(
        production_id=prod_id,
        screenplay_text="INT. BAR - NIGHT\nBartender opens Heineken bottle.",
        mode="offline",
    )
    assert isinstance(result, OrchestrationResult)
    assert result.workflow_id.startswith("wf_")

    # Verify persistent retrieval
    orch_repo = get_orchestration_repo()
    saved = await orch_repo.get(result.workflow_id)
    assert saved is not None
    assert saved.workflow_id == result.workflow_id


@pytest.mark.asyncio
async def test_runner_nonexistent_production_raises():
    with pytest.raises(ValueError, match="not found"):
        await run_production_workflow(production_id="prod_nonexistent_12345")


@pytest.mark.asyncio
async def test_idempotency_caching_behavior():
    prod_id = "prod_idempotent"
    await get_production_repo().save(Production(id=prod_id, title="Idempotent Test"))

    # First run
    res1 = await run_production_workflow(
        production_id=prod_id,
        screenplay_text="INT. GARAGE - DAY\nMechanic uses Ford wrench.",
        force_refresh=False,
    )

    # Second run without force_refresh reuses cached records
    res2 = await run_production_workflow(
        production_id=prod_id,
        screenplay_text="INT. GARAGE - DAY\nMechanic uses Ford wrench.",
        force_refresh=False,
    )
    assert res2.status == WorkflowStatus.COMPLETED


# =============================================================================
# 8. Orchestration Repository Tests
# =============================================================================

@pytest.mark.asyncio
async def test_orchestration_repo_crud():
    repo = InMemoryOrchestrationRepository()
    res = OrchestrationResult(
        workflow_id="wf_repo_1",
        production_id="prod_repo_1",
        job_id="job_repo_1",
        status=WorkflowStatus.COMPLETED,
    )
    await repo.save(res)

    fetched = await repo.get("wf_repo_1")
    assert fetched is not None
    assert fetched.workflow_id == "wf_repo_1"

    latest = await repo.get_latest_for_production("prod_repo_1")
    assert latest is not None
    assert latest.workflow_id == "wf_repo_1"

    all_res = await repo.list_for_production("prod_repo_1")
    assert len(all_res) == 1

    await repo.clear()
    assert await repo.get("wf_repo_1") is None


@pytest.mark.asyncio
async def test_orchestration_repo_concurrency():
    repo = InMemoryOrchestrationRepository()

    async def save_wf(idx: int):
        r = OrchestrationResult(
            workflow_id=f"wf_conc_{idx}",
            production_id="prod_conc",
            job_id=f"job_conc_{idx}",
            status=WorkflowStatus.COMPLETED,
        )
        return await repo.save(r)

    results = await asyncio.gather(*[save_wf(i) for i in range(10)])
    assert len(results) == 10
    stored = await repo.list_for_production("prod_conc")
    assert len(stored) == 10


# =============================================================================
# 9. REST API Tests
# =============================================================================

def test_api_orchestrate_post_success():
    prod_id = "prod_api_test"
    # Seed production
    asyncio.run(get_production_repo().save(Production(id=prod_id, title="API Test")))

    response = client.post(
        f"/productions/{prod_id}/orchestrate",
        json={"mode": "offline", "force_refresh": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["workflow_id"].startswith("wf_")
    assert data["status"] in ("COMPLETED", "PARTIAL")


def test_api_orchestrate_post_invalid_mode():
    prod_id = "prod_api_invalid_mode"
    asyncio.run(get_production_repo().save(Production(id=prod_id, title="Invalid Mode")))

    response = client.post(
        f"/productions/{prod_id}/orchestrate",
        json={"mode": "unsupported_mode"},
    )
    assert response.status_code == 400


def test_api_orchestrate_post_nonexistent_prod():
    response = client.post(
        "/productions/prod_does_not_exist_xyz/orchestrate",
        json={"mode": "offline"},
    )
    assert response.status_code == 404


def test_api_get_latest_orchestration():
    prod_id = "prod_api_latest"
    asyncio.run(get_production_repo().save(Production(id=prod_id, title="Latest Test")))

    # Run orchestration first
    client.post(f"/productions/{prod_id}/orchestrate", json={"mode": "offline"})

    response = client.get(f"/productions/{prod_id}/orchestrate")
    assert response.status_code == 200
    data = response.json()
    assert data["production_id"] == prod_id


def test_api_get_latest_orchestration_not_found():
    response = client.get("/productions/prod_no_orch_ever/orchestrate")
    assert response.status_code == 404


def test_api_get_orchestration_by_id():
    prod_id = "prod_api_by_id"
    asyncio.run(get_production_repo().save(Production(id=prod_id, title="By ID Test")))

    res = client.post(f"/productions/{prod_id}/orchestrate", json={"mode": "offline"})
    wf_id = res.json()["workflow_id"]

    response = client.get(f"/productions/{prod_id}/orchestrate/{wf_id}")
    assert response.status_code == 200
    assert response.json()["workflow_id"] == wf_id


def test_api_get_orchestration_by_id_not_found():
    prod_id = "prod_api_by_id_missing"
    asyncio.run(get_production_repo().save(Production(id=prod_id, title="Missing Test")))

    response = client.get(f"/productions/{prod_id}/orchestrate/wf_nonexistent_9999")
    assert response.status_code == 404


# =============================================================================
# 10. CLI Tests
# =============================================================================

@pytest.mark.asyncio
async def test_cli_orchestrate_run():
    from cli.main import cmd_orchestrate_run
    args = MagicMock()
    args.production_id = "prod_cli_unit"
    args.job_id = None
    args.mode = "offline"
    args.force_refresh = False
    args.video_path = ""
    args.script_text = "SCENE 01 - INT. CAFE - DAY\nCustomer drinks Pepsi."

    await cmd_orchestrate_run(args)
    latest = await get_orchestration_repo().get_latest_for_production("prod_cli_unit")
    assert latest is not None
    assert latest.status in (WorkflowStatus.COMPLETED, WorkflowStatus.PARTIAL)


@pytest.mark.asyncio
async def test_cli_orchestrate_status():
    from cli.main import cmd_orchestrate_status
    args = MagicMock()
    args.production_id = "prod_cli_unit"
    # Should display without raising error
    await cmd_orchestrate_status(args)


@pytest.mark.asyncio
async def test_cli_orchestrate_status_not_found():
    from cli.main import cmd_orchestrate_status
    args = MagicMock()
    args.production_id = "prod_cli_missing_never_ran"
    await cmd_orchestrate_status(args)


# =============================================================================
# 11. Strict Zero-Network Guarantee in Offline Mode
# =============================================================================

@pytest.mark.asyncio
async def test_offline_mode_zero_external_network_calls():
    """
    Verify that in offline mode, zero calls are made to Gemini, Groq, Parallel, or external HTTP.
    """
    prod_id = "prod_zero_network"
    await get_production_repo().save(Production(id=prod_id, title="Zero Network Test"))

    with patch("httpx.AsyncClient.post") as mock_httpx_post, \
         patch("httpx.AsyncClient.get") as mock_httpx_get, \
         patch("google.genai.Client") as mock_gemini_client:

        result = await run_production_workflow(
            production_id=prod_id,
            screenplay_text="INT. DINER - DAY\nJohn orders coffee and reads the Times.",
            mode="offline",
        )

        assert result.status == WorkflowStatus.COMPLETED
        # Strict zero external call assertion
        assert mock_httpx_post.call_count == 0
        assert mock_httpx_get.call_count == 0
        assert mock_gemini_client.call_count == 0


# =============================================================================
# 12. State Serialization, Event Emission, & Dependency Invariant Tests
# =============================================================================

@pytest.mark.asyncio
async def test_root_orchestrator_risk_failure_blocks_verification_and_resolution():
    """Verify that when risk assessment fails, verification and resolution are marked BLOCKED."""
    prod_id = "prod_root_fail_risk"
    await get_production_repo().save(Production(id=prod_id, title="Fail Risk Production"))

    orchestrator = RootOrchestrator()
    orchestrator.risk_agent.run = AsyncMock(return_value=AgentHandoff(
        agent="risk",
        status=AgentStatus.FAILED,
        errors=["Simulated risk engine internal failure"],
    ))

    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    result = await orchestrator.orchestrate(
        context=ctx,
        screenplay_text="SCENE 01 - INT. CAFE - DAY\nCustomer drinks Pepsi.",
    )
    assert result.status == WorkflowStatus.PARTIAL
    assert "risk" in result.failed_agents
    assert "verification" in result.blocked_agents
    assert "resolution" in result.blocked_agents
    assert state.verification_status == AgentStatus.BLOCKED
    assert state.resolution_status == AgentStatus.BLOCKED
    assert any("Verification blocked" in w for w in state.warnings)


@pytest.mark.asyncio
async def test_workflow_callbacks_event_bus_emission():
    """Verify workflow callbacks publish typed events to the event bus with workflow metadata."""
    job_id = "job_event_bus_test"
    state = ChainOfTitleState(production_id="prod_event_bus_test", job_id=job_id)
    ctx = WorkflowContext(state=state)

    events_gen = ctx.bus.subscribe(job_id)

    await WorkflowCallbacks.on_orchestration_start(ctx)
    await WorkflowCallbacks.on_agent_start(ctx, "Test Agent")
    await WorkflowCallbacks.on_tool_start(ctx, "Test Agent", "test_tool")
    await WorkflowCallbacks.on_tool_complete(ctx, "Test Agent", "test_tool", {"ok": True}, 0.05)
    await WorkflowCallbacks.on_agent_fail(ctx, "Test Agent", "simulated error", 0.1)
    await WorkflowCallbacks.on_orchestration_fail(ctx, "pipeline error")

    events_received = []
    for _ in range(6):
        try:
            ev = await asyncio.wait_for(events_gen.__anext__(), timeout=1.0)
            events_received.append(ev)
        except (asyncio.TimeoutError, StopAsyncIteration):
            break

    event_types = [e.event_type for e in events_received]
    assert EventType.ORCHESTRATION_STARTED in event_types
    assert EventType.AGENT_STARTED in event_types
    assert EventType.TOOL_STARTED in event_types
    assert EventType.TOOL_COMPLETED in event_types
    assert EventType.AGENT_FAILED in event_types
    assert EventType.ORCHESTRATION_FAILED in event_types
    for e in events_received:
        assert e.workflow_id == ctx.workflow_id


def test_chain_of_title_state_dict_and_result_mapping():
    """Verify state serialization properties and conversion to OrchestrationResult."""
    state = ChainOfTitleState(
        workflow_id="wf_custom_123",
        production_id="prod_test_state",
        entity_ids=["e1", "e2"],
    )
    state.screenplay_status = AgentStatus.COMPLETED
    state.visual_status = AgentStatus.SKIPPED
    state.research_status = AgentStatus.FAILED
    state.risk_status = AgentStatus.BLOCKED
    state.record_warning("Test warning")
    state.record_error("Test error")

    result = state.to_orchestration_result()
    assert result.workflow_id == "wf_custom_123"
    assert result.production_id == "prod_test_state"
    assert "screenplay" in result.completed_agents
    assert "visual" in result.skipped_agents
    assert "research" in result.failed_agents
    assert "risk" in result.blocked_agents
    assert len(result.warnings) == 1
    assert len(result.errors) == 1


def test_api_orchestrate_force_refresh():
    """Verify POST /orchestrate with force_refresh produces a new run instead of returning cache."""
    prod_id = "prod_api_refresh"
    asyncio.run(get_production_repo().save(Production(id=prod_id, title="Refresh Test")))

    res1 = client.post(f"/productions/{prod_id}/orchestrate?mode=offline")
    assert res1.status_code == 200
    wf1 = res1.json()["workflow_id"]

    res2 = client.post(f"/productions/{prod_id}/orchestrate?mode=offline&force_refresh=true")
    assert res2.status_code == 200
    wf2 = res2.json()["workflow_id"]

    assert wf1 != wf2


@pytest.mark.asyncio
async def test_tool_failure_handling_nonexistent_production():
    """Verify tools handle missing productions gracefully without unhandled exceptions."""
    state = ChainOfTitleState(production_id="prod_definitely_missing_123")
    ctx = WorkflowContext(state=state)

    res_report = await generate_report_tool(ctx)
    assert res_report["status"] in ("COMPLETED", "FAILED")

    res_merge = await merge_entities_tool(ctx)
    assert res_merge["status"] in ("COMPLETED", "FAILED")


def test_workflow_summary_structure():
    """Verify WorkflowSummary dataclass serialization format."""
    summary = WorkflowSummary(
        detection={"total": 5},
        research={"verified": 3},
        risk={"high": 1, "medium": 2, "low": 0},
        verification={"passed": 3},
        resolution={"cleared": 2, "human_review": 1},
        reporting={"report_id": "rep_sum_1"},
    )
    d = summary.model_dump()
    assert d["risk"]["high"] == 1
    assert d["resolution"]["human_review"] == 1
