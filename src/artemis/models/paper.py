"""Paper models representing academic publications discovered across sources."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from artemis.models.common import SourceProvenance, utc_now
from artemis.utils.ids import generate_id


class Paper(BaseModel):
    """Academic paper or preprint discovered from OpenAlex, arXiv, Crossref, etc."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        default_factory=lambda: generate_id("paper"),
        description="Unique identifier for the paper.",
    )
    title: str = Field(
        ...,
        description="Title of the research paper.",
    )
    abstract: Optional[str] = Field(
        default=None,
        description="Abstract of the research paper.",
    )
    published_date: Optional[str] = Field(
        default=None,
        description="Publication date (YYYY, YYYY-MM, or YYYY-MM-DD).",
    )
    year: Optional[int] = Field(
        default=None,
        description="Publication year.",
    )
    venue: Optional[str] = Field(
        default=None,
        description="Journal, conference, or repository where paper appeared.",
    )
    doi: Optional[str] = Field(
        default=None,
        description="Digital Object Identifier (e.g. 10.1145/...).",
    )
    arxiv_id: Optional[str] = Field(
        default=None,
        description="arXiv identifier (e.g. 2301.12345).",
    )
    openalex_id: Optional[str] = Field(
        default=None,
        description="OpenAlex work ID (e.g. W1234567890).",
    )
    url: Optional[str] = Field(
        default=None,
        description="Primary landing URL or repository entry for the publication.",
    )
    pdf_url: Optional[str] = Field(
        default=None,
        description="Direct link to open-access PDF if available.",
    )
    citation_count: Optional[int] = Field(
        default=None,
        description="Estimated citation count from source index.",
    )
    author_names: list[str] = Field(
        default_factory=list,
        description="List of author names associated with this publication.",
    )
    sources: list[SourceProvenance] = Field(
        default_factory=list,
        description="Ground-truth sources validating this paper.",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description="Record creation timestamp.",
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        description="Record last updated timestamp.",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Paper title must not be empty.")
        return stripped

    @field_validator("citation_count")
    @classmethod
    def validate_citation_count(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Citation count must be non-negative.")
        return v
