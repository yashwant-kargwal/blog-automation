"""OpenRouter-backed professional Markdown blog writer."""

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
from bloggen.config.settings import Settings, WriterSettings
from bloggen.core.logging import pipeline_step
from bloggen.providers.base import LLMProvider
from bloggen.providers.factory import create_provider
from bloggen.providers.models import ChatMessage, ChatRequest
from bloggen.prompts.loader import PromptLoader
from bloggen.research.analysis_models import StructuredResearch
from bloggen.seo.models import SEOPlan
from bloggen.writer.exceptions import WriterInputError, WriterOutputError
from bloggen.writer.models import BlogPost
from bloggen.writer.quality import count_words, validate_markdown

class BlogWriter:
    """Generate validated Markdown posts from research and SEO inputs."""

    def __init__(self, settings: Settings | WriterSettings, provider: LLMProvider | None = None, prompt_loader: PromptLoader | None = None) -> None:
        self.full_settings = settings if isinstance(settings, Settings) else None
        self.settings = settings.writer if isinstance(settings, Settings) else settings
        self.provider = provider
        self.prompts = prompt_loader or PromptLoader()

    @pipeline_step("writer.write")
    def write(self, research: StructuredResearch, seo: SEOPlan, *, style: str | None = None, use_cache: bool = True) -> BlogPost:
        """Generate and persist one professional Markdown article."""
        if not research.sources:
            raise WriterInputError("Research must contain at least one source.")
        selected_style = style or (self.full_settings.writer.default_style if self.full_settings else self.settings.default_style)
        if selected_style not in self.settings.available_styles:
            raise WriterInputError(f"Unsupported writing style: {selected_style}")
        cache_path = self._cache_path(research, seo, selected_style)
        if use_cache:
            cached = self._load_cache(cache_path)
            if cached is not None:
                logger.info("Blog writer cache hit slug={}", seo.slug)
                return cached

        provider = self.provider or self._create_provider()
        try:
            response = provider.complete(
                ChatRequest(
                    messages=[ChatMessage(role="system", content=self.prompts.render("writer/system.md")), ChatMessage(role="user", content=self._prompt(research, seo, selected_style))],
                    temperature=0.7,
                    max_tokens=self.settings.max_tokens,
                )
            )
        except Exception as exc:
            raise WriterOutputError("The writing provider could not generate the article.") from exc
        markdown = self._clean_response(response.content)
        violations = validate_markdown(markdown, self.settings.minimum_words, self.settings.maximum_words)
        if violations:
            logger.error("Generated blog failed quality checks: {}", violations)
            raise WriterOutputError("Generated Markdown failed quality checks: " + "; ".join(violations))
        post = BlogPost(
            title=seo.seo_title,
            slug=seo.slug,
            style=selected_style,
            markdown=markdown,
            word_count=count_words(markdown),
            source_urls=[str(source.url) for source in research.sources],
            generated_at=datetime.now(timezone.utc),
            model=response.model,
        )
        self._save(post, cache_path)
        return post

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

    def _prompt(self, research: StructuredResearch, seo: SEOPlan, style: str) -> str:
        return self.prompts.render(
            "writer/user.md",
            style=style,
            minimum_words=self.settings.minimum_words,
            maximum_words=self.settings.maximum_words,
            seo_json=seo.model_dump_json(indent=2),
            research_json=research.model_dump_json(indent=2),
        )

    @staticmethod
    def _clean_response(content: str) -> str:
        markdown = content.strip()
        if markdown.startswith("```"):
            markdown = re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", markdown, flags=re.I | re.S).strip()
        return markdown

    def _cache_path(self, research: StructuredResearch, seo: SEOPlan, style: str) -> Path:
        fingerprint = f"{style}|{research.model_dump_json()}|{seo.model_dump_json()}"
        return self.settings.output_directory / f"{hashlib.sha256(fingerprint.encode()).hexdigest()}.json"

    def _load_cache(self, path: Path) -> BlogPost | None:
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            post = BlogPost.model_validate(payload)
            age = datetime.now(timezone.utc) - post.generated_at
            if self.settings.cache_ttl_seconds and age > timedelta(seconds=self.settings.cache_ttl_seconds):
                path.unlink(missing_ok=True)
                return None
            return post
        except (OSError, ValueError, TypeError, ValidationError, KeyError):
            return None

    def _save(self, post: BlogPost, cache_path: Path) -> None:
        self.settings.output_directory.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(".tmp")
        temporary.write_text(post.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(cache_path)
        (self.settings.output_directory / f"{post.slug}.md").write_text(post.markdown + "\n", encoding="utf-8")
