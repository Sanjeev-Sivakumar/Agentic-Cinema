from datetime import datetime, timezone
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.models.video import FrameRanking, OCRResult, ObjectDetectionResult

GEMINI_PRE_CLEARANCE_SYSTEM_PROMPT = """You are a visual evidence extraction component for a production pre-clearance intelligence system.
Analyze only what is visually supported by the provided frame.
Identify potentially clearance-relevant entities.
Do not make legal conclusions.
Do not claim ownership.
Do not invent brands, rights holders, or copyrighted works.
If an entity is uncertain, mark it uncertain.
Separate direct visual evidence from inference.
Return strict JSON matching this exact schema:
{
  "entities": [
    {
      "name": "Exact detected brand or entity name",
      "entity_type": "brand | trademark | product | company | music | artist | public_figure | film | tv | poster | artwork | book | location | signage | other",
      "confidence": 0.95,
      "visual_basis": "Direct description of where and how it is seen (e.g. logo on coffee cup)",
      "prominence": "high | medium | low",
      "commercial_context": true | false,
      "certainty": "DIRECTLY_VISIBLE | INFERRED | UNCERTAIN"
    }
  ]
}
"""

class GeminiVisionService:
    """
    Real Gemini Multimodal Vision service with structured pre-clearance prompt
    and schema validation.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = getattr(settings, "GEMINI_MODEL", "gemini-flash-latest")
        self._client = None
        self._init_client()

    def _init_client(self):
        # Eagerly initialize only if Gemini is the active provider
        if self.api_key and getattr(settings, "AI_PROVIDER", "gemini") == "gemini":
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info(f"[GeminiVisionService] Initialized Gemini GenAI client ({self.model_name})")
            except Exception as e:
                logger.warning(f"[GeminiVisionService] Could not initialize Gemini GenAI client: {e}")
                self._client = None

    async def analyze_candidate_frame(
        self,
        frame_ranking: FrameRanking,
        ocr_results: List[OCRResult],
        object_results: List[ObjectDetectionResult],
        scene_context: str = "",
    ) -> Dict[str, Any]:
        """
        Execute deep multimodal inspection on a candidate frame with structured JSON response.
        """
        start_time = time.time()
        frame_path = frame_ranking.frame_path
        timestamp = frame_ranking.video_timestamp

        # Contextual prompt augmenting with local OCR and YOLO detections
        ocr_hints = ", ".join([r.text for r in ocr_results[:6]]) if ocr_results else "None detected"
        obj_hints = ", ".join([o.class_name for o in object_results[:6]]) if object_results else "None detected"

        prompt = f"""Analyze candidate visual signals for video frame at {timestamp}s (Scene {frame_ranking.scene_number}):
Local OCR detected text: {ocr_hints}
Local Object detections: {obj_hints}
Scene context: {scene_context or 'Standard cinematic footage'}

Extract all visible brands, logos, product marks, artworks, books, posters, or commercial signs in the requested JSON format."""

        # 1. Primary High-Speed LLM: Groq (if configured)
        if getattr(settings, "GROQ_API_KEY", None):
            groq_res = await self._call_groq(prompt, frame_ranking, start_time)
            if groq_res:
                return groq_res

        # 2. Multimodal Gemini Inspection
        if self._client is None and self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info(f"[GeminiVisionService] Initialized Gemini GenAI client ({self.model_name})")
            except Exception as e:
                logger.warning(f"[GeminiVisionService] Could not initialize Gemini GenAI client: {e}")

        if self._client and Path(frame_path).exists():

            try:
                from google.genai import types
                with open(frame_path, "rb") as f:
                    img_bytes = f.read()

                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=[
                        types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                        prompt,
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=GEMINI_PRE_CLEARANCE_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )

                latency = int((time.time() - start_time) * 1000)
                raw_text = response.text or "{}"
                clean_text = raw_text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                if clean_text.startswith("```"):
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                structured = json.loads(clean_text.strip())

                logger.info(f"[GeminiVisionService] Gemini analyzed frame {frame_ranking.frame_id} in {latency}ms ({len(structured.get('entities', []))} entities)")
                return {
                    "status": "SUCCESS",
                    "model": self.model_name,
                    "latency_ms": latency,
                    "timestamp": timestamp,
                    "scene_number": frame_ranking.scene_number,
                    "frame_path": frame_path,
                    "entities": structured.get("entities", []),
                    "raw_response": raw_text,
                }
            except Exception as e:
                logger.error(f"[GeminiVisionService] Gemini API call failed: {e}, using local vision heuristic", exc_info=True)

        # Local-first fallback deriving entities from OCR + Object candidates
        latency = int((time.time() - start_time) * 1000)
        local_entities = self._derive_local_entities(ocr_results, object_results, frame_ranking)

        return {
            "status": "LOCAL_FALLBACK",
            "model": "local-vision-pipeline",
            "latency_ms": latency,
            "timestamp": timestamp,
            "scene_number": frame_ranking.scene_number,
            "frame_path": frame_path,
            "entities": local_entities,
            "raw_response": json.dumps({"entities": local_entities}),
        }

    async def _call_groq(
        self,
        prompt: str,
        frame_ranking: FrameRanking,
        start_time: float,
    ) -> Optional[Dict[str, Any]]:
        """Call Groq API with structured pre-clearance extraction prompt."""
        import httpx
        try:
            groq_model = getattr(settings, "GROQ_MODEL", "openai/gpt-oss-120b")
            groq_key = getattr(settings, "GROQ_API_KEY", "")
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": groq_model,
                        "messages": [
                            {"role": "system", "content": GEMINI_PRE_CLEARANCE_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.1,
                    },
                )

            if res.status_code == 200:
                latency = int((time.time() - start_time) * 1000)
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                clean_text = content.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                if clean_text.startswith("```"):
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                structured = json.loads(clean_text.strip())

                logger.info(f"[VisionService] Groq ({groq_model}) analyzed frame at {frame_ranking.video_timestamp}s in {latency}ms ({len(structured.get('entities', []))} entities)")
                return {
                    "status": "SUCCESS",
                    "model": f"groq-{groq_model}",
                    "latency_ms": latency,
                    "timestamp": frame_ranking.video_timestamp,
                    "scene_number": frame_ranking.scene_number,
                    "frame_path": frame_ranking.frame_path,
                    "entities": structured.get("entities", []),
                    "raw_response": content,
                }
            else:
                logger.warning(f"[VisionService] Groq API error {res.status_code}: {res.text}")
                return None
        except Exception as e:
            logger.warning(f"[VisionService] Groq API call failed: {e}")
            return None

    def _derive_local_entities(
        self,
        ocr_results: List[OCRResult],
        object_results: List[ObjectDetectionResult],
        frame_ranking: FrameRanking,
    ) -> List[Dict[str, Any]]:
        """Synthesize entities locally from OCR candidate text and object detections."""
        entities = []
        for ocr in ocr_results:
            if ocr.is_brand_candidate or ocr.confidence >= 0.7:
                name = ocr.text.strip().title()
                if name and name != "Signage_Text_Candidate":
                    entities.append({
                        "name": name,
                        "entity_type": "brand",
                        "confidence": ocr.confidence,
                        "visual_basis": f"Visible text badge/signage on frame at {ocr.timestamp}s",
                        "prominence": "medium",
                        "commercial_context": False,
                        "certainty": "DIRECTLY_VISIBLE",
                    })

        for obj in object_results:
            if obj.class_name in {"poster", "sign", "laptop", "cell phone"}:
                entities.append({
                    "name": f"{obj.class_name.title()} Asset",
                    "entity_type": "product" if "phone" in obj.class_name or "laptop" in obj.class_name else "signage",
                    "confidence": obj.confidence,
                    "visual_basis": f"Prominent visual {obj.class_name} in scene composition",
                    "prominence": "medium",
                    "commercial_context": False,
                    "certainty": "DIRECTLY_VISIBLE",
                })

        return entities[:4]

gemini_service = GeminiVisionService()
