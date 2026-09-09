"""
Deterministic Resolution Engine for Chain of Title (Phase 7).
Translates verified findings, risks, and evidence into clear, operational next steps.

Strict Rules:
- Operational triage layer, NOT a legal decision engine.
- Never assert legal clearance or infringement.
- Deterministic, zero-network, 100% offline.
"""
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
import uuid

from app.core.logging import logger
from app.models.resolution import (
    ResolutionStatus,
    ResolutionAction,
    ResolutionPriority,
    ResolutionResult,
)
from app.models.entity import Entity, EntityClassification, EntityType, RiskLevel
from app.models.risk import RiskAssessment
from app.models.verification import VerificationResult, VerificationDecision


class ResolutionEngine:
    """
    Pure deterministic resolution intelligence engine.
    Applies rules A through I to produce operational next steps,
    evidence traceability, and neutral replacement suggestions.
    """

    @staticmethod
    def get_action_for_entity_type(
        entity_type_str: str,
        risk_level_str: str,
        verification_decision_str: str,
    ) -> ResolutionAction:
        """
        Maps entity type to a specific operational review action.
        """
        etype = entity_type_str.upper()

        if etype in ("BRAND", "PRODUCT", "TRADEMARK", "COMPANY"):
            return ResolutionAction.REVIEW_BRAND_USAGE
        elif etype in ("MUSIC", "SONG", "AUDIO"):
            return ResolutionAction.REVIEW_MUSIC_USAGE
        elif etype in ("ARTWORK", "POSTER", "BOOK", "PAINTING"):
            return ResolutionAction.REVIEW_ARTWORK_USAGE
        elif etype in ("LOCATION", "SIGNAGE", "BUILDING"):
            return ResolutionAction.REVIEW_LOCATION_USAGE
        elif etype in ("PERSON", "PUBLIC_FIGURE", "CELEBRITY"):
            return ResolutionAction.REVIEW_PUBLIC_FIGURE_USAGE
        elif etype in ("FILM", "TV_SHOW", "FILM_TV", "MEDIA"):
            return ResolutionAction.REQUEST_RIGHTS_INFORMATION
        else:
            return ResolutionAction.HUMAN_REVIEW

    @staticmethod
    def get_replacement_suggestion(
        entity_type_str: str,
        entity_name: str = "",
    ) -> str:
        """
        Generates neutral, non-branded replacement options.
        Strict rule: Never suggest real brand names.
        """
        etype = entity_type_str.upper()
        display_name = f" ('{entity_name}')" if entity_name else ""

        if etype in ("BRAND", "PRODUCT", "TRADEMARK", "COMPANY"):
            return (
                f"Consider replacing the identifiable branded element{display_name} "
                "with a neutral or unbranded prop/asset if operationally appropriate."
            )
        elif etype in ("MUSIC", "SONG", "AUDIO"):
            return (
                "Consider replacing the identified audio composition with cleared library music "
                "or original score composition."
            )
        elif etype in ("ARTWORK", "POSTER", "BOOK", "PAINTING"):
            return (
                f"Consider replacing or reframing the identifiable artwork{display_name} "
                "with production-commissioned or public domain alternatives."
            )
        elif etype in ("LOCATION", "SIGNAGE", "BUILDING"):
            return (
                "Consider replacing or digitally obscuring signage "
                "in post-production if practical."
            )
        elif etype in ("PERSON", "PUBLIC_FIGURE"):
            return (
                "Review visual likeness and consider replacing, reframing, digital obscuration, or securing a talent release agreement."
            )
        else:
            return (
                "Consider replacing with alternative creative assets or digital obscuration if operational review indicates."
            )

    @staticmethod
    def calculate_resolution_priority(
        risk_level: str,
        classification: str,
        has_contradiction: bool = False,
        verification_decision: str = "",
        risk_score: float = 0.0,
    ) -> ResolutionPriority:
        """
        Calculates operational resolution priority based on:
        - Risk level and risk score
        - Visual vs Script classification (Rule H & Rule I)
        - Contradictions (Rule C)
        - Verification decision
        """
        rl = risk_level.upper()
        cl = classification.upper()
        vd = verification_decision.upper()

        if has_contradiction and rl == "HIGH":
            return ResolutionPriority.CRITICAL

        if vd == "REJECTED":
            return ResolutionPriority.MEDIUM

        if rl == "HIGH":
            if cl == "VISUAL_ONLY" or risk_score >= 80:
                return ResolutionPriority.CRITICAL
            return ResolutionPriority.HIGH

        if rl == "MEDIUM":
            if cl == "VISUAL_ONLY":
                return ResolutionPriority.HIGH
            return ResolutionPriority.MEDIUM

        if rl == "LOW":
            if vd == "CONFIRMED":
                return ResolutionPriority.LOW
            return ResolutionPriority.INFO

        if vd == "INSUFFICIENT_EVIDENCE":
            if cl == "VISUAL_ONLY":
                return ResolutionPriority.HIGH
            return ResolutionPriority.MEDIUM

        return ResolutionPriority.MEDIUM

    @classmethod
    def resolve(
        cls,
        entity: Union[Entity, Dict[str, Any]],
        risk: Optional[Union[RiskAssessment, Dict[str, Any]]] = None,
        verification: Optional[Union[VerificationResult, Dict[str, Any]]] = None,
        research: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
    ) -> ResolutionResult:
        """
        Evaluates an entity along with its risk, verification, and research evidence
        to formulate an operational resolution recommendation.
        """
        # Safely extract entity attributes
        if isinstance(entity, dict):
            entity_id = entity.get("id") or entity.get("entity_id", "")
            entity_name = entity.get("name", "Unknown Entity")
            entity_type_raw = entity.get("entity_type", "BRAND")
            production_id = entity.get("production_id", "")
            classification_raw = entity.get("classification", "VISUAL_ONLY")
            evidence_frames = entity.get("evidence_frames", [])
        else:
            entity_id = entity.id
            entity_name = entity.name
            entity_type_raw = entity.entity_type.value if hasattr(entity.entity_type, "value") else str(entity.entity_type)
            production_id = entity.production_id
            classification_raw = (
                entity.classification.value
                if hasattr(entity.classification, "value")
                else str(entity.classification)
            )
            evidence_frames = list(entity.evidence_frames or [])

        # Safely extract verification attributes
        verification_decision = ""
        verification_confidence = 0.8
        verification_id = None
        contradictions: List[str] = []
        ver_evidence_ids: List[str] = []

        if verification is not None:
            if isinstance(verification, dict):
                verification_id = verification.get("verification_id") or verification.get("id")
                dec = verification.get("decision") or verification.get("status", "")
                verification_decision = dec.value if hasattr(dec, "value") else str(dec)
                verification_confidence = float(verification.get("confidence", 0.8))
                contradictions = list(verification.get("contradictions", []))
                ver_evidence_ids = list(verification.get("metadata", {}).get("evidence_ids", []))
            else:
                verification_id = verification.verification_id
                verification_decision = (
                    verification.decision.value
                    if hasattr(verification.decision, "value")
                    else str(verification.decision)
                )
                verification_confidence = float(verification.confidence or 0.8)
                contradictions = list(verification.contradictions or [])
                ver_evidence_ids = list(verification.metadata.get("evidence_ids", [])) if verification.metadata else []

        # Safely extract risk attributes
        risk_level = "UNKNOWN"
        risk_score = 0.0
        risk_confidence = 0.8
        risk_id = None

        if risk is not None:
            if isinstance(risk, dict):
                risk_id = risk.get("risk_id") or risk.get("id")
                rl = risk.get("risk_level", "UNKNOWN")
                risk_level = rl.value if hasattr(rl, "value") else str(rl)
                risk_score = float(risk.get("risk_score", 0.0))
                risk_confidence = float(risk.get("confidence", 0.8))
            else:
                risk_id = risk.risk_id
                risk_level = risk.risk_level.value if hasattr(risk.risk_level, "value") else str(risk.risk_level)
                risk_score = float(risk.risk_score or 0.0)
                risk_confidence = float(risk.confidence or 0.8)

        # Normalize strings
        dec_upper = verification_decision.upper()
        risk_upper = risk_level.upper()
        type_upper = entity_type_raw.upper()
        class_upper = classification_raw.upper()
        has_contradiction = len(contradictions) > 0

        # Build initial evidence traceability IDs
        supporting_evidence: List[str] = []
        for ef in evidence_frames:
            if ef and ef not in supporting_evidence:
                supporting_evidence.append(ef)
        for ve in ver_evidence_ids:
            if ve and ve not in supporting_evidence:
                supporting_evidence.append(ve)
        if verification_id and verification_id not in supporting_evidence:
            supporting_evidence.append(verification_id)
        if risk_id and risk_id not in supporting_evidence:
            supporting_evidence.append(risk_id)

        # Build research details if present
        research_status = ""
        research_rights_holder = None
        if research:
            research_status = str(research.get("status", "")).upper()
            research_rights_holder = research.get("rights_holder") or research.get("owner")
            res_id = research.get("id") or research.get("research_id")
            if res_id and res_id not in supporting_evidence:
                supporting_evidence.append(res_id)

        # Determine Resolution Status & Action via Deterministic Rules:
        resolution_status = ResolutionStatus.UNRESOLVED
        recommended_action = ResolutionAction.HUMAN_REVIEW
        action_reason = ""
        missing_evidence: List[str] = []
        required_information: List[str] = []
        replacement_suggestion: Optional[str] = None
        research_action: Optional[str] = None

        # RULE C: Contradiction takes immediate operational precedence
        if has_contradiction:
            resolution_status = ResolutionStatus.HUMAN_REVIEW
            recommended_action = ResolutionAction.ESCALATE
            action_reason = (
                f"Contradiction detected in verification evidence: {'; '.join(contradictions)}. "
                "Operational escalation recommended."
            )
            required_information = [
                "Clarification of discrepancies between visual appearance and research claims",
                "Secondary manual review of source media",
            ]

        # RULE A: Insufficient evidence
        elif dec_upper == "INSUFFICIENT_EVIDENCE":
            resolution_status = ResolutionStatus.MORE_EVIDENCE_REQUIRED
            recommended_action = ResolutionAction.COLLECT_EVIDENCE
            action_reason = (
                "Additional visual or audio evidence is required to verify the presence, "
                "duration, and prominence of this potential clearance item."
            )
            missing_evidence = [
                "High-resolution frame capture",
                "Clear unoccluded view of the item",
                "Timestamp range of continuous exposure",
            ]
            required_information = [
                "Secondary capture angle or uncompressed source file",
                "Production continuity log confirmation",
            ]

        # RULE B: Rejected by verification
        elif dec_upper == "REJECTED":
            resolution_status = ResolutionStatus.HUMAN_REVIEW
            recommended_action = ResolutionAction.HUMAN_REVIEW
            action_reason = (
                "The available visual and contextual evidence fails to support the initial detection "
                "or research finding. Production review recommended to confirm non-exposure."
            )
            required_information = [
                "Human review of flagged frames to confirm artifact or false positive",
            ]

        # RULE D: Research required (research returned NOT_FOUND or empty)
        elif (
            research_status in ("NOT_FOUND", "EMPTY")
            or (research and not research_rights_holder and str(research.get("status", "")).upper() == "NOT_FOUND")
        ):
            resolution_status = ResolutionStatus.RESEARCH_REQUIRED
            recommended_action = ResolutionAction.CONDUCT_RESEARCH
            research_action = "TARGETED_RIGHTS_RESEARCH"
            action_reason = (
                "Automated research was unable to establish definitive rights holder or registry data. "
                "Targeted external research recommended."
            )
            required_information = [
                "Trademark and copyright registry search records",
                "Rights holder, licensor, or estate contact information",
                "Commercial chain-of-title documentation",
            ]

        # RULE E: HIGH RISK + CONFIRMED
        elif risk_upper == "HIGH" and dec_upper == "CONFIRMED":
            resolution_status = ResolutionStatus.ACTION_REQUIRED
            recommended_action = cls.get_action_for_entity_type(type_upper, risk_upper, dec_upper)
            action_reason = (
                f"Confirmed high-exposure {type_upper.lower()} identified. "
                "Active operational review required to establish clearance pathway."
            )
            replacement_suggestion = cls.get_replacement_suggestion(type_upper, entity_name)
            required_information = [
                "Clearance rights holder verification",
                "License request paperwork or replacement assessment",
            ]

        # RULE F: MEDIUM RISK + CONFIRMED
        elif risk_upper == "MEDIUM" and dec_upper == "CONFIRMED":
            resolution_status = ResolutionStatus.HUMAN_REVIEW
            recommended_action = cls.get_action_for_entity_type(type_upper, risk_upper, dec_upper)
            action_reason = (
                f"Confirmed medium-exposure {type_upper.lower()} element. "
                "Production clearance review recommended."
            )
            replacement_suggestion = cls.get_replacement_suggestion(type_upper, entity_name)
            required_information = [
                "Assessment of incidental capture vs deliberate inclusion",
                "Editorial review of scene context",
            ]

        # RULE G: LOW RISK + CONFIRMED
        elif risk_upper == "LOW" and dec_upper == "CONFIRMED":
            resolution_status = ResolutionStatus.RESOLVED
            recommended_action = ResolutionAction.NO_ACTION
            action_reason = (
                "This item does not currently require an additional operational action based on the available evidence."
            )
            required_information = []

        # Default fallback
        else:
            resolution_status = ResolutionStatus.HUMAN_REVIEW
            recommended_action = ResolutionAction.HUMAN_REVIEW
            action_reason = (
                f"Item status ({risk_upper} risk, {dec_upper or 'PENDING'} verification) "
                "requires clearance supervisor review to determine appropriate next steps."
            )
            required_information = [
                "Supervisory clearance triage review",
            ]

        # Calculate Priority with Rule H (VISUAL_ONLY) and Rule I (SCRIPT_ONLY)
        priority = cls.calculate_resolution_priority(
            risk_level=risk_upper,
            classification=class_upper,
            has_contradiction=has_contradiction,
            verification_decision=dec_upper,
            risk_score=risk_score,
        )

        # Confidence is derived deterministically from verification and risk confidences
        combined_confidence = round(
            (verification_confidence * 0.6) + (risk_confidence * 0.4),
            2,
        )

        resolution = ResolutionResult(
            entity_id=entity_id,
            production_id=production_id,
            job_id=job_id,
            entity_name=entity_name,
            entity_type=type_upper,
            verification_decision=dec_upper if dec_upper else None,
            risk_level=risk_upper,
            risk_score=risk_score,
            resolution_status=resolution_status,
            recommended_action=recommended_action,
            priority=priority,
            action_reason=action_reason,
            supporting_evidence_ids=supporting_evidence,
            missing_evidence=missing_evidence,
            required_information=required_information,
            research_action=research_action,
            replacement_suggestion=replacement_suggestion,
            confidence=combined_confidence,
            resolver="DeterministicResolutionEngine",
            metadata={
                "classification": class_upper,
                "has_contradiction": has_contradiction,
                "contradictions": contradictions,
            },
        )

        logger.info(
            f"[ResolutionEngine] Resolved '{entity_name}' -> Status: {resolution.resolution_status}, "
            f"Action: {resolution.recommended_action}, Priority: {resolution.priority}"
        )

        return resolution
