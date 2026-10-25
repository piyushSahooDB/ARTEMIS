"""Common enums, provenance records, and base models for ARTEMIS."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class VerificationStatus(str, Enum):
    """Status indicating how trustworthy a field or entity record is.

    - VERIFIED: Directly confirmed from an official or authoritative source.
    - UNVERIFIED: Extracted or scraped but not yet verified against ground truth.
    - INFERRED: Synthesized or derived via heuristic or pattern match.
    - DISPUTED: Found conflicting information across different sources.
    """

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    INFERRED = "inferred"
    DISPUTED = "disputed"


class SourceProvenance(BaseModel):
    """Provenance record tracking the origin and ground truth evidence for data."""

    model_config = ConfigDict(extra="forbid")

    source_url: str = Field(
        ...,
        description="URL of the official page or public API where data was sourced.",
    )
    source_name: str = Field(
        ...,
        description="Name of source, e.g., 'faculty_page', 'openalex', 'arxiv', 'crossref'.",
    )
    extracted_at: datetime = Field(
        default_factory=utc_now,
        description="Timestamp when the data was extracted or verified.",
    )
    snippet: Optional[str] = Field(
        default=None,
        description="Raw snippet or fact from source supporting the data (prevents hallucination).",
    )
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.UNVERIFIED,
        description="Trustworthiness of this provenance entry.",
    )
