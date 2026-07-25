"""Reusable HTTPX client factory."""

import httpx

from bloggen.config.settings import HTTPSettings


def create_http_client(settings: HTTPSettings) -> httpx.Client:
    """Create a configured synchronous HTTP client.

    Request orchestration and domain-specific API behavior belong in future adapters.
    """
    return httpx.Client(
        base_url=settings.base_url or "",
        timeout=httpx.Timeout(settings.timeout_seconds),
        follow_redirects=True,
        headers={"User-Agent": "Bloggen/0.1.0"},
    )
