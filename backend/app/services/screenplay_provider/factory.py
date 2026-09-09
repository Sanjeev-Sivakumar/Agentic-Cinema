from typing import Optional
from app.core.config import settings
from app.core.logging import logger
from app.services.screenplay_provider.base import ScreenplayExtractionProvider
from app.services.screenplay_provider.local_provider import LocalScreenplayProvider
from app.services.screenplay_provider.gemini_provider import GeminiScreenplayProvider

def get_screenplay_provider(
    provider_name: Optional[str] = None,
) -> ScreenplayExtractionProvider:
    """
    Factory function returning the configured or explicitly requested ScreenplayExtractionProvider.
    Defaults to LocalScreenplayProvider for deterministic, zero-cost development/testing.
    """
    chosen = (provider_name or getattr(settings, "SCREENPLAY_PROVIDER", "local")).lower().strip()

    if chosen == "gemini":
        gemini_key = getattr(settings, "GEMINI_API_KEY", "")
        return GeminiScreenplayProvider(api_key=gemini_key)

    elif chosen == "local":
        return LocalScreenplayProvider()

    else:
        logger.warning(
            f"[ScreenplayProviderFactory] Unknown SCREENPLAY_PROVIDER '{chosen}'; defaulting to LocalScreenplayProvider"
        )
        return LocalScreenplayProvider()
