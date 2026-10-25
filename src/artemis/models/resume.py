"""Resume evidence models capturing student skills, projects, and achievements."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from artemis.models.common import VerificationStatus, utc_now
from artemis.utils.ids import generate_id


class EvidenceCategory(str, Enum):
    """Categorization of verified student résumé experiences."""

    PROJECT = "project"
    WORK_EXPERIENCE = "work_experience"
    RESEARCH_EXPERIENCE = "research_experience"
    COURSEWORK = "coursework"
    PUBLICATION = "publication"
    TECHNICAL_SKILL = "technical_skill"


class ResumeEvidence(BaseModel):
    """Specific verifiable qualification or project extracted from student's résumé.

    Used by the matching engine to ensure outreach emails only reference
    authentic student qualifications and never fabricate background.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        default_factory=lambda: generate_id("evid"),
        description="Unique identifier for this résumé evidence item.",
    )
    category: EvidenceCategory = Field(
        default=EvidenceCategory.PROJECT,
        description="Type of experience or qualification.",
    )
    title: str = Field(
        ...,
        description="Title of project, role, coursework, or skill group.",
    )
    description: str = Field(
        ...,
        description="Concrete description of what was built or researched.",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="Keywords, technologies, methods, or domains demonstrated.",
    )
    key_achievements: list[str] = Field(
        default_factory=list,
        description="Measurable outcomes, contributions, or technical highlights.",
    )
    source_reference: Optional[str] = Field(
        default=None,
        description="Provenance in résumé (e.g., 'Résumé page 1 / Projects' or repository URL).",
    )
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.UNVERIFIED,
        description="Verification state of this claim (unverified until verified/reviewed).",
    )
    raw_snippet: Optional[str] = Field(
        default=None,
        description="Exact raw text snippet from the résumé supporting this claim.",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description="Record creation timestamp.",
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        description="Record last updated timestamp.",
    )

    @field_validator("title", "description")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty.")
        return stripped
