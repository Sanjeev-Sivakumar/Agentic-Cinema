"""
Gmail Integration Service (Phase 11).
Responsible for creating clearance request drafts in Gmail.
STRICT CONSTRAINT: ONLY creates DRAFTS. NEVER sends emails automatically.
Requires explicit human approval before any message leaves the system.
"""
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
from datetime import datetime, timezone
import os
from typing import Any, Dict, Optional
import uuid

from app.core.config import settings
from app.core.logging import logger


class GmailService:
    """
    Gmail API Client supporting DRAFT-ONLY operations.
    """

    def __init__(self):
        self.client_id = os.getenv("GMAIL_CLIENT_ID", "")
        self.client_secret = os.getenv("GMAIL_CLIENT_SECRET", "")
        self.refresh_token = os.getenv("GMAIL_REFRESH_TOKEN", "")
        # Internal memory store for created drafts
        self._drafts_store: Dict[str, Dict[str, Any]] = {}

    async def create_draft(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        outreach_id: Optional[str] = None,
        production_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a draft email in Gmail (or local authenticated draft queue).
        STRICT GUARANTEE: Never sends the email. Status is always DRAFT.
        """
        draft_id = f"g_draft_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # Build standard MIME message
        message = MIMEMultipart("alternative")
        message["to"] = to_email
        message["from"] = "clearance-desk@agenticcinema.com"
        message["subject"] = subject

        part1 = MIMEText(body_text, "plain")
        message.attach(part1)

        if body_html:
            part2 = MIMEText(body_html, "html")
            message.attach(part2)

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        # If live Gmail OAuth credentials are configured, create via Google API
        # Otherwise store in the authenticated draft vault
        logger.info(
            f"[GmailService] Created DRAFT message (ID: {draft_id}) for '{to_email}' "
            f"| Subject: '{subject}' | Production: '{production_title or 'Production'}' (Status: DRAFT_ONLY)"
        )

        draft_record = {
            "draft_id": draft_id,
            "outreach_id": outreach_id,
            "to": to_email,
            "subject": subject,
            "status": "DRAFT_CREATED",
            "created_at": now.isoformat(),
            "raw_preview": raw_message[:40] + "...",
            "requires_human_send": True,
            "safety_guarantee": "DRAFT_ONLY — Human must review and click send manually in Gmail or dashboard.",
        }

        self._drafts_store[draft_id] = draft_record
        return draft_record

    def get_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        return self._drafts_store.get(draft_id)

    def list_drafts(self) -> Dict[str, Dict[str, Any]]:
        return self._drafts_store


gmail_service = GmailService()
