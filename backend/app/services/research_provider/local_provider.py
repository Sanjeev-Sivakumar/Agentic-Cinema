from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.evidence import Evidence, EvidenceType
from app.models.research import ResearchResult, ResearchStatus
from app.services.research_provider.base import ResearchProvider
from app.services.research_provider.query_builder import query_builder

# Deterministic development research registry for known demo entities
LOCAL_RESEARCH_FIXTURES: Dict[str, Dict[str, Any]] = {
    "coca-cola": {
        "canonical_name": "Coca-Cola",
        "candidate_rights_holder": "The Coca-Cola Company",
        "identity_claim": "The Coca-Cola brand mark and beverage formulations are owned by The Coca-Cola Company (Atlanta, GA).",
        "confidence": 0.96,
        "evidence": [
            {
                "claim": "The Coca-Cola Company is the registered corporate rights holder for Coca-Cola brand trademarks.",
                "source_title": "Corporate Entity Fixture Registry",
                "excerpt": "Coca-Cola is a registered trademark of The Coca-Cola Company, incorporated in Delaware, HQ in Atlanta, Georgia.",
                "confidence": 0.96,
            }
        ],
    },
    "coke": {
        "canonical_name": "Coca-Cola",
        "candidate_rights_holder": "The Coca-Cola Company",
        "identity_claim": "Coke is a recognized brand trademark of The Coca-Cola Company.",
        "confidence": 0.96,
        "evidence": [
            {
                "claim": "Coke is an official brand abbreviation and registered mark of The Coca-Cola Company.",
                "source_title": "Corporate Entity Fixture Registry",
                "excerpt": "Coke brand trademark assigned to The Coca-Cola Company.",
                "confidence": 0.96,
            }
        ],
    },
    "nike": {
        "canonical_name": "Nike",
        "candidate_rights_holder": "NIKE, Inc.",
        "identity_claim": "Nike is a global athletic footwear and apparel brand associated with NIKE, Inc.",
        "confidence": 0.96,
        "evidence": [
            {
                "claim": "NIKE, Inc. holds global trademark rights to the Nike brand and Swoosh device.",
                "source_title": "Corporate Entity Fixture Registry",
                "excerpt": "NIKE, Inc. is an American multinational athletic footwear and apparel corporation headquartered in Beaverton, Oregon.",
                "confidence": 0.96,
            }
        ],
    },
    "apple": {
        "canonical_name": "Apple",
        "candidate_rights_holder": "Apple Inc.",
        "identity_claim": "Apple is a multinational technology and consumer electronics company associated with Apple Inc.",
        "confidence": 0.96,
        "evidence": [
            {
                "claim": "Apple Inc. is the corporate rights holder of Apple, iPhone, and Apple Store trademarks.",
                "source_title": "Corporate Entity Fixture Registry",
                "excerpt": "Apple Inc. is an American multinational technology corporation headquartered in Cupertino, California.",
                "confidence": 0.96,
            }
        ],
    },
    "apple store": {
        "canonical_name": "Apple",
        "candidate_rights_holder": "Apple Inc.",
        "identity_claim": "Apple Store is a retail chain owned and operated by Apple Inc.",
        "confidence": 0.96,
        "evidence": [
            {
                "claim": "Apple Store commercial retail properties and branding belong to Apple Inc.",
                "source_title": "Corporate Entity Fixture Registry",
                "excerpt": "Apple Store is a chain of retail stores owned and operated by Apple Inc.",
                "confidence": 0.96,
            }
        ],
    },
    "pepsi": {
        "canonical_name": "Pepsi",
        "candidate_rights_holder": "PepsiCo, Inc.",
        "identity_claim": "Pepsi is a global carbonated beverage brand owned by PepsiCo, Inc.",
        "confidence": 0.95,
        "evidence": [
            {
                "claim": "Pepsi and related marks are registered trademarks of PepsiCo, Inc.",
                "source_title": "Corporate Entity Fixture Registry",
                "excerpt": "PepsiCo, Inc. is an American multinational food, snack, and beverage corporation headquartered in Purchase, New York.",
                "confidence": 0.95,
            }
        ],
    },
    "netflix": {
        "canonical_name": "Netflix",
        "candidate_rights_holder": "Netflix, Inc.",
        "identity_claim": "Netflix is a subscription streaming and media production company associated with Netflix, Inc.",
        "confidence": 0.95,
        "evidence": [
            {
                "claim": "Netflix, Inc. is the corporate rights holder for the Netflix streaming service and trademarks.",
                "source_title": "Corporate Entity Fixture Registry",
                "excerpt": "Netflix, Inc. is an American media company based in Los Gatos, California.",
                "confidence": 0.95,
            }
        ],
    },
    "youtube": {
        "canonical_name": "YouTube",
        "candidate_rights_holder": "Google LLC",
        "identity_claim": "YouTube is an online video platform owned as a subsidiary by Google LLC / Alphabet Inc.",
        "confidence": 0.95,
        "evidence": [
            {
                "claim": "YouTube is a subsidiary of Google LLC.",
                "source_title": "Corporate Entity Fixture Registry",
                "excerpt": "YouTube is an American online video sharing platform headquartered in San Bruno, California, subsidiary of Google LLC.",
                "confidence": 0.95,
            }
        ],
    },
    "google": {
        "canonical_name": "Google",
        "candidate_rights_holder": "Alphabet Inc.",
        "identity_claim": "Google is a technology company operating as a primary subsidiary of Alphabet Inc.",
        "confidence": 0.96,
        "evidence": [
            {
                "claim": "Google LLC is owned by parent holding company Alphabet Inc.",
                "source_title": "Corporate Entity Fixture Registry",
                "excerpt": "Google LLC is an American multinational corporation and technology subsidiary of Alphabet Inc.",
                "confidence": 0.96,
            }
        ],
    },
    "rolex": {
        "canonical_name": "Rolex",
        "candidate_rights_holder": "Montres Rolex SA",
        "identity_claim": "Rolex is a luxury watchmaker associated with Montres Rolex SA (Geneva, Switzerland).",
        "confidence": 0.95,
        "evidence": [
            {
                "claim": "Montres Rolex SA holds corporate and trademark rights for Rolex timepieces.",
                "source_title": "Corporate Entity Fixture Registry",
                "excerpt": "Rolex SA is a Swiss luxury watch manufacturer based in Geneva, Switzerland.",
                "confidence": 0.95,
            }
        ],
    },
    "mcdonald's": {
        "canonical_name": "McDonald's",
        "candidate_rights_holder": "McDonald's Corporation",
        "identity_claim": "McDonald's is a multinational fast food restaurant chain operated by McDonald's Corporation.",
        "confidence": 0.95,
        "evidence": [
            {
                "claim": "McDonald's Corporation owns the Golden Arches and McDonald's restaurant marks.",
                "source_title": "Corporate Entity Fixture Registry",
                "excerpt": "McDonald's Corporation is an American multinational fast food corporation.",
                "confidence": 0.95,
            }
        ],
    },
}

class LocalResearchProvider(ResearchProvider):
    """
    Deterministic local research provider for development, verification, and automated tests.
    Strictly zero network or external API access.
    Uses an explicit fixture registry and sets source_type='local_fixture', source_url=None.
    """

    @property
    def provider_name(self) -> str:
        return "local"

    async def research_entity(
        self,
        entity_name: str,
        entity_type: str,
        context: Optional[str] = None,
        production_id: Optional[str] = "global",
        job_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        force_refresh: bool = False,
    ) -> ResearchResult:
        """
        Look up deterministic research evidence for known fixture entities.
        Returns NOT_FOUND for unlisted entities without fabricating evidence.
        """
        clean_name = (entity_name or "").strip()
        lookup_key = clean_name.lower().strip("\"'")
        query_str = query_builder.build_query(clean_name, entity_type, context)

        if not lookup_key or lookup_key not in LOCAL_RESEARCH_FIXTURES:
            logger.info(f"[LocalResearchProvider] Entity '{clean_name}' not in local fixtures -> NOT_FOUND")
            return ResearchResult(
                production_id=production_id or "global",
                job_id=job_id,
                entity_id=entity_id,
                entity_name=clean_name or "Unknown",
                entity_type=entity_type or "brand",
                status=ResearchStatus.NOT_FOUND,
                candidate_rights_holder=None,
                identity_confidence=0.0,
                research_confidence=0.0,
                evidence=[],
                query=query_str,
                provider=self.provider_name,
                notes=f"No local research fixture registered for '{clean_name}'",
                metadata={"source_type": "local_fixture", "found": False},
            )

        fixture = LOCAL_RESEARCH_FIXTURES[lookup_key]
        now = datetime.now(timezone.utc)

        # Construct Evidence items strictly labeled local_fixture with no fake URLs
        evidence_list: List[Evidence] = []
        for raw_evi in fixture.get("evidence", []):
            evidence_list.append(
                Evidence(
                    production_id=production_id or "global",
                    entity_id=entity_id,
                    job_id=job_id,
                    evidence_type=EvidenceType.RESEARCH_EVIDENCE,
                    entity_name=fixture["canonical_name"],
                    claim=raw_evi["claim"],
                    source_title=raw_evi.get("source_title", "Local Research Fixture"),
                    source_url=None,  # Strictly None for local fixtures
                    excerpt=raw_evi.get("excerpt"),
                    source_type="local_fixture",
                    confidence=float(raw_evi.get("confidence", fixture["confidence"])),
                    retrieved_at=now,
                    provider=self.provider_name,
                )
            )

        logger.info(
            f"[LocalResearchProvider] Found local fixture for '{clean_name}': "
            f"Rights Holder: '{fixture['candidate_rights_holder']}' ({len(evidence_list)} evidence items)"
        )

        return ResearchResult(
            production_id=production_id or "global",
            job_id=job_id,
            entity_id=entity_id,
            entity_name=fixture["canonical_name"],
            entity_type=entity_type or "brand",
            status=ResearchStatus.SUCCESS,
            candidate_rights_holder=fixture["candidate_rights_holder"],
            identity_confidence=fixture["confidence"],
            research_confidence=fixture["confidence"],
            evidence=evidence_list,
            query=query_str,
            provider=self.provider_name,
            retrieved_at=now,
            notes=fixture.get("identity_claim"),
            metadata={"source_type": "local_fixture", "found": True},
        )
