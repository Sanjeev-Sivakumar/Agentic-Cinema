from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

SYSTEM_PRE_CLEARANCE_PROMPT = """You are a visual evidence extraction component for a film/video pre-clearance intelligence system.
Analyze ONLY what is visually supported by the provided candidate video frame.
Identify potentially clearance-relevant entities (brands, logos, products, registered marks, public figures, artworks, posters, books, films, tv shows, signage, distinctive vehicles).

CRITICAL CONSTRAINTS:
1. Do NOT make legal conclusions or claim legal risk.
2. Do NOT claim ownership or invent rights holders.
3. Do NOT invent licensing requirements or contact details.
4. Distinguish:
   - "direct" (clearly and directly visible in the frame)
   - "inference" (implied by visual context or partial branding)
   - "uncertain" (ambiguous, blurry, or low certainty)
5. Return strict JSON matching this exact schema:
{
  "entities": [
    {
      "name": "Exact detected brand or entity name",
      "entity_type": "brand | product | company | person | public_figure | music | artwork | poster | book | film | tv_show | location | signage | vehicle | other",
      "confidence": 0.95,
      "observation": "Direct visual description of where and how it appears in the frame",
      "evidence_type": "direct | inference | uncertain"
    }
  ]
}
"""

class VisionProvider(ABC):
    """
    Abstract Base Class for Multimodal Vision LLM Providers.
    Both GeminiVisionProvider and GroqVisionProvider implement this common interface.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'gemini', 'groq')."""
        pass

    @abstractmethod
    async def analyze_frame(
        self,
        frame_path: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze a candidate frame using multimodal vision intelligence.

        Args:
            frame_path: Local filesystem path to the frame image (JPEG/PNG).
            context: Contextual signals including timestamp, scene_number,
                     local OCR results, and local object detections.

        Returns:
            Dict containing:
                "status": "SUCCESS" | "LOCAL_FALLBACK" | "ERROR",
                "provider": str,
                "model": str,
                "latency_ms": int,
                "timestamp": float,
                "scene_number": int,
                "frame_path": str,
                "entities": List[Dict[str, Any]],
                "raw_response": str (optional)
        """
        pass
