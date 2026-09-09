import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.services.vision_provider.base import VisionProvider

GEMINI_CLEARANCE_SYSTEM_PROMPT = """You are a visual clearance-detection system for film footage.

Identify only entities visible in this image that could potentially matter for media clearance.

Look for:
* recognizable brands or logos
* named products
* companies
* music/artists if visually represented
* public figures
* films or TV works
* posters
* artwork
* books
* recognizable locations or signage

Do NOT report generic people, objects, furniture, clothing, or ordinary scenes.
Do NOT invent an entity that is not visually supported.

Return ONLY valid JSON with this structure:
{
  "entities": [
    {
      "name": "string",
      "entity_type": "brand|product|company|music|artist|public_figure|film|tv|artwork|book|location|other",
      "confidence": 0.0,
      "reason": "short evidence-based reason"
    }
  ]
}

If no clearance-relevant entity is visible, return:
{"entities": []}"""

def get_image_mime_type(file_path: Path) -> str:
    """Determine image MIME type based on file extension."""
    suffix = file_path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    elif suffix == ".png":
        return "image/png"
    elif suffix == ".webp":
        return "image/webp"
    elif suffix == ".gif":
        return "image/gif"
    return "image/jpeg"

class GeminiVisionProvider(VisionProvider):
    """
    Google Gemini Multimodal Vision Provider (PRIMARY / DEFAULT).
    Uses the google-genai SDK to perform structured clearance-focused visual entity extraction.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        self.model = model or getattr(settings, "GEMINI_VISION_MODEL", getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash"))
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
                logger.info(f"[GeminiVisionProvider] Initialized Gemini GenAI client (model: {self.model})")
            except Exception as e:
                logger.warning(f"[GeminiVisionProvider] Could not initialize Gemini GenAI client: {e}")
                self._client = None
        else:
            logger.debug("[GeminiVisionProvider] No GEMINI_API_KEY provided; client uninitialized")

    async def analyze_frame(
        self,
        frame_path: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute multimodal inspection via Gemini."""
        start_time = time.time()
        timestamp = context.get("timestamp", 0.0)
        scene_number = context.get("scene_number", 1)
        ocr_hints = context.get("ocr_hints", "")
        obj_hints = context.get("obj_hints", "")

        # 1. Validate API key
        if not self.api_key:
            latency = int((time.time() - start_time) * 1000)
            logger.error("[GeminiVisionProvider] GEMINI_API_KEY is missing or not configured")
            return {
                "status": "VISION_API_ERROR",
                "provider": self.provider_name,
                "model": self.model,
                "latency_ms": latency,
                "timestamp": timestamp,
                "scene_number": scene_number,
                "frame_path": frame_path,
                "entities": [],
                "error": "GEMINI_API_KEY is missing or not configured",
            }

        # 2. Validate frame path existence
        img_file = Path(frame_path)
        if not img_file.exists() or not img_file.is_file():
            latency = int((time.time() - start_time) * 1000)
            logger.error(f"[GeminiVisionProvider] Frame image file not found: '{frame_path}'")
            return {
                "status": "VISION_API_ERROR",
                "provider": self.provider_name,
                "model": self.model,
                "latency_ms": latency,
                "timestamp": timestamp,
                "scene_number": scene_number,
                "frame_path": frame_path,
                "entities": [],
                "error": f"Frame image file not found: '{frame_path}'",
            }

        # 3. Read image bytes
        try:
            with open(img_file, "rb") as f:
                img_bytes = f.read()
            if not img_bytes:
                raise ValueError("Image file is empty (0 bytes)")
        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            logger.error(f"[GeminiVisionProvider] Could not read image file '{frame_path}': {e}")
            return {
                "status": "VISION_API_ERROR",
                "provider": self.provider_name,
                "model": self.model,
                "latency_ms": latency,
                "timestamp": timestamp,
                "scene_number": scene_number,
                "frame_path": frame_path,
                "entities": [],
                "error": f"Could not read image file: {e}",
            }

        mime_type = get_image_mime_type(img_file)

        # 4. Lazy initialize client if needed
        if self._client is None:
            self._init_client()
            if self._client is None:
                latency = int((time.time() - start_time) * 1000)
                return {
                    "status": "VISION_API_ERROR",
                    "provider": self.provider_name,
                    "model": self.model,
                    "latency_ms": latency,
                    "timestamp": timestamp,
                    "scene_number": scene_number,
                    "frame_path": frame_path,
                    "entities": [],
                    "error": "Failed to initialize Gemini GenAI client",
                }

        # 5. Build concise prompt
        hints = []
        if ocr_hints:
            hints.append(f"OCR: {ocr_hints[:120]}")
        if obj_hints:
            hints.append(f"Objects: {obj_hints[:120]}")
        hints_str = f" Context signals: {'; '.join(hints)}." if hints else ""

        user_prompt = (
            f"Analyze candidate visual signals for video frame at {timestamp}s (Scene {scene_number}).{hints_str}\n"
            "Return valid JSON matching the requested schema."
        )

        # 6. Execute Gemini generate_content (with model fallback on 429 / 404)
        raw_text = ""
        effective_model = self.model
        models_to_try = [self.model]
        for fallback in ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash"]:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        from google.genai import types

        last_error = None
        for m in models_to_try:
            try:
                response = self._client.models.generate_content(
                    model=m,
                    contents=[
                        types.Part.from_bytes(data=img_bytes, mime_type=mime_type),
                        user_prompt,
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=GEMINI_CLEARANCE_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
                raw_text = getattr(response, "text", "") or "{}"
                effective_model = m
                break
            except Exception as api_err:
                last_error = api_err
                err_str = str(api_err)
                lower_err = err_str.lower()
                is_recoverable = (
                    "429" in err_str
                    or "resourceexhausted" in lower_err
                    or "rate_limit" in lower_err
                    or "quota" in lower_err
                    or "404" in err_str
                    or "not_found" in lower_err
                )
                if is_recoverable and m != models_to_try[-1]:
                    logger.warning(
                        f"[GeminiVisionProvider] Model '{m}' returned recoverable error ({err_str[:100]}); "
                        f"trying next fallback model..."
                    )
                    continue
                else:
                    break

        if not raw_text and last_error is not None:
            latency = int((time.time() - start_time) * 1000)
            err_str = str(last_error)
            lower_err = err_str.lower()
            is_rate_limited = (
                "429" in err_str
                or "resourceexhausted" in lower_err
                or "rate_limit" in lower_err
                or "quota" in lower_err
            )
            status = "VISION_RATE_LIMITED" if is_rate_limited else "VISION_API_ERROR"
            logger.error(f"[GeminiVisionProvider] API call failed ({status}): {err_str}")
            return {
                "status": status,
                "provider": self.provider_name,
                "model": effective_model,
                "latency_ms": latency,
                "timestamp": timestamp,
                "scene_number": scene_number,
                "frame_path": frame_path,
                "entities": [],
                "error": err_str,
            }

        # 7. Robust JSON parsing and validation
        latency = int((time.time() - start_time) * 1000)
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
            if not isinstance(parsed, dict):
                raise ValueError("Top-level JSON is not an object")

            raw_entities = parsed.get("entities")
            if not isinstance(raw_entities, list):
                raise ValueError("'entities' field is not a list")

        except Exception as json_err:
            logger.error(f"[GeminiVisionProvider] JSON parsing error: {json_err}. Raw: {clean_text[:300]}")
            return {
                "status": "VISION_JSON_ERROR",
                "provider": self.provider_name,
                "model": self.model,
                "latency_ms": latency,
                "timestamp": timestamp,
                "scene_number": scene_number,
                "frame_path": frame_path,
                "entities": [],
                "error": f"JSON parsing error: {json_err}",
                "raw_response": clean_text[:500],
            }

        # 8. Validate and filter individual entities
        from app.services.clearance_filter import is_clearance_relevant

        formatted_entities: List[Dict[str, Any]] = []
        for ent in raw_entities:
            if not isinstance(ent, dict):
                continue
            name = str(ent.get("name", "")).strip()
            if not name:
                continue

            entity_type = str(ent.get("entity_type", "brand")).lower().strip()
            try:
                conf = float(ent.get("confidence", 0.90))
                conf = max(0.0, min(1.0, conf))
            except (ValueError, TypeError):
                conf = 0.90

            reason = str(
                ent.get("reason")
                or ent.get("observation")
                or ent.get("visual_basis")
                or "Visually observed in frame"
            ).strip()

            candidate = {
                "name": name,
                "entity_type": entity_type,
                "confidence": conf,
                "reason": reason,
                "observation": reason,
                "visual_basis": reason,
                "evidence_type": "direct",
            }

            # Filter non-clearance noise
            if not is_clearance_relevant(candidate):
                logger.debug(f"[GeminiVisionProvider] Filtered non-clearance candidate: '{name}'")
                continue

            formatted_entities.append(candidate)

        # Distinguish SUCCESS vs NO_ENTITIES
        status = "VISION_SUCCESS" if formatted_entities else "VISION_NO_ENTITIES"
        logger.info(
            f"[GeminiVisionProvider] Successfully analyzed frame at {timestamp}s: "
            f"{len(formatted_entities)} entities ({status}, {latency}ms, model: {self.model})"
        )

        return {
            "status": status,
            "provider": self.provider_name,
            "model": self.model,
            "latency_ms": latency,
            "timestamp": timestamp,
            "scene_number": scene_number,
            "frame_path": frame_path,
            "entities": formatted_entities,
            "raw_response": raw_text,
        }
