from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.services.screenplay_parser import ScreenplayScene

class ScreenplayExtractionProvider(ABC):
    """Abstract interface for screenplay entity extraction intelligence providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier string (e.g. 'local', 'gemini')."""
        pass

    @abstractmethod
    async def extract_entities(
        self,
        screenplay_text: str,
        scenes: Optional[List[ScreenplayScene]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract clearance-relevant entities appearing in the screenplay.

        Parameters:
            screenplay_text: Raw or cleaned screenplay script text.
            scenes: Optional pre-parsed ScreenplayScene segments.

        Returns:
            List of candidate entity dictionaries containing:
            name, entity_type, confidence, scene, context, source
        """
        pass
