import asyncio
from typing import Dict, List, Optional
from app.models.orchestration import OrchestrationResult
from app.repositories.orchestration.base import OrchestrationRepository


class InMemoryOrchestrationRepository(OrchestrationRepository):
    """
    Thread-safe and async-safe in-memory repository for Google ADK Orchestration outcomes.
    Suitable for local development, tests, and CI/CD.
    """

    def __init__(self):
        self._workflows: Dict[str, OrchestrationResult] = {}
        self._lock = asyncio.Lock()

    async def save(self, result: OrchestrationResult) -> OrchestrationResult:
        async with self._lock:
            self._workflows[result.workflow_id] = result
            return result

    async def get(self, workflow_id: str) -> Optional[OrchestrationResult]:
        async with self._lock:
            return self._workflows.get(workflow_id)

    async def get_latest_for_production(self, production_id: str) -> Optional[OrchestrationResult]:
        async with self._lock:
            matches = [
                res for res in self._workflows.values()
                if res.production_id == production_id
            ]
            if not matches:
                return None
            matches.sort(key=lambda x: x.started_at, reverse=True)
            return matches[0]

    async def list_for_production(self, production_id: str) -> List[OrchestrationResult]:
        async with self._lock:
            matches = [
                res for res in self._workflows.values()
                if res.production_id == production_id
            ]
            matches.sort(key=lambda x: x.started_at, reverse=True)
            return matches

    async def clear(self) -> None:
        """Clear all stored workflows (useful in tests)."""
        async with self._lock:
            self._workflows.clear()
