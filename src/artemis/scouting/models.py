"""Models supporting academic paper scouting, author identity matching, and ranking."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from artemis.models.common import VerificationStatus
from artemis.models.paper import Paper


class AuthorMatch(BaseModel):
    """Author identity verification and institutional affiliation evidence."""

    model_config = ConfigDict(extra="forbid")

    author_name: str
    affiliations: list[str] = Field(default_factory=list)
    is_institution_matched: bool = False
    confidence: float = Field(default=0.4, ge=0.0, le=1.0)
    status: VerificationStatus = Field(default=VerificationStatus.UNVERIFIED)
    notes: str = Field(default="Name-only match; institutional affiliation not verified in metadata.")


class ScoutedPaper(BaseModel):
    """Academic paper with computed relevance, recency, and author match confidence."""

    model_config = ConfigDict(extra="forbid")

    paper: Paper
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    recency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    citation_score: float = Field(default=0.0, ge=0.0, le=1.0)
    composite_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    author_match: AuthorMatch
    matched_keywords: list[str] = Field(default_factory=list)
