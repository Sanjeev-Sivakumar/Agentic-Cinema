from app.repositories.base import (
    ProductionRepository,
    AnalysisJobRepository,
    EntityRepository,
    EvidenceRepository,
    RiskRepository,
    VerificationRepository,
    ClearanceRepository,
    ResearchRepository,
    ResolutionRepository,
    ReportRepository,
    OrchestrationRepository,
    FinancialExposureRepository,
    OutreachRepository,
    RemediationRepository,
)
from app.repositories.local.in_memory import (
    InMemoryProductionRepository,
    InMemoryAnalysisJobRepository,
    InMemoryEntityRepository,
    InMemoryEvidenceRepository,
    InMemoryRiskRepository,
    InMemoryVerificationRepository,
    InMemoryClearanceRepository,
    InMemoryResearchRepository,
    InMemoryResolutionRepository,
    InMemoryReportRepository,
    InMemoryFinancialExposureRepository,
    InMemoryOutreachRepository,
    InMemoryRemediationRepository,
)
from app.repositories.orchestration import InMemoryOrchestrationRepository

# Global repository instances for local development
_production_repo = InMemoryProductionRepository()
_job_repo = InMemoryAnalysisJobRepository()
_entity_repo = InMemoryEntityRepository()
_evidence_repo = InMemoryEvidenceRepository()
_risk_repo = InMemoryRiskRepository()
_verification_repo = InMemoryVerificationRepository()
_clearance_repo = InMemoryClearanceRepository()
_research_repo = InMemoryResearchRepository()
_resolution_repo = InMemoryResolutionRepository()
_report_repo = InMemoryReportRepository()
_orchestration_repo = InMemoryOrchestrationRepository()
_financial_exposure_repo = InMemoryFinancialExposureRepository()
_outreach_repo = InMemoryOutreachRepository()
_remediation_repo = InMemoryRemediationRepository()

def get_production_repo() -> ProductionRepository:
    return _production_repo

def get_job_repo() -> AnalysisJobRepository:
    return _job_repo

def get_entity_repo() -> EntityRepository:
    return _entity_repo

def get_evidence_repo() -> EvidenceRepository:
    return _evidence_repo

def get_risk_repo() -> RiskRepository:
    return _risk_repo

def get_verification_repo() -> VerificationRepository:
    return _verification_repo

def get_clearance_repo() -> ClearanceRepository:
    return _clearance_repo

def get_research_repo() -> ResearchRepository:
    return _research_repo

def get_resolution_repo() -> ResolutionRepository:
    return _resolution_repo

def get_report_repo() -> ReportRepository:
    return _report_repo

def get_orchestration_repo() -> OrchestrationRepository:
    return _orchestration_repo

def get_financial_exposure_repo() -> FinancialExposureRepository:
    return _financial_exposure_repo

def get_outreach_repo() -> OutreachRepository:
    return _outreach_repo

def get_remediation_repo() -> RemediationRepository:
    return _remediation_repo

__all__ = [
    "ProductionRepository",
    "AnalysisJobRepository",
    "EntityRepository",
    "EvidenceRepository",
    "RiskRepository",
    "VerificationRepository",
    "ClearanceRepository",
    "ResearchRepository",
    "ResolutionRepository",
    "ReportRepository",
    "OrchestrationRepository",
    "FinancialExposureRepository",
    "OutreachRepository",
    "RemediationRepository",
    "get_production_repo",
    "get_job_repo",
    "get_entity_repo",
    "get_evidence_repo",
    "get_risk_repo",
    "get_verification_repo",
    "get_clearance_repo",
    "get_research_repo",
    "get_resolution_repo",
    "get_report_repo",
    "get_orchestration_repo",
    "get_financial_exposure_repo",
    "get_outreach_repo",
    "get_remediation_repo",
]
