"""Crawler and faculty directory parsing package."""

from artemis.crawler.client import PoliteHttpClient, get_default_user_agent
from artemis.crawler.exceptions import (
    CrawlError,
    HttpError,
    JavaScriptRenderedPageError,
    RateLimitExceededError,
    UnsupportedPageError,
)
from artemis.crawler.faculty_parser import FacultyDirectoryParser

__all__ = [
    "CrawlError",
    "FacultyDirectoryParser",
    "HttpError",
    "JavaScriptRenderedPageError",
    "PoliteHttpClient",
    "RateLimitExceededError",
    "UnsupportedPageError",
    "get_default_user_agent",
]
