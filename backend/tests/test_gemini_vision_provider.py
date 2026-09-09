from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.core.config import settings
from app.models.entity import Entity, EntityClassification, EntitySource, EntityType
from app.services.screenplay_comparison import ScreenplayComparisonService
from app.services.vision_provider import (
    GeminiVisionProvider,
    GroqVisionProvider,
    get_vision_provider,
)

@pytest.fixture
def dummy_frame(tmp_path):
    f = tmp_path / "gemini_frame.jpg"
    f.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb" + b"\x00" * 32)
    return str(f)

# =========================================================================
# 1. Successful Gemini response with one entity
# =========================================================================
@pytest.mark.asyncio
async def test_gemini_success_with_one_entity(dummy_frame):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"entities": [{"name": "Nike", "entity_type": "brand", "confidence": 0.95, "reason": "Swoosh logo on running shoes"}]}'
    mock_client.models.generate_content.return_value = mock_resp

    provider = GeminiVisionProvider(api_key="dummy_gemini_key", model="gemini-2.5-flash")
    provider._client = mock_client

    res = await provider.analyze_frame(
        frame_path=dummy_frame,
        context={"timestamp": 4.5, "scene_number": 1, "ocr_hints": "", "obj_hints": ""},
    )

    assert res["status"] == "VISION_SUCCESS"
    assert res["provider"] == "gemini"
    assert res["model"] == "gemini-2.5-flash"
    assert len(res["entities"]) == 1
    ent = res["entities"][0]
    assert ent["name"] == "Nike"
    assert ent["entity_type"] == "brand"
    assert ent["confidence"] == 0.95
    assert "Swoosh" in ent["reason"]

# =========================================================================
# 2. Successful Gemini response with zero entities
# =========================================================================
@pytest.mark.asyncio
async def test_gemini_success_with_zero_entities(dummy_frame):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"entities": []}'
    mock_client.models.generate_content.return_value = mock_resp

    provider = GeminiVisionProvider(api_key="dummy_gemini_key")
    provider._client = mock_client

    res = await provider.analyze_frame(
        frame_path=dummy_frame,
        context={"timestamp": 10.0, "scene_number": 2},
    )

    assert res["status"] == "VISION_NO_ENTITIES"
    assert res["entities"] == []

# =========================================================================
# 3. Malformed JSON handling
# =========================================================================
@pytest.mark.asyncio
async def test_gemini_malformed_json(dummy_frame, caplog):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '```json\n{"entities": [invalid json content\n```'
    mock_client.models.generate_content.return_value = mock_resp

    provider = GeminiVisionProvider(api_key="dummy_gemini_key")
    provider._client = mock_client

    res = await provider.analyze_frame(
        frame_path=dummy_frame,
        context={"timestamp": 2.0, "scene_number": 1},
    )

    assert res["status"] == "VISION_JSON_ERROR"
    assert res["entities"] == []
    assert "JSON parsing error" in res["error"]
    assert "JSON parsing error" in caplog.text

# =========================================================================
# 4. API error handling (distinguished from 0 entities)
# =========================================================================
@pytest.mark.asyncio
async def test_gemini_api_error(dummy_frame, caplog):
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Google GenAI backend connection refused")

    provider = GeminiVisionProvider(api_key="dummy_gemini_key")
    provider._client = mock_client

    res = await provider.analyze_frame(
        frame_path=dummy_frame,
        context={"timestamp": 3.0, "scene_number": 1},
    )

    # Must NOT silently convert to 0 entities!
    assert res["status"] == "VISION_API_ERROR"
    assert res["entities"] == []
    assert "connection refused" in res["error"]
    assert "API call failed (VISION_API_ERROR)" in caplog.text

# =========================================================================
# 5. Missing API key handling
# =========================================================================
@pytest.mark.asyncio
async def test_gemini_missing_api_key(dummy_frame):
    with patch.object(settings, "GEMINI_API_KEY", ""):
        provider = GeminiVisionProvider(api_key="")
        res = await provider.analyze_frame(
            frame_path=dummy_frame,
            context={"timestamp": 1.0, "scene_number": 1},
        )

    assert res["status"] == "VISION_API_ERROR"
    assert "missing" in res["error"].lower()

# =========================================================================
# 6. Provider factory returns Gemini by default
# =========================================================================
def test_provider_factory_returns_gemini_by_default():
    with patch.object(settings, "AI_PROVIDER", "gemini"):
        provider = get_vision_provider()
        assert isinstance(provider, GeminiVisionProvider)
        assert provider.provider_name == "gemini"

# =========================================================================
# 7. Explicit --provider gemini and --provider groq work
# =========================================================================
def test_provider_factory_explicit_selection():
    prov_gemini = get_vision_provider("gemini")
    assert isinstance(prov_gemini, GeminiVisionProvider)
    assert prov_gemini.provider_name == "gemini"

    prov_groq = get_vision_provider("groq")
    assert isinstance(prov_groq, GroqVisionProvider)
    assert prov_groq.provider_name == "groq"

# =========================================================================
# 8. Screenplay comparison produces BOTH/VISUAL_ONLY correctly with Gemini
# =========================================================================
def test_screenplay_comparison_with_gemini_entities():
    svc = ScreenplayComparisonService()
    script = "INT. LIVING ROOM - DAY\nJohn drinks from a can of Pepsi on the table."

    visual_entities = [
        Entity(
            production_id="p1",
            job_id="j1",
            name="Pepsi",
            entity_type=EntityType.BRAND,
            sources=[EntitySource.VISUAL],
            confidence=0.95,
        ),
        Entity(
            production_id="p1",
            job_id="j1",
            name="Rolex",
            entity_type=EntityType.BRAND,
            sources=[EntitySource.VISUAL],
            confidence=0.92,
        ),
    ]

    all_updated, visual_only = svc.compare_against_screenplay(visual_entities, script)

    pepsi_ent = next(e for e in all_updated if e.name == "Pepsi")
    rolex_ent = next(e for e in all_updated if e.name == "Rolex")

    assert pepsi_ent.classification == EntityClassification.BOTH
    assert rolex_ent.classification == EntityClassification.VISUAL_ONLY
    assert len(visual_only) == 1
    assert visual_only[0].name == "Rolex"
