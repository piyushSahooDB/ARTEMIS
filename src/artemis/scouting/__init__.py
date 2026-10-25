"""Academic paper discovery, deduplication, and ranking package."""

from artemis.scouting.arxiv import ArxivClient
from artemis.scouting.crossref import CrossrefClient
from artemis.scouting.deduplication import deduplicate_papers
from artemis.scouting.models import AuthorMatch, ScoutedPaper
from artemis.scouting.openalex import OpenAlexClient
from artemis.scouting.ranker import PaperRanker

__all__ = [
    "ArxivClient",
    "AuthorMatch",
    "CrossrefClient",
    "OpenAlexClient",
    "PaperRanker",
    "ScoutedPaper",
    "deduplicate_papers",
]
