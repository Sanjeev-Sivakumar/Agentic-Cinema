"""
Deterministic Risk Scoring & Signal Engine for Chain of Title Pre-Clearance.

This is a PRODUCT TRIAGE SYSTEM designed to prioritize review workflows.
It is NOT a legal decision engine and does not provide legal advice or clearance conclusions.
"""

from typing import Any, Dict, List, Optional, Tuple
from app.models.entity import Entity, EntityClassification, EntityType, RiskLevel
from app.models.research import ResearchResult, ResearchStatus
from app.models.risk import RiskAssessment, RiskSignal


def _evaluate_visual_prominence(entity: Entity) -> Tuple[str, float, float, str]:
    """
    VISUAL_PROMINENCE signal.
    Evaluates prominence via explicit attribute or bounding box geometry.
    """
    prominence = (entity.prominence or "").lower().strip()
    if prominence == "high":
        return "high", 30.0, 30.0, "High visual prominence in scene composition"
    elif prominence == "medium":
        return "medium", 18.0, 18.0, "Moderate visual prominence in scene composition"
    elif prominence == "low":
        return "low", 5.0, 5.0, "Low or incidental visual prominence in frame"

    # Infer from bounding box if available
    bbox = entity.bounding_box or []
    if len(bbox) == 4:
        try:
            w = abs(float(bbox[2]) - float(bbox[0]))
            h = abs(float(bbox[3]) - float(bbox[1]))
            area = w * h
            if area > 0.15:
                return "high", 30.0, 30.0, f"Significant bounding box visual area ({area:.2f})"
            elif area > 0.04:
                return "medium", 18.0, 18.0, f"Moderate bounding box visual area ({area:.2f})"
            elif area > 0.0:
                return "low", 5.0, 5.0, f"Small bounding box visual area ({area:.2f})"
        except (ValueError, TypeError):
            pass

    return "unknown", 0.0, 0.0, "Visual prominence unknown or unrecorded"


def _evaluate_commercial_context(entity: Entity) -> Tuple[bool, float, float, str]:
    """
    COMMERCIAL_CONTEXT signal.
    Triggered if commercial_context flag is set or entity is a commercial brand/trademark.
    """
    etype_str = (entity.entity_type.value if hasattr(entity.entity_type, "value") else str(entity.entity_type)).upper()
    is_commercial = bool(entity.commercial_context) or (
        etype_str in ("BRAND", "PRODUCT", "TRADEMARK", "COMPANY") and entity.confidence >= 0.70
    )
    if is_commercial:
        return True, 18.0, 18.0, "Entity visual appearance carries commercial or promotional impression"
    return False, 0.0, 0.0, "No distinct commercial context identified"


def _evaluate_music_rights(entity: Entity) -> Tuple[bool, float, float, str]:
    """
    MUSIC_RIGHTS signal.
    Triggered if entity represents music composition, song, or artist identity (+25.0).
    """
    etype_str = (entity.entity_type.value if hasattr(entity.entity_type, "value") else str(entity.entity_type)).upper()
    name_lower = (entity.name or "").lower()

    is_music = (
        etype_str == "MUSIC"
        or "music" in name_lower
        or "song" in name_lower
        or "soundtrack" in name_lower
        or (bool(entity.metadata) and entity.metadata.get("is_music", False))
    )

    if is_music:
        return True, 25.0, 25.0, "Musical composition, master recording, or artist identity detected"
    return False, 0.0, 0.0, "Non-musical asset"


def _evaluate_visual_only(entity: Entity) -> Tuple[bool, float, float, str]:
    """
    VISUAL_ONLY signal.
    Triggered when entity was discovered purely in visual footage without screenplay pre-clearance (+25.0).
    """
    classification = entity.classification
    class_val = (classification.value if hasattr(classification, "value") else str(classification)).upper() if classification else ""
    is_vo = class_val == "VISUAL_ONLY" or (
        entity.sources
        and "VISUAL" in [str(s.value if hasattr(s, "value") else s).upper() for s in entity.sources]
        and "SCRIPT" not in [str(s.value if hasattr(s, "value") else s).upper() for s in entity.sources]
    )

    if is_vo:
        return True, 25.0, 25.0, "Unscripted visual finding detected solely in footage (VISUAL_ONLY)"
    return False, 0.0, 0.0, "Script-planned or multi-source presence"


def _evaluate_research_confidence(
    entity: Entity,
    research_result: Optional[ResearchResult] = None,
) -> Tuple[float, float, float, str]:
    """
    RESEARCH_CONFIDENCE signal.
    High confidence reduces score (-10); unverified/not found adds positive risk (+10).
    """
    conf = 0.0
    status_success = False
    status_not_found = False

    if research_result is not None:
        conf = float(getattr(research_result, "identity_confidence", 0.0) or getattr(research_result, "research_confidence", 0.0))
        status_success = (research_result.status == ResearchStatus.SUCCESS)
        status_not_found = (research_result.status == ResearchStatus.NOT_FOUND)
    elif entity.research_confidence > 0:
        conf = float(entity.research_confidence)
        status_success = True

    if status_success and conf >= 0.80:
        return conf, -10.0, -10.0, f"Strong verified corporate/trademark registry match reduces triage risk ({conf:.2f})"
    elif status_success and conf >= 0.50:
        return conf, -5.0, -5.0, f"Moderate research corroboration of rights holder ({conf:.2f})"
    elif status_not_found:
        return conf, 10.0, 10.0, "Unverified entity: registry search yielded no confirmed rights holder"
    return conf, 0.0, 0.0, f"Preliminary research status ({conf:.2f})"


def _evaluate_entity_type(entity: Entity) -> Tuple[str, float, float, str]:
    """
    ENTITY_TYPE signal.
    Applies baseline triage weight by entity type category.
    """
    etype_str = (entity.entity_type.value if hasattr(entity.entity_type, "value") else str(entity.entity_type)).upper()

    if etype_str in ("MUSIC",):
        return "music", 15.0, 15.0, "Music works carry strict statutory clearance exposure"
    elif etype_str in ("BRAND", "TRADEMARK"):
        return "brand", 12.0, 12.0, "Commercial brand or trademark subject to trademark clearance triage"
    elif etype_str in ("ARTWORK", "POSTER"):
        return "artwork", 10.0, 10.0, "Fine artwork or copyrighted graphics require provenance review"
    elif etype_str in ("PRODUCT", "COMPANY"):
        return "product", 8.0, 8.0, "Commercial product asset"
    elif etype_str in ("FILM", "TV", "TV_SHOW", "FILM_TV"):
        return "media", 8.0, 8.0, "Third-party audiovisual reference or excerpt"
    elif etype_str in ("PUBLIC_FIGURE", "PERSON"):
        return "person", 5.0, 5.0, "Recognizable persona subject to right of publicity review"
    elif etype_str in ("LOCATION", "PROP"):
        return "prop", 3.0, 3.0, "Physical prop or scenic element"
    return "other", 0.0, 0.0, "Generic or unclassified asset type"


def _evaluate_duration(entity: Entity) -> Tuple[str, float, float, str]:
    """
    DURATION signal.
    Extended appearances or multi-scene presence add triage weight (+10.0).
    """
    dur_sec = 0.0
    if entity.first_seen_timestamp is not None and entity.last_seen_timestamp is not None:
        dur_sec = max(0.0, entity.last_seen_timestamp - entity.first_seen_timestamp)
    elif entity.appearances > 1:
        dur_sec = entity.appearances * 1.5

    meta_dur = entity.metadata.get("duration") if entity.metadata else None
    if meta_dur is not None:
        try:
            dur_sec = max(dur_sec, float(meta_dur))
        except (ValueError, TypeError):
            pass

    if dur_sec >= 5.0 or entity.appearances >= 4:
        return "long/prominent", 10.0, 10.0, f"Extended on-screen presence ({dur_sec:.1f}s / {entity.appearances} occurrences)"
    elif dur_sec >= 1.5 or entity.appearances >= 2:
        return "medium", 5.0, 5.0, f"Moderate scene exposure ({dur_sec:.1f}s)"
    elif dur_sec > 0.0:
        return "brief", 2.0, 2.0, f"Brief or fleeting presence ({dur_sec:.1f}s)"
    return "unknown", 0.0, 0.0, "Duration undetermined"


def _evaluate_screen_position(entity: Entity) -> Tuple[str, float, float, str]:
    """
    SCREEN_POSITION signal.
    Central frame focal placement adds exposure (+5.0).
    """
    bbox = entity.bounding_box or []
    pos_meta = ((entity.metadata.get("screen_position") if entity.metadata else "") or "").lower()

    if pos_meta in ("foreground", "center", "foreground/center"):
        return "foreground/center", 5.0, 5.0, "Positioned prominently in camera foreground or focal center"
    elif pos_meta == "background":
        return "background", 2.0, 2.0, "Positioned in scene background"

    if len(bbox) == 4:
        try:
            center_x = (float(bbox[0]) + float(bbox[2])) / 2.0
            center_y = (float(bbox[1]) + float(bbox[3])) / 2.0
            if 0.20 <= center_x <= 0.80 and 0.20 <= center_y <= 0.80:
                return "center", 5.0, 5.0, f"Central frame coordinate bounding area ({center_x:.2f}, {center_y:.2f})"
            return "peripheral", 2.0, 2.0, "Incidental perimeter bounding coordinate"
        except (ValueError, TypeError):
            pass

    return "unknown", 0.0, 0.0, "Screen position unmeasured"


def _is_unknown_entity(entity: Entity, research_result: Optional[ResearchResult] = None) -> Tuple[bool, str]:
    """
    Determine if evidence is insufficient to perform a meaningful product-level triage.
    UNKNOWN is used when evidence is lacking, NEVER as a surrogate for LOW risk.
    """
    name = (entity.name or "").strip().lower()
    if not name or name in ("unknown", "n/a", "na", "unidentified", "none", "tbd", "unnamed"):
        return True, "Entity name is missing, placeholder, or unidentified"

    if entity.confidence < 0.35:
        return True, f"Visual detection confidence ({entity.confidence:.2f}) is critically low; triage unreliable"

    if not entity.sources and not entity.frame_path and not entity.context:
        return True, "No context, frame, or source attribution available to evaluate triage signals"

    return False, ""


def compute_evidence_confidence(
    entity: Entity,
    research_result: Optional[ResearchResult] = None,
    is_unknown: bool = False,
) -> float:
    """
    Compute evidence quality confidence based on detection certainty,
    visual presence, research status, and metadata completeness.
    """
    base_conf = float(entity.confidence) * 0.40
    visual_conf = 0.20 if (entity.frame_path or entity.evidence_ids or entity.bounding_box) else 0.05
    research_conf = 0.0
    if research_result is not None and research_result.status == ResearchStatus.SUCCESS:
        r_conf = getattr(research_result, "identity_confidence", 0.0) or getattr(research_result, "research_confidence", 0.0)
        research_conf = 0.25 * min(1.0, float(r_conf))
    elif entity.research_confidence > 0:
        research_conf = 0.20 * min(1.0, float(entity.research_confidence))
    else:
        research_conf = 0.05

    meta_conf = 0.15 if (entity.scene is not None and entity.context) else 0.08
    calculated_confidence = max(0.0, min(1.0, round(base_conf + visual_conf + research_conf + meta_conf, 2)))

    if is_unknown:
        calculated_confidence = min(0.30, calculated_confidence)

    return calculated_confidence


def generate_triage_explanation(
    entity: Entity,
    level: RiskLevel,
    signals: List[RiskSignal],
    is_unknown: bool = False,
    unknown_reason: str = "",
) -> str:
    """Generate explainable, non-legal product triage summary."""
    active_signals = [s for s in signals if s.contribution > 0]
    if is_unknown:
        return f"{entity.name or 'Entity'} triage status is UNKNOWN: {unknown_reason}. Further evidence acquisition recommended."

    signal_phrases = []
    for s in active_signals:
        if s.signal_name == "VISUAL_ONLY":
            signal_phrases.append("unscripted footage appearance (VISUAL_ONLY)")
        elif s.signal_name == "VISUAL_PROMINENCE":
            signal_phrases.append(f"{s.value} visual prominence")
        elif s.signal_name == "COMMERCIAL_CONTEXT":
            signal_phrases.append("commercial focal impression")
        elif s.signal_name == "MUSIC_RIGHTS":
            signal_phrases.append("music rights sensitivity")
        elif s.signal_name == "RESEARCH_CONFIDENCE":
            signal_phrases.append("corroborated trademark/rights registry records")
        elif s.signal_name == "ENTITY_TYPE":
            signal_phrases.append(f"{s.value} asset classification")
        elif s.signal_name == "DURATION":
            signal_phrases.append(f"{s.value} screen duration")
        elif s.signal_name == "SCREEN_POSITION":
            signal_phrases.append(f"{s.value} placement")

    summary_reasons = ", ".join(signal_phrases) if signal_phrases else "baseline incidental context"
    return (
        f"{entity.name} is prioritized as {level.value} review priority "
        f"based on {summary_reasons}. Potential clearance review is recommended."
    )


def calculate_risk(
    entity: Entity,
    research_result: Optional[ResearchResult] = None,
    production_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> RiskAssessment:
    """
    Deterministic risk calculation function.
    Given entity and optional research_result, computes:
      - 8 deterministic risk signals
      - clamped risk score (0-100)
      - risk level (LOW, MEDIUM, HIGH, UNKNOWN)
      - evidence-backed confidence (0.0-1.0)
      - structured human-readable explanation
    """
    prod_id = production_id or entity.production_id or "default"
    j_id = job_id or entity.job_id

    # 1. Check for UNKNOWN triage status
    is_unknown, unknown_reason = _is_unknown_entity(entity, research_result)

    # 2. Extract deterministic signals
    signals: List[RiskSignal] = []

    # Signal 1: VISUAL_PROMINENCE
    val, weight, contrib, expl = _evaluate_visual_prominence(entity)
    signals.append(RiskSignal(signal_name="VISUAL_PROMINENCE", value=val, weight=weight, contribution=contrib, explanation=expl))

    # Signal 2: COMMERCIAL_CONTEXT
    val, weight, contrib, expl = _evaluate_commercial_context(entity)
    signals.append(RiskSignal(signal_name="COMMERCIAL_CONTEXT", value=val, weight=weight, contribution=contrib, explanation=expl))

    # Signal 3: MUSIC_RIGHTS
    val, weight, contrib, expl = _evaluate_music_rights(entity)
    signals.append(RiskSignal(signal_name="MUSIC_RIGHTS", value=val, weight=weight, contribution=contrib, explanation=expl))

    # Signal 4: VISUAL_ONLY
    val, weight, contrib, expl = _evaluate_visual_only(entity)
    signals.append(RiskSignal(signal_name="VISUAL_ONLY", value=val, weight=weight, contribution=contrib, explanation=expl))

    # Signal 5: RESEARCH_CONFIDENCE
    val, weight, contrib, expl = _evaluate_research_confidence(entity, research_result)
    signals.append(RiskSignal(signal_name="RESEARCH_CONFIDENCE", value=val, weight=weight, contribution=contrib, explanation=expl))

    # Signal 6: ENTITY_TYPE
    val, weight, contrib, expl = _evaluate_entity_type(entity)
    signals.append(RiskSignal(signal_name="ENTITY_TYPE", value=val, weight=weight, contribution=contrib, explanation=expl))

    # Signal 7: DURATION
    val, weight, contrib, expl = _evaluate_duration(entity)
    signals.append(RiskSignal(signal_name="DURATION", value=val, weight=weight, contribution=contrib, explanation=expl))

    # Signal 8: SCREEN_POSITION
    val, weight, contrib, expl = _evaluate_screen_position(entity)
    signals.append(RiskSignal(signal_name="SCREEN_POSITION", value=val, weight=weight, contribution=contrib, explanation=expl))

    # 3. Deterministic score calculation
    if is_unknown:
        score = 0.0
        level = RiskLevel.UNKNOWN
    else:
        raw_score = sum(s.contribution for s in signals)
        score = max(0.0, min(100.0, float(raw_score)))

        # 4. Determine triage risk level
        if score >= 70.0:
            level = RiskLevel.HIGH
        elif score >= 40.0:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

    # 5. Deterministic Confidence Calculation
    calculated_confidence = compute_evidence_confidence(
        entity=entity,
        research_result=research_result,
        is_unknown=is_unknown,
    )

    # 6. Structured Explanation
    explanation = generate_triage_explanation(
        entity=entity,
        level=level,
        signals=signals,
        is_unknown=is_unknown,
        unknown_reason=unknown_reason,
    )

    return RiskAssessment(
        entity_id=entity.id,
        production_id=prod_id,
        job_id=j_id,
        entity_name=entity.name,
        risk_level=level,
        risk_score=score,
        signals=signals,
        explanation=explanation,
        confidence=calculated_confidence,
        assessor="RiskAssessmentAgent",
    )


# Alias for backward and testing compatibility
compute_risk_assessment = calculate_risk
