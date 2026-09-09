from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, List
import uuid
from pydantic import BaseModel, Field
from app.models.events import PipelineStage

class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class StageStatus(str, Enum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class StageState(BaseModel):
    stage: str
    status: StageStatus = StageStatus.WAITING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    latest_event: Optional[str] = None
    duration_ms: Optional[int] = None

class AnalysisJob(BaseModel):
    job_id: str = Field(default_factory=lambda: f"job_{uuid.uuid4().hex[:10]}")
    production_id: str
    status: JobStatus = JobStatus.QUEUED
    current_stage: Optional[str] = None
    progress: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    frames_processed: int = 0
    scenes_detected: int = 0
    entities_detected: int = 0
    visual_only_count: int = 0
    research_completed: int = 0
    verification_completed: int = 0
    stages: Dict[str, StageState] = Field(default_factory=dict)

    @classmethod
    def create_new(cls, production_id: str) -> "AnalysisJob":
        job = cls(production_id=production_id)
        for stage in PipelineStage:
            job.stages[stage.value] = StageState(stage=stage.value)
        return job
