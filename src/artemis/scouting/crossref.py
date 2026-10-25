"""Crossref API client for DOI metadata resolution and publisher enrichment."""

from __future__ import annotations

import re
from typing import Any

from artemis.crawler.client import PoliteHttpClient
from artemis.models.common import SourceProvenance, VerificationStatus
from artemis.models.paper import Paper
from artemis.scouting.models import AuthorMatch
from artemis.scouting.openalex import check_institution_affiliation, clean_doi

CROSSREF_WORKS_URL = "https://api.crossref.org/works"


class CrossrefClient:
    """Client for resolving authoritative DOI metadata from Crossref."""

    def __init__(self, client: PoliteHttpClient | None = None) -> None:
        self.client = client or PoliteHttpClient()

    def resolve_doi(self, doi: str) -> dict[str, Any] | None:
        """Fetch metadata for a given DOI from Crossref."""
        canonical = clean_doi(doi)
        if not canonical:
            return None

        url = f"{CROSSREF_WORKS_URL}/{canonical}"
        try:
            response = self.client.get(url)
            data = response.json()
            return data.get("message")
        except Exception:
            return None

    def enrich_paper(
        self,
        paper: Paper,
        target_author: str,
        target_institution: str | None,
    ) -> tuple[Paper, AuthorMatch | None]:
        """Enrich a paper with Crossref publisher metadata if DOI exists."""
        if not paper.doi:
            return paper, None

        msg = self.resolve_doi(paper.doi)
        if not msg:
            return paper, None

        # 1. Update missing title or venue
        if not paper.venue:
            container = msg.get("container-title")
            if container and isinstance(container, list) and container[0]:
                paper.venue = container[0]

        # 2. Update publication year/date if missing
        if not paper.year:
            published_print = msg.get("published-print") or msg.get("published-online") or msg.get("created")
            if published_print and "date-parts" in published_print:
                parts = published_print["date-parts"][0]
                if parts:
                    paper.year = int(parts[0])
                    if len(parts) >= 3:
                        paper.published_date = f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"

        # 3. Check author affiliations from Crossref
        authors = msg.get("author", [])
        affiliations: list[str] = []
        target_norm = target_author.lower()

        for a in authors:
            given = a.get("given", "")
            family = a.get("family", "")
            full = f"{given} {family}".strip()
            if target_norm in full.lower():
                for aff in a.get("affiliation", []):
                    name = aff.get("name")
                    if name:
                        affiliations.append(name)

        author_match: AuthorMatch | None = None
        if affiliations and target_institution:
            is_matched = check_institution_affiliation(affiliations, target_institution)
            if is_matched:
                author_match = AuthorMatch(
                    author_name=target_author,
                    affiliations=affiliations,
                    is_institution_matched=True,
                    confidence=1.0,
                    status=VerificationStatus.VERIFIED,
                    notes=f"Crossref confirmed affiliation: {target_institution}",
                )

        # Attach Crossref provenance
        paper.sources.append(
            SourceProvenance(
                source_url=f"https://doi.org/{clean_doi(paper.doi)}",
                source_name="crossref",
                snippet=f"Metadata resolved via Crossref for DOI: {paper.doi}",
                verification_status=author_match.status if author_match else VerificationStatus.UNVERIFIED,
            )
        )

        return paper, author_match
