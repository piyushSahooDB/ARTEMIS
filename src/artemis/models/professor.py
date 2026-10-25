"""Professor models representing discovered academic researchers."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from artemis.models.common import SourceProvenance, VerificationStatus, utc_now
from artemis.utils.ids import generate_id


class Professor(BaseModel):
    """Academic researcher or faculty member discovered during scouting."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        default_factory=lambda: generate_id("prof"),
        description="Unique identifier for the professor.",
    )
    name: str = Field(
        ...,
        description="Full name of the professor or researcher.",
    )
    title: Optional[str] = Field(
        default=None,
        description="Academic title (e.g., 'Associate Professor').",
    )
    department: Optional[str] = Field(
        default=None,
        description="Department or school within the institution.",
    )
    institution: str = Field(
        ...,
        description="University or research institution name.",
    )
    email: Optional[str] = Field(
        default=None,
        description="Official contact email. Must never be fabricated; leave None if unconfirmed.",
    )
    email_status: VerificationStatus = Field(
        default=VerificationStatus.UNVERIFIED,
        description="Verification state of the email address.",
    )
    profile_url: Optional[str] = Field(
        default=None,
        description="URL to the official faculty profile page.",
    )
    lab_url: Optional[str] = Field(
        default=None,
        description="URL to the professor's research lab or group homepage.",
    )
    scholar_url: Optional[str] = Field(
        default=None,
        description="URL to the professor's Google Scholar profile.",
    )
    research_interests: list[str] = Field(
        default_factory=list,
        description="List of stated research areas or keywords.",
    )
    sources: list[SourceProvenance] = Field(
        default_factory=list,
        description="Ground-truth sources validating this professor's information.",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description="Record creation timestamp.",
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        description="Record last updated timestamp.",
    )

    @field_validator("name", "institution")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace only.")
        return stripped

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            return None
        if "@" not in stripped or "." not in stripped.split("@")[-1]:
            raise ValueError(f"Invalid email address format: '{v}'")
        return stripped
