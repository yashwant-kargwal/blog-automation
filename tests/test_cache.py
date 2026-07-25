"""Shared cache tests."""

from bloggen.cache.store import CacheStore


def test_cache_round_trip_and_cleanup(tmp_path) -> None:
    store = CacheStore(tmp_path, "ai", ttl_seconds=86400)
    key = store.key("model", "prompt")
    store.set_json(key, {"content": "cached"})

    assert store.get_json(key) == {"content": "cached"}
    assert store.stats()[0] == 1
    assert store.cleanup(expired_only=False) == 1
    assert store.get_json(key) is None
