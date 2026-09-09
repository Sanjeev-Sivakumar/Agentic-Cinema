import time
from typing import Any, Dict, Optional
from app.core.config import settings
from app.core.logging import logger
from app.services.vision_provider.base import VisionProvider
from app.services.vision_provider.gemini_provider import GeminiVisionProvider
from app.services.vision_provider.groq_provider import GroqVisionProvider

class LocalHeuristicVisionProvider(VisionProvider):
    """
    Local heuristic vision fallback provider.
    Synthesizes candidates directly from local OCR and YOLO detections without external API calls.
    Used when API keys are not provided or in automated unit tests.
    """

    @property
    def provider_name(self) -> str:
        return "local-heuristic"

    async def analyze_frame(
        self,
        frame_path: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        start_time = time.time()
        timestamp = context.get("timestamp", 0.0)
        scene_number = context.get("scene_number", 1)
        ocr_results = context.get("ocr_results", [])
        object_results = context.get("object_results", [])

        entities = []
        screenplay_entities = context.get("screenplay_entities", [])
        if not screenplay_entities and context.get("screenplay_text"):
            s_text = context["screenplay_text"]
            screenplay_entities = [w.strip(".,;:!?\"'()[]{}") for w in s_text.split() if len(w) >= 3 and w[0].isupper()]

        from app.services.entity_normalization import normalize_ocr_candidate
        from app.services.clearance_filter import is_clearance_relevant

        seen_names = set()
        for ocr in ocr_results:
            text = getattr(ocr, "text", "") if hasattr(ocr, "text") else ocr.get("text", "")
            conf = getattr(ocr, "confidence", 0.85) if hasattr(ocr, "confidence") else ocr.get("confidence", 0.85)
            if not text or len(text) < 2 or conf < 0.35:
                continue

            if not is_clearance_relevant({"name": text, "confidence": conf}):
                continue

            norm_res = normalize_ocr_candidate(text, screenplay_entities=screenplay_entities, confidence=conf)
            if not norm_res:
                continue

            cand_name = norm_res["name"]
            cand_type = norm_res["entity_type"]
            cand_conf = norm_res["confidence"]

            if not is_clearance_relevant({"name": cand_name, "entity_type": cand_type, "confidence": cand_conf}):
                continue

            if cand_name.lower() in seen_names:
                continue
            seen_names.add(cand_name.lower())

            entities.append({
                "name": cand_name,
                "entity_type": cand_type,
                "confidence": min(0.95, round(cand_conf, 2)),
                "observation": f"OCR visual detection '{text}' normalized to '{cand_name}'",
                "evidence_type": "direct",
                "raw_text": text,
            })

        for obj in object_results:
            label = getattr(obj, "label", None) or getattr(obj, "class_name", "") if hasattr(obj, "label") else obj.get("label", obj.get("class_name", ""))
            conf = getattr(obj, "confidence", 0.75) if hasattr(obj, "confidence") else obj.get("confidence", 0.75)
            if label and label in {"bottle", "cup", "cell phone", "laptop", "car", "book", "poster"}:
                cand_name = f"Unidentified {label.title()}"
                if is_clearance_relevant({"name": cand_name, "entity_type": "product"}):
                    entities.append({
                        "name": cand_name,
                        "entity_type": "product",
                        "confidence": min(0.90, round(conf, 2)),
                        "observation": f"Object detector identified candidate {label}",
                        "evidence_type": "inference",
                    })

        latency = int((time.time() - start_time) * 1000)
        return {
            "status": "SUCCESS",
            "provider": self.provider_name,
            "model": "local-signals",
            "latency_ms": latency,
            "timestamp": timestamp,
            "scene_number": scene_number,
            "frame_path": frame_path,
            "entities": entities,
        }

def get_vision_provider(provider_name: Optional[str] = None) -> VisionProvider:
    """
    Factory function returning the configured or requested VisionProvider.
    Gemini is PRIMARY / DEFAULT. Groq is OPTIONAL backup.
    Respects AI_PROVIDER configuration (defaults to gemini).
    """
    chosen = (provider_name or getattr(settings, "AI_PROVIDER", "gemini")).lower().strip()

    if chosen in ("local", "local-heuristic", "heuristic", "offline"):
        logger.info(f"[VisionProviderFactory] Using local heuristic vision provider ({chosen})")
        return LocalHeuristicVisionProvider()

    elif chosen == "gemini":
        gemini_key = getattr(settings, "GEMINI_API_KEY", "")
        if provider_name is not None:
            return GeminiVisionProvider(api_key=gemini_key)
        if gemini_key:
            return GeminiVisionProvider(api_key=gemini_key)
        groq_key = getattr(settings, "GROQ_API_KEY", "")
        if groq_key:
            logger.info("[VisionProviderFactory] Gemini key missing; falling back to available Groq key")
            return GroqVisionProvider(api_key=groq_key)
        logger.info("[VisionProviderFactory] Gemini requested but GEMINI_API_KEY missing; using local heuristic fallback")
        return LocalHeuristicVisionProvider()

    elif chosen == "groq":
        groq_key = getattr(settings, "GROQ_API_KEY", "")
        if provider_name is not None:
            return GroqVisionProvider(api_key=groq_key)
        if groq_key:
            return GroqVisionProvider(api_key=groq_key)
        gemini_key = getattr(settings, "GEMINI_API_KEY", "")
        if gemini_key:
            logger.info("[VisionProviderFactory] Groq key missing; falling back to available Gemini API key")
            return GeminiVisionProvider(api_key=gemini_key)
        logger.info("[VisionProviderFactory] Groq requested but GROQ_API_KEY missing; using local heuristic fallback")
        return LocalHeuristicVisionProvider()

    else:
        logger.warning(f"[VisionProviderFactory] Unknown AI_PROVIDER '{chosen}'; using local heuristic fallback")
        return LocalHeuristicVisionProvider()

