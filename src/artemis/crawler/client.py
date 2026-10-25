"""Polite HTTP client with rate limiting, custom user-agent, and timeout guards."""

from __future__ import annotations

import os
import time
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx

from artemis.crawler.exceptions import HttpError, RateLimitExceededError


def get_default_user_agent() -> str:
    """Return configured or standard User-Agent header for polite academic requests."""
    custom = os.getenv("ARTEMIS_USER_AGENT")
    if custom and custom.strip():
        return custom.strip()

    email = os.getenv("ARTEMIS_CONTACT_EMAIL", "").strip()
    contact = f"; mailto:{email}" if email else ""
    return (
        f"ARTEMIS-AcademicScout/0.2.0 "
        f"(+https://github.com/piyushSahooDB/ARTEMIS{contact}; polite student research assistant)"
    )


class PoliteHttpClient:
    """HTTP client adhering to polite scraping practices.

    - Enforces request timeouts.
    - Tracks per-host request intervals to prevent overloading university servers.
    - Identifies itself with a configurable, accurate academic User-Agent.
    - Handles HTTP 429 Too Many Requests and Retry-After headers politely.
    """

    def __init__(
        self,
        user_agent: str | None = None,
        timeout: float = 10.0,
        min_host_interval: float = 0.5,
        max_retries: int = 2,
        client: httpx.Client | None = None,
    ) -> None:
        self.user_agent = user_agent or get_default_user_agent()
        self.timeout = timeout
        self.min_host_interval = min_host_interval
        self.max_retries = max_retries
        self._last_request_time: dict[str, float] = {}

        self._client = client or httpx.Client(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            headers={"User-Agent": self.user_agent},
        )
        self._owns_client = client is None

    def close(self) -> None:
        """Close underlying HTTP client."""
        if self._owns_client and not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> PoliteHttpClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _rate_limit(self, url: str) -> None:
        """Enforce domain-level politeness interval."""
        host = urlparse(url).netloc.lower()
        now = time.monotonic()
        last_time = self._last_request_time.get(host)

        if last_time is not None:
            elapsed = now - last_time
            if elapsed < self.min_host_interval:
                time.sleep(self.min_host_interval - elapsed)

        self._last_request_time[host] = time.monotonic()

    def get(
        self,
        url: str,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        """Send a polite GET request with rate limiting and retry handling."""
        combined_headers = {"User-Agent": self.user_agent}
        if headers:
            combined_headers.update(headers)

        retries = 0
        while True:
            self._rate_limit(url)
            try:
                response = self._client.get(
                    url,
                    headers=combined_headers,
                    params=params,
                    timeout=self.timeout,
                )
            except httpx.TimeoutException as exc:
                raise HttpError(url, 408, f"Request timed out after {self.timeout}s: {url}") from exc
            except httpx.RequestError as exc:
                raise HttpError(url, 0, f"Network error connecting to {url}: {exc}") from exc

            if response.status_code == 429:
                retry_after_header = response.headers.get("Retry-After")
                retry_after = 1.0
                if retry_after_header:
                    try:
                        retry_after = float(retry_after_header)
                    except ValueError:
                        retry_after = 2.0

                if retries < self.max_retries and retry_after <= 5.0:
                    retries += 1
                    time.sleep(retry_after)
                    continue
                raise RateLimitExceededError(url, retry_after=retry_after)

            if response.is_error:
                raise HttpError(
                    url=url,
                    status_code=response.status_code,
                    message=f"HTTP {response.status_code} {response.reason_phrase} for {url}",
                )

            return response
