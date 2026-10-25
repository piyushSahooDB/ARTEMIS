"""OpenAlex academic API client for discovering author works and institutional affiliations."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from artemis.crawler.client import PoliteHttpClient
from artemis.models.common import SourceProvenance, VerificationStatus
from artemis.models.paper import Paper
from artemis.scouting.models import AuthorMatch

OPENALEX_WORKS_URL = "https://api.openalex.org/works"


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    """Reconstruct abstract string from OpenAlex inverted index representation."""
    if not inverted_index:
        return None
    position_word_map: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            position_word_map[pos] = word
    if not position_word_map:
        return None
    sorted_positions = sorted(position_word_map.keys())
    return " ".join(position_word_map[pos] for pos in sorted_positions)


def clean_doi(raw_doi: str | None) -> str | None:
    """Extract canonical DOI string from URL or raw text."""
    if not raw_doi:
        return None
    m = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", raw_doi)
    return m.group(0) if m else raw_doi.replace("https://doi.org/", "").strip()


def check_institution_affiliation(
    authorship_institutions: list[str],
    target_institution: str,
) -> bool:
    """Check if any author affiliation matches the professor's institution."""
    target_clean = re.sub(r"[^\w\s]", "", target_institution.lower()).split()
    # Filter common stop words like "university", "institute", "of", "the"
    significant_tokens = [t for t in target_clean if t not in ("university", "institute", "of", "the", "college", "at", "for")]
    if not significant_tokens:
        significant_tokens = target_clean

    for affil in authorship_institutions:
        affil_lower = affil.lower()
        if all(token in affil_lower for token in significant_tokens):
            return True
    return False


class OpenAlexClient:
    """Client for querying the OpenAlex scholarly database."""

    def __init__(self, client: PoliteHttpClient | None = None) -> None:
        self.client = client or PoliteHttpClient()

    def search_papers(
        self,
        author_name: str,
        institution: str | None = None,
        keywords: list[str] | None = None,
        max_results: int = 10,
    ) -> list[tuple[Paper, AuthorMatch]]:
        """Search papers for a given author with optional institution and keyword filters."""
        params: dict[str, Any] = {
            "filter": f"raw_author_name.search:{author_name}",
            "per-page": max_results,
            "sort": "publication_year:desc,cited_by_count:desc",
        }
        if keywords:
            params["search"] = " ".join(keywords)

        response = self.client.get(OPENALEX_WORKS_URL, params=params)
        data = response.json()
        results = data.get("results", [])

        papers_with_matches: list[tuple[Paper, AuthorMatch]] = []
        for item in results:
            paper, author_match = self._parse_work_item(item, author_name, institution)
            papers_with_matches.append((paper, author_match))

        return papers_with_matches

    def _parse_work_item(
        self,
        item: dict[str, Any],
        target_author: str,
        target_institution: str | None,
    ) -> tuple[Paper, AuthorMatch]:
        """Convert OpenAlex JSON object into a Paper and an AuthorMatch."""
        title = item.get("title") or "Untitled Paper"
        doi = clean_doi(item.get("doi"))
        openalex_id = item.get("id", "").split("/")[-1]
        year = item.get("publication_year")
        pub_date = item.get("publication_date") or (str(year) if year else None)
        citations = item.get("cited_by_count")

        primary_loc = item.get("primary_location") or {}
        source_loc = primary_loc.get("source") or {}
        venue = source_loc.get("display_name")
        landing_url = primary_loc.get("landing_page_url") or (f"https://doi.org/{doi}" if doi else item.get("id"))
        pdf_url = primary_loc.get("pdf_url")

        abstract = reconstruct_abstract(item.get("abstract_inverted_index"))

        authorships = item.get("authorships", [])
        author_names: list[str] = []
        matched_affiliations: list[str] = []
        author_found = False

        target_norm = target_author.lower()

        for a in authorships:
            author_obj = a.get("author") or {}
            dname = author_obj.get("display_name") or ""
            if dname:
                author_names.append(dname)

            if target_norm in dname.lower() or any(part in dname.lower() for part in target_norm.split() if len(part) > 2):
                author_found = True
                for inst in a.get("institutions", []):
                    inst_name = inst.get("display_name")
                    if inst_name:
                        matched_affiliations.append(inst_name)
                for raw_aff in a.get("raw_affiliation_strings", []):
                    if raw_aff and raw_aff not in matched_affiliations:
                        matched_affiliations.append(raw_aff)

        # Institutional verification check
        is_inst_matched = False
        if target_institution and matched_affiliations:
            is_inst_matched = check_institution_affiliation(matched_affiliations, target_institution)

        if is_inst_matched:
            author_match = AuthorMatch(
                author_name=target_author,
                affiliations=matched_affiliations,
                is_institution_matched=True,
                confidence=1.0,
                status=VerificationStatus.VERIFIED,
                notes=f"Author institutional affiliation verified with {target_institution}.",
            )
        else:
            notes = (
                "Name-only match; institutional affiliation not verified in paper metadata."
                if not matched_affiliations
                else f"Affiliation ({', '.join(matched_affiliations[:2])}) does not match target institution {target_institution}."
            )
            author_match = AuthorMatch(
                author_name=target_author,
                affiliations=matched_affiliations,
                is_institution_matched=False,
                confidence=0.4,
                status=VerificationStatus.UNVERIFIED,
                notes=notes,
            )

        prov = SourceProvenance(
            source_url=item.get("id") or landing_url or OPENALEX_WORKS_URL,
            source_name="openalex",
            snippet=f"Retrieved from OpenAlex work {openalex_id}: {title}",
            verification_status=author_match.status,
        )

        paper = Paper(
            title=title,
            abstract=abstract,
            published_date=pub_date,
            year=year,
            venue=venue,
            doi=doi,
            openalex_id=openalex_id,
            url=landing_url,
            pdf_url=pdf_url,
            citation_count=citations,
            author_names=author_names,
            sources=[prov],
        )

        return paper, author_match
