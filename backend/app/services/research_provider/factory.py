from typing import Optional
from app.core.config import settings
from app.core.logging import logger
from app.services.research_provider.base import ResearchProvider
from app.services.research_provider.local_provider import LocalResearchProvider
from app.services.research_provider.parallel_provider import ParallelResearchProvider

def get_research_provider(
    provider_name: Optional[str] = None,
) -> ResearchProvider:
    """
    Factory function returning the configured or explicitly requested ResearchProvider.
    Defaults to LocalResearchProvider for zero-cost, deterministic local development and tests.
    Returns ParallelResearchProvider when RESEARCH_PROVIDER is 'parallel'.
    """
    chosen = (provider_name or getattr(settings, "RESEARCH_PROVIDER", "local")).lower().strip()

    if chosen == "parallel":
        return ParallelResearchProvider()

    elif chosen == "local":
        return LocalResearchProvider()

    else:
        logger.warning(
            f"[ResearchProviderFactory] Unknown RESEARCH_PROVIDER '{chosen}'; defaulting to LocalResearchProvider"
        )
        return LocalResearchProvider()


