from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.services.screenplay_parser import ScreenplayScene
from app.services.screenplay_provider.base import ScreenplayExtractionProvider
from app.services.screenplay_provider.local_provider import LocalScreenplayProvider
from app.services.screenplay_provider.gemini_provider import GeminiScreenplayProvider

class HybridScreenplayProvider(ScreenplayExtractionProvider):
    """
    Hybrid Screenplay Provider:
    Attempts Google Gemini extraction if GEMINI_API_KEY is available.
    Falls back gracefully to LocalScreenplayProvider if Gemini API is unavailable or errors.
    """

    def __init__(self, gemini_provider: GeminiScreenplayProvider, local_provider: LocalScreenplayProvider):
        self._gemini = gemini_provider
        self._local = local_provider

    @property
    def provider_name(self) -> str:
        return "hybrid"

    async def extract_entities(
        self,
        screenplay_text: str,
        scenes: Optional[List[ScreenplayScene]] = None,
    ) -> List[Dict[str, Any]]:
        if self._gemini and self._gemini.api_key:
            try:
                gemini_entities = await self._gemini.extract_entities(screenplay_text, scenes=scenes)
                if gemini_entities:
                    logger.info(f"[HybridScreenplayProvider] Extracted {len(gemini_entities)} entities via Gemini GenAI")
                    return gemini_entities
            except Exception as e:
                logger.warning(f"[HybridScreenplayProvider] Gemini extraction failed ({e}); falling back to local extractor")

        # Fallback to local rule-based extractor
        return await self._local.extract_entities(screenplay_text, scenes=scenes)


def get_screenplay_provider(
    provider_name: Optional[str] = None,
) -> ScreenplayExtractionProvider:
    """
    Factory function returning the configured ScreenplayExtractionProvider.
    """
    chosen = (provider_name or getattr(settings, "SCREENPLAY_PROVIDER", "local")).lower().strip()
    gemini_key = getattr(settings, "GEMINI_API_KEY", "")

    local_prov = LocalScreenplayProvider()

    if chosen == "gemini" and gemini_key:
        return GeminiScreenplayProvider(api_key=gemini_key)
    elif chosen == "local":
        return local_prov
    else:
        # Default to hybrid if gemini_key exists, otherwise local
        if gemini_key:
            gemini_prov = GeminiScreenplayProvider(api_key=gemini_key)
            return HybridScreenplayProvider(gemini_prov, local_prov)
        return local_prov

