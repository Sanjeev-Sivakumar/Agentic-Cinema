import re
from typing import Optional

class ResearchQueryBuilder:
    """
    Deterministic query builder that constructs targeted search queries
    for factual rights-holder and trademark clearance investigation.
    """

    @staticmethod
    def build_query(
        entity_name: str,
        entity_type: str,
        context: Optional[str] = None,
    ) -> str:
        """
        Build an objective, targeted research query tailored to the entity category.
        """
        clean_name = (entity_name or "").strip().strip("\"'")
        type_norm = (entity_type or "brand").lower().strip()

        if type_norm in ("brand", "product", "trademark"):
            base = f'"{clean_name}" brand company rights holder official'
        elif type_norm in ("company", "corporation"):
            base = f'"{clean_name}" corporation ownership rights holder official'
        elif type_norm in ("music", "artist", "song"):
            base = f'"{clean_name}" artist music rights holder official'
        elif type_norm in ("artwork", "painting", "poster", "sculpture"):
            base = f'"{clean_name}" artwork artist copyright rights holder'
        elif type_norm in ("film", "tv_show", "film_tv", "movie", "tv"):
            base = f'"{clean_name}" film production company rights holder'
        elif type_norm in ("book", "novel", "publication"):
            base = f'"{clean_name}" book author publisher copyright'
        elif type_norm in ("location", "signage"):
            base = f'"{clean_name}" commercial location owner operator official'
        else:
            base = f'"{clean_name}" {type_norm} rights holder official'

        # If a specific contextual cue is present (e.g. artist name or author mention), extract cleanly
        if context:
            # Extract possible artist/company hint if indicated by 'by <Name>' (capitalized words)
            by_match = re.search(r"\bby\s+([A-Z0-9][A-Za-z0-9&]*(?:\s+[A-Z0-9][A-Za-z0-9&]*)*)\b", context)
            if by_match:
                artist_hint = by_match.group(1).strip()
                if artist_hint and artist_hint.lower() not in clean_name.lower():
                    base += f' "{artist_hint}"'

        return base.strip()

query_builder = ResearchQueryBuilder()
