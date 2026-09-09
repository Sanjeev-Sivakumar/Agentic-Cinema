from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from app.models.entity import Entity, EntityClassification, EntityType
from app.models.evidence import Evidence, EvidenceType
from app.models.production import Production
from app.models.remediation import RemediationStatus, RemediationType, VisualRemediationProposal
from app.models.resolution import ResolutionAction, ResolutionResult
from app.repositories import (
    get_entity_repo,
    get_evidence_repo,
    get_production_repo,
    get_remediation_repo,
    get_resolution_repo,
)
from app.services.visual_remediation_service import visual_remediation_service
from app.adk.agents.remediation_agent import RemediationAgent
from app.adk.context import WorkflowContext
from app.adk.state import ChainOfTitleState


@pytest.fixture
def sample_frame_image(tmp_path: Path) -> str:
    """Create a temporary dummy video frame."""
    frame_path = tmp_path / "test_frame_001.jpg"
    img = Image.new("RGB", (640, 360), color=(73, 109, 137))
    img.save(frame_path)
    return str(frame_path)


@pytest.mark.asyncio
async def test_visual_remediation_mask_and_blur(sample_frame_image: str):
    """Verify Gaussian blur and side-by-side comparison artifact generation."""
    entity = Entity(
        id="ent_vis_rem_01",
        production_id="prod_test_rem",
        name="Cadbury Bar",
        entity_type=EntityType.BRAND,
        classification=EntityClassification.VISUAL_ONLY,
        frame_path=sample_frame_image,
        bounding_box=[100, 100, 300, 250],
    )

    proposal = await visual_remediation_service.generate_proposal(
        entity=entity,
        remediation_type=RemediationType.BLUR_REMOVE,
        job_id="job_test_rem",
    )

    assert proposal is not None
    assert proposal.entity_name == "Cadbury Bar"
    assert proposal.remediation_type == RemediationType.BLUR_REMOVE
    assert proposal.status == RemediationStatus.PROPOSED
    assert "HUMAN/EDITOR REVIEW REQUIRED" in proposal.disclaimer

    # Check generated files
    assert Path(proposal.proposed_frame_path).exists()
    assert proposal.mask_path and Path(proposal.mask_path).exists()
    assert proposal.comparison_frame_path and Path(proposal.comparison_frame_path).exists()

    # Original frame must be untouched
    assert Path(sample_frame_image).exists()


@pytest.mark.asyncio
async def test_visual_remediation_neutral_replacement(sample_frame_image: str):
    """Verify neutral unbranded replacement technique."""
    entity = Entity(
        id="ent_vis_rem_02",
        production_id="prod_test_rem",
        name="Branded Soda Can",
        entity_type=EntityType.BRAND,
        classification=EntityClassification.VISUAL_ONLY,
        frame_path=sample_frame_image,
        bounding_box=[50, 50, 150, 200],
    )

    proposal = await visual_remediation_service.generate_proposal(
        entity=entity,
        remediation_type=RemediationType.NEUTRAL_REPLACEMENT,
        job_id="job_test_rem",
    )

    assert proposal is not None
    assert proposal.remediation_type == RemediationType.NEUTRAL_REPLACEMENT
    assert Path(proposal.proposed_frame_path).exists()
    assert proposal.comparison_frame_path and Path(proposal.comparison_frame_path).exists()


@pytest.mark.asyncio
async def test_remediation_repository_crud():
    """Verify remediation repository save and list."""
    repo = get_remediation_repo()
    prop = VisualRemediationProposal(
        remediation_id="rem_crud_01",
        production_id="prod_rem_crud",
        entity_id="ent_rem_crud",
        entity_name="Vintage Poster",
        job_id="job_crud_01",
        remediation_type=RemediationType.AI_INPAINTING,
        original_frame_path="/tmp/orig.jpg",
        mask_path="/tmp/mask.jpg",
        proposed_frame_path="/tmp/clean.jpg",
    )
    await repo.save(prop)

    fetched = await repo.get("rem_crud_01")
    assert fetched is not None
    assert fetched.entity_name == "Vintage Poster"

    plist = await repo.list_for_production("prod_rem_crud")
    assert len(plist) >= 1
    assert any(x.id == "rem_crud_01" for x in plist)


@pytest.mark.asyncio
async def test_adk_remediation_agent(sample_frame_image: str):
    """Verify ADK RemediationAgent workflow integration."""
    prod_repo = get_production_repo()
    ent_repo = get_entity_repo()
    ev_repo = get_evidence_repo()
    resol_repo = get_resolution_repo()

    prod = Production(id="prod_adk_rem_01", title="Studio Shoot")
    await prod_repo.save(prod)

    ent = Entity(
        id="ent_adk_rem_01",
        production_id="prod_adk_rem_01",
        name="Neon Sign",
        entity_type=EntityType.SIGNAGE,
        classification=EntityClassification.VISUAL_ONLY,
        risk_level="HIGH",
        frame_path=sample_frame_image,
        bounding_box=[20, 20, 100, 80],
    )
    await ent_repo.save(ent)

    ev = Evidence(
        id="ev_adk_rem_01",
        production_id="prod_adk_rem_01",
        entity_id="ent_adk_rem_01",
        evidence_type=EvidenceType.VIDEO_FRAME,
        frame_path=sample_frame_image,
        bounding_box=[20, 20, 100, 80],
    )
    await ev_repo.save(ev)

    resol = ResolutionResult(
        id="resol_adk_rem_01",
        production_id="prod_adk_rem_01",
        entity_id="ent_adk_rem_01",
        recommended_action=ResolutionAction.CONSIDER_REPLACEMENT,
    )
    await resol_repo.save(resol)

    state = ChainOfTitleState(
        production_id="prod_adk_rem_01",
        job_id="job_adk_rem_01",
    )
    state.entity_ids = ["ent_adk_rem_01"]
    state.evidence_ids = ["ev_adk_rem_01"]
    context = WorkflowContext(state=state)

    agent = RemediationAgent()
    handoff = await agent.run(context, entity_ids=["ent_adk_rem_01"])
    assert handoff.status.value == "COMPLETED"
    assert len(handoff.result_ids) >= 1
