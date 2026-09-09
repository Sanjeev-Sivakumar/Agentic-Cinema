import re
from typing import Any, Dict, List, Set, Union
from app.core.logging import logger
from app.models.entity import Entity, EntityType

# Generic non-clearance terms that must be rejected
GENERIC_CLEARANCE_BLACKLIST: Set[str] = {
    # Generic persons / humans
    "person",
    "man",
    "woman",
    "human",
    "boy",
    "girl",
    "people",
    "crowd",
    "individual",
    "someone",
    "adult",
    "child",
    # Generic objects / items / furniture / clothing / narrative fixtures
    "object",
    "thing",
    "item",
    "element",
    "product",
    "chair",
    "table",
    "desk",
    "furniture",
    "bottle",
    "cup",
    "laptop",
    "phone",
    "smartphone",
    "clothing",
    "shirt",
    "shoe",
    "shoes",
    "door",
    "window",
    "room",
    "wall",
    "counter",
    "floor",
    "street",
    "house",
    "road",
    "building",
    "sky",
    "tree",
    "booth",
    "glass",
    "barista",
    "customer",
    "unidentified product",
    "unknown product",
    "unidentified object",
    "unknown object",
    "unknown brand",
    "unknown entity",
    "unidentified entity",
    # Generic production / visualization noise
    "creative visualisation",
    "creative visualization",
    "visualisation",
    "visualization",
    "statutory warning",
    "disclaimer",
    "cameraman",
    "crew",
    "background",
    "reference",
    "relcrence",
    "refcrence",
    "refcrencc",
    "relerence",
    "slate",
    "timecode",
}

# Production / slate / technical reference prefixes (allowing standalone or prefix form)
RE_REFERENCE_PREFIX = re.compile(
    r"(?i)\b(?:asc\s+)?(?:re[a-z]{0,3}ren(?:ce|cc)|code|slate|cam|take|scene|reel|timecode|tc|fps|iso)(?:[\s:;_-]|$)",
)

# Mixed alphanumeric code patterns typical of camera slates, timecodes, or reference markers
# e.g. C023P062122cS, CO23p0, P062122, 023P0621
RE_SLATE_CODE = re.compile(
    r"(?i)\b(?:[a-z]{1,4}\d{2,}[a-z0-9]*|\d{2,}[a-z]{1,4}[a-z0-9]*)\b"
)

# Production / camera / color abbreviations that are not brands
PRODUCTION_ACRONYMS: Set[str] = {
    "asc", "lut", "log", "fps", "iso", "dop", "tc", "ac", "raw", "nd", "wb", "rec", "sync"
}

# Known legitimate short brands / acronyms without standard vowels or with numbers
LEGIT_SHORT_BRANDS: Set[str] = {
    "hp", "lg", "3m", "gu", "ge", "bp", "vw", "dkny", "fcuk", "bmw", "ibm",
    "kfc", "cnn", "bbc", "mgm", "mtv", "hbo", "dhl", "ups", "fedex", "cbs",
    "nbc", "abc", "amc", "tnt", "espn", "vfx", "cgi", "dj", "tv", "pc", "vr", "ai"
}

# Copyright / legal boilerplate disclaimer tokens
COPYRIGHT_DISCLAIMER_PHRASES = (
    "all rights reserved",
    "copyright",
    "trademark of",
    "rights reserved",
    "pat. pend",
    "pat pending",
    "all rights",
)

class ClearanceFilterService:
    """
    Clearance-focused validation and filtering layer.
    Rejects generic detections (Person, Object, Item, Creative Visualisation, single-letter OCR noise),
    technical metadata (ASC, Reference codes, slates), and copyright boilerplate
    before entities reach canonical deduplication or downstream intelligence.
    """

    @staticmethod
    def normalize_text(text: str) -> str:
        """Strip punctuation and extra whitespace for robust matching."""
        spaced = re.sub(r"[-_]+", " ", text.lower().strip())
        clean = re.sub(r"[^\w\s]", "", spaced)
        return " ".join(clean.split())

    def is_clearance_relevant(self, item: Union[Entity, Dict[str, Any]]) -> bool:
        """
        Determine if an entity candidate is relevant for media pre-clearance.
        """
        if isinstance(item, Entity):
            name = item.name or ""
            entity_type_val = item.entity_type.value if hasattr(item.entity_type, "value") else str(item.entity_type)
            confidence = item.confidence
            context = item.context or ""
        elif isinstance(item, dict):
            name = item.get("name") or ""
            entity_type_val = str(item.get("entity_type") or "brand").lower()
            confidence = float(item.get("confidence", 0.8))
            context = item.get("context") or item.get("observation") or ""
        else:
            return False

        clean_name = name.strip()
        if not clean_name:
            return False

        norm = self.normalize_text(clean_name)
        if not norm:
            return False

        # Rule 1: Reject single-character OCR noise, and 2-character tokens unless recognized short brand
        if len(clean_name) <= 1 or len(norm) <= 1:
            logger.debug(f"[ClearanceFilter] Rejected single-character OCR noise: '{clean_name}'")
            return False
        if len(norm) <= 2 and norm not in LEGIT_SHORT_BRANDS:
            logger.debug(f"[ClearanceFilter] Rejected non-brand 2-character OCR fragment: '{clean_name}'")
            return False

        # Rule 2: Reject exact matches against generic blacklist
        if norm in GENERIC_CLEARANCE_BLACKLIST or clean_name.lower() in GENERIC_CLEARANCE_BLACKLIST:
            logger.debug(f"[ClearanceFilter] Rejected generic non-clearance entity: '{clean_name}'")
            return False

        # Rule 3: Reject phrases starting with generic production notices or disclaimers
        if any(norm.startswith(prefix) for prefix in ("creative visual", "statutory warning", "disclaimer")):
            logger.debug(f"[ClearanceFilter] Rejected generic notice: '{clean_name}'")
            return False

        # Rule 4: Reject generic unidentified placeholders
        if any(norm.startswith(prefix) for prefix in ("unidentified ", "unknown ")):
            logger.debug(f"[ClearanceFilter] Rejected unidentified placeholder: '{clean_name}'")
            return False

        # Rule 5: Reject reference / slate / camera markers (e.g. "Reference: C023...", "ASC Reference: CO23p0", "Relcrence")
        if RE_REFERENCE_PREFIX.search(clean_name):
            logger.debug(f"[ClearanceFilter] Rejected reference/slate candidate: '{clean_name}'")
            return False

        # Rule 6: Reject production acronyms (e.g. "ASC", "ASc", "LUT", "FPS")
        if norm in PRODUCTION_ACRONYMS or clean_name.lower() in PRODUCTION_ACRONYMS:
            logger.debug(f"[ClearanceFilter] Rejected production acronym: '{clean_name}'")
            return False

        # Rule 7: Reject copyright / legal boilerplate strings
        lower_name = clean_name.lower()
        if any(phrase in lower_name for phrase in COPYRIGHT_DISCLAIMER_PHRASES) or "©" in clean_name or "(c)" in lower_name:
            logger.debug(f"[ClearanceFilter] Rejected copyright/legal boilerplate: '{clean_name}'")
            return False

        # Rule 8: Reject technical slate / serial codes (e.g. "C023P062122cS", "CO23p0")
        # unless it is an explicitly allowed short brand (e.g. "3M")
        if norm not in LEGIT_SHORT_BRANDS and clean_name.lower() not in LEGIT_SHORT_BRANDS:
            tokens = re.split(r"[\s:;_-]+", clean_name)
            for token in tokens:
                if len(token) >= 4 and RE_SLATE_CODE.match(token):
                    digits = sum(1 for c in token if c.isdigit())
                    letters = sum(1 for c in token if c.isalpha())
                    if digits >= 2 and letters >= 2:
                        logger.debug(f"[ClearanceFilter] Rejected slate code token: '{clean_name}' ({token})")
                        return False

        # Rule 9: Reject unpronounceable consonant clusters (>= 5 consonants in a row, e.g. "crncc", "clrcnc")
        # unless token is in legitimate short brands
        if norm not in LEGIT_SHORT_BRANDS:
            tokens = re.split(r"[\s:;_-]+", clean_name)
            for token in tokens:
                t_lower = token.lower()
                if t_lower in LEGIT_SHORT_BRANDS:
                    continue
                if re.search(r"[bcdfghjklmnpqrstvwxz]{5,}", t_lower):
                    logger.debug(f"[ClearanceFilter] Rejected unpronounceable consonant cluster: '{clean_name}' ({token})")
                    return False
                if len(t_lower) >= 4 and not re.search(r"[aeiouy]", t_lower):
                    logger.debug(f"[ClearanceFilter] Rejected vowel-less token: '{clean_name}' ({token})")
                    return False

        # Rule 10: Handle person types - reject generic person descriptions unless public figure
        if entity_type_val in ("person", "human", "people"):
            generic_person_phrases = {"a person", "a man", "a woman", "unknown person", "actor", "actress", "extra"}
            if norm in generic_person_phrases or norm in GENERIC_CLEARANCE_BLACKLIST:
                return False

        return True

    def filter_entities(self, entities: List[Any]) -> List[Any]:
        """Filter a list of entities, preserving order."""
        return [e for e in entities if self.is_clearance_relevant(e)]

clearance_filter_service = ClearanceFilterService()
is_clearance_relevant = clearance_filter_service.is_clearance_relevant
