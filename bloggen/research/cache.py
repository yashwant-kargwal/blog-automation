"""Persistent JSON cache for structured search responses."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

from bloggen.research.exceptions import SearchCacheError
from bloggen.research.models import SearchResponse


class SearchCache:
    """Small filesystem cache with TTL-based invalidation."""

    def __init__(self, directory: Path, ttl_seconds: int) -> None:
        self.directory = directory
        self.ttl_seconds = ttl_seconds

    def key(self, query: str, depth: int, top_n: int, backends: list[str]) -> str:
        """Create a stable cache key from all result-shaping inputs."""
        payload = f"{query.casefold().strip()}|{depth}|{top_n}|{','.join(backends)}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, key: str) -> SearchResponse | None:
        """Return a non-expired cached response, if available."""
        path = self.directory / f"{key}.json"
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            timestamp = datetime.fromisoformat(payload["searched_at"])
            if self.ttl_seconds and datetime.now(timezone.utc) - timestamp > timedelta(seconds=self.ttl_seconds):
                path.unlink(missing_ok=True)
                return None
            response = SearchResponse.model_validate(payload)
            return response.model_copy(update={"cached": True})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Ignoring invalid search cache entry {}: {}", path, exc)
            return None

    def put(self, key: str, response: SearchResponse) -> None:
        """Persist a response atomically."""
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            target = self.directory / f"{key}.json"
            temporary = target.with_suffix(".tmp")
            temporary.write_text(response.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(target)
        except OSError as exc:
            raise SearchCacheError(f"Could not write search cache: {self.directory}") from exc
