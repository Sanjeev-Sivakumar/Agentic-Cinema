from abc import ABC, abstractmethod
from typing import Optional
from app.models.research import ResearchResult

class ResearchProvider(ABC):
    """Abstract interface for factual entity clearance research providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier string (e.g. 'local', 'parallel')."""
        pass

    @abstractmethod
    async def research_entity(
        self,
        entity_name: str,
        entity_type: str,
        context: Optional[str] = None,
        production_id: Optional[str] = "global",
        job_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        force_refresh: bool = False,
    ) -> ResearchResult:
        """
        Conduct factual research into entity identity and candidate rights holders.

        Parameters:
            entity_name: Canonical name of the detected entity.
            entity_type: Entity category (e.g. 'brand', 'product', 'music', 'artwork').
            context: Narrative or visual context snippet where entity appeared.
            production_id: Associated production identifier.
            job_id: Analysis job identifier.
            entity_id: Unique entity identifier.

        Returns:
            ResearchResult with status, candidate rights holder, confidence, and Evidence records.
        """
        pass
