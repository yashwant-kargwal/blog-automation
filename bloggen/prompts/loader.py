"""Strict Markdown prompt template loader."""

from pathlib import Path
from string import Template
from typing import Mapping


class PromptError(RuntimeError):
    """Raised when a prompt template cannot be loaded or rendered."""


class PromptLoader:
    """Load Markdown prompt templates and inject named variables."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2] / "prompts"

    def load(self, name: str) -> str:
        """Read a Markdown template by relative path."""
        path = (self.root / name).resolve()
        if self.root.resolve() not in path.parents or path.suffix.casefold() != ".md":
            raise PromptError(f"Invalid Markdown prompt path: {name}")
        if not path.is_file():
            raise PromptError(f"Prompt template not found: {name}")
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PromptError(f"Could not read prompt template: {name}") from exc

    def render(self, name: str, variables: Mapping[str, object] | None = None, **kwargs: object) -> str:
        """Render a Markdown template with strict variable substitution."""
        values = dict(variables or {})
        values.update(kwargs)
        template = Template(self.load(name))
        try:
            return template.substitute({key: str(value) for key, value in values.items()}).strip()
        except (KeyError, ValueError) as exc:
            raise PromptError(f"Missing or invalid variable in prompt template {name}: {exc}") from exc
