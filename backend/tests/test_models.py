import pytest
from app.models.entity import Entity, EntitySource, EntityClassification, EntityType, RiskLevel
from app.models.analysis import AnalysisJob, JobStatus
from app.models.events import PipelineStage

def test_entity_dynamic_classification():
    # Visual Only
    e_visual = Entity(
        production_id="prod_01",
        name="Coffee Cup Brand",
        sources=[EntitySource.VISUAL],
    )
    assert e_visual.classification == EntityClassification.VISUAL_ONLY

    # Script Only
    e_script = Entity(
        production_id="prod_01",
        name="Vintage Ferrari mentioned in script dialogue",
        sources=[EntitySource.SCRIPT],
    )
    assert e_script.classification == EntityClassification.SCRIPT_ONLY

    # Both (Script + Visual)
    e_both = Entity(
        production_id="prod_01",
        name="Hero Watch",
        sources=[EntitySource.SCRIPT, EntitySource.VISUAL],
    )
    assert e_both.classification == EntityClassification.BOTH

    # Audio Only
    e_audio = Entity(
        production_id="prod_01",
        name="Background Jazz Track",
        sources=[EntitySource.AUDIO],
    )
    assert e_audio.classification == EntityClassification.AUDIO_ONLY

def test_analysis_job_initialization():
    job = AnalysisJob.create_new(production_id="prod_999")
    assert job.production_id == "prod_999"
    assert job.status == JobStatus.QUEUED
    assert len(job.stages) >= 12
    assert "Screenplay Extraction" in job.stages
    assert "Report Generation" in job.stages
    assert "Financial Exposure" in job.stages
    assert "Clearance Outreach" in job.stages
    assert "Visual Remediation" in job.stages
    assert job.stages["Screenplay Extraction"].status.value == "WAITING"
