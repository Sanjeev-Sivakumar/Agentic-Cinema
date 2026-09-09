from abc import ABC, abstractmethod
from typing import List, Optional
from app.models.orchestration import OrchestrationResult


class OrchestrationRepository(ABC):
    """Abstract base repository for persisting Google ADK Orchestration outcomes."""

    @abstractmethod
    async def save(self, result: OrchestrationResult) -> OrchestrationResult:
        """Save or update an orchestration result."""
        pass

    @abstractmethod
    async def get(self, workflow_id: str) -> Optional[OrchestrationResult]:
        """Retrieve an orchestration result by workflow ID."""
        pass

    @abstractmethod
    async def get_latest_for_production(self, production_id: str) -> Optional[OrchestrationResult]:
        """Retrieve the most recent orchestration result for a production."""
        pass

    @abstractmethod
    async def list_for_production(self, production_id: str) -> List[OrchestrationResult]:
        """List all orchestration results for a production ordered by creation time descending."""
        pass
