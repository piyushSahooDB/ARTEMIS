"""Email draft models managing personalized outreach drafts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from artemis.models.common import utc_now
from artemis.utils.ids import generate_id


class EmailDraftStatus(str, Enum):
    """Lifecycle status of an outreach draft.

    Under ARTEMIS safety rules, drafts are ONLY created or synced to Gmail as drafts,
    never sent automatically.
    """

    DRAFT_PENDING = "draft_pending"
    SYNCED_TO_GMAIL = "synced_to_gmail"
    NEEDS_REVIEW = "needs_review"
    DISCARDED = "discarded"


class EmailDraft(BaseModel):
    """Personalized email draft targeting a specific professor."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        default_factory=lambda: generate_id("draft"),
        description="Unique identifier for the email draft.",
    )
    professor_id: str = Field(
        ...,
        description="ID of the professor to whom this draft is addressed.",
    )
    brief_id: Optional[str] = Field(
        default=None,
        description="ID of the ResearchBrief grounding this draft, if applicable.",
    )
    recipient_email: str = Field(
        ...,
        description="Verified contact email address for the professor.",
    )
    recipient_name: str = Field(
        ...,
        description="Name of the recipient as addressed.",
    )
    subject: str = Field(
        ...,
        description="Email subject line.",
    )
    body: str = Field(
        ...,
        description="Email body text.",
    )
    rationale: Optional[str] = Field(
        default=None,
        description="Explanation of why this angle and evidence were chosen.",
    )
    status: EmailDraftStatus = Field(
        default=EmailDraftStatus.DRAFT_PENDING,
        description="Current draft status in ARTEMIS.",
    )
    gmail_draft_id: Optional[str] = Field(
        default=None,
        description="Remote draft ID in Gmail once synchronized via OAuth API.",
    )
    verification_notes: Optional[str] = Field(
        default=None,
        description="Safety audit notes verifying email validity and fact alignment.",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description="Record creation timestamp.",
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        description="Record last updated timestamp.",
    )

    @field_validator("recipient_email")
    @classmethod
    def validate_recipient_email(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Recipient email must not be empty.")
        if "@" not in stripped or "." not in stripped.split("@")[-1]:
            raise ValueError(f"Invalid email address: '{v}'")
        return stripped

    @field_validator("recipient_name", "subject", "body")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty.")
        return stripped
