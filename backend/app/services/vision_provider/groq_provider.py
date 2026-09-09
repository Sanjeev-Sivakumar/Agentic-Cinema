import asyncio
import base64
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.services.vision_provider.base import VisionProvider

# Clearance-focused prompt instructing model to only extract relevant entities without prose explanations
GROQ_CLEARANCE_PROMPT = """You are detecting potential media-clearance-relevant entities visible in this frame. Identify recognizable brands, trademarks, logos, products, companies, music-related references, artists, public figures, films, television works, books, artwork, posters, signage, and other identifiable copyrighted or trademarked works.
Do not return generic objects or people unless the person is a recognizable public figure relevant to clearance.
Do not invent entity names. If uncertain, omit the entity. Do not output prose explanations.
Return strict JSON:
{"entities":[{"name":"Exact Brand/Entity Name","entity_type":"brand|trademark|product|company|public_figure|artwork|poster|book|film|signage|music|other","confidence":0.95,"context":"Brief location in frame","evidence":"direct|inference"}]}"""

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

def parse_groq_rate_limit(error_text: str, retry_after_header: Optional[str] = None) -> Tuple[bool, float]:
    """
    Detect rate limit exceeded and parse server-provided retry duration in seconds.
    Returns (is_rate_limit, retry_seconds).
    """
    is_rate_limit = False
    retry_secs = 2.0  # safe default

    lower_text = error_text.lower()
    if (
        "rate_limit" in lower_text
        or "rate limit" in lower_text
        or "tpm" in lower_text
        or "tokens per minute" in lower_text
        or "429" in lower_text
    ):
        is_rate_limit = True

    # 1. Check Retry-After header if provided
    if retry_after_header:
        try:
            return True, max(0.5, float(retry_after_header))
        except (ValueError, TypeError):
            pass

    # 2. Parse seconds: "try again in 1.25s" or "try again in 2s"
    m_sec = re.search(r"try again in ([\d\.]+)\s*s", error_text, re.IGNORECASE)
    if m_sec:
        try:
            return True, max(0.5, float(m_sec.group(1)))
        except ValueError:
            pass

    # 3. Parse minutes and seconds: "try again in 1m20s"
    m_ms = re.search(r"try again in (?:(\d+)m)?\s*([\d\.]+)s", error_text, re.IGNORECASE)
    if m_ms:
        try:
            mins = float(m_ms.group(1) or 0)
            secs = float(m_ms.group(2) or 0)
            return True, max(0.5, mins * 60.0 + secs)
        except ValueError:
            pass

    return is_rate_limit, retry_secs

class GroqVisionProvider(VisionProvider):
    """
    Groq Multimodal Vision Provider for fast, clearance-focused visual inspection.
    Uses Groq's OpenAI-compatible multimodal endpoint with qwen/qwen3.6-27b.
    Incorporates rate limit (HTTP 429) detection and graceful degradation.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "GROQ_API_KEY", "")
        self.model = model or getattr(settings, "GROQ_MODEL", "qwen/qwen3.6-27b")
        self._sdk_client = None
        self._init_client()

    @property
    def provider_name(self) -> str:
        return "groq"

    def _init_client(self):
        if self.api_key and not self.api_key.startswith("mock_"):
            try:
                import groq
                self._sdk_client = groq.AsyncGroq(api_key=self.api_key)
                logger.info(f"[GroqVisionProvider] Initialized Groq SDK client (model: {self.model})")
            except ImportError:
                logger.info(f"[GroqVisionProvider] Groq SDK not installed, using direct httpx client (model: {self.model})")
                self._sdk_client = None
            except Exception as e:
                logger.warning(f"[GroqVisionProvider] Could not initialize Groq SDK client: {e}")
                self._sdk_client = None
        else:
            self._sdk_client = None

    def _validate_image(self, frame_path: str) -> Dict[str, Any]:
        """
        Validate image file existence, readability, base64 encoding, and MIME type.
        Returns a dict with 'valid': bool, 'data_url': str, 'error': str.
        """
        path = Path(frame_path)
        if not path.exists():
            return {"valid": False, "error": f"Image file does not exist: '{frame_path}'"}
        if not path.is_file():
            return {"valid": False, "error": f"Path is not a regular file: '{frame_path}'"}

        try:
            with open(path, "rb") as f:
                img_bytes = f.read()
            if not img_bytes:
                return {"valid": False, "error": f"Image file is empty (0 bytes): '{frame_path}'"}
        except Exception as e:
            return {"valid": False, "error": f"Could not open/read image file: {e}"}

        try:
            b64_image = base64.b64encode(img_bytes).decode("utf-8")
            if not b64_image:
                return {"valid": False, "error": "Base64 encoding resulted in empty string"}
        except Exception as e:
            return {"valid": False, "error": f"Base64 encoding failed: {e}"}

        mime_type = get_image_mime_type(path)
        image_data_url = f"data:{mime_type};base64,{b64_image}"
        if not image_data_url or len(image_data_url) <= len(f"data:{mime_type};base64,"):
            return {"valid": False, "error": "Generated image data URL is empty or invalid"}

        return {"valid": True, "data_url": image_data_url, "mime_type": mime_type}

    async def analyze_frame(
        self,
        frame_path: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute multimodal inspection via Groq using qwen/qwen3.6-27b.
        Supports 429 rate limit detection and graceful skip.
        """
        start_time = time.time()
        timestamp = context.get("timestamp", 0.0)
        scene_number = context.get("scene_number", 1)
        ocr_hints = context.get("ocr_hints", "")
        obj_hints = context.get("obj_hints", "")

        if not self.api_key:
            latency = int((time.time() - start_time) * 1000)
            return {
                "status": "LOCAL_FALLBACK",
                "provider": self.provider_name,
                "model": self.model,
                "latency_ms": latency,
                "timestamp": timestamp,
                "scene_number": scene_number,
                "frame_path": frame_path,
                "entities": [],
                "message": "Groq API key not set",
            }

        # Validate image file and encoding
        validation = self._validate_image(frame_path)
        if not validation["valid"]:
            latency = int((time.time() - start_time) * 1000)
            logger.error(f"[GroqVisionProvider] Image validation failed: {validation['error']}")
            return {
                "status": "ERROR",
                "provider": self.provider_name,
                "model": self.model,
                "latency_ms": latency,
                "timestamp": timestamp,
                "scene_number": scene_number,
                "frame_path": frame_path,
                "entities": [],
                "error": validation["error"],
            }

        image_data_url = validation["data_url"]

        # Concise contextual hints to minimize prompt token usage
        hints = []
        if ocr_hints:
            hints.append(f"OCR: {ocr_hints[:100]}")
        if obj_hints:
            hints.append(f"Objects: {obj_hints[:100]}")
        hints_str = f" Context signals: {'; '.join(hints)}." if hints else ""

        user_prompt = (
            f"{GROQ_CLEARANCE_PROMPT}\n\n"
            f"Frame at {timestamp}s (Scene {scene_number}).{hints_str}\n"
            "Return valid JSON matching schema."
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url,
                        },
                    },
                ],
            }
        ]

        raw_text = ""
        max_attempts = 2  # at most 1 controlled retry on 429
        for attempt in range(max_attempts):
            try:
                if self._sdk_client:
                    try:
                        chat_completion = await self._sdk_client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            temperature=0.1,
                            max_tokens=600,
                            response_format={"type": "json_object"},
                        )
                        raw_text = chat_completion.choices[0].message.content or "{}"
                        break
                    except Exception as sdk_err:
                        status_code = getattr(sdk_err, "status_code", 400)
                        resp_obj = getattr(sdk_err, "response", None)
                        err_body = ""
                        retry_hdr = None
                        if resp_obj is not None:
                            err_body = getattr(resp_obj, "text", "") or str(resp_obj)
                            retry_hdr = getattr(resp_obj, "headers", {}).get("retry-after")
                        elif hasattr(sdk_err, "body"):
                            err_body = str(sdk_err.body)
                        elif hasattr(sdk_err, "message"):
                            err_body = str(sdk_err.message)
                        else:
                            err_body = str(sdk_err)

                        is_rl, retry_secs = parse_groq_rate_limit(err_body, retry_hdr)
                        if status_code == 429 or is_rl:
                            logger.warning(f"[GroqVisionProvider] Groq rate limit reached; retry after {retry_secs:.2f} seconds.")
                            if attempt == 0 and retry_secs <= 4.0:
                                await asyncio.sleep(retry_secs + 0.1)
                                continue
                            else:
                                latency = int((time.time() - start_time) * 1000)
                                logger.warning(f"[GroqVisionProvider] Skipping frame at {timestamp}s gracefully due to rate limit.")
                                return {
                                    "status": "SKIPPED",
                                    "provider": self.provider_name,
                                    "model": self.model,
                                    "latency_ms": latency,
                                    "timestamp": timestamp,
                                    "scene_number": scene_number,
                                    "frame_path": frame_path,
                                    "entities": [],
                                    "message": f"Groq rate limit reached; retry after {retry_secs:.2f} seconds.",
                                    "rate_limited": True,
                                }

                        logger.error(f"[GroqVisionProvider] Groq API error status={status_code} body={err_body}")
                        raise RuntimeError(f"Groq API error status={status_code} body={err_body}") from sdk_err
                else:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "model": self.model,
                                "messages": messages,
                                "temperature": 0.1,
                                "max_tokens": 600,
                                "response_format": {"type": "json_object"},
                            },
                        )

                        if resp.status_code == 429:
                            is_rl, retry_secs = parse_groq_rate_limit(resp.text, resp.headers.get("Retry-After"))
                            logger.warning(f"[GroqVisionProvider] Groq rate limit reached; retry after {retry_secs:.2f} seconds.")
                            if attempt == 0 and retry_secs <= 4.0:
                                await asyncio.sleep(retry_secs + 0.1)
                                continue
                            else:
                                latency = int((time.time() - start_time) * 1000)
                                logger.warning(f"[GroqVisionProvider] Skipping frame at {timestamp}s gracefully due to rate limit.")
                                return {
                                    "status": "SKIPPED",
                                    "provider": self.provider_name,
                                    "model": self.model,
                                    "latency_ms": latency,
                                    "timestamp": timestamp,
                                    "scene_number": scene_number,
                                    "frame_path": frame_path,
                                    "entities": [],
                                    "message": f"Groq rate limit reached; retry after {retry_secs:.2f} seconds.",
                                    "rate_limited": True,
                                }

                        if resp.is_error:
                            status_code = resp.status_code
                            body_text = resp.text
                            logger.error(f"[GroqVisionProvider] Groq API error status={status_code} body={body_text}")
                            resp.raise_for_status()

                        data = resp.json()
                        raw_text = data["choices"][0]["message"]["content"] or "{}"
                        break
            except Exception as e:
                if attempt == max_attempts - 1:
                    latency = int((time.time() - start_time) * 1000)
                    err_msg = str(e)
                    if "Groq API error" not in err_msg and "Groq rate limit" not in err_msg:
                        logger.error(f"[GroqVisionProvider] API call failed: {e}", exc_info=True)
                    return {
                        "status": "ERROR",
                        "provider": self.provider_name,
                        "model": self.model,
                        "latency_ms": latency,
                        "timestamp": timestamp,
                        "scene_number": scene_number,
                        "frame_path": frame_path,
                        "entities": [],
                        "error": err_msg,
                    }

        try:
            latency = int((time.time() - start_time) * 1000)
            clean_text = raw_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]

            parsed = json.loads(clean_text.strip())
            raw_entities = parsed.get("entities", [])
            formatted_entities = []

            for ent in raw_entities:
                name = str(ent.get("name", "")).strip()
                if not name:
                    continue

                context_str = ent.get("context") or ent.get("observation") or ent.get("visual_basis") or "Visually observed in frame"
                evidence_str = ent.get("evidence") or ent.get("evidence_type") or "direct"

                candidate = {
                    "name": name,
                    "entity_type": str(ent.get("entity_type", "brand")).lower(),
                    "confidence": float(ent.get("confidence", 0.90)),
                    "context": context_str,
                    "observation": context_str,
                    "evidence": evidence_str,
                    "evidence_type": evidence_str,
                }

                # Defense-in-depth: filter non-clearance noise
                from app.services.clearance_filter import is_clearance_relevant
                if not is_clearance_relevant(candidate):
                    logger.debug(f"[GroqVisionProvider] Omitted non-clearance candidate: '{name}'")
                    continue

                formatted_entities.append(candidate)

            logger.info(f"[GroqVisionProvider] Successfully analyzed frame at {timestamp}s: {len(formatted_entities)} entities ({latency}ms, model: {self.model})")
            return {
                "status": "SUCCESS",
                "provider": self.provider_name,
                "model": self.model,
                "latency_ms": latency,
                "timestamp": timestamp,
                "scene_number": scene_number,
                "frame_path": frame_path,
                "entities": formatted_entities,
                "raw_response": raw_text,
            }

        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            err_msg = str(e)
            logger.error(f"[GroqVisionProvider] Failed to parse response: {e}", exc_info=True)
            return {
                "status": "ERROR",
                "provider": self.provider_name,
                "model": self.model,
                "latency_ms": latency,
                "timestamp": timestamp,
                "scene_number": scene_number,
                "frame_path": frame_path,
                "entities": [],
                "error": err_msg,
            }
