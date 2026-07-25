"""Safe namespaced filesystem cache."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypeVar

from loguru import logger

T = TypeVar("T")


class CacheStore:
    """A small atomic JSON/text cache with TTL and namespace isolation."""

    def __init__(self, root: Path = Path("data/cache"), namespace: str = "default", ttl_seconds: int = 86400) -> None:
        if not namespace or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in namespace.casefold()):
            raise ValueError("Cache namespace must contain only letters, numbers, hyphens, or underscores")
        self.root = root
        self.namespace = namespace
        self.ttl_seconds = ttl_seconds
        self.directory = root / namespace

    @staticmethod
    def key(*parts: object) -> str:
        """Create a stable SHA-256 key from cache inputs."""
        return hashlib.sha256("\x1f".join(str(part) for part in parts).encode("utf-8")).hexdigest()

    def get_json(self, key: str) -> Any | None:
        """Read a valid JSON payload or return ``None`` on miss/expiry."""
        envelope = self._read(key, ".json")
        return envelope["payload"] if envelope is not None else None

    def set_json(self, key: str, payload: Any) -> Path:
        """Write a JSON payload atomically."""
        return self._write(key, ".json", {"payload": payload})

    def get_text(self, key: str) -> str | None:
        """Read a valid text payload or return ``None`` on miss/expiry."""
        envelope = self._read(key, ".txt")
        return envelope["payload"] if envelope is not None else None

    def set_text(self, key: str, payload: str) -> Path:
        """Write a text payload atomically."""
        return self._write(key, ".txt", {"payload": payload})

    def cleanup(self, *, expired_only: bool = True) -> int:
        """Remove expired entries, or all namespace entries when requested."""
        removed = 0
        if not self.directory.is_dir():
            return removed
        for path in self.directory.iterdir():
            if not path.is_file() or path.name == ".gitkeep":
                continue
            if not expired_only:
                path.unlink(missing_ok=True)
                removed += 1
                continue
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
                expires_at = datetime.fromisoformat(envelope["expires_at"])
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                continue
            if datetime.now(timezone.utc) >= expires_at:
                path.unlink(missing_ok=True)
                removed += 1
        return removed

    def stats(self) -> tuple[int, int]:
        """Return entry count and total bytes for this namespace."""
        if not self.directory.is_dir():
            return 0, 0
        files = [path for path in self.directory.iterdir() if path.is_file() and path.name != ".gitkeep"]
        return len(files), sum(path.stat().st_size for path in files)

    def _read(self, key: str, suffix: str, *, delete_expired: bool = True) -> dict[str, Any] | None:
        path = self.directory / f"{key}{suffix}"
        if not path.is_file():
            return None
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            expires_at = datetime.fromisoformat(envelope["expires_at"])
            if self.ttl_seconds and datetime.now(timezone.utc) >= expires_at:
                if delete_expired:
                    path.unlink(missing_ok=True)
                return None
            return envelope
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            logger.warning("Ignoring invalid cache entry {}: {}", path, exc)
            return None

    def _write(self, key: str, suffix: str, payload: dict[str, Any]) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        envelope = {"created_at": now.isoformat(), "expires_at": (now + timedelta(seconds=self.ttl_seconds)).isoformat(), **payload}
        target = self.directory / f"{key}{suffix}"
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(envelope, ensure_ascii=False, default=str), encoding="utf-8")
        temporary.replace(target)
        return target
