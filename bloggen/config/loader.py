"""Load YAML and environment configuration into validated settings."""

from pathlib import Path
import os
from typing import Any

import yaml
from dotenv import load_dotenv

from bloggen.config.settings import Settings


def project_root() -> Path:
    """Return the repository root based on this package's location."""
    return Path(__file__).resolve().parents[2]


def load_yaml_config(path: Path | None = None) -> dict[str, Any]:
    """Read non-secret defaults from a YAML file."""
    config_path = path or project_root() / "config" / "config.yaml"
    if not config_path.is_file():
        return {}
    with config_path.open("r", encoding="utf-8") as config_file:
        loaded = yaml.safe_load(config_file) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Configuration root must be a mapping: {config_path}")
    return loaded


def load_settings() -> Settings:
    """Load YAML defaults, dotenv values, and environment overrides."""
    load_dotenv(project_root() / ".env")
    config = load_yaml_config()
    providers = config.setdefault("providers", {})
    openrouter = providers.setdefault("openrouter", {})
    if os.getenv("OPENROUTER_API_KEY") and not os.getenv("BLOGGEN_PROVIDERS__OPENROUTER__API_KEY"):
        openrouter["api_key"] = os.environ["OPENROUTER_API_KEY"]
    return Settings(**config)
