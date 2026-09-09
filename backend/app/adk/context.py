from typing import Any, Optional
from app.core.config import settings, Settings
from app.core.logging import logger
from app.services import event_bus, EventBus
from app.adk.state import ChainOfTitleState
from app.repositories import (
    get_production_repo,
    get_job_repo,
    get_entity_repo,
    get_evidence_repo,
    get_research_repo,
    get_risk_repo,
    get_verification_repo,
    get_clearance_repo,
    get_resolution_repo,
    get_financial_exposure_repo,
    get_outreach_repo,
    get_remediation_repo,
    get_report_repo,
    get_orchestration_repo,
    ProductionRepository,
    AnalysisJobRepository,
    EntityRepository,
    EvidenceRepository,
    ResearchRepository,
    RiskRepository,
    VerificationRepository,
    ClearanceRepository,
    ReportRepository,
    OrchestrationRepository,
)


class WorkflowContext:
    """
    Context provided to Google ADK agents and tools during orchestration.
    Provides safe access to shared state, repositories, EventBus, configuration,
    and execution mode without exposing API keys or secrets.
    """

    def __init__(
        self,
        state: ChainOfTitleState,
        force_refresh: bool = False,
        execution_mode: Optional[str] = None,
        production_repo: Optional[ProductionRepository] = None,
        job_repo: Optional[AnalysisJobRepository] = None,
        entity_repo: Optional[EntityRepository] = None,
        evidence_repo: Optional[EvidenceRepository] = None,
        research_repo: Optional[ResearchRepository] = None,
        risk_repo: Optional[RiskRepository] = None,
        verification_repo: Optional[VerificationRepository] = None,
        clearance_repo: Optional[ClearanceRepository] = None,
        report_repo: Optional[ReportRepository] = None,
        orchestration_repo: Optional[OrchestrationRepository] = None,
        bus: Optional[EventBus] = None,
        config: Optional[Settings] = None,
    ):
        self.state = state
        self.force_refresh = force_refresh
        self.config = config or settings
        # Resolve execution mode: explicit argument > config.ADK_MODE > "offline"
        self.execution_mode = (execution_mode or getattr(self.config, "ADK_MODE", "offline")).lower()

        # Repositories
        self.production_repo = production_repo or get_production_repo()
        self.job_repo = job_repo or get_job_repo()
        self.entity_repo = entity_repo or get_entity_repo()
        self.evidence_repo = evidence_repo or get_evidence_repo()
        self.research_repo = research_repo or get_research_repo()
        self.risk_repo = risk_repo or get_risk_repo()
        self.verification_repo = verification_repo or get_verification_repo()
        self.clearance_repo = clearance_repo or get_clearance_repo()
        self.report_repo = report_repo or get_report_repo()
        self.orchestration_repo = orchestration_repo or get_orchestration_repo()

        # Event bus & logger
        self.bus = bus or event_bus
        self.logger = logger

    @property
    def production_id(self) -> str:
        return self.state.production_id

    @property
    def job_id(self) -> str:
        return self.state.job_id

    @property
    def workflow_id(self) -> str:
        return self.state.workflow_id

    @property
    def is_offline(self) -> bool:
        return self.execution_mode == "offline"

    @property
    def mode(self) -> str:
        return self.execution_mode

    @property
    def settings(self) -> Settings:
        return self.config

    @property
    def resolution_repo(self):
        return get_resolution_repo()

    @property
    def financial_exposure_repo(self):
        return get_financial_exposure_repo()

    @property
    def outreach_repo(self):
        return get_outreach_repo()

    @property
    def remediation_repo(self):
        return get_remediation_repo()
