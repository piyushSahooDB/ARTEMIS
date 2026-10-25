"""A.R.T.E.M.I.S.

Autonomous Research Tracking, Exploration, Matching & Intelligent Scouting.
"""

from artemis.crawler.client import PoliteHttpClient
from artemis.crawler.faculty_parser import FacultyDirectoryParser
from artemis.scouting.arxiv import ArxivClient
from artemis.scouting.crossref import CrossrefClient
from artemis.scouting.openalex import OpenAlexClient
from artemis.service import ArtemisScoutingService, FacultyScoutResult

__version__ = "0.2.0"

__all__ = [
    "ArtemisScoutingService",
    "ArxivClient",
    "CrossrefClient",
    "FacultyDirectoryParser",
    "FacultyScoutResult",
    "OpenAlexClient",
    "PoliteHttpClient",
]
