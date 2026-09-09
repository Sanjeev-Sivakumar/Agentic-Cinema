from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.agents.text_agent import TextAgent, text_agent
from app.core.config import settings
from app.main import app
from app.models.entity import EntityClassification, EntitySource, EntityType
from app.models.events import EventType
from app.models.production import Production
from app.repositories import get_production_repo
from app.services.events import event_bus
from app.services.screenplay_parser import ScreenplaySceneParser
from app.services.screenplay_provider import (
    GeminiScreenplayProvider,
    LocalScreenplayProvider,
    get_screenplay_provider,
)

# =========================================================================
# Test 1: Scene detection (headings & fallback)
# =========================================================================
def test_scene_detection_headings_and_fallback():
    parser = ScreenplaySceneParser()
    script_multi = (
        "SCENE 01 - INT. COFFEE SHOP - DAY\n"
        "Arjun sits near the counter.\n"
        "EXT. STREET - NIGHT\n"
        "Cars pass through the rain.\n"
    )
    scenes = parser.parse_scenes(script_multi)
    assert len(scenes) == 2
    assert scenes[0].scene_number == 1
    assert "INT. COFFEE SHOP - DAY" in scenes[0].heading
    assert scenes[1].scene_number == 2
    assert "EXT. STREET - NIGHT" in scenes[1].heading

    # Fallback when no sluglines are present
    script_no_headings = "Just some narrative text without any slugline.\nSecond line of dialogue."
    fallback_scenes = parser.parse_scenes(script_no_headings)
    assert len(fallback_scenes) == 1
    assert fallback_scenes[0].scene_number == 1
    assert fallback_scenes[0].heading == "SCENE 1"
    assert "narrative text" in fallback_scenes[0].text

# =========================================================================
# Test 2: Single brand extraction
# =========================================================================
@pytest.mark.asyncio
async def test_single_brand_extraction():
    agent = TextAgent()
    script = (
        "INT. APARTMENT - DAY\n"
        "Leo opens the refrigerator and pulls out a chilled can of Coca-Cola.\n"
    )
    entities = await agent.analyze_screenplay(script, production_id="p_test_1")
    assert len(entities) == 1
    ent = entities[0]
    assert ent.name == "Coca-Cola"
    assert ent.entity_type == EntityType.BRAND
    assert ent.confidence >= 0.90
    assert ent.scene == 1
    assert "Coca-Cola" in ent.context

# =========================================================================
# Test 3: Multiple brands extraction
# =========================================================================
@pytest.mark.asyncio
async def test_multiple_brand_extraction():
    agent = TextAgent()
    script = (
        "INT. LIVING ROOM - DAY\n"
        "Arjun sips a Pepsi while watching a series on Netflix.\n"
        "Across the table, Sara laces up her new Nike sneakers.\n"
    )
    entities = await agent.analyze_screenplay(script, production_id="p_test_2")
    names = {e.name for e in entities}
    assert "Pepsi" in names
    assert "Netflix" in names
    assert "Nike" in names
    assert len(entities) == 3

# =========================================================================
# Test 4: Scene-specific entity extraction
# =========================================================================
@pytest.mark.asyncio
async def test_scene_specific_entity_association():
    agent = TextAgent()
    script = (
        "INT. COFFEE SHOP - DAY\n"
        "Customer wears a Nike shirt.\n\n"
        "EXT. DOWNTOWN - NIGHT\n"
        "Arjun stops outside the glass entrance of the Apple Store.\n"
    )
    entities = await agent.analyze_screenplay(script, production_id="p_test_3")
    assert len(entities) == 2

    nike_ent = next(e for e in entities if e.name == "Nike")
    apple_ent = next(e for e in entities if e.name == "Apple")

    assert nike_ent.scene == 1
    assert apple_ent.scene == 2

# =========================================================================
# Test 5: Duplicate normalization and deduplication
# =========================================================================
@pytest.mark.asyncio
async def test_duplicate_normalization_and_merging():
    agent = TextAgent()
    script = (
        "SCENE 01 - INT. DINER - DAY\n"
        "Arjun orders a cold Coca Cola bottle from the waiter.\n\n"
        "SCENE 02 - EXT. GAS STATION - NIGHT\n"
        "He buys another ice-cold coca-cola before getting back in the vehicle.\n"
    )
    entities = await agent.analyze_screenplay(script, production_id="p_test_4")

    # Both mentions of Coca Cola should merge into 1 logical entity
    assert len(entities) == 1
    coke = entities[0]
    assert coke.name == "Coca-Cola"
    assert coke.scene == 1  # first scene
    assert coke.appearances == 2
    assert coke.metadata.get("first_scene") == 1
    assert coke.metadata.get("last_scene") == 2
    assert coke.metadata.get("scenes") == [1, 2]
    assert len(coke.metadata.get("contexts", [])) == 2

# =========================================================================
# Test 6: Generic person and object filtering
# =========================================================================
@pytest.mark.asyncio
async def test_generic_person_and_object_filtering():
    agent = TextAgent()
    script = (
        "INT. OFFICE - DAY\n"
        "A woman enters the room through the door.\n"
        "A man sits quietly in a wooden chair near the glass window.\n"
        "The barista sets down a cup on the counter.\n"
    )
    entities = await agent.analyze_screenplay(script, production_id="p_test_5")
    # All generic words (woman, man, room, door, chair, window, barista, cup, counter) must be filtered
    assert len(entities) == 0

# =========================================================================
# Test 7: Source is screenplay / SCRIPT
# =========================================================================
@pytest.mark.asyncio
async def test_entity_source_is_screenplay():
    agent = TextAgent()
    script = "INT. ROOM - DAY\nArjun puts on his Rolex watch.\n"
    entities = await agent.analyze_screenplay(script, production_id="p_test_6")
    assert len(entities) == 1
    ent = entities[0]
    assert EntitySource.SCRIPT in ent.sources
    assert ent.sources == [EntitySource.SCRIPT]
    assert ent.source == "SCRIPT"
    assert ent.classification == EntityClassification.SCRIPT_ONLY

# =========================================================================
# Test 8: Empty screenplay handling
# =========================================================================
@pytest.mark.asyncio
async def test_empty_screenplay_handling():
    agent = TextAgent()
    res1 = await agent.analyze_screenplay("", production_id="p_test_7")
    assert res1 == []

    res2 = await agent.analyze_screenplay("   \n\n\t   ", production_id="p_test_7")
    assert res2 == []

# =========================================================================
# Test 9: No clearance entities in screenplay
# =========================================================================
@pytest.mark.asyncio
async def test_no_clearance_entities_screenplay():
    agent = TextAgent()
    script = (
        "INT. LIVING ROOM - MORNING\n"
        "David looks out across the green fields.\n"
        "DAVID\n"
        "It's a quiet morning.\n"
    )
    entities = await agent.analyze_screenplay(script, production_id="p_test_8")
    assert len(entities) == 0

# =========================================================================
# Test 10: Malformed provider response handling
# =========================================================================
@pytest.mark.asyncio
async def test_malformed_provider_response():
    mock_prov = MagicMock()
    mock_prov.provider_name = "mock_corrupt"
    # Returns corrupted / non-dict / missing name entries
    mock_prov.extract_entities = AsyncMock(
        return_value=[
            None,
            "corrupted_string",
            {"name": "", "entity_type": "brand"},
            {"name": "Valid Brand", "entity_type": "brand", "confidence": 0.95, "scene": 1, "context": "Seen in shop"},
            12345,
        ]
    )

    agent = TextAgent(provider=mock_prov)
    script = "INT. SHOP - DAY\nValid Brand on display."
    entities = await agent.analyze_screenplay(script, production_id="p_test_9")

    # Corrupted items safely ignored, only valid item preserved
    assert len(entities) == 1
    assert entities[0].name == "Valid Brand"

# =========================================================================
# Test 11: Real event emission to EventBus
# =========================================================================
@pytest.mark.asyncio
async def test_event_emission_on_event_bus():
    agent = TextAgent()
    job_id = "job_script_event_test"
    script = (
        "SCENE 01 - INT. COFFEE SHOP - DAY\n"
        "Arjun buys a Coca-Cola.\n"
    )
    await agent.analyze_screenplay(script, production_id="p_evt_test", job_id=job_id)

    history = event_bus.get_history(job_id)
    event_types = [e.event_type for e in history]

    assert EventType.SCREENPLAY_ANALYSIS_STARTED in event_types
    assert EventType.SCREENPLAY_SCENE_DETECTED in event_types
    assert EventType.SCREENPLAY_ENTITY_EXTRACTED in event_types
    assert EventType.SCREENPLAY_ANALYSIS_COMPLETED in event_types

# =========================================================================
# Test 12: Provider factory defaults to LOCAL during tests
# =========================================================================
def test_provider_factory_defaults_to_local():
    with patch.object(settings, "SCREENPLAY_PROVIDER", "local"):
        provider = get_screenplay_provider()
        assert isinstance(provider, LocalScreenplayProvider)
        assert provider.provider_name == "local"

    # Default without explicit argument
    provider_default = get_screenplay_provider()
    assert isinstance(provider_default, LocalScreenplayProvider)

# =========================================================================
# Test 13: Gemini provider is never called during tests
# =========================================================================
@pytest.mark.asyncio
async def test_gemini_provider_is_never_called_during_tests():
    with patch.object(
        GeminiScreenplayProvider,
        "extract_entities",
        side_effect=AssertionError("CRITICAL: Gemini provider must NOT be invoked during tests!"),
    ):
        agent = TextAgent()
        script = "INT. ROOM - DAY\nArjun drinks a Pepsi.\n"
        entities = await agent.analyze_screenplay(script, production_id="p_safe_test")
        assert len(entities) == 1
        assert entities[0].name == "Pepsi"

# =========================================================================
# Test 14: API endpoint POST /productions/{id}/screenplay/analyze
# =========================================================================
@pytest.mark.asyncio
async def test_api_screenplay_analyze_endpoint():
    prod_repo = get_production_repo()
    test_prod = Production(title="Screenplay Test Prod", description="Phase 3 Test")
    saved_prod = await prod_repo.create(test_prod)

    client = TestClient(app)
    payload = {
        "text": (
            "SCENE 01 - INT. COFFEE SHOP - DAY\n"
            "Arjun buys a Coca-Cola.\n\n"
            "SCENE 02 - EXT. STREET - NIGHT\n"
            "He passes an Apple Store.\n"
        )
    }

    response = client.post(f"/productions/{saved_prod.id}/screenplay/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["production_id"] == saved_prod.id
    assert data["scene_count"] == 2
    assert data["entity_count"] == 2
    entity_names = [e["name"] for e in data["entities"]]
    assert "Coca-Cola" in entity_names
    assert "Apple" in entity_names
