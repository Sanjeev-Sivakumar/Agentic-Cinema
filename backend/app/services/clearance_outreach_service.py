"""
Clearance Outreach Service (Phase 11).
Generates formal entertainment industry rights clearance request letters
customized to the specific entity, verified rights holder, scene timestamp,
duration, and worldwide distribution scope.
Uses Gemini LLM or high-fidelity legal template engine.
"""
from datetime import datetime, timezone
import os
import re
from typing import Any, Dict, List, Optional
import uuid

from app.core.config import settings
from app.core.logging import logger
from app.models.entity import Entity, EntityClassification, EntityType
from app.models.outreach import ClearanceOutreachDraft, OutreachStatus
from app.models.research import ResearchResult
from app.models.resolution import ResolutionResult
from app.services.gmail_service import gmail_service


class ClearanceOutreachService:
    """
    Service for generating tailored clearance permission request packages.
    """

    def __init__(self):
        self.gemini_api_key = (
            getattr(settings, "GEMINI_API_KEY", "")
            or os.getenv("GEMINI_API_KEY", "")
            or os.getenv("GOOGLE_API_KEY", "")
        ).strip()

    def _generate_template_draft(
        self,
        entity_name: str,
        rights_holder: str,
        production_title: str,
        scene_number: Optional[int],
        timestamp: Optional[float],
        duration_sec: Optional[float],
        entity_type: str,
        rights_scope: str,
    ) -> Dict[str, str]:
        """Deterministic entertainment legal clearance letter generator."""
        time_str = f"at timecode {timestamp:.2f}s" if timestamp is not None else "in principal photography"
        scene_str = f"Scene {scene_number}" if scene_number is not None else "the feature production"
        dur_str = f"approximately {duration_sec:.1f} seconds" if duration_sec else "brief incidental exposure"

        subject = f"Clearance Permission Request: '{entity_name}' in Feature Production '{production_title}'"

        body_text = f"""ATTENTION: Legal & Clearance / Licensing Department
RE: {rights_holder} — Request for Permission & Display Clearance

Dear Rights Holder Licensing Representative,

We are writing on behalf of the production team for the feature project titled '{production_title}'.

During the production and post-production review of our project, an appearance of '{entity_name}' was identified in {scene_str} ({time_str}, {dur_str}). The usage context is non-derogatory, incidental, and integral to the realistic cinematic environment of the scene.

To ensure comprehensive chain-of-title integrity and avoid any distribution impediments, we hereby formally request your non-exclusive permission to include the visual/audio depiction of '{entity_name}' in the final cut of '{production_title}'.

Requested Clearance Terms:
1. Permitted Asset: Visual / Contextual depiction of '{entity_name}'
2. Production Title: '{production_title}'
3. Rights Scope: {rights_scope}
4. Exclusivity: Non-exclusive
5. Commercial Terms: Standard non-derogatory theatrical, streaming, and home entertainment broadcast

Please let us know your standard licensing procedure or if you require an official clearance execution agreement. We appreciate your prompt assistance in facilitating this clearance.

Sincerely,

Production Clearance & Legal Affairs Department
Chain of Title Clearance Intelligence Cockpit
Email: clearance-desk@agenticcinema.com
"""

        body_html = f"""<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #111827; max-width: 650px;">
  <p><strong>ATTENTION:</strong> Legal &amp; Clearance / Licensing Department<br>
  <strong>RE:</strong> {rights_holder} &mdash; Request for Permission &amp; Display Clearance</p>

  <p>Dear Rights Holder Licensing Representative,</p>

  <p>We are writing on behalf of the production team for the feature project titled <strong>&lsquo;{production_title}&rsquo;</strong>.</p>

  <p>During the post-production review of our project, an appearance of <strong>&lsquo;{entity_name}&rsquo;</strong> was identified in <em>{scene_str}</em> ({time_str}, {dur_str}). The usage context is non-derogatory, incidental, and integral to the realistic cinematic environment of the scene.</p>

  <div style="background: #f3f4f6; border-left: 4px solid #3b82f6; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
    <h4 style="margin: 0 0 8px 0; color: #1e3a8a;">Requested Clearance Terms:</h4>
    <ul style="margin: 0; padding-left: 20px;">
      <li><strong>Permitted Asset:</strong> Visual / Contextual depiction of &lsquo;{entity_name}&rsquo;</li>
      <li><strong>Production Title:</strong> &lsquo;{production_title}&rsquo;</li>
      <li><strong>Rights Scope:</strong> {rights_scope}</li>
      <li><strong>Exclusivity:</strong> Non-exclusive</li>
      <li><strong>Commercial Terms:</strong> Standard non-derogatory theatrical, streaming, and broadcast inclusion</li>
    </ul>
  </div>

  <p>Please let us know your standard licensing procedure or if you require our formal clearance agreement counter-signed. We appreciate your prompt assistance.</p>

  <p>Sincerely,<br>
  <strong>Production Clearance &amp; Legal Affairs</strong><br>
  <span style="color: #6b7280; font-size: 13px;">Chain of Title Clearance Intelligence Cockpit &bull; clearance-desk@agenticcinema.com</span></p>
</div>"""

        return {"subject": subject, "body_text": body_text, "body_html": body_html}

    async def generate_outreach_draft(
        self,
        entity: Entity,
        research: Optional[ResearchResult] = None,
        resolution: Optional[ResolutionResult] = None,
        production_title: str = "Demo Feature: Clearance Benchmark",
        create_gmail_draft: bool = True,
    ) -> ClearanceOutreachDraft:
        """
        Generates a tailored clearance outreach draft and registers a DRAFT in Gmail.
        """
        clean_name = (entity.name or "").strip()
        rights_holder = (
            (research.candidate_rights_holder if research else None)
            or getattr(entity, "rights_holder", None)
            or f"{clean_name} Legal Affairs"
        )
        entity_type_str = entity.entity_type.value if hasattr(entity.entity_type, "value") else str(entity.entity_type)
        scene_num = entity.scene
        timestamp = entity.timestamp
        duration = getattr(entity, "duration", None)
        rights_scope = "Worldwide, Theatrical, VOD, Streaming & All Media in Perpetuity"

        # Attempt to derive a plausible clearance email from rights holder
        clean_domain = re.sub(r"[^a-zA-Z0-9]", "", rights_holder.split()[0].lower())
        recipient_email = f"clearance@{clean_domain}.com"

        # Generate draft content
        draft_content = self._generate_template_draft(
            entity_name=clean_name,
            rights_holder=rights_holder,
            production_title=production_title,
            scene_number=scene_num,
            timestamp=timestamp,
            duration_sec=duration,
            entity_type=entity_type_str,
            rights_scope=rights_scope,
        )

        outreach_id = f"out_{uuid.uuid4().hex[:10]}"

        # Create draft via GmailService (DRAFT ONLY)
        gmail_draft_id = None
        if create_gmail_draft:
            try:
                g_res = await gmail_service.create_draft(
                    to_email=recipient_email,
                    subject=draft_content["subject"],
                    body_text=draft_content["body_text"],
                    body_html=draft_content["body_html"],
                    outreach_id=outreach_id,
                    production_title=production_title,
                )
                gmail_draft_id = g_res.get("draft_id")
            except Exception as e:
                logger.warning(f"[ClearanceOutreachService] Failed to create Gmail draft: {e}")

        evidence_ids = []
        if research and research.evidence:
            evidence_ids = [ev.id for ev in research.evidence if getattr(ev, "id", None)]

        draft = ClearanceOutreachDraft(
            outreach_id=outreach_id,
            entity_id=entity.id,
            production_id=entity.production_id,
            entity_name=clean_name,
            rights_holder=rights_holder,
            recipient_email=recipient_email,
            subject=draft_content["subject"],
            body_text=draft_content["body_text"],
            body_html=draft_content["body_html"],
            scene_number=scene_num,
            timestamp=timestamp,
            exposure_duration_sec=duration,
            requested_rights_scope=rights_scope,
            status=OutreachStatus.DRAFTED,
            requires_human_approval=True,
            gmail_draft_id=gmail_draft_id,
            evidence_ids=evidence_ids,
            notes="Formal clearance permission letter drafted. Pending legal / production supervisor approval before dispatch.",
        )

        logger.info(
            f"[ClearanceOutreachService] Generated clearance outreach draft '{draft.outreach_id}' "
            f"for '{clean_name}' -> Rights Holder: '{rights_holder}' (Status: DRAFTED)"
        )
        return draft


clearance_outreach_service = ClearanceOutreachService()
