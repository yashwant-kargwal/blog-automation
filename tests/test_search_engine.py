"""Search engine behavior tests without network access."""

from bloggen.research.engine import SearchEngine
from bloggen.research.models import SearchResult


def test_search_results_are_deduplicated_by_canonical_url() -> None:
    results = [
        SearchResult(rank=1, title="One", url="https://example.com/page?utm_source=test", source="example.com"),
        SearchResult(rank=2, title="Same", url="https://EXAMPLE.com/page/", source="example.com"),
    ]

    unique = SearchEngine._deduplicate(results)

    assert len(unique) == 1
    assert unique[0].rank == 1
