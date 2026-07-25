"""Offline tests for evidence-grounded research analysis."""

import json
from datetime import datetime, timezone

from bloggen.config.settings import ResearchSettings
from bloggen.providers.models import ChatResponse
from bloggen.research.analyzer import ResearchAnalyzer
from bloggen.scraper.models import ScrapedPage


class FakeProvider:
    name = "fake"

    def complete(self, request):
        del request
        return ChatResponse(
            model="fake-model",
            content=json.dumps(
                {
                    "facts": [
                        {"statement": "Python is a language.", "evidence": "Python is a programming language.", "citations": ["https://example.com/article"]},
                        {"statement": "Unsupported claim.", "evidence": "Not present.", "citations": ["https://example.com/article"]},
                    ],
                    "statistics": [],
                    "important_concepts": [],
                    "frequently_asked_questions": [],
                    "quotes": [],
                    "key_takeaways": [],
                }
            ),
        )


def test_analyzer_discards_unsupported_items(tmp_path) -> None:
    page = ScrapedPage(
        url="https://example.com/article",
        final_url="https://example.com/article",
        title="Article",
        markdown="# Article\n\nPython is a programming language.",
        word_count=5,
        content_hash="hash",
        status_code=200,
        extracted_at=datetime.now(timezone.utc),
    )
    settings = ResearchSettings(output_directory=tmp_path)

    result = ResearchAnalyzer(settings, provider=FakeProvider()).analyze([page], "Python")

    assert len(result.facts) == 1
    assert result.discarded_items == 1
    assert list(tmp_path.glob("*.json"))
