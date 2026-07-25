"""Deterministic quality validation for generated Markdown blogs."""

import math
import re
from collections import Counter
from collections.abc import Iterable

from bloggen.research.analysis_models import StructuredResearch
from bloggen.seo.models import SEOPlan
from bloggen.core.logging import pipeline_step
from bloggen.validation.models import Score, ValidationResult, WeakSection


class ValidationEngine:
    """Analyze SEO, language quality, readability, confidence, and duplication risk."""

    @pipeline_step("validation.validate")
    def validate(
        self,
        markdown: str,
        *,
        seo: SEOPlan | None = None,
        research: StructuredResearch | None = None,
        source_urls: Iterable[str] = (),
    ) -> ValidationResult:
        """Return a complete validation report for Markdown content."""
        if not markdown.strip():
            raise ValueError("Blog Markdown cannot be empty")
        words = self._words(markdown)
        seo_score, seo_suggestions = self._seo_score(markdown, seo)
        grammar_score, grammar_suggestions = self._grammar_score(markdown)
        readability_score, readability_suggestions = self._readability_score(markdown)
        confidence_score, confidence_suggestions = self._confidence_score(markdown, research, source_urls)
        duplicate_score, duplicate_suggestions = self._duplicate_score(markdown)
        weak_sections, section_suggestions = self._weak_sections(markdown)
        suggestions = self._unique(seo_suggestions + grammar_suggestions + readability_suggestions + confidence_suggestions + duplicate_suggestions + section_suggestions)
        overall = round(
            seo_score.score * 0.25
            + grammar_score.score * 0.20
            + readability_score.score * 0.20
            + confidence_score.score * 0.20
            + (100 - duplicate_score.score) * 0.15,
            1,
        )
        return ValidationResult(
            seo=seo_score,
            grammar=grammar_score,
            readability=readability_score,
            confidence=confidence_score,
            duplicate_risk=duplicate_score,
            weak_sections=weak_sections,
            suggestions=suggestions,
            overall_rating=self._rating(overall),
            overall_score=overall,
            word_count=len(words),
        )

    def _seo_score(self, markdown: str, seo: SEOPlan | None) -> tuple[Score, list[str]]:
        suggestions: list[str] = []
        checks: list[bool] = []
        h1 = re.findall(r"^# (.+)$", markdown, re.MULTILINE)
        h2 = re.findall(r"^## (.+)$", markdown, re.MULTILINE)
        h3 = re.findall(r"^### (.+)$", markdown, re.MULTILINE)
        checks.extend([len(h1) == 1, bool(h2), bool(h3), bool(re.search(r"(?m)^[-*+] ", markdown)), bool(re.search(r"\|.+\|\n\|[-: |]+\|", markdown))])
        if not h1:
            suggestions.append("Add one clear H1 matching the article topic.")
        if not h2 or not h3:
            suggestions.append("Use a complete H1/H2/H3 heading hierarchy.")
        if seo:
            lower = markdown.casefold()
            keyword = seo.primary_keyword.casefold()
            checks.extend([keyword in lower, keyword in " ".join(h1).casefold() if h1 else False, 30 <= len(seo.meta_description) <= 160, 20 <= len(seo.seo_title) <= 70])
            if keyword not in lower:
                suggestions.append(f"Use the primary keyword naturally: {seo.primary_keyword}.")
            if len(seo.meta_description) > 160:
                suggestions.append("Shorten the meta description to 160 characters or fewer.")
        score = round(sum(checks) / len(checks) * 100, 1) if checks else 0
        return Score(score=score, label=self._rating(score), rationale=f"{sum(checks)} of {len(checks)} SEO checks passed."), suggestions

    def _grammar_score(self, markdown: str) -> tuple[Score, list[str]]:
        prose = self._prose(markdown)
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", prose) if part.strip()]
        if not sentences:
            return Score(score=0, label="Poor", rationale="No prose sentences detected."), ["Add complete prose sentences."]
        errors = 0
        for sentence in sentences:
            if sentence[0].isalpha() and not sentence[0].isupper():
                errors += 1
        errors += len(re.findall(r"\b(\w+)\s+\1\b", prose, re.I))
        errors += len(re.findall(r"\s+[,.!?]", prose))
        score = max(0.0, round(100 - (errors / len(sentences) * 100), 1))
        suggestions = ["Review sentence capitalization and repeated words."] if errors else []
        return Score(score=score, label=self._rating(score), rationale=f"Detected {errors} likely grammar issue(s) across {len(sentences)} sentences."), suggestions

    def _readability_score(self, markdown: str) -> tuple[Score, list[str]]:
        prose = self._prose(markdown)
        words = self._words(prose)
        sentences = max(1, len(re.findall(r"[.!?](?:\s|$)", prose)))
        syllables = sum(self._syllables(word) for word in words)
        if not words:
            return Score(score=0, label="Poor", rationale="No readable prose detected."), ["Add readable prose content."]
        flesch = max(0.0, min(100.0, 206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words))))
        suggestions = ["Use shorter sentences and simpler words where possible."] if flesch < 50 else []
        return Score(score=round(flesch, 1), label=self._readability_label(flesch), rationale=f"Flesch reading ease estimate: {flesch:.1f}."), suggestions

    def _confidence_score(self, markdown: str, research: StructuredResearch | None, source_urls: Iterable[str]) -> tuple[Score, list[str]]:
        sources = {str(url).rstrip("/").casefold() for url in source_urls}
        if research:
            sources.update(str(source.url).rstrip("/").casefold() for source in research.sources)
        if not sources:
            return Score(score=35, label="Low", rationale="No source URLs were supplied for confidence checking."), ["Attach source URLs to the generated blog."]
        cited = sum(1 for source in sources if source in markdown.casefold())
        score = round(50 + (50 * cited / len(sources)), 1)
        suggestions = [] if cited else ["Include a clearly labeled sources section or contextual citations."]
        return Score(score=score, label=self._confidence_label(score), rationale=f"{cited} of {len(sources)} supplied source URL(s) appear in the blog."), suggestions

    def _duplicate_score(self, markdown: str) -> tuple[Score, list[str]]:
        paragraphs = [self._normalize(item) for item in re.split(r"\n\s*\n", markdown) if len(self._words(item)) >= 8]
        repeated_paragraphs = len(paragraphs) - len(set(paragraphs))
        tokens = [word.casefold() for word in self._words(markdown)]
        ngrams = [" ".join(tokens[index : index + 5]) for index in range(max(0, len(tokens) - 4))]
        repeated_ngrams = sum(count - 1 for count in Counter(ngrams).values() if count > 1)
        score = min(100.0, round(repeated_paragraphs * 30 + repeated_ngrams * 2, 1))
        suggestions = ["Rewrite repeated paragraphs or phrases to reduce duplication risk."] if score else []
        return Score(score=score, label=self._risk_label(score), rationale=f"Found {repeated_paragraphs} repeated paragraph(s) and {repeated_ngrams} repeated phrase occurrence(s)."), suggestions

    def _weak_sections(self, markdown: str) -> tuple[list[WeakSection], list[str]]:
        matches = list(re.finditer(r"^(#{2,3}) (.+)$", markdown, re.MULTILINE))
        weak: list[WeakSection] = []
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
            words = len(self._words(markdown[match.end() : end]))
            if words < 80:
                weak.append(WeakSection(heading=match.group(2).strip(), issue="Section is too short to fully develop its point.", words=words))
        return weak, [f"Expand weak section: {item.heading}." for item in weak]

    @staticmethod
    def _words(value: str) -> list[str]:
        return re.findall(r"\b[\w][\w'-]*\b", value)

    @staticmethod
    def _prose(markdown: str) -> str:
        return re.sub(r"```.*?```|!\[[^]]*\]\([^)]*\)|\[[^]]*\]\([^)]*\)|^#{1,6}\s+|^[|:\-+*` ]+$", " ", markdown, flags=re.MULTILINE | re.DOTALL)

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().split())

    @staticmethod
    def _syllables(word: str) -> int:
        clean = re.sub(r"[^a-z]", "", word.casefold())
        if len(clean) <= 3:
            return 1
        count = len(re.findall(r"[aeiouy]+", clean))
        if clean.endswith("e") and count > 1:
            count -= 1
        return max(1, count)

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @staticmethod
    def _rating(score: float) -> str:
        return "Excellent" if score >= 85 else "Good" if score >= 70 else "Needs improvement" if score >= 50 else "Poor"

    @staticmethod
    def _readability_label(score: float) -> str:
        return "Very easy" if score >= 80 else "Easy" if score >= 65 else "Standard" if score >= 50 else "Difficult"

    @staticmethod
    def _confidence_label(score: float) -> str:
        return "High" if score >= 85 else "Medium" if score >= 60 else "Low"

    @staticmethod
    def _risk_label(score: float) -> str:
        return "High" if score >= 50 else "Medium" if score >= 20 else "Low"
