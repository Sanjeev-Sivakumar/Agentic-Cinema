import pytest
from app.models.entity import Entity, EntityClassification, EntityType
from app.models.outreach import ClearanceOutreachDraft, OutreachStatus
from app.models.production import Production
from app.models.research import ResearchResult, ResearchStatus
from app.models.resolution import ResolutionAction, ResolutionPriority, ResolutionResult, ResolutionStatus
from app.repositories import (
    get_entity_repo,
    get_outreach_repo,
    get_production_repo,
    get_research_repo,
    get_resolution_repo,
)
from app.services.clearance_outreach_service import clearance_outreach_service
from app.services.gmail_service import gmail_service
from app.adk.agents.outreach_agent import OutreachAgent
from app.adk.context import WorkflowContext
from app.adk.state import ChainOfTitleState


@pytest.mark.asyncio
async def test_clearance_outreach_draft_generation():
    """Verify clearance outreach letter drafting for a licensed entity."""
    entity = Entity(
        id="ent_outreach_cadbury",
        production_id="prod_test_outreach",
        name="Cadbury",
        entity_type=EntityType.BRAND,
        classification=EntityClassification.BOTH,
        scene=3,
        timestamp=12.5,
    )

    research = ResearchResult(
        id="res_outreach_cadbury",
        production_id="prod_test_outreach",
        entity_id="ent_outreach_cadbury",
        entity_name="Cadbury",
        query='"Cadbury" corporate rights holder trademark status',
        status=ResearchStatus.SUCCESS,
        candidate_rights_holder="Cadbury UK Limited / Mondelez International",
    )

    resolution = ResolutionResult(
        id="resol_outreach_cadbury",
        production_id="prod_test_outreach",
        entity_id="ent_outreach_cadbury",
        recommended_action=ResolutionAction.REQUEST_LICENSE_INFORMATION,
        resolution_status=ResolutionStatus.ACTION_REQUIRED,
        priority=ResolutionPriority.HIGH,
    )

    draft = await clearance_outreach_service.generate_outreach_draft(
        production_title="The Midnight Run",
        entity=entity,
        research=research,
        resolution=resolution,
    )

    assert draft.entity_name == "Cadbury"
    assert "Cadbury UK Limited" in draft.rights_holder
    assert draft.status == OutreachStatus.DRAFTED
    assert draft.requires_human_approval is True
    assert "The Midnight Run" in draft.subject
    assert "Scene 3" in draft.body_text or "12.50s" in draft.body_text
    assert "Worldwide" in draft.requested_rights_scope


@pytest.mark.asyncio
async def test_gmail_service_draft_only_guarantee():
    """Verify that GmailService strictly creates drafts and never auto-dispatches emails."""
    draft_res = await gmail_service.create_draft(
        to_email="licensing@mondelezinternational.com",
        subject="PERMISSION REQUEST: Cadbury Brand Usage",
        body_text="Dear Licensing Department, We request permission to depict Cadbury Dairy Milk.",
        production_title="Echoes of Time",
    )

    assert draft_res["status"] in ("DRAFT_CREATED", "DRAFT_MIME_PREPARED")
    assert draft_res["draft_id"] is not None


@pytest.mark.asyncio
async def test_outreach_lifecycle_transitions():
    """Verify outreach status transitions and human approval."""
    repo = get_outreach_repo()
    draft = ClearanceOutreachDraft(
        outreach_id="out_test_life_01",
        production_id="prod_out_life",
        entity_id="ent_out_life",
        entity_name="Sony Walkman",
        rights_holder="Sony Group Corporation",
        recipient_email="clearance@sony.com",
        subject="Clearance Request: Sony Walkman",
        body_text="Clearance letter body...",
        body_html="<p>Clearance letter body...</p>",
        status=OutreachStatus.DRAFTED,
        requires_human_approval=True,
    )
    await repo.save(draft)

    # Update status to APPROVED
    draft.status = OutreachStatus.APPROVED
    draft.approved_by = "Legal Counsel"
    await repo.save(draft)

    fetched = await repo.get("out_test_life_01")
    assert fetched.status == OutreachStatus.APPROVED
    assert fetched.approved_by == "Legal Counsel"


@pytest.mark.asyncio
async def test_adk_outreach_agent():
    """Verify ADK OutreachAgent workflow execution."""
    prod_repo = get_production_repo()
    ent_repo = get_entity_repo()
    res_repo = get_research_repo()
    resol_repo = get_resolution_repo()

    prod = Production(id="prod_adk_out_01", title="Cyber Heist")
    await prod_repo.save(prod)

    ent = Entity(
        id="ent_adk_out_01",
        production_id="prod_adk_out_01",
        name="Rolex",
        entity_type=EntityType.BRAND,
        classification=EntityClassification.BOTH,
        risk_level="HIGH",
    )
    await ent_repo.save(ent)

    res = ResearchResult(
        id="res_adk_out_01",
        production_id="prod_adk_out_01",
        entity_id="ent_adk_out_01",
        entity_name="Rolex",
        query='"Rolex" corporate rights holder',
        status=ResearchStatus.SUCCESS,
        candidate_rights_holder="Rolex SA",
    )
    await res_repo.save(res)

    resol = ResolutionResult(
        id="resol_adk_out_01",
        production_id="prod_adk_out_01",
        entity_id="ent_adk_out_01",
        recommended_action=ResolutionAction.REQUEST_LICENSE_INFORMATION,
        resolution_status=ResolutionStatus.ACTION_REQUIRED,
    )
    await resol_repo.save(resol)

    state = ChainOfTitleState(
        production_id="prod_adk_out_01",
        job_id="job_adk_out_01",
    )
    state.entity_ids = ["ent_adk_out_01"]
    context = WorkflowContext(state=state)

    agent = OutreachAgent()
    handoff = await agent.run(context, entity_ids=["ent_adk_out_01"])
    assert handoff.status.value == "COMPLETED"
    assert len(handoff.result_ids) >= 1
