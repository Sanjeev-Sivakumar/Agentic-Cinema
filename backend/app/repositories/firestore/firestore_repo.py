"""
Firestore repository implementations for future cloud deployment.
Drop-in replacement for in-memory repositories.
"""
from typing import List, Optional
from app.models.production import Production
from app.models.analysis import AnalysisJob
from app.models.entity import Entity
from app.models.evidence import Evidence
from app.models.risk import RiskAssessment
from app.models.verification import VerificationResult
from app.models.clearance import ClearanceRequest
from app.repositories.base import (
    ProductionRepository,
    AnalysisJobRepository,
    EntityRepository,
    EvidenceRepository,
    RiskRepository,
    VerificationRepository,
    ClearanceRepository,
)
from app.services.firestore import firestore_service

class FirestoreProductionRepository(ProductionRepository):
    def __init__(self):
        self.service = firestore_service

    async def create(self, production: Production) -> Production:
        await self.service.set_document("productions", production.id, production.model_dump())
        return production

    async def get(self, production_id: str) -> Optional[Production]:
        doc = await self.service.get_document("productions", production_id)
        return Production(**doc) if doc else None

    async def list_all(self) -> List[Production]:
        docs = await self.service.query_collection("productions", [])
        return [Production(**doc) for doc in docs]

    async def update(self, production: Production) -> Production:
        await self.service.set_document("productions", production.id, production.model_dump())
        return production

    async def delete(self, production_id: str) -> bool:
        return True
