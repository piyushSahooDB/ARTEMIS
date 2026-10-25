"""Paper deduplication across OpenAlex, arXiv, and Crossref data sources."""

from __future__ import annotations

import re
from typing import Sequence

from artemis.models.paper import Paper
from artemis.scouting.models import AuthorMatch


def normalize_title(title: str) -> str:
    """Normalize paper title for fuzzy comparison (lower, strip punctuation, collapse whitespace)."""
    lowered = title.lower()
    cleaned = re.sub(r"[^\w\s]", "", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def deduplicate_papers(
    items: Sequence[tuple[Paper, AuthorMatch]],
) -> list[tuple[Paper, AuthorMatch]]:
    """Deduplicate papers using DOI, arXiv ID, and normalized titles, merging metadata."""
    doi_map: dict[str, int] = {}
    arxiv_map: dict[str, int] = {}
    title_map: dict[str, int] = {}

    deduped: list[tuple[Paper, AuthorMatch]] = []

    for paper, author_match in items:
        norm_doi = paper.doi.lower().strip() if paper.doi else None
        norm_arxiv = paper.arxiv_id.lower().strip() if paper.arxiv_id else None
        norm_title = normalize_title(paper.title)

        match_idx: int | None = None

        if norm_doi and norm_doi in doi_map:
            match_idx = doi_map[norm_doi]
        elif norm_arxiv and norm_arxiv in arxiv_map:
            match_idx = arxiv_map[norm_arxiv]
        elif norm_title and len(norm_title) > 15 and norm_title in title_map:
            match_idx = title_map[norm_title]

        if match_idx is not None:
            # Merge with existing paper
            existing_paper, existing_match = deduped[match_idx]
            merged_paper = _merge_papers(existing_paper, paper)
            merged_match = _merge_author_matches(existing_match, author_match)
            deduped[match_idx] = (merged_paper, merged_match)

            # Update maps with newly merged IDs
            if merged_paper.doi:
                doi_map[merged_paper.doi.lower().strip()] = match_idx
            if merged_paper.arxiv_id:
                arxiv_map[merged_paper.arxiv_id.lower().strip()] = match_idx
        else:
            new_idx = len(deduped)
            deduped.append((paper, author_match))
            if norm_doi:
                doi_map[norm_doi] = new_idx
            if norm_arxiv:
                arxiv_map[norm_arxiv] = new_idx
            if norm_title and len(norm_title) > 15:
                title_map[norm_title] = new_idx

    return deduped


def _merge_papers(p1: Paper, p2: Paper) -> Paper:
    """Merge two representations of the same academic paper."""
    # Preferred DOI & arXiv ID
    doi = p1.doi or p2.doi
    arxiv_id = p1.arxiv_id or p2.arxiv_id
    openalex_id = p1.openalex_id or p2.openalex_id

    # Title: prefer longer or better-cased title
    title = p1.title if len(p1.title) >= len(p2.title) else p2.title

    # Abstract: prefer richer/longer abstract
    abstract = p1.abstract
    if not abstract or (p2.abstract and len(p2.abstract) > len(abstract)):
        abstract = p2.abstract

    # Citation count: take max
    citations = p1.citation_count
    if p2.citation_count is not None:
        citations = max(citations or 0, p2.citation_count)

    # URLs
    url = p1.url or p2.url
    pdf_url = p1.pdf_url or p2.pdf_url
    venue = p1.venue or p2.venue
    year = p1.year or p2.year
    published_date = p1.published_date or p2.published_date

    # Combine author names preserving order and uniqueness
    author_names = list(p1.author_names)
    for a in p2.author_names:
        if a not in author_names:
            author_names.append(a)

    # Combine provenance sources without duplicate URLs
    seen_urls = set(s.source_url for s in p1.sources)
    sources = list(p1.sources)
    for s in p2.sources:
        if s.source_url not in seen_urls:
            sources.append(s)
            seen_urls.add(s.source_url)

    return Paper(
        id=p1.id,
        title=title,
        abstract=abstract,
        published_date=published_date,
        year=year,
        venue=venue,
        doi=doi,
        arxiv_id=arxiv_id,
        openalex_id=openalex_id,
        url=url,
        pdf_url=pdf_url,
        citation_count=citations,
        author_names=author_names,
        sources=sources,
        created_at=p1.created_at,
        updated_at=p1.updated_at,
    )


def _merge_author_matches(m1: AuthorMatch, m2: AuthorMatch) -> AuthorMatch:
    """Merge author match details, prioritizing higher confidence / verified status."""
    if m1.confidence >= m2.confidence and m1.is_institution_matched:
        return m1
    if m2.is_institution_matched:
        return m2

    combined_affils = list(m1.affiliations)
    for aff in m2.affiliations:
        if aff not in combined_affils:
            combined_affils.append(aff)

    return AuthorMatch(
        author_name=m1.author_name,
        affiliations=combined_affils,
        is_institution_matched=m1.is_institution_matched or m2.is_institution_matched,
        confidence=max(m1.confidence, m2.confidence),
        status=m1.status if m1.confidence >= m2.confidence else m2.status,
        notes=m1.notes if m1.confidence >= m2.confidence else m2.notes,
    )
