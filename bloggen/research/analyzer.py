"""Evidence-constrained research analysis over scraped articles."""

import json
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from loguru import logger
from pydantic import ValidationError

from bloggen.config.settings import ResearchSettings, Settings
from bloggen.cache.ai import CachedLLMProvider
from bloggen.cache.store import CacheStore
from bloggen.core.logging import pipeline_step
from bloggen.providers.base import LLMProvider
from bloggen.providers.factory import create_provider
from bloggen.providers.models import ChatMessage, ChatRequest
from bloggen.prompts.loader import PromptLoader
from bloggen.research.analysis_exceptions import ResearchInputError, ResearchOutputError
from bloggen.research.analysis_models import (
    AnalysisEnvelope,
    FrequentlyAskedQuestion,
    GroundedItem,
    ImportantConcept,
    Quote,
    ResearchSource,
    Statistic,
    StructuredResearch,
)
from bloggen.scraper.models import ScrapedPage

class ResearchAnalyzer:
    """Analyze scraped pages into a citation-validated JSON research artifact."""

    def __init__(self, settings: Settings | ResearchSettings, provider: LLMProvider | None = None, prompt_loader: PromptLoader | None = None) -> None:
        self.settings = settings.research if isinstance(settings, Settings) else settings
        self.provider = provider
        self.prompts = prompt_loader or PromptLoader()
        self.output_directory = self.settings.output_directory

    @pipeline_step("research.analyze")
    def analyze(self, articles: Iterable[ScrapedPage], topic: str = "", *, use_cache: bool = True) -> StructuredResearch:
        """Analyze articles and persist a validated JSON artifact."""
        pages = list(articles)
        if not pages:
            raise ResearchInputError("At least one scraped article is required.")
        source_urls = {self._canonical_url(page.final_url or page.url) for page in pages}
        resolved_topic = topic.strip() or pages[0].title or "Research synthesis"
        cache_path = self._cache_path(pages, resolved_topic)
        if use_cache:
            cached = self._load_cache(cache_path, source_urls)
            if cached:
                logger.info("Research analysis cache hit topic={!r}", resolved_topic)
                return cached

        provider = self.provider or self._create_provider()
        prompt = self._build_prompt(pages, resolved_topic)
        try:
            response = provider.complete(
                ChatRequest(
                    messages=[ChatMessage(role="system", content=self.prompts.render("research/system.md")), ChatMessage(role="user", content=prompt)],
                    temperature=0,
                    max_tokens=12000,
                )
            )
            envelope = AnalysisEnvelope.model_validate(self._parse_json(response.content))
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            logger.error("Research model returned invalid structured output: {}", exc)
            raise ResearchOutputError("The analysis provider returned invalid structured research JSON.") from exc

        validated, discarded = self._validate_grounding(envelope, pages, source_urls)
        result = StructuredResearch(
            topic=resolved_topic,
            generated_at=datetime.now(timezone.utc),
            model=response.model,
            sources=[ResearchSource(url=page.final_url or page.url, title=page.title, content_hash=page.content_hash) for page in pages],
            **validated,
            discarded_items=discarded,
        )
        self._save_cache(cache_path, result)
        return result

    def _settings_for_provider(self) -> Settings:
        """Return full settings for the provider factory when given research settings."""
        if isinstance(self.settings, ResearchSettings):
            from bloggen.config.loader import load_settings

            return load_settings()
        return self.settings

    def _create_provider(self) -> LLMProvider:
        settings = self._settings_for_provider()
        provider = create_provider(settings)
        if settings.cache.enabled:
            return CachedLLMProvider(provider, CacheStore(settings.cache.directory, "ai", settings.cache.ttl_seconds))
        return provider

    def _build_prompt(self, pages: list[ScrapedPage], topic: str) -> str:
        """Build a source-labeled prompt with no untrusted instruction execution."""
        documents = []
        for index, page in enumerate(pages, start=1):
            documents.append(f"SOURCE {index}\nURL: {page.final_url or page.url}\nTITLE: {page.title}\nARTICLE:\n{page.markdown}")
        schema = {
            "facts": [{"statement": "", "evidence": "", "citations": ["https://source.example"]}],
            "statistics": [{"statement": "", "value": "", "evidence": "", "citations": ["https://source.example"]}],
            "important_concepts": [{"name": "", "statement": "", "evidence": "", "citations": ["https://source.example"]}],
            "frequently_asked_questions": [{"question": "", "answer": "", "statement": "", "evidence": "", "citations": ["https://source.example"]}],
            "quotes": [{"text": "", "attribution": "", "evidence": "", "citations": ["https://source.example"]}],
            "key_takeaways": [{"statement": "", "evidence": "", "citations": ["https://source.example"]}],
        }
        return self.prompts.render("research/user.md", topic=topic, schema=json.dumps(schema, indent=2), articles="\n\n".join(documents))

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        """Parse plain or fenced JSON without accepting surrounding prose."""
        candidate = content.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.I | re.S).strip()
        if not candidate.startswith("{") or not candidate.endswith("}"):
            raise ValueError("Model output was not a JSON object")
        parsed = json.loads(candidate)
        if not isinstance(parsed, dict):
            raise ValueError("Model output JSON must be an object")
        return parsed

    def _validate_grounding(self, envelope: AnalysisEnvelope, pages: list[ScrapedPage], source_urls: set[str]) -> tuple[dict[str, list[Any]], int]:
        """Keep only items whose citations and verbatim evidence match input articles."""
        content_by_url = {self._canonical_url(page.final_url or page.url): self._normalize_text(page.markdown) for page in pages}
        output: dict[str, list[Any]] = {}
        discarded = 0
        for field_name in ("facts", "statistics", "important_concepts", "frequently_asked_questions", "quotes", "key_takeaways"):
            kept = []
            for item in getattr(envelope, field_name):
                citations = {self._canonical_url(str(url)) for url in item.citations}
                evidence = self._normalize_text(item.evidence)
                supported = citations and citations.issubset(source_urls) and any(evidence in content_by_url[url] for url in citations if url in content_by_url)
                if isinstance(item, Quote):
                    supported = bool(supported) and any(self._normalize_text(item.text) in content_by_url[url] for url in citations if url in content_by_url)
                if supported:
                    kept.append(item)
                else:
                    discarded += 1
            output[field_name] = kept
        return output, discarded

    def _cache_path(self, pages: list[ScrapedPage], topic: str) -> Path:
        import hashlib

        fingerprint = "|".join([topic.casefold(), *(page.content_hash for page in pages)])
        return self.output_directory / f"{hashlib.sha256(fingerprint.encode()).hexdigest()}.json"

    def _load_cache(self, path: Path, source_urls: set[str]) -> StructuredResearch | None:
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            result = StructuredResearch.model_validate(payload)
            if result.generated_at.tzinfo is None:
                return None
            if self.settings.analysis_cache_ttl_seconds and (datetime.now(timezone.utc) - result.generated_at).total_seconds() > self.settings.analysis_cache_ttl_seconds:
                path.unlink(missing_ok=True)
                return None
            if {self._canonical_url(str(source.url)) for source in result.sources} != source_urls:
                return None
            return result
        except (OSError, ValueError, TypeError, ValidationError, KeyError):
            return None

    def _save_cache(self, path: Path, result: StructuredResearch) -> None:
        self.output_directory.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _canonical_url(url: str) -> str:
        parsed = urlsplit(url.strip())
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, "")).casefold()

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(value.split()).casefold()
