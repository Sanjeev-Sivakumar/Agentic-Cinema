"""
Verification Engine — Phase 6 Deterministic Evidence Verification Layer.

The Verification Engine performs adversarial checks on entities, research results,
and risk assessments to determine whether available evidence factually supports
the claims made.

Strict principles:
- Adversarial review: does not simply rubber-stamp research or risk agents.
- Triage / evidence checking only: does NOT provide legal advice or legal opinions.
- Deterministic, zero-network calculations.
"""

from typing import Any, Dict, List, Optional, Tuple
from app.core.logging import logger
from app.models.entity import Entity, EntityClassification, EntitySource, EntityType
from app.models.research import ResearchResult, ResearchStatus
from app.models.risk import RiskAssessment, RiskLevel, RiskSignal
from app.models.evidence import Evidence
from app.models.verification import VerificationCheck, VerificationDecision, VerificationResult


class VerificationEngine:
    """
    Adversarial verification engine evaluating 7 core checks,
    detecting contradictions, and producing deterministic verification results.
    """

    def verify(
        self,
        entity: Entity,
        research: Optional[ResearchResult] = None,
        risk: Optional[RiskAssessment] = None,
        evidence_list: Optional[List[Evidence]] = None,
        script_text: Optional[str] = None,
    ) -> VerificationResult:
        """
        Execute comprehensive adversarial verification for an entity.
        """
        evidence_list = evidence_list or []
        checks: List[VerificationCheck] = []
        claims_supported: List[str] = []
        claims_disputed: List[str] = []
        contradictions: List[str] = []

        # 1. CONTRADICTION_CHECK (Adversarial rule evaluations)
        detected_contradictions = self._detect_contradictions(
            entity=entity,
            research=research,
            risk=risk,
            evidence_list=evidence_list,
            script_text=script_text,
        )
        contradictions.extend(detected_contradictions)

        chk_contradiction = VerificationCheck(
            name="CONTRADICTION_CHECK",
            passed=len(contradictions) == 0,
            evidence_evaluated=[f"Contradictions found: {len(contradictions)}"],
            explanation=(
                "No evidence contradictions detected across entity, research, and risk data."
                if len(contradictions) == 0
                else f"Contradictions detected: {'; '.join(contradictions)}"
            ),
            severity_if_failed="HIGH",
        )
        checks.append(chk_contradiction)
        if chk_contradiction.passed:
            claims_supported.append("Cross-source consistency verified without factual contradictions.")
        else:
            claims_disputed.append(f"Contradictions detected in evidence chain: {'; '.join(contradictions)}")

        # 2. IDENTITY_SUPPORT Check
        chk_identity, id_supported, id_disputed = self._check_identity_support(entity, research)
        checks.append(chk_identity)
        if id_supported:
            claims_supported.append(id_supported)
        if id_disputed:
            claims_disputed.append(id_disputed)

        # 3. RESEARCH_SUPPORT Check
        chk_research, res_supported, res_disputed = self._check_research_support(entity, research)
        checks.append(chk_research)
        if res_supported:
            claims_supported.append(res_supported)
        if res_disputed:
            claims_disputed.append(res_disputed)

        # 4. EVIDENCE_QUALITY Check
        chk_evidence, ev_supported, ev_disputed = self._check_evidence_quality(entity, evidence_list)
        checks.append(chk_evidence)
        if ev_supported:
            claims_supported.append(ev_supported)
        if ev_disputed:
            claims_disputed.append(ev_disputed)

        # 5. RISK_SUPPORT Check
        chk_risk, rk_supported, rk_disputed = self._check_risk_support(entity, risk)
        checks.append(chk_risk)
        if rk_supported:
            claims_supported.append(rk_supported)
        if rk_disputed:
            claims_disputed.append(rk_disputed)

        # 6. SOURCE_CONSISTENCY Check
        chk_source, src_supported, src_disputed = self._check_source_consistency(entity, script_text)
        checks.append(chk_source)
        if src_supported:
            claims_supported.append(src_supported)
        if src_disputed:
            claims_disputed.append(src_disputed)

        # 7. METADATA_COMPLETENESS Check
        chk_meta, meta_supported, meta_disputed = self._check_metadata_completeness(entity)
        checks.append(chk_meta)
        if meta_supported:
            claims_supported.append(meta_supported)
        if meta_disputed:
            claims_disputed.append(meta_disputed)

        # Calculate Confidence & Decision
        confidence = self._calculate_confidence(
            entity=entity,
            research=research,
            risk=risk,
            checks=checks,
        )

        decision = self._determine_decision(
            checks=checks,
            contradictions=contradictions,
            confidence=confidence,
            research=research,
            evidence_list=evidence_list,
        )

        recommended_action = self._recommend_action(decision, entity, contradictions)

        # Retrieve candidate registry info
        registry_source = "USPTO / Trademark Database"
        registration_number = None
        if research and research.evidence:
            for ev in research.evidence:
                src = getattr(ev, "source_title", None) or getattr(ev, "source", None) or getattr(ev, "source_url", None)
                if src:
                    registry_source = src
                reg_num = getattr(ev, "registration_number", None)
                if reg_num:
                    registration_number = reg_num
                    break

        rights_holder_str = (
            (research.candidate_rights_holder if research else None)
            or entity.candidate_rights_holder
            or entity.rights_holder
            or entity.name
        )

        return VerificationResult(
            entity_id=entity.id,
            production_id=entity.production_id,
            entity_name=entity.name,
            decision=decision,
            confidence=confidence,
            checks_run=checks,
            claims_supported=claims_supported,
            claims_disputed=claims_disputed,
            contradictions=contradictions,
            recommended_action=recommended_action,
            registry_source=registry_source,
            registration_number=registration_number,
            notes=f"Adversarial verification completed. Decision: {decision.value} (Confidence: {confidence:.2f})",
            metadata={
                "rights_holder": rights_holder_str,
                "checks_passed": sum(1 for c in checks if c.passed),
                "checks_total": len(checks),
                "contradictions_count": len(contradictions),
            },
        )

    # -------------------------------------------------------------------------
    # Contradiction Detection Rules
    # -------------------------------------------------------------------------
    def _detect_contradictions(
        self,
        entity: Entity,
        research: Optional[ResearchResult],
        risk: Optional[RiskAssessment],
        evidence_list: List[Evidence],
        script_text: Optional[str],
    ) -> List[str]:
        contradictions: List[str] = []

        # Rule 1: Conflicting rights holders across evidence / research
        if research and research.evidence:
            holders = {
                ev.candidate_rights_holder.strip().lower()
                for ev in research.evidence
                if ev.candidate_rights_holder
            }
            if len(holders) > 1:
                contradictions.append(
                    f"Multiple conflicting rights holders identified in evidence: {', '.join(holders)}"
                )

        # Rule 2: MUSIC_RIGHTS risk signal on non-music entity without audio evidence
        if risk:
            music_signals = [
                s for s in risk.signals
                if ("MUSIC" in (getattr(s, "signal_name", None) or getattr(s, "signal_type", "")).upper()
                or "SONG" in (getattr(s, "signal_name", None) or getattr(s, "signal_type", "")).upper())
                and (
                    getattr(s, "value", False) is True
                    or (isinstance(getattr(s, "value", None), str) and getattr(s, "value").lower() not in ("", "false", "none", "0"))
                    or (getattr(s, "contribution", 0.0) or 0.0) > 0.0
                )
            ]
            has_audio_source = EntitySource.AUDIO in entity.sources
            has_music_type = entity.entity_type == EntityType.MUSIC
            if music_signals and not has_audio_source and not has_music_type:
                contradictions.append(
                    "Risk assessment claims MUSIC_RIGHTS exposure, but entity lacks audio source and is not classified as MUSIC."
                )

        # Rule 3: VISUAL_ONLY classification contradicted by verbatim presence in screenplay
        if entity.classification == EntityClassification.VISUAL_ONLY and script_text:
            if entity.name.lower() in script_text.lower():
                contradictions.append(
                    f"Entity classified as VISUAL_ONLY, but name '{entity.name}' appears verbatim in the screenplay."
                )

        # Rule 4: Research status is NOT_FOUND but candidate rights holder is claimed as verified
        if research and research.status == ResearchStatus.NOT_FOUND:
            if research.candidate_rights_holder and research.candidate_rights_holder.strip():
                contradictions.append(
                    "Research status is NOT_FOUND, but candidate rights holder is populated with affirmative claimant."
                )

        # Rule 5: Audio-only classification but visual frames attached
        if entity.classification == EntityClassification.AUDIO_ONLY and (entity.frame_path or entity.evidence_frames):
            contradictions.append(
                "Entity classified as AUDIO_ONLY, but video frame evidence is attached."
            )

        return contradictions

    # -------------------------------------------------------------------------
    # 7 Core Checks Implementation
    # -------------------------------------------------------------------------
    def _check_identity_support(
        self,
        entity: Entity,
        research: Optional[ResearchResult],
    ) -> Tuple[VerificationCheck, Optional[str], Optional[str]]:
        candidate = (
            (research.candidate_rights_holder if research else None)
            or entity.candidate_rights_holder
            or entity.rights_holder
        )
        passed = bool(candidate and candidate.strip() and candidate.strip().lower() != "pending verification")

        supported = None
        disputed = None
        if passed:
            supported = f"Candidate rights holder '{candidate}' identified and substantiated."
            explanation = f"Entity identity verified against rights holder record '{candidate}'."
        else:
            disputed = f"Entity '{entity.name}' lacks a confirmed candidate rights holder."
            explanation = "No substantiated candidate rights holder identified in research or metadata."

        return (
            VerificationCheck(
                name="IDENTITY_SUPPORT",
                passed=passed,
                evidence_evaluated=[f"Candidate: {candidate or 'None'}"],
                explanation=explanation,
                severity_if_failed="MEDIUM" if not passed else "LOW",
            ),
            supported,
            disputed,
        )

    def _check_research_support(
        self,
        entity: Entity,
        research: Optional[ResearchResult],
    ) -> Tuple[VerificationCheck, Optional[str], Optional[str]]:
        if not research:
            return (
                VerificationCheck(
                    name="RESEARCH_SUPPORT",
                    passed=False,
                    evidence_evaluated=["Research record: None"],
                    explanation="No research record available for entity.",
                    severity_if_failed="MEDIUM",
                ),
                None,
                f"Missing research record for '{entity.name}'.",
            )

        passed = (
            research.status != ResearchStatus.NOT_FOUND
            and research.research_confidence >= 0.40
        )
        if passed:
            supported = f"Research completed with {research.research_confidence * 100:.0f}% confidence ({research.status.value})."
            explanation = f"Research provides sufficient evidence (Status: {research.status.value}, Confidence: {research.research_confidence:.2f})."
            disputed = None
        else:
            supported = None
            disputed = f"Research failed or inconclusive (Status: {research.status.value}, Confidence: {research.research_confidence:.2f})."
            explanation = f"Research support is insufficient or unverified (Status: {research.status.value})."

        return (
            VerificationCheck(
                name="RESEARCH_SUPPORT",
                passed=passed,
                evidence_evaluated=[
                    f"Status: {research.status.value}",
                    f"Confidence: {research.research_confidence:.2f}",
                    f"Evidence items: {len(research.evidence)}",
                ],
                explanation=explanation,
                severity_if_failed="MEDIUM",
            ),
            supported,
            disputed,
        )

    def _check_evidence_quality(
        self,
        entity: Entity,
        evidence_list: List[Evidence],
    ) -> Tuple[VerificationCheck, Optional[str], Optional[str]]:
        has_frames = bool(entity.frame_path or entity.evidence_frames or evidence_list)
        has_context = bool(entity.context or entity.visual_basis or entity.scene)
        has_bbox = bool(entity.bounding_box and len(entity.bounding_box) == 4)

        # Quality passes if there is verifiable physical/script context and evidence
        passed = has_frames or has_context

        if passed:
            details = []
            if has_frames:
                details.append("Visual frame capture available")
            if has_bbox:
                details.append("Spatial bounding box localized")
            if has_context:
                details.append(f"Context verified in Scene {entity.scene or 'N/A'}")
            supported = f"Primary evidence quality verified: {', '.join(details)}."
            disputed = None
            explanation = f"Evidence quality verified with {len(evidence_list)} evidence records."
        else:
            supported = None
            disputed = f"Entity '{entity.name}' has no frame capture or contextual evidence."
            explanation = "Evidence quality is insufficient: no video frames or context located."

        return (
            VerificationCheck(
                name="EVIDENCE_QUALITY",
                passed=passed,
                evidence_evaluated=[
                    f"Frames: {1 if entity.frame_path else len(entity.evidence_frames)}",
                    f"Evidence records: {len(evidence_list)}",
                    f"Bounding box: {entity.bounding_box}",
                ],
                explanation=explanation,
                severity_if_failed="MEDIUM",
            ),
            supported,
            disputed,
        )

    def _check_risk_support(
        self,
        entity: Entity,
        risk: Optional[RiskAssessment],
    ) -> Tuple[VerificationCheck, Optional[str], Optional[str]]:
        if not risk:
            # Fallback to entity's own risk fields
            if entity.risk_level != RiskLevel.UNKNOWN:
                return (
                    VerificationCheck(
                        name="RISK_SUPPORT",
                        passed=True,
                        evidence_evaluated=[f"Entity risk level: {entity.risk_level.value}"],
                        explanation="Entity has pre-calculated risk score in metadata.",
                        severity_if_failed="LOW",
                    ),
                    f"Risk score {entity.risk_score:.1f} ({entity.risk_level.value}) recorded on entity.",
                    None,
                )
            return (
                VerificationCheck(
                    name="RISK_SUPPORT",
                    passed=False,
                    evidence_evaluated=["Risk assessment: None"],
                    explanation="No risk assessment available for verification.",
                    severity_if_failed="LOW",
                ),
                None,
                f"No risk assessment data available for '{entity.name}'.",
            )

        # Risk support passes if the score is calculated with confidence > 0.3
        passed = risk.confidence >= 0.30
        if passed:
            supported = f"Risk assessment substantiated: {risk.overall_risk_level.value} ({risk.risk_score:.0f}/100, confidence {risk.confidence:.2f})."
            disputed = None
            explanation = f"Risk assessment has {len(risk.signals)} supporting signals and {risk.confidence:.2f} confidence."
        else:
            supported = None
            disputed = f"Risk score ({risk.risk_score:.0f}) lacks supporting confidence ({risk.confidence:.2f})."
            explanation = "Risk assessment confidence is below acceptable threshold."

        return (
            VerificationCheck(
                name="RISK_SUPPORT",
                passed=passed,
                evidence_evaluated=[
                    f"Level: {risk.overall_risk_level.value}",
                    f"Score: {risk.risk_score:.1f}",
                    f"Confidence: {risk.confidence:.2f}",
                    f"Signals: {len(risk.signals)}",
                ],
                explanation=explanation,
                severity_if_failed="LOW",
            ),
            supported,
            disputed,
        )

    def _check_source_consistency(
        self,
        entity: Entity,
        script_text: Optional[str],
    ) -> Tuple[VerificationCheck, Optional[str], Optional[str]]:
        classification = entity.classification
        sources = entity.sources

        passed = True
        explanation = "Source classifications align across footage and screenplay."

        if classification == EntityClassification.SCRIPT_ONLY and EntitySource.VISUAL in sources:
            passed = False
            explanation = "Inconsistency: entity classified as SCRIPT_ONLY but VISUAL source is present."
        elif classification == EntityClassification.VISUAL_ONLY and EntitySource.SCRIPT in sources:
            passed = False
            explanation = "Inconsistency: entity classified as VISUAL_ONLY but SCRIPT source is present."
        elif classification == EntityClassification.BOTH and (EntitySource.SCRIPT not in sources or EntitySource.VISUAL not in sources):
            passed = False
            explanation = "Inconsistency: entity classified as BOTH but lacks one of the required sources."

        if passed:
            supported = f"Source classification '{classification.value}' verified consistent with source list."
            disputed = None
        else:
            supported = None
            disputed = f"Source inconsistency for '{entity.name}': {explanation}"

        return (
            VerificationCheck(
                name="SOURCE_CONSISTENCY",
                passed=passed,
                evidence_evaluated=[
                    f"Classification: {classification.value}",
                    f"Sources: {[s.value for s in sources]}",
                ],
                explanation=explanation,
                severity_if_failed="HIGH",
            ),
            supported,
            disputed,
        )

    def _check_metadata_completeness(
        self,
        entity: Entity,
    ) -> Tuple[VerificationCheck, Optional[str], Optional[str]]:
        has_type = bool(entity.entity_type)
        has_name = bool(entity.name and entity.name.strip())
        has_prod = bool(entity.production_id)

        passed = has_type and has_name and has_prod
        if passed:
            supported = f"Required metadata complete (Type: {entity.entity_type.value}, Name: '{entity.name}')."
            disputed = None
            explanation = "Entity has all essential metadata fields populated."
        else:
            supported = None
            disputed = "Entity missing essential identification metadata."
            explanation = "One or more essential metadata fields (name, entity_type, production_id) missing."

        return (
            VerificationCheck(
                name="METADATA_COMPLETENESS",
                passed=passed,
                evidence_evaluated=[
                    f"Name: {entity.name}",
                    f"Type: {entity.entity_type.value if entity.entity_type else 'None'}",
                    f"Scene: {entity.scene}",
                    f"Timestamp: {entity.timestamp}",
                ],
                explanation=explanation,
                severity_if_failed="LOW",
            ),
            supported,
            disputed,
        )

    # -------------------------------------------------------------------------
    # Decision Determination & Confidence Calculation
    # -------------------------------------------------------------------------
    def _calculate_confidence(
        self,
        entity: Entity,
        research: Optional[ResearchResult],
        risk: Optional[RiskAssessment],
        checks: List[VerificationCheck],
    ) -> float:
        # Base confidence calculation
        weights = [entity.confidence]
        if research:
            weights.append(research.research_confidence)
        if risk:
            weights.append(risk.confidence)

        base_confidence = sum(weights) / len(weights) if weights else 0.85

        # Penalties based on failed checks
        deductions = 0.0
        for chk in checks:
            if not chk.passed:
                if chk.severity_if_failed == "HIGH":
                    deductions += 0.30
                elif chk.severity_if_failed == "MEDIUM":
                    deductions += 0.15
                elif chk.severity_if_failed == "LOW":
                    deductions += 0.05

        if not research:
            deductions += 0.15

        final_confidence = max(0.0, min(1.0, base_confidence - deductions))
        return round(final_confidence, 2)

    def _determine_decision(
        self,
        checks: List[VerificationCheck],
        contradictions: List[str],
        confidence: float,
        research: Optional[ResearchResult],
        evidence_list: List[Evidence],
    ) -> VerificationDecision:
        # 1. Critical contradictions lead to REJECTED assessment
        if len(contradictions) > 0:
            return VerificationDecision.REJECTED

        check_map = {c.name: c for c in checks}

        # 2. Insufficient evidence if research or evidence is completely absent
        if (
            (not research or research.status == ResearchStatus.NOT_FOUND)
            and len(evidence_list) == 0
            and check_map.get("EVIDENCE_QUALITY")
            and not check_map["EVIDENCE_QUALITY"].passed
        ):
            return VerificationDecision.INSUFFICIENT_EVIDENCE

        # 3. Check for high severity failure
        high_failures = [c for c in checks if not c.passed and c.severity_if_failed == "HIGH"]
        if high_failures:
            return VerificationDecision.REJECTED

        # 4. If all key checks pass and confidence is strong -> CONFIRMED
        passed_count = sum(1 for c in checks if c.passed)
        if passed_count == len(checks) and confidence >= 0.70:
            return VerificationDecision.CONFIRMED

        # 5. If medium checks failed or confidence is borderline -> REVIEW
        return VerificationDecision.REVIEW

    def _recommend_action(
        self,
        decision: VerificationDecision,
        entity: Entity,
        contradictions: List[str],
    ) -> str:
        """Provide explainable, non-legal triage recommendations."""
        if decision == VerificationDecision.CONFIRMED:
            return (
                f"Candidate rights holder and evidence for '{entity.name}' are substantiated. "
                "Recommended next step: proceed to standard clearance licensing workflow."
            )
        elif decision == VerificationDecision.REJECTED:
            reasons = "; ".join(contradictions) if contradictions else "unsubstantiated claims"
            return (
                f"Discrepancies or contradictions detected for '{entity.name}' ({reasons}). "
                "Recommended next step: flag for manual clearance audit and review primary evidence."
            )
        elif decision == VerificationDecision.INSUFFICIENT_EVIDENCE:
            return (
                f"Evidence for '{entity.name}' is inconclusive. "
                "Recommended next step: capture higher-resolution video frames or conduct manual trademark registry search."
            )
        else:  # REVIEW
            return (
                f"Evidence partially supports '{entity.name}', but confidence is moderate. "
                "Recommended next step: assign to production coordinator for secondary verification review."
            )


verification_engine = VerificationEngine()
