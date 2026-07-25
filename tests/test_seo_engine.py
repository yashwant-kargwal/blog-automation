"""Offline SEO engine tests."""

import json
from datetime import datetime, timezone

from bloggen.config.settings import SEOSettings
from bloggen.providers.models import ChatResponse
from bloggen.research.analysis_models import ResearchSource, StructuredResearch
from bloggen.seo.engine import SEOEngine


class FakeSEOProvider:
    def complete(self, request):
        del request
        return ChatResponse(
            model="fake-seo-model",
            content=json.dumps(
                {
                    "seo_title": "Python HTTP Clients Guide",
                    "meta_description": "A practical guide to Python HTTP clients and reliable requests.",
                    "slug": "python-http-clients-guide",
                    "primary_keyword": "Python HTTP clients",
                    "secondary_keywords": ["HTTPX", "Python requests"],
                    "lsi_keywords": ["timeouts", "retries"],
                    "suggested_images": [{"description": "HTTP request flow", "alt_text": "Python HTTP request flow", "placement": "Introduction", "image_type": "diagram"}],
                    "target_word_count": 1600,
                    "faq": [{"question": "What is an HTTP client?", "answer_direction": "Define it using the research."}],
                    "heading_structure": [{"level": 1, "text": "Python HTTP Clients Guide", "purpose": "Main title"}],
                    "internal_linking_suggestions": [{"anchor_text": "HTTP client basics", "target_topic": "HTTP clients", "placement": "Introduction", "reason": "Contextual relevance", "target_url": None}],
                }
            ),
        )


def test_seo_plan_is_structured_and_cached(tmp_path) -> None:
    research = StructuredResearch(
        topic="Python HTTP clients",
        generated_at=datetime.now(timezone.utc),
        model="research-model",
        sources=[ResearchSource(url="https://example.com/article", content_hash="hash")],
    )
    plan = SEOEngine(SEOSettings(output_directory=tmp_path), provider=FakeSEOProvider()).generate(research)

    assert plan.slug == "python-http-clients-guide"
    assert plan.primary_keyword == "Python HTTP clients"
    assert list(tmp_path.glob("*.json"))
