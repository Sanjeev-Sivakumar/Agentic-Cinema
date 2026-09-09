import asyncio
from typing import Dict, List, Optional, Any
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
    FinancialExposureRepository,
    OutreachRepository,
    RemediationRepository,
)

class InMemoryProductionRepository(ProductionRepository):
    def __init__(self):
        self._data: Dict[str, Production] = {}
        self._lock = asyncio.Lock()

    async def create(self, production: Production) -> Production:
        async with self._lock:
            self._data[production.id] = production
            return production

    async def save(self, production: Production) -> Production:
        return await self.create(production)


    async def get(self, production_id: str) -> Optional[Production]:
        async with self._lock:
            return self._data.get(production_id)

    async def list_all(self) -> List[Production]:
        async with self._lock:
            return list(self._data.values())

    async def update(self, production: Production) -> Production:
        async with self._lock:
            self._data[production.id] = production
            return production

    async def delete(self, production_id: str) -> bool:
        async with self._lock:
            if production_id in self._data:
                del self._data[production_id]
                return True
            return False


class InMemoryAnalysisJobRepository(AnalysisJobRepository):
    def __init__(self):
        self._data: Dict[str, AnalysisJob] = {}
        self._lock = asyncio.Lock()

    async def create(self, job: AnalysisJob) -> AnalysisJob:
        async with self._lock:
            self._data[job.job_id] = job
            return job

    async def get(self, job_id: str) -> Optional[AnalysisJob]:
        async with self._lock:
            return self._data.get(job_id)

    async def get_by_production(self, production_id: str) -> List[AnalysisJob]:
        async with self._lock:
            return [job for job in self._data.values() if job.production_id == production_id]

    async def update(self, job: AnalysisJob) -> AnalysisJob:
        async with self._lock:
            self._data[job.job_id] = job
            return job

    async def save(self, job: AnalysisJob) -> AnalysisJob:
        return await self.update(job)


class InMemoryEntityRepository(EntityRepository):
    def __init__(self):
        self._data: Dict[str, Entity] = {}
        self._lock = asyncio.Lock()

    async def create(self, entity: Entity) -> Entity:
        async with self._lock:
            self._data[entity.id] = entity
            return entity

    async def save(self, entity: Entity) -> Entity:
        return await self.create(entity)


    async def get(self, entity_id: str) -> Optional[Entity]:
        async with self._lock:
            return self._data.get(entity_id)

    async def list_by_production(self, production_id: str) -> List[Entity]:
        async with self._lock:
            return [e for e in self._data.values() if e.production_id == production_id]

    async def list_by_job(self, job_id: str) -> List[Entity]:
        async with self._lock:
            return [e for e in self._data.values() if e.job_id == job_id]

    async def update(self, entity: Entity) -> Entity:
        async with self._lock:
            self._data[entity.id] = entity
            return entity

    async def delete(self, entity_id: str) -> bool:
        async with self._lock:
            if entity_id in self._data:
                del self._data[entity_id]
                return True
            return False


class InMemoryEvidenceRepository(EvidenceRepository):
    def __init__(self):
        self._data: Dict[str, Evidence] = {}
        self._lock = asyncio.Lock()

    async def create(self, evidence: Evidence) -> Evidence:
        async with self._lock:
            self._data[evidence.id] = evidence
            return evidence

    async def save(self, evidence: Evidence) -> Evidence:
        return await self.create(evidence)

    async def get(self, evidence_id: str) -> Optional[Evidence]:
        async with self._lock:
            return self._data.get(evidence_id)

    async def list_by_production(self, production_id: str) -> List[Evidence]:
        async with self._lock:
            return [e for e in self._data.values() if e.production_id == production_id]

    async def list_by_entity(self, entity_id: str) -> List[Evidence]:
        async with self._lock:
            return [e for e in self._data.values() if e.entity_id == entity_id]


class InMemoryRiskRepository(RiskRepository):
    def __init__(self):
        self._data: Dict[str, RiskAssessment] = {}
        self._lock = asyncio.Lock()

    async def save(self, risk: RiskAssessment) -> RiskAssessment:
        async with self._lock:
            self._data[risk.risk_id] = risk
            return risk

    async def create(self, risk: RiskAssessment) -> RiskAssessment:
        return await self.save(risk)

    async def get_by_entity(self, entity_id: str) -> Optional[RiskAssessment]:
        async with self._lock:
            matching = [r for r in self._data.values() if r.entity_id == entity_id]
            if not matching:
                return None
            return max(matching, key=lambda r: (r.updated_at or r.created_at))


    async def get(self, entity_id_or_risk_id: str) -> Optional[RiskAssessment]:
        async with self._lock:
            if entity_id_or_risk_id in self._data:
                return self._data[entity_id_or_risk_id]
            for r in self._data.values():
                if r.entity_id == entity_id_or_risk_id:
                    return r
            return None

    async def list_for_production(self, production_id: str) -> List[RiskAssessment]:
        async with self._lock:
            return [r for r in self._data.values() if r.production_id == production_id]

    async def list_by_production(self, production_id: str) -> List[RiskAssessment]:
        return await self.list_for_production(production_id)


class InMemoryVerificationRepository(VerificationRepository):
    def __init__(self):
        self._data: Dict[str, VerificationResult] = {}
        self._lock = asyncio.Lock()

    async def save(self, verification: VerificationResult) -> VerificationResult:
        async with self._lock:
            key = verification.verification_id or getattr(verification, "id", None)
            self._data[key] = verification
            return verification

    async def create(self, verification: VerificationResult) -> VerificationResult:
        return await self.save(verification)

    async def get(self, verification_id_or_entity_id: str) -> Optional[VerificationResult]:
        async with self._lock:
            if verification_id_or_entity_id in self._data:
                return self._data[verification_id_or_entity_id]
            matching = [v for v in self._data.values() if v.entity_id == verification_id_or_entity_id]
            if matching:
                return max(matching, key=lambda v: v.verified_at)
            return None

    async def get_by_entity(self, entity_id: str) -> Optional[VerificationResult]:
        async with self._lock:
            matching = [v for v in self._data.values() if v.entity_id == entity_id]
            if not matching:
                return None
            return max(matching, key=lambda v: v.verified_at)

    async def list_for_production(self, production_id: str) -> List[VerificationResult]:
        async with self._lock:
            return [v for v in self._data.values() if v.production_id == production_id]

    async def list_by_production(self, production_id: str) -> List[VerificationResult]:
        return await self.list_for_production(production_id)


class InMemoryClearanceRepository(ClearanceRepository):
    def __init__(self):
        self._data: Dict[str, ClearanceRequest] = {}
        self._lock = asyncio.Lock()

    async def create(self, request: ClearanceRequest) -> ClearanceRequest:
        async with self._lock:
            self._data[request.id] = request
            return request

    async def get(self, request_id: str) -> Optional[ClearanceRequest]:
        async with self._lock:
            return self._data.get(request_id)

    async def list_by_production(self, production_id: str) -> List[ClearanceRequest]:
        async with self._lock:
            return [r for r in self._data.values() if r.production_id == production_id]

    async def update(self, request: ClearanceRequest) -> ClearanceRequest:
        async with self._lock:
            self._data[request.id] = request
            return request


class InMemoryResearchRepository(ResearchRepository):
    def __init__(self):
        self._data: Dict[str, ResearchResult] = {}
        self._lock = asyncio.Lock()

    async def save(self, result: ResearchResult) -> ResearchResult:
        async with self._lock:
            self._data[result.id] = result
            return result

    async def get_by_entity(self, entity_id: str) -> Optional[ResearchResult]:
        async with self._lock:
            for res in self._data.values():
                if res.entity_id == entity_id:
                    return res
            return None

    async def get(self, entity_id_or_result_id: str) -> Optional[ResearchResult]:
        async with self._lock:
            if entity_id_or_result_id in self._data:
                return self._data[entity_id_or_result_id]
            for res in self._data.values():
                if res.entity_id == entity_id_or_result_id:
                    return res
            return None

    async def list_for_production(self, production_id: str) -> List[ResearchResult]:
        async with self._lock:
            return [r for r in self._data.values() if r.production_id == production_id]


class InMemoryResolutionRepository(ResolutionRepository):
    def __init__(self):
        self._data: Dict[str, ResolutionResult] = {}
        self._lock = asyncio.Lock()

    async def save(self, resolution: ResolutionResult) -> ResolutionResult:
        async with self._lock:
            key = resolution.resolution_id or resolution.id
            self._data[key] = resolution
            return resolution

    async def create(self, resolution: ResolutionResult) -> ResolutionResult:
        return await self.save(resolution)

    async def get(self, resolution_id_or_entity_id: str) -> Optional[ResolutionResult]:
        async with self._lock:
            if resolution_id_or_entity_id in self._data:
                return self._data[resolution_id_or_entity_id]
            matching = [r for r in self._data.values() if r.entity_id == resolution_id_or_entity_id]
            if matching:
                return max(matching, key=lambda r: r.updated_at)
            return None

    async def get_by_entity(self, entity_id: str) -> Optional[ResolutionResult]:
        async with self._lock:
            matching = [r for r in self._data.values() if r.entity_id == entity_id]
            if not matching:
                return None
            return max(matching, key=lambda r: r.updated_at)

    async def list_for_production(self, production_id: str) -> List[ResolutionResult]:
        async with self._lock:
            return [r for r in self._data.values() if r.production_id == production_id]

    async def list_by_production(self, production_id: str) -> List[ResolutionResult]:
        return await self.list_for_production(production_id)


class InMemoryReportRepository(ReportRepository):
    def __init__(self):
        self._data: Dict[str, ReportResult] = {}
        self._lock = asyncio.Lock()

    async def create(self, report: ReportResult) -> ReportResult:
        async with self._lock:
            self._data[report.report_id] = report
            return report

    async def save(self, report: ReportResult) -> ReportResult:
        return await self.create(report)

    async def get(self, report_id: str) -> Optional[ReportResult]:
        async with self._lock:
            return self._data.get(report_id)

    async def get_by_production(self, production_id: str) -> Optional[ReportResult]:
        async with self._lock:
            reports = [r for r in self._data.values() if r.production_id == production_id]
            if not reports:
                return None
            return max(reports, key=lambda r: r.generated_at)

    async def list_by_production(self, production_id: str) -> List[ReportResult]:
        async with self._lock:
            reports = [r for r in self._data.values() if r.production_id == production_id]
            return sorted(reports, key=lambda r: r.generated_at, reverse=True)

    async def delete(self, report_id: str) -> bool:
        async with self._lock:
            if report_id in self._data:
                del self._data[report_id]
                return True
            return False


class InMemoryFinancialExposureRepository(FinancialExposureRepository):
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def save(self, exposure: Any) -> Any:
        async with self._lock:
            self._data[exposure.exposure_id] = exposure
            return exposure

    async def get(self, exposure_id: str) -> Optional[Any]:
        async with self._lock:
            return self._data.get(exposure_id)

    async def get_by_entity(self, entity_id: str) -> Optional[Any]:
        async with self._lock:
            for exp in self._data.values():
                if exp.entity_id == entity_id:
                    return exp
            return None

    async def list_for_production(self, production_id: str) -> List[Any]:
        async with self._lock:
            return [exp for exp in self._data.values() if exp.production_id == production_id]

    async def list_by_production(self, production_id: str) -> List[Any]:
        return await self.list_for_production(production_id)


class InMemoryOutreachRepository(OutreachRepository):
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def save(self, draft: Any) -> Any:
        async with self._lock:
            self._data[draft.outreach_id] = draft
            return draft

    async def get(self, outreach_id: str) -> Optional[Any]:
        async with self._lock:
            return self._data.get(outreach_id)

    async def list_for_production(self, production_id: str) -> List[Any]:
        async with self._lock:
            return [d for d in self._data.values() if d.production_id == production_id]

    async def list_by_production(self, production_id: str) -> List[Any]:
        return await self.list_for_production(production_id)

    async def list_by_entity(self, entity_id: str) -> List[Any]:
        async with self._lock:
            return [d for d in self._data.values() if d.entity_id == entity_id]


class InMemoryRemediationRepository(RemediationRepository):
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def save(self, proposal: Any) -> Any:
        async with self._lock:
            self._data[proposal.remediation_id] = proposal
            return proposal

    async def get(self, remediation_id: str) -> Optional[Any]:
        async with self._lock:
            return self._data.get(remediation_id)

    async def list_for_production(self, production_id: str) -> List[Any]:
        async with self._lock:
            return [p for p in self._data.values() if p.production_id == production_id]

    async def list_by_production(self, production_id: str) -> List[Any]:
        return await self.list_for_production(production_id)

    async def list_by_entity(self, entity_id: str) -> List[Any]:
        async with self._lock:
            return [p for p in self._data.values() if p.entity_id == entity_id]


