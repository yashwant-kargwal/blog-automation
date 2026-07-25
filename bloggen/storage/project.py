"""Safe timestamped project artifact store."""

import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

import markdown

from bloggen import __version__
from bloggen.storage.exceptions import ArtifactExistsError, ProjectExistsError

PROJECT_FOLDERS = ("research", "seo", "content", "html", "logs", "metadata")


class ProjectStore:
    """Create and populate one isolated, non-overwriting project directory."""

    def __init__(self, root: Path = Path("data/projects"), project_path: Path | None = None) -> None:
        self.root = root
        self.path = project_path
        self.created_at: datetime | None = None

    @classmethod
    def create(cls, root: Path, name: str = "bloggen-project") -> "ProjectStore":
        """Create a unique UTC timestamp folder without replacing existing data."""
        root.mkdir(parents=True, exist_ok=True)
        slug = cls._slug(name)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        for sequence in range(1000):
            suffix = "" if sequence == 0 else f"-{sequence:02d}"
            candidate = root / f"{timestamp}-{slug}{suffix}"
            try:
                candidate.mkdir(parents=False, exist_ok=False)
            except FileExistsError:
                continue
            for folder in PROJECT_FOLDERS:
                (candidate / folder).mkdir()
            store = cls(root, candidate)
            store.created_at = datetime.now(timezone.utc)
            return store
        raise ProjectExistsError("Could not allocate a unique timestamped project directory.")

    @property
    def project_id(self) -> str:
        """Return the unique project directory name."""
        if self.path is None:
            raise ProjectExistsError("Project has not been created.")
        return self.path.name

    def save_json(self, category: str, filename: str, payload: Any) -> Path:
        """Save one JSON artifact without overwriting an existing file."""
        return self._save_bytes(category, filename, json.dumps(payload, indent=2, ensure_ascii=False, default=str).encode("utf-8"))

    def save_markdown(self, filename: str, content: str) -> Path:
        """Save Markdown content under the content folder."""
        return self._save_text("content", filename, content)

    def save_html(self, filename: str, content: str, *, title: str = "Bloggen article") -> Path:
        """Convert Markdown to a standalone HTML artifact."""
        body = markdown.markdown(content, extensions=["tables", "fenced_code", "sane_lists"])
        document = f"<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\"><title>{escape(title)}</title></head><body>{body}</body></html>\n"
        return self._save_text("html", filename, document)

    def save_log_snapshot(self, source: Path | None = None) -> Path:
        """Copy the current application log into the project."""
        source_path = source or Path("data/logs/bloggen.log")
        content = source_path.read_text(encoding="utf-8", errors="replace") if source_path.is_file() else "No application log entries were available.\n"
        return self._save_text("logs", "run.log", content)

    def finalize(self, **metadata: Any) -> Path:
        """Write final metadata and return the immutable project path."""
        payload = {"project_id": self.project_id, "created_at": self.created_at or datetime.now(timezone.utc), "completed_at": datetime.now(timezone.utc), "version": __version__, "artifacts": self._artifacts(), **metadata}
        return self._write_metadata(payload)

    def _write_metadata(self, payload: dict[str, Any]) -> Path:
        return self.save_json("metadata", "project.json", payload)

    def _artifacts(self) -> list[str]:
        if self.path is None:
            return []
        return sorted(str(item.relative_to(self.path)) for item in self.path.rglob("*") if item.is_file() and item.name != "project.json")

    def _save_text(self, category: str, filename: str, content: str) -> Path:
        return self._save_bytes(category, filename, content.encode("utf-8"))

    def _save_bytes(self, category: str, filename: str, content: bytes) -> Path:
        if self.path is None:
            raise ProjectExistsError("Project has not been created.")
        if category not in PROJECT_FOLDERS:
            raise ValueError(f"Unknown project artifact category: {category}")
        target = (self.path / category / filename).resolve()
        category_path = (self.path / category).resolve()
        if category_path not in target.parents:
            raise ValueError("Artifact filename must remain inside its project category")
        if target.exists():
            raise ArtifactExistsError(f"Refusing to overwrite existing artifact: {target}")
        target.write_bytes(content)
        return target

    @staticmethod
    def _slug(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        return normalized[:60] or "bloggen-project"
