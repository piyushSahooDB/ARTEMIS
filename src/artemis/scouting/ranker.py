"""Paper ranking and scoring engine separating topic relevance from author identity confidence."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Sequence

from artemis.models.paper import Paper
from artemis.scouting.models import AuthorMatch, ScoutedPaper


class PaperRanker:
    """Ranks papers by balancing keyword relevance, recency, and foundational citations.

    Critically separates subject-matter relevance from identity confidence in the author.
    """

    def __init__(self, current_year: int | None = None) -> None:
        self.current_year = current_year or datetime.now().year

    def rank(
        self,
        papers: Sequence[tuple[Paper, AuthorMatch]],
        keywords: Sequence[str] | None = None,
    ) -> list[ScoutedPaper]:
        """Score and rank papers, returning ordered list of ScoutedPaper items."""
        kw_list = [k.lower().strip() for k in keywords if k.strip()] if keywords else []
        scouted: list[ScoutedPaper] = []

        for paper, author_match in papers:
            rel_score, matched_kws = self._calculate_keyword_relevance(paper, kw_list)
            rec_score = self._calculate_recency(paper)
            cit_score = self._calculate_citation_boost(paper)

            # Composite relevance formula:
            # - 60% Keyword relevance (how closely paper addresses student interest)
            # - 25% Recency (fresher research is preferred for active outreach)
            # - 15% Citations (protects older foundational papers from being discarded)
            if kw_list:
                comp_rel = 0.60 * rel_score + 0.25 * rec_score + 0.15 * cit_score
            else:
                # If no keywords specified, rely on recency and citations
                comp_rel = 0.65 * rec_score + 0.35 * cit_score

            comp_rel = max(0.0, min(1.0, comp_rel))

            scouted.append(
                ScoutedPaper(
                    paper=paper,
                    relevance_score=round(rel_score, 3),
                    recency_score=round(rec_score, 3),
                    citation_score=round(cit_score, 3),
                    composite_relevance=round(comp_rel, 3),
                    author_match=author_match,
                    matched_keywords=matched_kws,
                )
            )

        # Primary sort: verified authors first, then composite relevance
        scouted.sort(
            key=lambda x: (
                x.author_match.is_institution_matched,
                x.composite_relevance,
                x.paper.citation_count or 0,
            ),
            reverse=True,
        )

        return scouted

    def _calculate_keyword_relevance(
        self,
        paper: Paper,
        keywords: list[str],
    ) -> tuple[float, list[str]]:
        """Calculate keyword overlap across title, abstract, and venue."""
        if not keywords:
            return 0.5, []

        title_lower = paper.title.lower()
        abstract_lower = (paper.abstract or "").lower()
        venue_lower = (paper.venue or "").lower()

        matched_kws: list[str] = []
        score = 0.0

        for kw in keywords:
            kw_matched = False
            # Title match (high weight)
            if kw in title_lower:
                score += 3.0
                kw_matched = True
            # Abstract match (medium weight)
            elif kw in abstract_lower:
                score += 1.5
                kw_matched = True
            # Venue match (low weight)
            elif kw in venue_lower:
                score += 0.8
                kw_matched = True

            if kw_matched:
                matched_kws.append(kw)

        # Normalize against total possible score if all keywords were in title
        max_possible = len(keywords) * 3.0
        normalized = min(1.0, score / max_possible) if max_possible > 0 else 0.0
        return normalized, matched_kws

    def _calculate_recency(self, paper: Paper) -> float:
        """Calculate recency score (1.0 for recent, smooth decay for older papers)."""
        year = paper.year
        if not year:
            return 0.5

        diff = self.current_year - year
        if diff <= 1:
            return 1.0
        if diff <= 3:
            return 0.85
        if diff <= 5:
            return 0.70
        if diff <= 10:
            return 0.50
        if diff <= 15:
            return 0.35
        return 0.20

    def _calculate_citation_boost(self, paper: Paper) -> float:
        """Calculate logarithmic boost for foundational papers based on citation count."""
        c = paper.citation_count
        if c is None or c <= 0:
            return 0.0
        # 1 citation -> 0.1, 10 citations -> 0.35, 100 citations -> 0.67, 1000 citations -> 1.0
        return min(1.0, math.log10(c + 1) / 3.0)
