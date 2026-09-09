import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from app.core.config import settings
from app.models.entity import Entity, EntityType
from app.services.clearance_filter import is_clearance_relevant, clearance_filter_service
from app.services.vision_provider import (
    GeminiVisionProvider,
    GroqVisionProvider,
    get_vision_provider,
)

@pytest.fixture
def dummy_image_file(tmp_path):
    img_path = tmp_path / "test_frame.jpg"
    # Minimal JPEG header bytes
    img_path.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb" + b"\x00" * 32)
    return str(img_path)

# =========================================================================
# 1 & 2. Valid Groq Multimodal Request & Model qwen/qwen3.6-27b
# =========================================================================
@pytest.mark.asyncio
async def test_groq_request_format_and_parameters(dummy_image_file):
    provider = GroqVisionProvider(api_key="mock_groq_key")
    captured_request = {}

    async def mock_post(url, headers=None, json=None):
        captured_request["url"] = url
        captured_request["headers"] = headers
        captured_request["json"] = json

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.is_error = False
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"entities": [{"name": "Sony", "entity_type": "brand", "confidence": 0.94, "context": "Camera body logo", "evidence": "direct"}]}'
                    }
                }
            ]
        }
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        res = await provider.analyze_frame(
            frame_path=dummy_image_file,
            context={"timestamp": 5.2, "scene_number": 2, "ocr_hints": "SONY", "obj_hints": "camera"},
        )

    # 1. Valid endpoint & headers
    assert captured_request["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured_request["headers"]["Authorization"] == "Bearer mock_groq_key"

    body = captured_request["json"]
    # 2. Model is qwen/qwen3.6-27b
    assert body["model"] == "qwen/qwen3.6-27b"

    # Cost-controlled token limits & JSON mode
    assert body["response_format"] == {"type": "json_object"}
    assert body["temperature"] == 0.1
    assert body["max_tokens"] <= 600

    # Multimodal structure
    assert len(body["messages"]) == 1
    msg = body["messages"][0]
    assert msg["role"] == "user"
    assert len(msg["content"]) == 2

    text_part = msg["content"][0]
    assert text_part["type"] == "text"
    assert "JSON" in text_part["text"]

    # Image encoded as data:image/jpeg;base64,...
    image_part = msg["content"][1]
    assert image_part["type"] == "image_url"
    assert image_part["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert len(image_part["image_url"]["url"]) > 30

# =========================================================================
# 3. JSON Output Parsing
# =========================================================================
@pytest.mark.asyncio
async def test_groq_response_entity_parsing(dummy_image_file):
    provider = GroqVisionProvider(api_key="mock_groq_key")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"entities": [{"name": "Ray-Ban", "entity_type": "brand", "confidence": 0.92, "context": "Sunglasses worn by protagonist", "evidence": "direct"}]}'
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await provider.analyze_frame(
            frame_path=dummy_image_file,
            context={"timestamp": 8.0, "scene_number": 1},
        )

    assert res["status"] == "SUCCESS"
    assert res["model"] == "qwen/qwen3.6-27b"
    assert len(res["entities"]) == 1
    ent = res["entities"][0]
    assert ent["name"] == "Ray-Ban"
    assert ent["entity_type"] == "brand"
    assert ent["confidence"] == 0.92
    assert "Sunglasses" in ent["context"]
    assert ent["evidence"] == "direct"

# =========================================================================
# 4. HTTP 429 Rate Limit Handling (Detection, Retry, and Graceful Skip)
# =========================================================================
@pytest.mark.asyncio
async def test_groq_http_429_graceful_skip_on_rate_limit(dummy_image_file, caplog):
    provider = GroqVisionProvider(api_key="mock_groq_key")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 429
    mock_resp.is_error = True
    mock_resp.headers = {"Retry-After": "8.5"}
    mock_resp.text = '{"error":{"message":"Rate limit reached for model qwen/qwen3.6-27b on tokens per minute (TPM). Please try again in 8.5s.","type":"tokens","code":"rate_limit_exceeded"}}'

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await provider.analyze_frame(
            frame_path=dummy_image_file,
            context={"timestamp": 4.0, "scene_number": 1},
        )

    # Must NOT crash; must skip frame gracefully
    assert res["status"] == "SKIPPED"
    assert res["entities"] == []
    assert res.get("rate_limited") is True
    assert "Groq rate limit reached" in caplog.text

@pytest.mark.asyncio
async def test_groq_http_429_controlled_retry_success(dummy_image_file, caplog):
    provider = GroqVisionProvider(api_key="mock_groq_key")

    # First attempt: 429 with short delay (0.2s)
    mock_resp_429 = MagicMock(spec=httpx.Response)
    mock_resp_429.status_code = 429
    mock_resp_429.is_error = True
    mock_resp_429.headers = {}
    mock_resp_429.text = '{"error":{"message":"Please try again in 0.2s.","type":"tokens","code":"rate_limit_exceeded"}}'

    # Second attempt: 200 OK
    mock_resp_200 = MagicMock(spec=httpx.Response)
    mock_resp_200.status_code = 200
    mock_resp_200.is_error = False
    mock_resp_200.json.return_value = {
        "choices": [
            {"message": {"content": '{"entities": [{"name": "Pepsi", "entity_type": "brand", "confidence": 0.95}]}'}}
        ]
    }

    call_count = 0
    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_resp_429 if call_count == 1 else mock_resp_200

    with patch("httpx.AsyncClient.post", side_effect=mock_post), patch("asyncio.sleep", new_callable=AsyncMock):
        res = await provider.analyze_frame(
            frame_path=dummy_image_file,
            context={"timestamp": 2.0, "scene_number": 1},
        )

    assert call_count == 2
    assert res["status"] == "SUCCESS"
    assert len(res["entities"]) == 1
    assert res["entities"][0]["name"] == "Pepsi"
    assert "Groq rate limit reached; retry after" in caplog.text

# =========================================================================
# 5. Generic "Person" is filtered
# =========================================================================
def test_clearance_filter_generic_person():
    assert is_clearance_relevant({"name": "Person", "entity_type": "person"}) is False
    assert is_clearance_relevant({"name": "person", "entity_type": "person"}) is False
    assert is_clearance_relevant({"name": "Man", "entity_type": "person"}) is False
    assert is_clearance_relevant({"name": "Woman", "entity_type": "person"}) is False
    assert is_clearance_relevant({"name": "Human", "entity_type": "person"}) is False
    assert is_clearance_relevant({"name": "Object", "entity_type": "object"}) is False
    assert is_clearance_relevant({"name": "Thing", "entity_type": "object"}) is False
    assert is_clearance_relevant({"name": "Item", "entity_type": "product"}) is False

    # Domain model Entity check
    ent_person = Entity(
        production_id="p1",
        job_id="j1",
        name="Person",
        entity_type=EntityType.PERSON,
    )
    assert is_clearance_relevant(ent_person) is False

# =========================================================================
# 6. Single-character OCR noise such as "S" is filtered
# =========================================================================
def test_clearance_filter_single_character_ocr_noise():
    assert is_clearance_relevant({"name": "S", "entity_type": "brand"}) is False
    assert is_clearance_relevant({"name": "X", "entity_type": "signage"}) is False
    assert is_clearance_relevant({"name": "1", "entity_type": "other"}) is False
    assert is_clearance_relevant({"name": " ", "entity_type": "brand"}) is False
    assert is_clearance_relevant({"name": "Creative Visualisation", "entity_type": "signage"}) is False
    assert is_clearance_relevant({"name": "Creative Visualization", "entity_type": "other"}) is False

# =========================================================================
# 7. Legitimate "Nike" / "Coca-Cola" style entity is retained
# =========================================================================
def test_clearance_filter_legitimate_entities():
    # Recognizable brands, products, companies, public figures
    assert is_clearance_relevant({"name": "Nike", "entity_type": "brand"}) is True
    assert is_clearance_relevant({"name": "Coca-Cola", "entity_type": "brand"}) is True
    assert is_clearance_relevant({"name": "Apple", "entity_type": "brand"}) is True
    assert is_clearance_relevant({"name": "Pepsi", "entity_type": "brand"}) is True
    assert is_clearance_relevant({"name": "Samsung", "entity_type": "brand"}) is True
    assert is_clearance_relevant({"name": "Spotify", "entity_type": "company"}) is True
    assert is_clearance_relevant({"name": "Taylor Swift", "entity_type": "public_figure"}) is True
    assert is_clearance_relevant({"name": "Marvel", "entity_type": "company"}) is True

    # Legitimate short brands must NOT be rejected
    assert is_clearance_relevant({"name": "HP", "entity_type": "brand"}) is True
    assert is_clearance_relevant({"name": "LG", "entity_type": "brand"}) is True
    assert is_clearance_relevant({"name": "3M", "entity_type": "brand"}) is True

# =========================================================================
# 8. Provider factory still supports both Groq and Gemini
# =========================================================================
def test_provider_factory_groq_and_gemini():
    groq_prov = get_vision_provider("groq")
    assert isinstance(groq_prov, GroqVisionProvider)
    assert groq_prov.model == "qwen/qwen3.6-27b"

    gemini_prov = get_vision_provider("gemini")
    assert isinstance(gemini_prov, GeminiVisionProvider)
