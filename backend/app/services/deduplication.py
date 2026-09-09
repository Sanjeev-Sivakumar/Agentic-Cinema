import re
from typing import List, Tuple
from app.core.logging import logger
from app.models.entity import Entity

class EntityDeduplicationService:
    """
    Real entity deduplication service.
    Normalizes brand names, matches entity types, and aggregates multi-scene evidence frames
    to canonical entity entries.
    """

    @staticmethod
    def normalize_name(name: str) -> str:
        """Strip punctuation, spaces, and casing for robust entity matching."""
        # Replace hyphens and underscores with spaces first
        spaced = re.sub(r"[-_]+", " ", name.lower())
        clean = re.sub(r"[^\w\s]", "", spaced)
        return " ".join(clean.split())

    @staticmethod
    def alphanumeric_key(name: str) -> str:
        """Compact alphanumeric representation for strict brand identity matching."""
        return re.sub(r"[\W_]+", "", name.lower())

    def deduplicate_entities(self, entities: List[Entity]) -> Tuple[List[Entity], List[Tuple[Entity, Entity]]]:
        """
        Deduplicate entities list. Returns (canonical_entities, list_of_merged_pairs).
        Filters generic non-clearance detections before canonical grouping.
        """
        import difflib
        from app.services.clearance_filter import is_clearance_relevant
        from app.services.entity_normalization import entity_normalization_service

        canonical: List[Entity] = []
        merged_events: List[Tuple[Entity, Entity]] = []

        valid_entities = [e for e in entities if is_clearance_relevant(e)]
        for entity in valid_entities:
            # Canonical normalization if OCR candidate or alias
            norm_cand = entity_normalization_service.normalize_ocr_candidate(entity.name, confidence=entity.confidence)
            if norm_cand and norm_cand.get("is_normalized"):
                entity.name = norm_cand["name"]

            norm = self.normalize_name(entity.name)
            alpha_key = self.alphanumeric_key(entity.name)
            matched_canonical = None

            for c in canonical:
                c_norm = self.normalize_name(c.name)
                c_alpha = self.alphanumeric_key(c.name)

                # Fuzzy similarity between normalized names
                sim = difflib.SequenceMatcher(None, norm, c_norm).ratio()

                # Match on normalized form, compact alphanumeric key, high fuzzy similarity, or strong substring match
                is_name_match = (
                    norm == c_norm
                    or alpha_key == c_alpha
                    or sim >= 0.82
                    or (len(norm) > 4 and norm in c_norm)
                    or (len(c_norm) > 4 and c_norm in norm)
                )
                is_type_match = (c.entity_type == entity.entity_type or "brand" in (c.entity_type.value.lower(), entity.entity_type.value.lower()))

                if is_name_match and is_type_match:
                    matched_canonical = c
                    break

            if matched_canonical:
                # Update appearances count and timestamps
                matched_canonical.appearances += 1
                if entity.timestamp is not None:
                    if matched_canonical.first_seen_timestamp is None or entity.timestamp < matched_canonical.first_seen_timestamp:
                        matched_canonical.first_seen_timestamp = entity.timestamp
                    if matched_canonical.last_seen_timestamp is None or entity.timestamp > matched_canonical.last_seen_timestamp:
                        matched_canonical.last_seen_timestamp = entity.timestamp

                # Combine sources
                for s in entity.sources:
                    if s not in matched_canonical.sources:
                        matched_canonical.sources.append(s)

                # Merge evidence frames and update confidence if higher
                if entity.frame_path:
                    if entity.frame_path not in matched_canonical.evidence_ids:
                        matched_canonical.evidence_ids.append(entity.frame_path)
                    if entity.frame_path not in matched_canonical.evidence_frames:
                        matched_canonical.evidence_frames.append(entity.frame_path)

                if entity.bounding_box and not matched_canonical.bounding_box:
                    matched_canonical.bounding_box = entity.bounding_box

                matched_canonical.confidence = max(matched_canonical.confidence, entity.confidence)
                matched_canonical.risk_score = max(matched_canonical.risk_score, entity.risk_score)
                merged_events.append((matched_canonical, entity))
                logger.info(f"[Deduplication] Merged duplicate '{entity.name}' (appearance #{matched_canonical.appearances}) into canonical '{matched_canonical.name}'")
            else:
                entity.first_seen_timestamp = entity.timestamp
                entity.last_seen_timestamp = entity.timestamp
                entity.appearances = 1
                if entity.frame_path:
                    if entity.frame_path not in entity.evidence_ids:
                        entity.evidence_ids.append(entity.frame_path)
                    if entity.frame_path not in entity.evidence_frames:
                        entity.evidence_frames.append(entity.frame_path)
                canonical.append(entity)

        return canonical, merged_events

deduplication_service = EntityDeduplicationService()

