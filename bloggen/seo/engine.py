"""Evidence-aware SEO planning over structured research."""

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import ValidationError

from bloggen.cache.ai import CachedLLMProvider
from bloggen.cache.store import CacheStore
from bloggen.config.settings import SEOSettings, Settings
from bloggen.core.logging import pipeline_step
from bloggen.providers.base import LLMProvider
from bloggen.providers.factory import create_provider
from bloggen.providers.models import ChatMessage, ChatRequest
from bloggen.prompts.loader import PromptLoader
from bloggen.research.analysis_models import StructuredResearch
from bloggen.seo.exceptions import SEOInputError, SEOOutputError
from bloggen.seo.models import SEOPlan

class SEOEngine:
    """Generate and persist validated SEO plans from structured research."""

    def __init__(self, settings: Settings | SEOSettings, provider: LLMProvider | None = None, prompt_loader: PromptLoader | None = None) -> None:
        self.full_settings = settings if isinstance(settings, Settings) else None
        self.settings = settings.seo if isinstance(settings, Settings) else settings
        self.provider = provider
        self.prompts = prompt_loader or PromptLoader()

    @pipeline_step("seo.generate")
    def generate(self, research: StructuredResearch, topic: str = "", *, use_cache: bool = True) -> SEOPlan:
        """Generate one structured SEO plan."""
        if not research.sources:
            raise SEOInputError("Structured research must contain at least one source.")
        resolved_topic = topic.strip() or research.topic
        cache_path = self._cache_path(research, resolved_topic)
        if use_cache:
            cached = self._load_cache(cache_path)
            if cached is not None:
                logger.info("SEO plan cache hit topic={!r}", resolved_topic)
                return cached

        provider = self.provider or self._create_provider()
        try:
            response = provider.complete(
                ChatRequest(
                    messages=[ChatMessage(role="system", content=self.prompts.render("seo/system.md")), ChatMessage(role="user", content=self._prompt(research, resolved_topic))],
                    temperature=0,
                    max_tokens=self.settings.max_tokens,
                )
            )
            payload = self._parse_json(response.content)
            payload.setdefault("topic", resolved_topic)
            payload.setdefault("source_urls", [str(source.url) for source in research.sources])
            payload["generated_at"] = datetime.now(timezone.utc)
            payload["model"] = response.model
            plan = SEOPlan.model_validate(payload)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            logger.error("SEO provider returned invalid JSON: {}", exc)
            raise SEOOutputError("The SEO provider returned invalid structured JSON.") from exc

        self._validate_links(plan, research)
        self._save_cache(cache_path, plan)
        return plan

    def _provider_settings(self) -> Settings:
        if self.full_settings is not None:
            return self.full_settings
        from bloggen.config.loader import load_settings

        return load_settings()

    def _create_provider(self) -> LLMProvider:
        settings = self._provider_settings()
        provider = create_provider(settings)
        if settings.cache.enabled:
            return CachedLLMProvider(provider, CacheStore(settings.cache.directory, "ai", settings.cache.ttl_seconds))
        return provider

    def _prompt(self, research: StructuredResearch, topic: str) -> str:
        schema: dict[str, Any] = {
            "topic": topic,
            "seo_title": "",
            "meta_description": "",
            "slug": "",
            "primary_keyword": "",
            "secondary_keywords": [],
            "lsi_keywords": [],
            "suggested_images": [{"description": "", "alt_text": "", "placement": "", "image_type": ""}],
            "target_word_count": 0,
            "faq": [{"question": "", "answer_direction": ""}],
            "heading_structure": [{"level": 1, "text": "", "purpose": ""}],
            "internal_linking_suggestions": [{"anchor_text": "", "target_topic": "", "placement": "", "reason": "", "target_url": None}],
        }
        return self.prompts.render("seo/user.md", topic=topic, schema=json.dumps(schema, indent=2), research_json=research.model_dump_json(indent=2))

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        candidate = content.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.I | re.S).strip()
        if not candidate.startswith("{") or not candidate.endswith("}"):
            raise ValueError("SEO output was not a JSON object")
        parsed = json.loads(candidate)
        if not isinstance(parsed, dict):
            raise ValueError("SEO output JSON must be an object")
        return parsed

    @staticmethod
    def _validate_links(plan: SEOPlan, research: StructuredResearch) -> None:
        """Reject invented target URLs while allowing URL-less suggestions."""
        allowed = {str(source.url).rstrip("/").casefold() for source in research.sources}
        for suggestion in plan.internal_linking_suggestions:
            if suggestion.target_url and suggestion.target_url.rstrip("/").casefold() not in allowed:
                raise SEOOutputError(f"SEO plan invented an internal URL: {suggestion.target_url}")

    def _cache_path(self, research: StructuredResearch, topic: str) -> Path:
        fingerprint = f"{topic.casefold()}|{research.model_dump_json()}"
        return self.settings.output_directory / f"{hashlib.sha256(fingerprint.encode()).hexdigest()}.json"

    def _load_cache(self, path: Path) -> SEOPlan | None:
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            plan = SEOPlan.model_validate(payload)
            age = datetime.now(timezone.utc) - plan.generated_at
            if self.settings.cache_ttl_seconds and age > timedelta(seconds=self.settings.cache_ttl_seconds):
                path.unlink(missing_ok=True)
                return None
            return plan
        except (OSError, ValueError, TypeError, ValidationError, KeyError):
            return None

    def _save_cache(self, path: Path, plan: SEOPlan) -> None:
        self.settings.output_directory.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
