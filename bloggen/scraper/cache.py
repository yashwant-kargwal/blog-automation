"""Persistent cache for extracted pages."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

from bloggen.scraper.models import ScrapedPage


class PageCache:
    """Filesystem page cache with atomic writes and expiry."""

    def __init__(self, directory: Path, ttl_seconds: int) -> None:
        self.directory = directory
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def key(url: str) -> str:
        """Return a stable cache key for a URL."""
        return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()

    def get(self, url: str) -> ScrapedPage | None:
        """Read a valid cached page."""
        path = self.directory / f"{self.key(url)}.json"
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            extracted_at = datetime.fromisoformat(payload["extracted_at"])
            if self.ttl_seconds and datetime.now(timezone.utc) - extracted_at > timedelta(seconds=self.ttl_seconds):
                path.unlink(missing_ok=True)
                return None
            return ScrapedPage.model_validate(payload).model_copy(update={"cached": True})
        except (OSError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Ignoring invalid page cache entry {}: {}", path, exc)
            return None

    def put(self, page: ScrapedPage) -> None:
        """Persist a page atomically."""
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f"{self.key(page.url)}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(page.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(target)
