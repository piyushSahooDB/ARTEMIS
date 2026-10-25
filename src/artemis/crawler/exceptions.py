"""Exceptions related to web crawling and faculty extraction."""

from __future__ import annotations


class CrawlError(Exception):
    """Base exception for crawler and extraction failures."""


class UnsupportedPageError(CrawlError):
    """Raised when a target page format cannot be processed."""


class JavaScriptRenderedPageError(UnsupportedPageError):
    """Raised when a directory requires client-side JavaScript execution (SPA)."""

    def __init__(self, url: str, message: str | None = None) -> None:
        default_msg = (
            f"The faculty directory at '{url}' appears to be rendered via client-side JavaScript (SPA). "
            "ARTEMIS parses standard static HTML pages and does not execute arbitrary JavaScript. "
            "Please provide an institute page with server-rendered HTML faculty listings."
        )
        super().__init__(message or default_msg)
        self.url = url


class HttpError(CrawlError):
    """Raised when an HTTP error occurs."""

    def __init__(self, url: str, status_code: int, message: str | None = None) -> None:
        super().__init__(message or f"HTTP {status_code} while fetching {url}")
        self.url = url
        self.status_code = status_code


class RateLimitExceededError(HttpError):
    """Raised when HTTP 429 Too Many Requests is returned and retry limit is exceeded."""

    def __init__(self, url: str, retry_after: float | None = None) -> None:
        super().__init__(
            url=url,
            status_code=429,
            message=f"Rate limit exceeded (HTTP 429) for {url}. Retry-After: {retry_after}s",
        )
        self.retry_after = retry_after
