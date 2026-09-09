import re
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.services.screenplay_parser import ScreenplayScene, screenplay_scene_parser
from app.services.screenplay_provider.base import ScreenplayExtractionProvider

# Known clearance entity registry with predefined entity types
CLEARANCE_LEXICON = [
    # Brands & Products
    (r"\b(?:coca[\s\-]cola|coke)\b", "Coca-Cola", "brand", 0.96),
    (r"\bpepsi(?:[\s\-]cola)?\b", "Pepsi", "brand", 0.95),
    (r"\bnike(?:\s+inc\.?)?\b", "Nike", "brand", 0.95),
    (r"\bapple(?:\s+inc\.?)?(?:\s+store)?\b", "Apple", "brand", 0.95),
    (r"\b(?:iphone|ipad|macbook)\b", "Apple iPhone", "product", 0.94),
    (r"\bgoogle(?:\s+llc)?\b", "Google", "company", 0.95),
    (r"\bnetflix\b", "Netflix", "company", 0.95),
    (r"\byoutube\b", "YouTube", "company", 0.95),
    (r"\bmcdonald'?s\b", "McDonald's", "brand", 0.95),
    (r"\bsony\b", "Sony", "company", 0.94),
    (r"\bsamsung\b", "Samsung", "brand", 0.94),
    (r"\bdisney\b", "Disney", "company", 0.95),
    (r"\brolex\b", "Rolex", "brand", 0.95),
    (r"\bmercedes(?:\-benz)?\b", "Mercedes-Benz", "brand", 0.94),
    (r"\bbmw\b", "BMW", "brand", 0.94),
    (r"\bgucci\b", "Gucci", "brand", 0.93),
    (r"\bprada\b", "Prada", "brand", 0.93),
    (r"\bstarbucks\b", "Starbucks", "brand", 0.95),
    (r"\bamazon\b", "Amazon", "company", 0.94),
    (r"\bmicrosoft\b", "Microsoft", "company", 0.94),
    (r"\bcadbury(?:\s+dairy\s+milk)?\b", "Cadbury", "brand", 0.96),
    (r"\bdairy\s+milk\b", "Cadbury Dairy Milk", "product", 0.95),
]

# Contextual pattern rules for creative / media clearance types
CONTEXTUAL_RULES = [
    # Music / Song / Artist
    (
        r"(?:listening to|music by|track|song|album)\s+['\"]([^'\"]+)['\"]",
        "music",
        0.90,
    ),
    (
        r"(?:song|music):\s*([A-Za-z0-9\s&]+?)(?:\.|\n|$)",
        "music",
        0.90,
    ),
    # Poster / Painting / Artwork
    (
        r"(?:poster for|poster of|painting of|artwork by)\s+['\"]([^'\"]+)['\"]",
        "artwork",
        0.88,
    ),
    # Book / Novel
    (
        r"(?:reading|book|novel)\s+['\"]([^'\"]+)['\"]",
        "book",
        0.89,
    ),
    # Film / TV Show
    (
        r"(?:watching|movie|film|tv show)\s+['\"]([^'\"]+)['\"]",
        "film",
        0.90,
    ),
]

def extract_surrounding_sentence(text: str, start_pos: int, end_pos: int) -> str:
    """Extract full sentence or line containing the detected match."""
    # Find line boundaries or sentence boundaries
    line_start = text.rfind("\n", 0, start_pos)
    line_start = 0 if line_start == -1 else line_start + 1

    line_end = text.find("\n", end_pos)
    line_end = len(text) if line_end == -1 else line_end

    snippet = text[line_start:line_end].strip()
    return snippet or text[max(0, start_pos - 40) : min(len(text), end_pos + 40)].strip()

class LocalScreenplayProvider(ScreenplayExtractionProvider):
    """
    Deterministic rule-based screenplay entity extraction provider.
    Used for local development and deterministic test execution.
    Requires zero external AI or network calls.
    """

    @property
    def provider_name(self) -> str:
        return "local"

    async def extract_entities(
        self,
        screenplay_text: str,
        scenes: Optional[List[ScreenplayScene]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract clearance-relevant entities across scenes using deterministic pattern matching.
        """
        if not screenplay_text or not screenplay_text.strip():
            return []

        active_scenes = scenes if scenes is not None else screenplay_scene_parser.parse_scenes(screenplay_text)
        if not active_scenes:
            return []

        extracted_entities: List[Dict[str, Any]] = []

        for scene in active_scenes:
            scene_text = scene.text
            scene_num = scene.scene_number

            # 1. Check Lexicon Brands / Companies / Products
            for pattern, canonical_name, entity_type, conf in CLEARANCE_LEXICON:
                for match in re.finditer(pattern, scene_text, re.IGNORECASE):
                    start, end = match.span()
                    context_snippet = extract_surrounding_sentence(scene_text, start, end)
                    extracted_entities.append(
                        {
                            "name": canonical_name,
                            "entity_type": entity_type,
                            "confidence": conf,
                            "scene": scene_num,
                            "context": context_snippet,
                            "source": ["screenplay"],
                        }
                    )

            # 2. Check Contextual Creative Works (music, artwork, books, film)
            for pattern, entity_type, conf in CONTEXTUAL_RULES:
                for match in re.finditer(pattern, scene_text, re.IGNORECASE):
                    named_group = match.group(1).strip()
                    if named_group and len(named_group) > 1:
                        start, end = match.span()
                        context_snippet = extract_surrounding_sentence(scene_text, start, end)
                        extracted_entities.append(
                            {
                                "name": named_group,
                                "entity_type": entity_type,
                                "confidence": conf,
                                "scene": scene_num,
                                "context": context_snippet,
                                "source": ["screenplay"],
                            }
                        )

        logger.info(
            f"[LocalScreenplayProvider] Deterministically extracted {len(extracted_entities)} raw mentions across {len(active_scenes)} scenes"
        )
        return extracted_entities
