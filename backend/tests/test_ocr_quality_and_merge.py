import pytest
from app.models.entity import Entity, EntityClassification, EntitySource, EntityType
from app.models.production import Production
from app.services.clearance_filter import is_clearance_relevant, clearance_filter_service
from app.services.entity_normalization import entity_normalization_service, normalize_ocr_candidate
from app.services.deduplication import deduplication_service
from app.adk.context import WorkflowContext
from app.adk.state import ChainOfTitleState
from app.adk.tools.entity_tools import merge_entities_tool
from app.repositories import get_production_repo, get_entity_repo


def test_clearance_filter_rejects_reference_slate_codes():
    """Verify reference prefixes, camera slate IDs, and technical codes are rejected."""
    bad_candidates = [
        "Reference: C023P062122cS",
        "Refcrencc: C023P062122cS",
        "Relcrence: C023p062122cS",
        "ASC Reference: CO23p0",
        "Reference: C023",
        "Slate: A001_C002",
        "Take: 03",
        "Cam: A",
        "ASc",
        "ASC",
        "LUT",
        "LOG",
        "FPS",
        "ISO",
        "crncc",
        "clrcnc",
    ]
    for text in bad_candidates:
        assert is_clearance_relevant({"name": text, "entity_type": "brand"}) is False, f"Expected '{text}' to be rejected"


def test_clearance_filter_rejects_copyright_boilerplate():
    """Verify copyright boilerplate lines are rejected from clearance entity promotion."""
    boilerplate = [
        "2022 The Coca-Cola Company All Rights Reserved",
        "All Rights Reserved",
        "Copyright 2024",
        "© 2023 Acme Corp",
        "(c) Warner Bros",
    ]
    for text in boilerplate:
        assert is_clearance_relevant({"name": text, "entity_type": "brand"}) is False, f"Expected '{text}' to be rejected"


def test_clearance_filter_preserves_legitimate_brands():
    """Verify legitimate clearance brands, including short acronyms, are preserved."""
    good_brands = [
        "Coca-Cola",
        "Pepsi",
        "Nike",
        "Apple",
        "Sony",
        "Samsung",
        "Starbucks",
        "Rolex",
        "McDonald's",
        "HP",
        "LG",
        "3M",
        "BMW",
        "KFC",
        "IBM",
        "BBC",
        "CNN",
    ]
    for brand in good_brands:
        assert is_clearance_relevant({"name": brand, "entity_type": "brand"}) is True, f"Expected '{brand}' to be allowed"


def test_normalize_ocr_candidate_fuzzy_brand():
    """Verify corrupted cursive OCR strings normalize cleanly to canonical entities."""
    # Test Spencerian cursive OCR corruptions for Coca-Cola
    res1 = normalize_ocr_candidate("GceGola")
    assert res1 is not None
    assert res1["name"] == "Coca-Cola"
    assert res1["is_normalized"] is True

    res2 = normalize_ocr_candidate("gcebelas")
    assert res2 is not None
    assert res2["name"] == "Coca-Cola"

    # Test Apple iPhone variations
    res3 = normalize_ocr_candidate("iPhone")
    assert res3 is not None
    assert "iPhone" in res3["name"] or res3["name"] == "Apple iPhone"

    # Test rejection of slate codes in normalization
    assert normalize_ocr_candidate("ASC Reference: CO23p0") is None
    assert normalize_ocr_candidate("Reference: C023P062122cS") is None
    assert normalize_ocr_candidate("ASc") is None


def test_deduplication_fuzzy_and_canonical():
    """Verify deduplication service merges fuzzy brand variants and applies canonical names."""
    e1 = Entity(
        production_id="prod_dedup",
        name="GceGola",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        confidence=0.85,
    )
    e2 = Entity(
        production_id="prod_dedup",
        name="Coca-Cola",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        confidence=0.95,
    )
    canonical, merged = deduplication_service.deduplicate_entities([e1, e2])
    assert len(canonical) == 1
    assert canonical[0].name == "Coca-Cola"
    assert canonical[0].appearances == 2


@pytest.mark.asyncio
async def test_merge_entities_tool_unifies_cross_modal_coca_cola():
    """
    CRITICAL TEST:
    Verify that when Coca-Cola exists in both screenplay and footage (even if OCR detected 'GceGola'),
    it is unified into a SINGLE entity with sources [SCRIPT, VISUAL] and classification BOTH.
    """
    prod_id = "prod_coca_cola_unification"
    prod = Production(
        id=prod_id,
        title="Unification Showcase",
        script_text="John enters the cafe and orders a cold bottle of Coca-Cola, typing away on his MacBook.",
    )
    await get_production_repo().save(prod)

    # 1. Screenplay Entity: Coca-Cola (from text agent)
    ent_script_cola = Entity(
        id="ent_script_cola",
        production_id=prod_id,
        name="Coca-Cola",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.SCRIPT],
        classification=EntityClassification.SCRIPT_ONLY,
    )

    # 2. Screenplay Entity: MacBook (from text agent)
    ent_script_mac = Entity(
        id="ent_script_mac",
        production_id=prod_id,
        name="MacBook",
        entity_type=EntityType.PRODUCT,
        sources=[EntitySource.SCRIPT],
        classification=EntityClassification.SCRIPT_ONLY,
    )

    # 3. Visual Entity: GceGola (corrupted cursive OCR from video)
    ent_vis_gcegola = Entity(
        id="ent_vis_gcegola",
        production_id=prod_id,
        name="GceGola",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        confidence=0.88,
        scene=1,
        timestamp=3.5,
        frame_path="/frames/scene1_mid.jpg",
        bounding_box=[0.1, 0.2, 0.3, 0.4],
    )

    # 4. Visual Entity: Unscripted Billboard (truly unscripted)
    ent_vis_nike = Entity(
        id="ent_vis_nike",
        production_id=prod_id,
        name="Nike",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        confidence=0.92,
        scene=2,
        timestamp=8.0,
    )

    # 5. Garbage OCR Entity (should be purged)
    ent_garbage = Entity(
        id="ent_garbage_ref",
        production_id=prod_id,
        name="Reference: C023P062122cS",
        entity_type=EntityType.BRAND,
        sources=[EntitySource.VISUAL],
        confidence=0.70,
    )

    repo = get_entity_repo()
    await repo.save(ent_script_cola)
    await repo.save(ent_script_mac)
    await repo.save(ent_vis_gcegola)
    await repo.save(ent_vis_nike)
    await repo.save(ent_garbage)

    # Execute merge_entities_tool
    state = ChainOfTitleState(production_id=prod_id)
    ctx = WorkflowContext(state=state)

    result = await merge_entities_tool(ctx)

    assert result["status"] == "COMPLETED"
    # Garbage was purged, Coca-Cola script & visual unified into 1!
    # Expected remaining entities: Coca-Cola (BOTH), MacBook (SCRIPT_ONLY), Nike (VISUAL_ONLY) -> 3 entities!
    assert result["total_entities"] == 3
    assert result["both_count"] == 1
    assert result["visual_only_count"] == 1
    assert result["script_only_count"] == 1

    # Verify Coca-Cola in repo
    refreshed = await repo.list_by_production(prod_id)
    cola = next((e for e in refreshed if "coca" in e.name.lower()), None)
    assert cola is not None
    assert cola.name == "Coca-Cola"
    assert EntitySource.SCRIPT in cola.sources
    assert EntitySource.VISUAL in cola.sources
    assert cola.classification == EntityClassification.BOTH
    # Evidence frames and timestamps from visual detection preserved
    assert cola.frame_path == "/frames/scene1_mid.jpg"
    assert cola.timestamp == 3.5

    # Verify garbage was deleted
    garbage = await repo.get("ent_garbage_ref")
    assert garbage is None
