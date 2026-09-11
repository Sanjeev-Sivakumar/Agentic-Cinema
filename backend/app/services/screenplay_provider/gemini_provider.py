import json
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.services.screenplay_parser import ScreenplayScene, screenplay_scene_parser
from app.services.screenplay_provider.base import ScreenplayExtractionProvider

GEMINI_SCREENPLAY_SYSTEM_PROMPT = """You are a screenplay clearance intelligence system for film, television, and media production.

Analyze the provided screenplay text and identify ONLY clearance-relevant entities.
Look for:
* recognizable brands or named products
* real companies or corporations
* music tracks, songs, or musical artists mentioned in scene actions/dialogue
* real public figures referenced in dialogue or narrative
* real films, TV shows, or media works
* named posters, paintings, sculptures, or artworks
* real books, novels, or publications
* real recognizable commercial locations, stores, hotels, or venues

CRITICAL RULES:
1. Do NOT report generic characters (e.g. John, Arjun, Waiter, Police Officer) unless identified as an actual real-world public figure.
2. Do NOT report generic objects, furniture, ordinary vehicles, rooms, clothing, or props without brand affiliation.
3. Preserve the scene number for each entity mention.
4. Extract direct textual context supporting the detection.
5. Do NOT provide legal conclusions, licensing advice, rights holder assessments, or contact information.
6. Do NOT invent or infer entities not explicitly evidenced in the text.
7. Return ONLY valid JSON matching this schema:
{
  "entities": [
    {
      "name": "Exact Brand or Entity Name",
      "entity_type": "brand|product|company|music|artist|public_figure|film|tv|artwork|book|location|other",
      "confidence": 0.95,
      "scene": 1,
      "context": "Exact sentence or context from screenplay"
    }
  ]
}
If no clearance-relevant entities exist, return:
{"entities": []}"""

class GeminiScreenplayProvider(ScreenplayExtractionProvider):
    """
    Google Gemini Screenplay Intelligence Provider.
    Extracts clearance entities from screenplay text using structured Gemini JSON generation.
    NOTE: DORMANT / PRODUCTION PROVIDER. Must not be invoked during Phase 3 tests.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        self.model = model or getattr(
            settings,
            "GEMINI_SCREENPLAY_MODEL",
            getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash"),
        )
        self._client = None
        self._init_client()

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _init_client(self):
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info(f"[GeminiScreenplayProvider] Initialized Gemini client (model: {self.model})")
            except Exception as e:
                logger.warning(f"[GeminiScreenplayProvider] Failed to initialize Gemini client: {e}")
                self._client = None
        else:
            logger.debug("[GeminiScreenplayProvider] GEMINI_API_KEY not configured; client uninitialized")

    async def extract_entities(
        self,
        screenplay_text: str,
        scenes: Optional[List[ScreenplayScene]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract clearance-relevant entities via structured Gemini LLM prompt.
        """
        if not self.api_key:
            logger.error("[GeminiScreenplayProvider] GEMINI_API_KEY is missing")
            raise RuntimeError("GEMINI_API_KEY is missing or not configured for GeminiScreenplayProvider")

        if self._client is None:
            self._init_client()
            if self._client is None:
                raise RuntimeError("Could not initialize Gemini GenAI client")

        if not screenplay_text or not screenplay_text.strip():
            return []

        active_scenes = scenes if scenes is not None else screenplay_scene_parser.parse_scenes(screenplay_text)
        scenes_formatted = "\n\n".join(
            [f"--- SCENE {s.scene_number}: {s.heading} ---\n{s.text}" for s in active_scenes]
        )

        user_prompt = (
            f"Extract all clearance-relevant entities from the following screenplay:\n\n"
            f"{scenes_formatted}\n\n"
            f"Return strict JSON matching the schema."
        )

        try:
            from google.genai import types
            response = self._client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=GEMINI_SCREENPLAY_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            raw_text = getattr(response, "text", "") or "{}"
        except Exception as e:
            logger.error(f"[GeminiScreenplayProvider] API call failed: {e}")
            raise RuntimeError(f"Gemini Screenplay API error: {e}")

        # Parse JSON
        clean_text = raw_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        elif clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        try:
            parsed = json.loads(clean_text)
            raw_entities = parsed.get("entities", [])
            if not isinstance(raw_entities, list):
                raw_entities = []
        except Exception as json_err:
            logger.error(f"[GeminiScreenplayProvider] JSON decoding error: {json_err}. Content: {clean_text[:200]}")
            raw_entities = []

        formatted: List[Dict[str, Any]] = []
        for ent in raw_entities:
            if not isinstance(ent, dict):
                continue
            name = str(ent.get("name", "")).strip()
            if not name:
                continue

            try:
                scene_num = int(ent.get("scene", 1) or 1)
            except (ValueError, TypeError):
                scene_num = 1

            try:
                conf = float(ent.get("confidence", 0.95))
            except (ValueError, TypeError):
                conf = 0.95

            formatted.append(
                {
                    "name": name,
                    "entity_type": str(ent.get("entity_type", "brand")).lower().strip(),
                    "confidence": conf,
                    "scene": scene_num,
                    "context": str(ent.get("context", "")).strip(),
                    "source": ["screenplay"],
                }
            )

        return formatted
