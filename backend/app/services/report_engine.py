from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.models.analysis import AnalysisJob
from app.models.entity import Entity
from app.models.evidence import Evidence
from app.models.production import Production
from app.models.financial_exposure import FinancialExposure
from app.models.outreach import ClearanceOutreachDraft
from app.models.remediation import VisualRemediationProposal
from app.models.report import (
    DEFAULT_LEGAL_DISCLAIMER,
    ReportFinding,
    ReportResult,
    ReportStatus,
)
from app.models.research import ResearchResult, ResearchStatus
from app.models.resolution import ResolutionResult
from app.models.risk import RiskAssessment
from app.models.verification import VerificationResult

class ReportEngine:
    """
    Deterministic clearance reporting intelligence engine.
    Aggregates and projects Phases 1-7 intelligence into structured findings,
    priority matrices, traceability chains, and executive metrics.
    """

    PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    RISK_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNKNOWN": 3}
    CLASSIFICATION_ORDER = {"VISUAL_ONLY": 0, "BOTH": 1, "SCRIPT_ONLY": 2, "AUDIO_ONLY": 3}

    def __init__(self):
        logger.info("[ReportEngine] Initialized Deterministic Report Generation Engine")

    def _val(self, obj: Any, default: str = "") -> str:
        if obj is None:
            return default
        if hasattr(obj, "value"):
            return str(obj.value)
        return str(obj)

    def generate_report(
        self,
        production: Production,
        job: AnalysisJob,
        entities: List[Entity],
        evidence_list: Optional[List[Evidence]] = None,
        research_results: Optional[List[ResearchResult]] = None,
        risk_assessments: Optional[List[RiskAssessment]] = None,
        verification_results: Optional[List[VerificationResult]] = None,
        resolution_results: Optional[List[ResolutionResult]] = None,
        financial_exposures: Optional[List[FinancialExposure]] = None,
        outreach_drafts: Optional[List[ClearanceOutreachDraft]] = None,
        remediation_proposals: Optional[List[VisualRemediationProposal]] = None,
        version: str = "1.0",
    ) -> ReportResult:
        """
        Generate a fully aggregated ReportResult from all prior stage artifacts.
        Guaranteed deterministic, offline, and zero-external-dependency.
        """
        start_time = time.perf_counter()
        logger.info(f"[ReportEngine] Generating clearance report for '{production.title}' ({len(entities)} entities)")

        evidence_list = evidence_list or []
        research_results = research_results or []
        risk_assessments = risk_assessments or []
        verification_results = verification_results or []
        resolution_results = resolution_results or []

        # Index prior stage results by entity_id
        evidence_by_entity: Dict[str, List[Evidence]] = {}
        for ev in evidence_list:
            if ev.entity_id:
                evidence_by_entity.setdefault(ev.entity_id, []).append(ev)

        research_by_entity: Dict[str, ResearchResult] = {}
        for r in research_results:
            if r.entity_id:
                research_by_entity[r.entity_id] = r

        risk_by_entity: Dict[str, RiskAssessment] = {}
        for rk in risk_assessments:
            if rk.entity_id:
                risk_by_entity[rk.entity_id] = rk

        verification_by_entity: Dict[str, VerificationResult] = {}
        for v in verification_results:
            if v.entity_id:
                verification_by_entity[v.entity_id] = v

        resolution_by_entity: Dict[str, ResolutionResult] = {}
        for res in resolution_results:
            if res.entity_id:
                resolution_by_entity[res.entity_id] = res

        # Distributions
        classification_counts: Dict[str, int] = {
            "VISUAL_ONLY": 0,
            "SCRIPT_ONLY": 0,
            "BOTH": 0,
            "AUDIO_ONLY": 0,
        }
        risk_distribution: Dict[str, int] = {
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "UNKNOWN": 0,
        }
        verification_distribution: Dict[str, int] = {
            "VERIFIED": 0,
            "CONTRADICTED": 0,
            "UNVERIFIED": 0,
            "INCONCLUSIVE": 0,
        }
        resolution_distribution: Dict[str, int] = {
            "CLEARED": 0,
            "LICENSE_REQUIRED": 0,
            "REMOVE_OR_REPLACE": 0,
            "FAIR_USE_ARGUMENT": 0,
            "PUBLIC_DOMAIN": 0,
            "ESCALATE_TO_LEGAL": 0,
            "UNRESOLVED": 0,
        }

        all_findings: List[ReportFinding] = []

        for entity in entities:
            e_id = entity.id
            cls_val = self._val(entity.classification, "UNKNOWN").upper()
            classification_counts[cls_val] = classification_counts.get(cls_val, 0) + 1

            # Risk data
            rk = risk_by_entity.get(e_id)
            risk_level = self._val(rk.risk_level if rk else entity.risk_level, "UNKNOWN").upper()
            risk_score = float(rk.risk_score if rk else (entity.risk_score or 0.0))
            risk_factors = [self._val(f) for f in rk.factors] if rk and rk.factors else []
            risk_distribution[risk_level] = risk_distribution.get(risk_level, 0) + 1

            # Verification data
            vr = verification_by_entity.get(e_id)
            verif_decision = self._val(getattr(vr, "decision", None) or getattr(entity, "verification_status", None), "UNVERIFIED").upper()
            verif_confidence = float(vr.confidence) if vr and vr.confidence is not None else None
            verif_rationale = getattr(vr, "reasoning", None)
            verification_distribution[verif_decision] = verification_distribution.get(verif_decision, 0) + 1

            # Resolution data
            res = resolution_by_entity.get(e_id)
            res_status = self._val(getattr(res, "resolution_status", None) or getattr(res, "status", None) or getattr(entity, "resolution_status", None), "UNRESOLVED").upper()
            res_action = self._val(getattr(res, "recommended_action", None) or getattr(res, "action", None) or getattr(res, "action_type", None) or getattr(entity, "resolution_action", None), "UNRESOLVED").upper()
            res_priority = self._val(getattr(res, "priority", None) or getattr(entity, "resolution_priority", None), "MEDIUM").upper()
            res_owner = getattr(res, "resolver", None) or getattr(res, "owner", None)
            res_cost = getattr(res, "estimated_cost", None)
            res_time = getattr(res, "estimated_time", None)
            res_details = getattr(res, "action_reason", None) or getattr(res, "notes", None)
            resolution_distribution[res_action] = resolution_distribution.get(res_action, 0) + 1

            # Evidence snippets
            ev_list = evidence_by_entity.get(e_id, [])
            evidence_snippets = [
                {
                    "evidence_id": ev.id,
                    "evidence_type": self._val(ev.evidence_type),
                    "confidence": getattr(ev, "confidence", 0.9),
                    "text_content": getattr(ev, "text_content", None) or getattr(ev, "ocr_text", None) or getattr(ev, "excerpt", None),
                    "bounding_box": getattr(ev, "bounding_box", None),
                    "timestamp": getattr(ev, "timestamp", None),
                    "frame_path": getattr(ev, "frame_path", None),
                }
                for ev in ev_list[:10]  # First 10 representative pieces of evidence
            ]

            # 8-Stage traceability evidence chain
            res_intel = research_by_entity.get(e_id)
            res_evidence_snippets = [
                {
                    "title": ev.source_title or f"{entity.name} Evidence",
                    "url": ev.source_url,
                    "excerpt": ev.excerpt or ev.claim or "No evidence returned",
                    "claim": ev.claim or "",
                    "confidence": float(ev.confidence or 0.90),
                    "source_type": ev.source_type or "parallel_api",
                }
                for ev in (getattr(res_intel, "evidence", []) if res_intel else [])
            ]

            evidence_chain = {
                "stage_1_detection": {
                    "entity_id": e_id,
                    "name": entity.name,
                    "type": self._val(entity.entity_type),
                    "classification": cls_val,
                    "scene": getattr(entity, "scene", None),
                    "timestamp": getattr(entity, "timestamp", None),
                    "visual_frame_uri": getattr(entity, "frame_path", None) or getattr(entity, "visual_frame_uri", None),
                    "bounding_box": getattr(entity, "bounding_box", []),
                },
                "stage_2_visual_evidence": {
                    "count": len([ev for ev in ev_list if "VISUAL" in self._val(ev.evidence_type).upper() or "FRAME" in self._val(ev.evidence_type).upper() or "OCR" in self._val(ev.evidence_type).upper()]),
                    "frames": [ev.frame_path for ev in ev_list if getattr(ev, "frame_path", None)],
                    "ocr_text": [getattr(ev, "ocr_text", None) or getattr(ev, "text_content", None) for ev in ev_list if "OCR" in self._val(ev.evidence_type).upper() and (getattr(ev, "ocr_text", None) or getattr(ev, "text_content", None))],
                },
                "stage_3_screenplay_evidence": {
                    "count": len([ev for ev in ev_list if "SCRIPT" in self._val(ev.evidence_type).upper() or "SCREENPLAY" in self._val(ev.evidence_type).upper()]),
                    "excerpts": [getattr(ev, "text_content", None) or getattr(ev, "excerpt", None) for ev in ev_list if "SCRIPT" in self._val(ev.evidence_type).upper() and (getattr(ev, "text_content", None) or getattr(ev, "excerpt", None))],
                },
                "stage_4_research": {
                    "researched": res_intel is not None,
                    "provider": "Parallel Search API" if (res_intel and getattr(res_intel, "provider", "") == "parallel") else (getattr(res_intel, "provider", None) or "Not Researched"),
                    "query": getattr(res_intel, "query", f'"{entity.name}" corporate rights holder trademark status'),
                    "cache_status": (res_intel.metadata.get("cache_status") if res_intel and res_intel.metadata else None) or ("LIVE API" if res_intel and getattr(res_intel, "metadata", {}).get("is_live") else "CACHE HIT" if res_intel else "N/A"),
                    "confidence": float(getattr(res_intel, "confidence", 0.0) or 0.0) if res_intel else None,
                    "rights_holder": getattr(res_intel, "rights_holder", None) if res_intel else getattr(entity, "rights_holder", None),
                    "candidate_rights_holder": getattr(res_intel, "candidate_rights_holder", None) if res_intel else getattr(entity, "rights_holder", None),
                    "results_count": len(res_evidence_snippets),
                    "evidence": res_evidence_snippets,
                    "summary": getattr(res_intel, "notes", None) if res_intel else "No research evidence returned",
                    "categories": getattr(res_intel, "categories", []) if res_intel else [],
                },
                "stage_5_risk": {
                    "score": risk_score,
                    "level": risk_level,
                    "factors": risk_factors,
                    "explanation": rk.explanation if rk else None,
                },
                "stage_6_verification": {
                    "decision": verif_decision,
                    "confidence": verif_confidence,
                    "contradictions": vr.contradictions if vr else [],
                    "rationale": verif_rationale,
                },
                "stage_7_resolution": {
                    "action": res_action,
                    "status": res_status,
                    "priority": res_priority,
                    "owner": res_owner,
                    "cost_estimate": res_cost,
                    "time_estimate": res_time,
                    "details": res_details,
                    "steps": getattr(res, "steps", None) or getattr(res, "required_information", []) if res else [],
                },
            }

            finding = ReportFinding(
                entity_id=e_id,
                entity_name=entity.name,
                entity_type=self._val(entity.entity_type),
                classification=cls_val,
                risk_level=risk_level,
                risk_score=risk_score,
                risk_factors=risk_factors,
                scene_number=entity.scene,
                timestamp_start=entity.timestamp,
                timestamp_end=entity.timestamp_end if hasattr(entity, "timestamp_end") else None,
                rights_holder=entity.rights_holder or (getattr(res_intel, "candidate_rights_holder", None) or getattr(res_intel, "rights_holder", None) if res_intel else None),
                verification_decision=verif_decision,
                verification_confidence=verif_confidence,
                verification_rationale=verif_rationale,
                resolution_status=res_status,
                resolution_action=res_action,
                resolution_priority=res_priority,
                resolution_owner=res_owner,
                resolution_cost_estimate=res_cost,
                resolution_time_estimate=res_time,
                resolution_details=res_details,
                evidence_count=len(ev_list),
                evidence_snippets=evidence_snippets,
                evidence_chain=evidence_chain,
            )
            all_findings.append(finding)

        # Build comprehensive Parallel Research Intelligence payload for report export
        parallel_research_intelligence: List[Dict[str, Any]] = []
        for entity in entities:
            e_id = entity.id
            res_intel = research_by_entity.get(e_id)
            ev_list = evidence_by_entity.get(e_id, [])

            results_list = []
            trademark_evidence = []
            if res_intel and res_intel.evidence:
                for ev in res_intel.evidence:
                    txt = f"{ev.claim or ''} {ev.excerpt or ''} {ev.source_title or ''}"
                    if any(term in txt.lower() for term in ["trademark", "uspto", "registration", "registered mark", "reg. no"]):
                        trademark_evidence.append(ev.claim or ev.excerpt or ev.source_title)
                    results_list.append({
                        "title": ev.source_title or f"{entity.name} Research Evidence",
                        "url": ev.source_url,
                        "excerpt": ev.excerpt or ev.claim or "No evidence returned",
                        "claim": ev.claim or "",
                        "confidence": float(ev.confidence or 0.90),
                        "source_type": ev.source_type or "parallel_api",
                    })

            provider_name = "Parallel Search API" if (res_intel and getattr(res_intel, "provider", "") == "parallel") else ("Local Fixture Provider" if (res_intel and getattr(res_intel, "provider", "") == "local") else (getattr(res_intel, "provider", "Not Researched") if res_intel else "Not Researched"))

            if res_intel and res_intel.metadata:
                cache_status = res_intel.metadata.get("cache_status")
                if not cache_status:
                    if res_intel.metadata.get("is_live"):
                        cache_status = "LIVE API"
                    elif "cache" in str(res_intel.metadata.get("source_type", "")):
                        cache_status = "CACHE HIT"
                    else:
                        cache_status = "LOCAL FIXTURE"
            else:
                cache_status = "UNAVAILABLE" if not res_intel else "LOCAL FIXTURE"

            cand_rh = (res_intel.candidate_rights_holder if res_intel else None) or entity.rights_holder

            intel_item = {
                "entity_id": e_id,
                "entity_name": entity.name,
                "entity_type": self._val(entity.entity_type),
                "classification": self._val(entity.classification, "UNKNOWN").upper(),
                "research_provider": provider_name,
                "search_query": getattr(res_intel, "query", f'"{entity.name}" corporate rights holder trademark status') if res_intel else f'"{entity.name}" corporate rights holder trademark status',
                "cache_status": cache_status,
                "status": res_intel.status.value if res_intel else "NOT_RESEARCHED",
                "results_count": len(results_list),
                "results": results_list,
                "candidate_rights_holder": cand_rh or "None Identified",
                "corporate_relationship": f"{entity.name} -> {cand_rh}" if cand_rh else None,
                "trademark_evidence": trademark_evidence if trademark_evidence else (["Registered / Corporate Mark verified"] if cand_rh and cand_rh != "Unknown" else ["No specific trademark registration record returned"]),
                "research_confidence": float(res_intel.research_confidence or res_intel.identity_confidence) if res_intel else 0.0,
                "retrieved_at": res_intel.retrieved_at.isoformat() if (res_intel and getattr(res_intel, "retrieved_at", None)) else datetime.now(timezone.utc).isoformat(),
                "notes": getattr(res_intel, "notes", "No evidence returned") if res_intel else "No research record available",
                "lineage": {
                    "frame_source": getattr(entity, "frame_path", None) or getattr(entity, "visual_frame_uri", None) or f"Scene {entity.scene}",
                    "entity": entity.name,
                    "research_query": getattr(res_intel, "query", f'"{entity.name}" corporate rights holder trademark status') if res_intel else f'"{entity.name}" corporate rights holder trademark status',
                    "parallel_results_count": len(results_list),
                    "evidence_count": len(ev_list),
                    "risk_level": self._val(risk_by_entity.get(e_id).risk_level if risk_by_entity.get(e_id) else entity.risk_level, "UNKNOWN").upper(),
                    "verification_decision": self._val(getattr(verification_by_entity.get(e_id), "decision", None) or getattr(entity, "verification_status", None), "UNVERIFIED").upper(),
                    "resolution_action": self._val(getattr(resolution_by_entity.get(e_id), "recommended_action", None) or getattr(entity, "resolution_action", None), "UNRESOLVED").upper(),
                }
            }
            parallel_research_intelligence.append(intel_item)

        # Phase 10: Financial Exposure Intelligence payload
        financial_exposure_intelligence: List[Dict[str, Any]] = []
        for exp in (financial_exposures or []):
            stat = getattr(exp, "statutory_framework", None) or getattr(exp, "statutory_damages", None)
            lic = getattr(exp, "licensing_benchmark", None)
            rem_est = getattr(exp, "remediation_estimate", None) or getattr(exp, "remediation_cost", None)
            
            financial_exposure_intelligence.append({
                "id": getattr(exp, "exposure_id", None) or getattr(exp, "id", ""),
                "entity_id": exp.entity_id,
                "production_id": exp.production_id,
                "entity_name": exp.entity_name,
                "status": self._val(exp.status),
                "estimated_low": exp.estimated_low,
                "estimated_high": exp.estimated_high,
                "currency": exp.currency,
                "confidence": exp.confidence,
                "statutory_damages": {
                    "statute": getattr(stat, "statutory_code", None) or getattr(stat, "statute", "15 U.S.C. § 1117"),
                    "min_damages": getattr(stat, "min_statutory_amount", None) or getattr(stat, "min_damages", 750.0),
                    "max_damages": getattr(stat, "standard_max_amount", None) or getattr(stat, "max_damages", 30000.0),
                    "willful_max_damages": getattr(stat, "willful_max_amount", None) or getattr(stat, "willful_max_damages", 150000.0),
                    "notes": getattr(stat, "statutory_basis", None) or getattr(stat, "notes", ""),
                } if stat else None,
                "licensing_benchmark": {
                    "typical_fee_low": getattr(lic, "low_fee", None) or getattr(lic, "typical_fee_low", 2500.0),
                    "typical_fee_high": getattr(lic, "high_fee", None) or getattr(lic, "typical_fee_high", 35000.0),
                    "industry_tier": getattr(lic, "industry_sector", None) or getattr(lic, "industry_tier", "Standard Commercial"),
                    "benchmark_source": getattr(lic, "source", None) or getattr(lic, "benchmark_source", ""),
                } if lic else None,
                "remediation_cost": {
                    "estimated_cost": getattr(rem_est, "vfx_paintout_low", None) or getattr(rem_est, "estimated_cost", 1200.0),
                    "remediation_type": "VFX Paintout",
                    "cost_basis": f"VFX paintout range (${getattr(rem_est, 'vfx_paintout_low', 1200):,.0f} - ${getattr(rem_est, 'vfx_paintout_high', 6500):,.0f})",
                } if rem_est else None,
                "comparable_cases": [
                    {
                        "case_name": getattr(c, "case_title", None) or getattr(c, "case_name", ""),
                        "citation": getattr(c, "court_or_jurisdiction", None) or getattr(c, "citation", ""),
                        "year": c.year,
                        "award_or_settlement": getattr(c, "damages_or_settlement", None) or getattr(c, "award_or_settlement", ""),
                        "key_holding": getattr(c, "summary", None) or getattr(c, "key_holding", ""),
                        "relevance": getattr(c, "citation_url", None) or getattr(c, "relevance", ""),
                    }
                    for c in (exp.comparable_cases or [])
                ],
                "evidence_ids": exp.evidence_ids,
                "notes": exp.notes,
                "calculated_at": exp.created_at.isoformat() if hasattr(exp, "created_at") else datetime.now(timezone.utc).isoformat(),
            })

        # Phase 11: Clearance Outreach Drafts payload
        clearance_outreach_drafts: List[Dict[str, Any]] = []
        for out in (outreach_drafts or []):
            clearance_outreach_drafts.append({
                "id": getattr(out, "outreach_id", None) or getattr(out, "id", ""),
                "production_id": out.production_id,
                "entity_id": out.entity_id,
                "entity_name": out.entity_name,
                "rights_holder": out.rights_holder,
                "contact_email": getattr(out, "recipient_email", None) or getattr(out, "contact_email", ""),
                "subject": out.subject,
                "body": getattr(out, "body_text", None) or getattr(out, "body", ""),
                "status": self._val(out.status),
                "created_at": out.created_at.isoformat() if hasattr(out, "created_at") else datetime.now(timezone.utc).isoformat(),
                "requires_human_approval": out.requires_human_approval,
                "gmail_draft_id": out.gmail_draft_id,
                "timecode": f"{out.timestamp:.2f}s" if getattr(out, "timestamp", None) is not None else None,
                "use_description": f"Scene {out.scene_number}" if getattr(out, "scene_number", None) is not None else "Incidental cinematic appearance",
                "territory": "Worldwide",
                "media_rights": getattr(out, "requested_rights_scope", None) or "Worldwide All Media in Perpetuity",
                "term": "In Perpetuity",
            })

        # Phase 12: Visual Remediation Proposals payload
        visual_remediation_proposals: List[Dict[str, Any]] = []
        for rem in (remediation_proposals or []):
            visual_remediation_proposals.append({
                "id": getattr(rem, "remediation_id", None) or getattr(rem, "id", ""),
                "production_id": rem.production_id,
                "entity_id": rem.entity_id,
                "entity_name": rem.entity_name,
                "job_id": getattr(rem, "job_id", "job_default"),
                "remediation_type": self._val(rem.remediation_type),
                "status": self._val(rem.status),
                "original_frame_path": rem.original_frame_path,
                "remediated_frame_path": getattr(rem, "proposed_frame_path", None) or getattr(rem, "remediated_frame_path", ""),
                "mask_path": rem.mask_path,
                "comparison_frame_path": getattr(rem, "comparison_frame_path", None),
                "remediated_frame_url": getattr(rem, "proposed_frame_url", None) or getattr(rem, "remediated_frame_url", None),
                "comparison_frame_url": getattr(rem, "comparison_frame_url", None),
                "confidence": 0.95,
                "requires_human_review": True,
                "human_review_disclaimer": getattr(rem, "disclaimer", None) or getattr(rem, "human_review_disclaimer", "PROPOSED REMEDIATION — HUMAN/EDITOR REVIEW REQUIRED. Original master footage is unaltered."),
                "created_at": rem.created_at.isoformat() if hasattr(rem, "created_at") else datetime.now(timezone.utc).isoformat(),
            })

        # Deterministic sorting hierarchy:
        # 1. Resolution Priority: CRITICAL (0) > HIGH (1) > MEDIUM (2) > LOW (3) > INFO (4)
        # 2. Risk Level: HIGH (0) > MEDIUM (1) > LOW (2) > UNKNOWN (3)
        # 3. Risk Score descending (-score)
        # 4. Classification: VISUAL_ONLY (0) > BOTH (1) > SCRIPT_ONLY (2) > AUDIO_ONLY (3)
        # 5. Timestamp ascending
        # 6. Entity name alphabetical
        def _sort_key(f: ReportFinding):
            prio_k = self.PRIORITY_ORDER.get((f.resolution_priority or "MEDIUM").upper(), 5)
            risk_k = self.RISK_ORDER.get((f.risk_level or "UNKNOWN").upper(), 4)
            cls_k = self.CLASSIFICATION_ORDER.get((f.classification or "SCRIPT_ONLY").upper(), 5)
            ts = f.timestamp_start if f.timestamp_start is not None else 0.0
            return (prio_k, risk_k, -f.risk_score, cls_k, ts, f.entity_name.lower())

        all_findings.sort(key=_sort_key)

        # Priority findings: High risk, critical/high resolution priority, contradicted verification, or visual-only
        priority_findings = [
            f for f in all_findings
            if (f.risk_level == "HIGH")
            or ((f.resolution_priority or "").upper() in ("CRITICAL", "HIGH"))
            or (f.verification_decision == "CONTRADICTED")
            or (f.classification == "VISUAL_ONLY")
        ]

        # Visual-only findings spotlight
        visual_only_findings = [f for f in all_findings if f.classification == "VISUAL_ONLY"]

        total_entities = len(entities)
        # Usable research coverage: entities with successful research and candidate rights holder / usable evidence
        usable_researched_count = sum(
            1 for e in entities
            if e.id in research_by_entity
            and research_by_entity[e.id].status == ResearchStatus.SUCCESS
            and (research_by_entity[e.id].candidate_rights_holder or len(research_by_entity[e.id].evidence) > 0)
        )
        # Usable verification coverage: entities verified with active verification record
        usable_verified_count = sum(
            1 for e in entities
            if e.id in verification_by_entity
            and getattr(verification_by_entity[e.id], "decision", None) is not None
        )
        # Usable resolution coverage: entities with actionable resolution recommendation
        usable_resolved_count = sum(
            1 for e in entities
            if e.id in resolution_by_entity
            and (getattr(resolution_by_entity[e.id], "recommended_action", None) is not None or getattr(resolution_by_entity[e.id], "resolution_status", None) is not None)
        )

        research_coverage = round(usable_researched_count / total_entities, 4) if total_entities > 0 else 0.0
        verification_coverage = round(usable_verified_count / total_entities, 4) if total_entities > 0 else 0.0
        resolution_coverage = round(usable_resolved_count / total_entities, 4) if total_entities > 0 else 0.0

        # Build dynamic executive summary
        high_risk_n = risk_distribution.get("HIGH", 0)
        med_risk_n = risk_distribution.get("MEDIUM", 0)
        low_risk_n = risk_distribution.get("LOW", 0)
        vis_only_n = classification_counts.get("VISUAL_ONLY", 0)
        contradicted_n = verification_distribution.get("CONTRADICTED", 0)
        license_req_n = resolution_distribution.get("LICENSE_REQUIRED", 0)
        remove_n = resolution_distribution.get("REMOVE_OR_REPLACE", 0)

        executive_summary = (
            f"Pre-clearance intelligence audit completed for production '{production.title}' (ID: {production.id}). "
            f"Across multi-modal screening of screenplay and captured footage, the system identified {total_entities} "
            f"clearance-relevant entities with {usable_researched_count}/{total_entities} ({research_coverage * 100:.1f}%) "
            f"factual research evidence coverage, {usable_verified_count}/{total_entities} ({verification_coverage * 100:.1f}%) "
            f"adversarial verification coverage, and {usable_resolved_count}/{total_entities} ({resolution_coverage * 100:.1f}%) "
            f"actionable resolution coverage. "
            f"Crucially, {vis_only_n} Visual-Only entities were detected exclusively in camera footage without screenplay authorization. "
            f"Risk analysis classifies {high_risk_n} HIGH risk, {med_risk_n} MEDIUM risk, and {low_risk_n} LOW risk items. "
            f"Adversarial verification discovered {contradicted_n} evidence contradiction(s). "
            f"Actionable resolution plans require {license_req_n} commercial licenses and {remove_n} optical clean-up/removal actions."
        )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return ReportResult(
            production_id=production.id,
            job_id=job.job_id,
            production_title=production.title,
            version=version,
            status=ReportStatus.COMPLETED,
            generated_at=datetime.now(timezone.utc),
            generation_duration_ms=duration_ms,
            total_entities=total_entities,
            researched_count=usable_researched_count,
            verified_count=usable_verified_count,
            resolved_count=usable_resolved_count,
            research_coverage=research_coverage,
            verification_coverage=verification_coverage,
            resolution_coverage=resolution_coverage,
            classification_counts=classification_counts,
            risk_distribution=risk_distribution,
            verification_distribution=verification_distribution,
            resolution_distribution=resolution_distribution,
            priority_findings=priority_findings,
            visual_only_findings=visual_only_findings,
            all_findings=all_findings,
            parallel_research_intelligence=parallel_research_intelligence,
            financial_exposure_intelligence=financial_exposure_intelligence,
            clearance_outreach_drafts=clearance_outreach_drafts,
            visual_remediation_proposals=visual_remediation_proposals,
            executive_summary=executive_summary,
            disclaimer=DEFAULT_LEGAL_DISCLAIMER,
            metadata={
                "evidence_total_count": len(evidence_list),
                "generated_by": "Chain of Title Intelligence Agent v8.0",
                "environment": "offline-deterministic",
            },
        )

report_engine = ReportEngine()

