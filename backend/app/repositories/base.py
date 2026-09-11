from abc import ABC, abstractmethod
from typing import List, Optional
from app.models.production import Production
from app.models.analysis import AnalysisJob
from app.models.entity import Entity
from app.models.evidence import Evidence
from app.models.risk import RiskAssessment
from app.models.verification import VerificationResult
from app.models.clearance import ClearanceRequest
from app.models.report import Report, ReportResult
from app.models.research import ResearchResult
from app.models.resolution import ResolutionResult

class ProductionRepository(ABC):
    @abstractmethod
    async def create(self, production: Production) -> Production:
        pass

    @abstractmethod
    async def save(self, production: Production) -> Production:
        pass


    @abstractmethod
    async def get(self, production_id: str) -> Optional[Production]:
        pass

    @abstractmethod
    async def list_all(self) -> List[Production]:
        pass

    @abstractmethod
    async def update(self, production: Production) -> Production:
        pass

    @abstractmethod
    async def delete(self, production_id: str) -> bool:
        pass


class AnalysisJobRepository(ABC):
    @abstractmethod
    async def create(self, job: AnalysisJob) -> AnalysisJob:
        pass

    @abstractmethod
    async def get(self, job_id: str) -> Optional[AnalysisJob]:
        pass

    @abstractmethod
    async def get_by_production(self, production_id: str) -> List[AnalysisJob]:
        pass

    @abstractmethod
    async def update(self, job: AnalysisJob) -> AnalysisJob:
        pass

    async def save(self, job: AnalysisJob) -> AnalysisJob:
        existing = await self.get(job.job_id)
        if existing:
            return await self.update(job)
        return await self.create(job)


class EntityRepository(ABC):
    @abstractmethod
    async def create(self, entity: Entity) -> Entity:
        pass

    @abstractmethod
    async def save(self, entity: Entity) -> Entity:
        pass


    @abstractmethod
    async def get(self, entity_id: str) -> Optional[Entity]:
        pass

    @abstractmethod
    async def list_by_production(self, production_id: str) -> List[Entity]:
        pass

    @abstractmethod
    async def list_by_job(self, job_id: str) -> List[Entity]:
        pass

    @abstractmethod
    async def update(self, entity: Entity) -> Entity:
        pass

    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        pass


class EvidenceRepository(ABC):
    @abstractmethod
    async def create(self, evidence: Evidence) -> Evidence:
        pass

    @abstractmethod
    async def get(self, evidence_id: str) -> Optional[Evidence]:
        pass

    @abstractmethod
    async def list_by_production(self, production_id: str) -> List[Evidence]:
        pass

    @abstractmethod
    async def list_by_entity(self, entity_id: str) -> List[Evidence]:
        pass

    async def save(self, evidence: Evidence) -> Evidence:
        return await self.create(evidence)


class RiskRepository(ABC):
    @abstractmethod
    async def save(self, risk: RiskAssessment) -> RiskAssessment:
        pass

    @abstractmethod
    async def get(self, risk_id: str) -> Optional[RiskAssessment]:
        pass

    @abstractmethod
    async def get_by_entity(self, entity_id: str) -> Optional[RiskAssessment]:
        pass

    @abstractmethod
    async def list_for_production(self, production_id: str) -> List[RiskAssessment]:
        pass

    async def create(self, risk: RiskAssessment) -> RiskAssessment:
        return await self.save(risk)

    async def list_by_production(self, production_id: str) -> List[RiskAssessment]:
        return await self.list_for_production(production_id)


class VerificationRepository(ABC):
    @abstractmethod
    async def create(self, verification: VerificationResult) -> VerificationResult:
        pass

    @abstractmethod
    async def save(self, verification: VerificationResult) -> VerificationResult:
        pass

    @abstractmethod
    async def get(self, verification_id: str) -> Optional[VerificationResult]:
        pass

    @abstractmethod
    async def get_by_entity(self, entity_id: str) -> Optional[VerificationResult]:
        pass

    @abstractmethod
    async def list_by_production(self, production_id: str) -> List[VerificationResult]:
        pass

    @abstractmethod
    async def list_for_production(self, production_id: str) -> List[VerificationResult]:
        pass


class ClearanceRepository(ABC):
    @abstractmethod
    async def create(self, request: ClearanceRequest) -> ClearanceRequest:
        pass

    @abstractmethod
    async def get(self, request_id: str) -> Optional[ClearanceRequest]:
        pass

    @abstractmethod
    async def list_by_production(self, production_id: str) -> List[ClearanceRequest]:
        pass

    @abstractmethod
    async def update(self, request: ClearanceRequest) -> ClearanceRequest:
        pass


class ResearchRepository(ABC):
    @abstractmethod
    async def save(self, result: "ResearchResult") -> "ResearchResult":
        pass

    @abstractmethod
    async def get_by_entity(self, entity_id: str) -> Optional["ResearchResult"]:
        pass

    @abstractmethod
    async def get(self, entity_id: str) -> Optional["ResearchResult"]:
        pass

    @abstractmethod
    async def list_for_production(self, production_id: str) -> List["ResearchResult"]:
        pass


class ResolutionRepository(ABC):
    @abstractmethod
    async def create(self, resolution: ResolutionResult) -> ResolutionResult:
        pass

    @abstractmethod
    async def save(self, resolution: ResolutionResult) -> ResolutionResult:
        pass

    @abstractmethod
    async def get(self, resolution_id_or_entity_id: str) -> Optional[ResolutionResult]:
        pass

    @abstractmethod
    async def get_by_entity(self, entity_id: str) -> Optional[ResolutionResult]:
        pass

    @abstractmethod
    async def list_by_production(self, production_id: str) -> List[ResolutionResult]:
        pass

    @abstractmethod
    async def list_for_production(self, production_id: str) -> List[ResolutionResult]:
        pass


class ReportRepository(ABC):
    @abstractmethod
    async def create(self, report: ReportResult) -> ReportResult:
        pass

    @abstractmethod
    async def save(self, report: ReportResult) -> ReportResult:
        pass

    @abstractmethod
    async def get(self, report_id: str) -> Optional[ReportResult]:
        pass

    @abstractmethod
    async def get_by_production(self, production_id: str) -> Optional[ReportResult]:
        pass

    @abstractmethod
    async def list_by_production(self, production_id: str) -> List[ReportResult]:
        pass

class FinancialExposureRepository(ABC):
    @abstractmethod
    async def save(self, exposure: "FinancialExposure") -> "FinancialExposure":
        pass

    @abstractmethod
    async def get(self, exposure_id: str) -> Optional["FinancialExposure"]:
        pass

    @abstractmethod
    async def get_by_entity(self, entity_id: str) -> Optional["FinancialExposure"]:
        pass

    @abstractmethod
    async def list_for_production(self, production_id: str) -> List["FinancialExposure"]:
        pass

    @abstractmethod
    async def list_by_production(self, production_id: str) -> List["FinancialExposure"]:
        pass


class OutreachRepository(ABC):
    @abstractmethod
    async def save(self, draft: "ClearanceOutreachDraft") -> "ClearanceOutreachDraft":
        pass

    @abstractmethod
    async def get(self, outreach_id: str) -> Optional["ClearanceOutreachDraft"]:
        pass

    @abstractmethod
    async def list_for_production(self, production_id: str) -> List["ClearanceOutreachDraft"]:
        pass

    @abstractmethod
    async def list_by_production(self, production_id: str) -> List["ClearanceOutreachDraft"]:
        pass

    @abstractmethod
    async def list_by_entity(self, entity_id: str) -> List["ClearanceOutreachDraft"]:
        pass


class RemediationRepository(ABC):
    @abstractmethod
    async def save(self, proposal: "VisualRemediationProposal") -> "VisualRemediationProposal":
        pass

    @abstractmethod
    async def get(self, remediation_id: str) -> Optional["VisualRemediationProposal"]:
        pass

    @abstractmethod
    async def list_for_production(self, production_id: str) -> List["VisualRemediationProposal"]:
        pass

    @abstractmethod
    async def list_by_production(self, production_id: str) -> List["VisualRemediationProposal"]:
        pass

    @abstractmethod
    async def list_by_entity(self, entity_id: str) -> List["VisualRemediationProposal"]:
        pass


from app.repositories.orchestration.base import OrchestrationRepository

