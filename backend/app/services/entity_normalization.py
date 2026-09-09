import difflib
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from app.core.logging import logger

# Canonical brand registry derived from clearance standards
CANONICAL_CLEARANCE_ENTITIES: Dict[str, Dict[str, Any]] = {
    "coca-cola": {
        "canonical_name": "Coca-Cola",
        "entity_type": "brand",
        "aliases": ["coca cola", "coke", "coca-cola company", "diet coke", "coca cola zero"],
        "slogans": ["real magic", "taste the feeling", "open happiness"],
        "ocr_fuzzy_patterns": [r"gce[\s\-_]*gola", r"gcebelas", r"cozt[\s\-_]*colo", r"coetcolo", r"coca[\s\-_]*gola"],
    },
    "pepsi": {
        "canonical_name": "Pepsi",
        "entity_type": "brand",
        "aliases": ["pepsi cola", "pepsi-cola", "pepsi zero"],
        "slogans": ["for the love of it", "that's what i like"],
        "ocr_fuzzy_patterns": [r"peps[i1l]", r"peps[i1l][\s\-_]*cola"],
    },
    "nike": {
        "canonical_name": "Nike",
        "entity_type": "brand",
        "aliases": ["nike inc", "nike swoosh"],
        "slogans": ["just do it"],
        "ocr_fuzzy_patterns": [r"n[i1l]ke"],
    },
    "apple": {
        "canonical_name": "Apple",
        "entity_type": "brand",
        "aliases": ["apple inc", "apple store", "macintosh"],
        "slogans": ["think different"],
        "ocr_fuzzy_patterns": [r"app[l1]e"],
    },
    "apple iphone": {
        "canonical_name": "Apple iPhone",
        "entity_type": "product",
        "aliases": ["iphone", "ipad", "macbook", "apple watch"],
        "slogans": [],
        "ocr_fuzzy_patterns": [r"[i1l]phone", r"[i1l]pad", r"macb[o0]{2}k"],
    },
    "starbucks": {
        "canonical_name": "Starbucks",
        "entity_type": "brand",
        "aliases": ["starbucks coffee", "frappuccino"],
        "slogans": [],
        "ocr_fuzzy_patterns": [r"starb[uü]cks?", r"starb[uü]k"],
    },
    "sony": {
        "canonical_name": "Sony",
        "entity_type": "company",
        "aliases": ["sony corporation", "sony bravia", "playstation"],
        "slogans": ["make.believe", "be moved"],
        "ocr_fuzzy_patterns": [r"s[o0]ny"],
    },
    "samsung": {
        "canonical_name": "Samsung",
        "entity_type": "brand",
        "aliases": ["samsung galaxy", "samsung electronics"],
        "slogans": [],
        "ocr_fuzzy_patterns": [r"sams[uü]ng"],
    },
    "rolex": {
        "canonical_name": "Rolex",
        "entity_type": "brand",
        "aliases": ["rolex watch", "rolex submariner"],
        "slogans": [],
        "ocr_fuzzy_patterns": [r"r[o0]lex"],
    },
    "mcdonald's": {
        "canonical_name": "McDonald's",
        "entity_type": "brand",
        "aliases": ["mcdonalds", "golden arches", "big mac"],
        "slogans": ["i'm lovin' it", "im lovin it"],
        "ocr_fuzzy_patterns": [r"mcd[o0]na[l1]ds?"],
    },
}

# Common OCR letter confusions in stylised / cursive fonts
OCR_CONFUSION_MAP = {
    'g': 'c',
    'e': 'c',
    '0': 'o',
    '1': 'i',
    '5': 's',
    '8': 'b',
    '@': 'a',
    '$': 's',
    '|': 'l',
}


class EntityNormalizationService:
    """
    Generalized entity normalization and fuzzy brand reconciliation service.
    Normalizes corrupted OCR tokens to canonical entities, suppresses non-entity
    visual noise, and validates text quality.
    """

    @staticmethod
    def clean_text(text: str) -> str:
        """Strip punctuation noise, normalize spacing and hyphens."""
        spaced = re.sub(r"[\t\r\n]+", " ", text.strip())
        spaced = re.sub(r"[\s\-_]+", " ", spaced)
        # Remove trailing and leading punctuation
        return spaced.strip(".,;:!?\"'()[]{}<>- ")

    @staticmethod
    def simplify_for_matching(text: str) -> str:
        """Simplify text for similarity matching (lowercase, alphanumeric only)."""
        return re.sub(r"[^\w]", "", text.lower())

    def apply_ocr_deconfusion(self, text: str) -> str:
        """Apply inverse substitutions for common OCR font confusions."""
        chars = []
        for ch in text.lower():
            chars.append(OCR_CONFUSION_MAP.get(ch, ch))
        return "".join(chars)

    def normalize_ocr_candidate(
        self,
        candidate_text: str,
        screenplay_entities: Optional[List[str]] = None,
        confidence: float = 0.85,
    ) -> Optional[Dict[str, Any]]:
        """
        Normalize a raw OCR candidate text string.
        Returns a dict with canonical_name, entity_type, confidence, and is_normalized,
        or None if the candidate is rejected as uncorrectable OCR artifact.
        """
        raw = self.clean_text(candidate_text)
        if not raw or len(raw) < 2:
            return None

        lower_raw = raw.lower()
        simple_raw = self.simplify_for_matching(raw)

        # 1. Direct match against canonical entities, aliases, or slogans
        for key, info in CANONICAL_CLEARANCE_ENTITIES.items():
            # Check canonical name
            if lower_raw == key or lower_raw == info["canonical_name"].lower():
                return {
                    "name": info["canonical_name"],
                    "entity_type": info["entity_type"],
                    "confidence": max(confidence, 0.95),
                    "is_normalized": True,
                    "matched_canonical": info["canonical_name"],
                    "raw_text": raw,
                }

            # Check aliases
            for alias in info.get("aliases", []):
                if lower_raw == alias or simple_raw == self.simplify_for_matching(alias):
                    return {
                        "name": info["canonical_name"],
                        "entity_type": info["entity_type"],
                        "confidence": max(confidence, 0.93),
                        "is_normalized": True,
                        "matched_canonical": info["canonical_name"],
                        "raw_text": raw,
                    }

            # Check slogans (e.g. 'Real Magic' -> associated with Coca-Cola campaign)
            for slogan in info.get("slogans", []):
                if lower_raw == slogan or simple_raw == self.simplify_for_matching(slogan):
                    return {
                        "name": raw.title(),
                        "entity_type": "trademark",
                        "confidence": max(confidence, 0.92),
                        "is_normalized": True,
                        "associated_brand": info["canonical_name"],
                        "raw_text": raw,
                    }

            # Check regex fuzzy patterns
            for pat in info.get("ocr_fuzzy_patterns", []):
                if re.search(pat, lower_raw):
                    logger.info(f"[EntityNormalization] Fuzzy matched OCR pattern '{raw}' -> '{info['canonical_name']}'")
                    return {
                        "name": info["canonical_name"],
                        "entity_type": info["entity_type"],
                        "confidence": max(confidence, 0.90),
                        "is_normalized": True,
                        "matched_canonical": info["canonical_name"],
                        "raw_text": raw,
                    }

        # 2. Fuzzy match against Screenplay Entities if provided
        if screenplay_entities:
            for s_name in screenplay_entities:
                clean_s = self.clean_text(s_name)
                s_lower = clean_s.lower()
                s_simple = self.simplify_for_matching(clean_s)

                # Direct match
                if lower_raw == s_lower or simple_raw == s_simple:
                    return {
                        "name": clean_s,
                        "entity_type": "brand",
                        "confidence": max(confidence, 0.94),
                        "is_normalized": True,
                        "matched_canonical": clean_s,
                        "raw_text": raw,
                    }

                # SequenceMatcher similarity
                sim = difflib.SequenceMatcher(None, lower_raw, s_lower).ratio()
                sim_simple = difflib.SequenceMatcher(None, simple_raw, s_simple).ratio()

                # Also test deconfused OCR string
                deconfused = self.apply_ocr_deconfusion(simple_raw)
                sim_deconfused = difflib.SequenceMatcher(None, deconfused, s_simple).ratio()

                if max(sim, sim_simple, sim_deconfused) >= 0.65:
                    logger.info(f"[EntityNormalization] Fuzzy matched script entity '{raw}' -> '{clean_s}' (sim: {max(sim, sim_simple, sim_deconfused):.2f})")
                    return {
                        "name": clean_s,
                        "entity_type": "brand",
                        "confidence": max(confidence, 0.88),
                        "is_normalized": True,
                        "matched_canonical": clean_s,
                        "raw_text": raw,
                    }

        # 3. Fuzzy match against canonical clearance entities using Levenshtein / SequenceMatcher
        for key, info in CANONICAL_CLEARANCE_ENTITIES.items():
            canon_name = info["canonical_name"]
            canon_simple = self.simplify_for_matching(canon_name)

            sim = difflib.SequenceMatcher(None, simple_raw, canon_simple).ratio()
            deconfused = self.apply_ocr_deconfusion(simple_raw)
            sim_deconf = difflib.SequenceMatcher(None, deconfused, canon_simple).ratio()

            if max(sim, sim_deconf) >= 0.70:
                logger.info(f"[EntityNormalization] Fuzzy matched canonical '{raw}' -> '{canon_name}' (sim: {max(sim, sim_deconf):.2f})")
                return {
                    "name": canon_name,
                    "entity_type": info["entity_type"],
                    "confidence": max(confidence, 0.88),
                    "is_normalized": True,
                    "matched_canonical": canon_name,
                    "raw_text": raw,
                }

        # 4. If not matching any known brand or screenplay entity:
        # Evaluate whether candidate is a clean proper noun / distinct brand, or uncorrectable noise
        from app.services.clearance_filter import is_clearance_relevant
        if not is_clearance_relevant({"name": raw, "confidence": confidence}):
            return None

        # Clean proper noun visual candidate
        return {
            "name": raw.title() if raw.islower() else raw,
            "entity_type": "brand",
            "confidence": confidence,
            "is_normalized": False,
            "raw_text": raw,
        }


entity_normalization_service = EntityNormalizationService()
normalize_ocr_candidate = entity_normalization_service.normalize_ocr_candidate


def deduplicate_screenplay_entities(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalizes brand names, matches entity types, and aggregates multi-scene occurrences
    for screenplay candidates before Entity domain model instantiation.
    """
    from app.services.clearance_filter import is_clearance_relevant

    canonical_map: Dict[str, Dict[str, Any]] = {}
    for cand in candidates:
        if not is_clearance_relevant(cand):
            continue

        raw_name = cand.get("name", "").strip()
        norm_res = entity_normalization_service.normalize_ocr_candidate(raw_name)
        canon_name = norm_res["name"] if (norm_res and norm_res.get("is_normalized")) else raw_name
        key = entity_normalization_service.simplify_for_matching(canon_name)

        cand_scene = cand.get("scene", 1)
        cand_ctx = cand.get("context")

        if key in canonical_map:
            existing = canonical_map[key]
            meta = existing.setdefault("metadata", {})
            meta["occurrences"] = meta.get("occurrences", 1) + 1
            meta["first_scene"] = min(meta.get("first_scene", cand_scene), cand_scene)
            meta["last_scene"] = max(meta.get("last_scene", cand_scene), cand_scene)
            scenes = meta.setdefault("scenes", [existing.get("scene", cand_scene)])
            if cand_scene not in scenes:
                scenes.append(cand_scene)
            contexts = meta.setdefault("contexts", [])
            if cand_ctx:
                contexts.append(cand_ctx)
            existing["confidence"] = max(float(existing.get("confidence", 0.9)), float(cand.get("confidence", 0.9)))
        else:
            cand_copy = dict(cand)
            cand_copy["name"] = canon_name
            meta = cand_copy.setdefault("metadata", {})
            meta["occurrences"] = 1
            meta["first_scene"] = cand_scene
            meta["last_scene"] = cand_scene
            meta["scenes"] = [cand_scene]
            meta["contexts"] = [cand_ctx] if cand_ctx else []
            canonical_map[key] = cand_copy

    return list(canonical_map.values())
