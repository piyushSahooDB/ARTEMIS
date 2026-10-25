"""Research brief models bridging professor publications and student qualifications."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from artemis.models.common import SourceProvenance, utc_now
from artemis.utils.ids import generate_id


class ResearchBrief(BaseModel):
    """Structured synthesis of a professor's research and its alignment to student evidence."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        default_factory=lambda: generate_id("brief"),
        description="Unique identifier for the research brief.",
    )
    professor_id: str = Field(
        ...,
        description="ID of the professor this brief is prepared for.",
    )
    paper_id: Optional[str] = Field(
        default=None,
        description="ID of the specific paper analyzed, if applicable.",
    )
    headline: str = Field(
        ...,
        description="High-level topic or title of the brief.",
    )
    summary: str = Field(
        ...,
        description="Accessible, accurate summary of the research questions and findings.",
    )
    core_contributions: list[str] = Field(
        default_factory=list,
        description="Verified technical contributions extracted from the publication.",
    )
    methodology: Optional[str] = Field(
        default=None,
        description="Experimental setup, datasets, or theoretical techniques used.",
    )
    potential_alignment: str = Field(
        ...,
        description="Explicit reasoning linking student evidence to the professor's agenda.",
    )
    matched_evidence_ids: list[str] = Field(
        default_factory=list,
        description="List of ResumeEvidence IDs that factually support this alignment.",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Identified or stated limitations of the research paper.",
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="Explicit gaps where student background does not meet paper prerequisites.",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Thoughtful research inquiries or extension ideas to raise in dialogue.",
    )
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0 to 1.0) indicating match and factual certainty.",
    )
    confidence_notes: Optional[str] = Field(
        default=None,
        description="Explicit note distinguishing verified facts from uncertain hypotheses.",
    )
    sources: list[SourceProvenance] = Field(
        default_factory=list,
        description="Ground-truth sources backing up claims in this brief.",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description="Record creation timestamp.",
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        description="Record last updated timestamp.",
    )

    @field_validator("professor_id", "headline", "summary", "potential_alignment")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field must not be empty.")
        return stripped
