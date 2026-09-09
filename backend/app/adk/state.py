from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

from app.models.orchestration import (
    WorkflowStatus,
    AgentStatus,
    WorkflowSummary,
    OrchestrationResult,
)


class ChainOfTitleState(BaseModel):
    """
    Serializable shared workflow state for the Google ADK Root Agent and specialized agents.
    Tracks execution status, entity references, evidence lineage, agent timings, and errors.
    """
    production_id: str
    job_id: str = Field(default_factory=lambda: f"job_{uuid.uuid4().hex[:8]}")
    workflow_id: str = Field(default_factory=lambda: f"wf_{uuid.uuid4().hex[:10]}")
    workflow_status: WorkflowStatus = WorkflowStatus.PENDING

    # Agent statuses
    screenplay_status: AgentStatus = AgentStatus.PENDING
    visual_status: AgentStatus = AgentStatus.PENDING
    research_status: AgentStatus = AgentStatus.PENDING
    risk_status: AgentStatus = AgentStatus.PENDING
    verification_status: AgentStatus = AgentStatus.PENDING
    resolution_status: AgentStatus = AgentStatus.PENDING
    exposure_status: AgentStatus = AgentStatus.PENDING
    outreach_status: AgentStatus = AgentStatus.PENDING
    remediation_status: AgentStatus = AgentStatus.PENDING
    report_status: AgentStatus = AgentStatus.PENDING

    # Results & entity references
    screenplay_result_ids: List[str] = Field(default_factory=list)
    entity_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    research_result_ids: List[str] = Field(default_factory=list)
    risk_result_ids: List[str] = Field(default_factory=list)
    verification_result_ids: List[str] = Field(default_factory=list)
    resolution_result_ids: List[str] = Field(default_factory=list)
    exposure_result_ids: List[str] = Field(default_factory=list)
    outreach_result_ids: List[str] = Field(default_factory=list)
    remediation_result_ids: List[str] = Field(default_factory=list)
    report_id: Optional[str] = None

    # Metadata & tracking
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    current_agent: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    agent_durations: Dict[str, float] = Field(default_factory=dict)
    agent_outputs: Dict[str, Any] = Field(default_factory=dict)
    workflow_summary: Optional[WorkflowSummary] = None

    def update_agent_status(
        self,
        agent_name: str,
        status: AgentStatus,
        duration: float = 0.0,
        outputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update individual agent status and timestamps."""
        self.updated_at = datetime.now(timezone.utc)
        normalized = agent_name.lower()

        if "screenplay" in normalized or "text" in normalized:
            self.screenplay_status = status
        elif "visual" in normalized or "video" in normalized:
            self.visual_status = status
        elif "research" in normalized:
            self.research_status = status
        elif "risk" in normalized:
            self.risk_status = status
        elif "verification" in normalized or "verify" in normalized:
            self.verification_status = status
        elif "resolution" in normalized or "resolve" in normalized:
            self.resolution_status = status
        elif "exposure" in normalized or "financial" in normalized:
            self.exposure_status = status
        elif "outreach" in normalized:
            self.outreach_status = status
        elif "remediation" in normalized or "remediate" in normalized:
            self.remediation_status = status
        elif "report" in normalized:
            self.report_status = status

        if duration > 0.0:
            self.agent_durations[agent_name] = round(duration, 3)
        if outputs:
            self.agent_outputs[agent_name] = outputs

    def record_error(self, error: str) -> None:
        """Record workflow error and update timestamp."""
        self.errors.append(error)
        self.updated_at = datetime.now(timezone.utc)

    def record_warning(self, warning: str) -> None:
        """Record workflow warning and update timestamp."""
        self.warnings.append(warning)
        self.updated_at = datetime.now(timezone.utc)

    def get_completed_agents(self) -> List[str]:
        completed = []
        if self.screenplay_status == AgentStatus.COMPLETED:
            completed.append("screenplay")
        if self.visual_status == AgentStatus.COMPLETED:
            completed.append("visual")
        if self.research_status == AgentStatus.COMPLETED:
            completed.append("research")
        if self.risk_status == AgentStatus.COMPLETED:
            completed.append("risk")
        if self.verification_status == AgentStatus.COMPLETED:
            completed.append("verification")
        if self.resolution_status == AgentStatus.COMPLETED:
            completed.append("resolution")
        if self.exposure_status == AgentStatus.COMPLETED:
            completed.extend(["exposure", "financial_exposure"])
        if self.outreach_status == AgentStatus.COMPLETED:
            completed.extend(["outreach", "clearance_outreach"])
        if self.remediation_status == AgentStatus.COMPLETED:
            completed.extend(["remediation", "visual_remediation"])
        if self.report_status == AgentStatus.COMPLETED:
            completed.append("report")
        return completed

    def get_failed_agents(self) -> List[str]:
        failed = []
        if self.screenplay_status == AgentStatus.FAILED:
            failed.append("screenplay")
        if self.visual_status == AgentStatus.FAILED:
            failed.append("visual")
        if self.research_status == AgentStatus.FAILED:
            failed.append("research")
        if self.risk_status == AgentStatus.FAILED:
            failed.append("risk")
        if self.verification_status == AgentStatus.FAILED:
            failed.append("verification")
        if self.resolution_status == AgentStatus.FAILED:
            failed.append("resolution")
        if self.exposure_status == AgentStatus.FAILED:
            failed.extend(["exposure", "financial_exposure"])
        if self.outreach_status == AgentStatus.FAILED:
            failed.extend(["outreach", "clearance_outreach"])
        if self.remediation_status == AgentStatus.FAILED:
            failed.extend(["remediation", "visual_remediation"])
        if self.report_status == AgentStatus.FAILED:
            failed.append("report")
        return failed

    def get_blocked_agents(self) -> List[str]:
        blocked = []
        if self.screenplay_status == AgentStatus.BLOCKED:
            blocked.append("screenplay")
        if self.visual_status == AgentStatus.BLOCKED:
            blocked.append("visual")
        if self.research_status == AgentStatus.BLOCKED:
            blocked.append("research")
        if self.risk_status == AgentStatus.BLOCKED:
            blocked.append("risk")
        if self.verification_status == AgentStatus.BLOCKED:
            blocked.append("verification")
        if self.resolution_status == AgentStatus.BLOCKED:
            blocked.append("resolution")
        if self.exposure_status == AgentStatus.BLOCKED:
            blocked.extend(["exposure", "financial_exposure"])
        if self.outreach_status == AgentStatus.BLOCKED:
            blocked.extend(["outreach", "clearance_outreach"])
        if self.remediation_status == AgentStatus.BLOCKED:
            blocked.extend(["remediation", "visual_remediation"])
        if self.report_status == AgentStatus.BLOCKED:
            blocked.append("report")
        return blocked

    def get_skipped_agents(self) -> List[str]:
        skipped = []
        if self.screenplay_status == AgentStatus.SKIPPED:
            skipped.append("screenplay")
        if self.visual_status == AgentStatus.SKIPPED:
            skipped.append("visual")
        if self.research_status == AgentStatus.SKIPPED:
            skipped.append("research")
        if self.risk_status == AgentStatus.SKIPPED:
            skipped.append("risk")
        if self.verification_status == AgentStatus.SKIPPED:
            skipped.append("verification")
        if self.resolution_status == AgentStatus.SKIPPED:
            skipped.append("resolution")
        if self.exposure_status == AgentStatus.SKIPPED:
            skipped.extend(["exposure", "financial_exposure"])
        if self.outreach_status == AgentStatus.SKIPPED:
            skipped.extend(["outreach", "clearance_outreach"])
        if self.remediation_status == AgentStatus.SKIPPED:
            skipped.extend(["remediation", "visual_remediation"])
        if self.report_status == AgentStatus.SKIPPED:
            skipped.append("report")
        return skipped

    def to_orchestration_result(self) -> OrchestrationResult:
        """Convert state into final persistent OrchestrationResult model."""
        end_time = self.completed_at or datetime.now(timezone.utc)
        total_duration = max(0.0, (end_time - self.started_at).total_seconds())

        return OrchestrationResult(
            workflow_id=self.workflow_id,
            production_id=self.production_id,
            job_id=self.job_id,
            status=self.workflow_status,
            current_agent=self.current_agent,
            completed_agents=self.get_completed_agents(),
            failed_agents=self.get_failed_agents(),
            blocked_agents=self.get_blocked_agents(),
            skipped_agents=self.get_skipped_agents(),
            entity_ids=list(dict.fromkeys(self.entity_ids)),
            evidence_ids=list(dict.fromkeys(self.evidence_ids)),
            report_id=self.report_id,
            warnings=list(self.warnings),
            errors=list(self.errors),
            started_at=self.started_at,
            completed_at=self.completed_at,
            duration=round(total_duration, 3),
            workflow_summary=self.workflow_summary,
            agent_durations=dict(self.agent_durations),
            agent_outputs=dict(self.agent_outputs),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state for JSON / SSE transmission."""
        data = self.model_dump()
        data["started_at"] = self.started_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        data["completed_at"] = self.completed_at.isoformat() if self.completed_at else None
        data["workflow_status"] = self.workflow_status.value
        data["screenplay_status"] = self.screenplay_status.value
        data["visual_status"] = self.visual_status.value
        data["research_status"] = self.research_status.value
        data["risk_status"] = self.risk_status.value
        data["verification_status"] = self.verification_status.value
        data["resolution_status"] = self.resolution_status.value
        data["report_status"] = self.report_status.value
        return data
