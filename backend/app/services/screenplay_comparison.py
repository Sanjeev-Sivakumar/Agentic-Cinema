import re
from typing import List, Optional, Tuple
from app.core.logging import logger
from app.models.entity import Entity, EntityClassification, EntitySource

class ScreenplayComparisonService:
    """
    Screenplay Comparison Service.
    Compares detected visual entities against screenplay text to isolate VISUAL-ONLY findings.
    """

    def compare_against_screenplay(
        self,
        footage_entities: List[Entity],
        screenplay_text: str,
        script_entities: Optional[List[Entity]] = None,
    ) -> Tuple[List[Entity], List[Entity]]:
        """
        Compare footage entities against screenplay text and script entities.
        Returns (all_entities_updated, visual_only_entities).
        Classifies each entity as BOTH, SCRIPT_ONLY, or VISUAL_ONLY.
        """
        normalized_script = screenplay_text.lower()
        visual_only_findings: List[Entity] = []
        all_entities: List[Entity] = []

        # Process visual entities
        for entity in footage_entities:
            entity_name_clean = re.sub(r"[^\w\s]", "", entity.name.lower()).strip()
            words = [w for w in entity_name_clean.split() if len(w) > 2]

            from app.services.entity_normalization import CANONICAL_CLEARANCE_ENTITIES, entity_normalization_service

            # Check if entity or distinctive tokens or aliases are present in screenplay
            is_in_script = EntitySource.SCRIPT in entity.sources
            if not is_in_script:
                if entity_name_clean and entity_name_clean in normalized_script:
                    is_in_script = True
                elif len(words) >= 2 and all(w in normalized_script for w in words):
                    is_in_script = True
                else:
                    # Check canonical entity aliases
                    norm_c = entity_normalization_service.normalize_ocr_candidate(entity.name)
                    if norm_c and norm_c.get("matched_canonical"):
                        key = norm_c["matched_canonical"].lower()
                        if key in CANONICAL_CLEARANCE_ENTITIES:
                            for alias in CANONICAL_CLEARANCE_ENTITIES[key].get("aliases", []):
                                if alias in normalized_script:
                                    is_in_script = True
                                    break

            if is_in_script:
                if EntitySource.SCRIPT not in entity.sources:
                    entity.sources.append(EntitySource.SCRIPT)
                logger.info(f"[ScreenplayComparison] Entity '{entity.name}' found in screenplay -> classification BOTH")
            else:
                # Strictly Visual-Only
                entity.sources = [EntitySource.VISUAL]
                visual_only_findings.append(entity)
                logger.info(f"[ScreenplayComparison] 🚨 VISUAL-ONLY FINDING: '{entity.name}' absent from screenplay")

            all_entities.append(entity)

        # Process optional script-only entities
        if script_entities:
            existing_names = {re.sub(r"[^\w\s]", "", e.name.lower()).strip() for e in footage_entities}
            for s_ent in script_entities:
                clean_s = re.sub(r"[^\w\s]", "", s_ent.name.lower()).strip()
                if clean_s not in existing_names:
                    s_ent.sources = [EntitySource.SCRIPT]
                    all_entities.append(s_ent)
                    logger.info(f"[ScreenplayComparison] Entity '{s_ent.name}' in script only -> classification SCRIPT_ONLY")

        return all_entities, visual_only_findings

screenplay_comparison_service = ScreenplayComparisonService()
