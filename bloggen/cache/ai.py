"""Provider wrapper for reusable OpenRouter responses."""

import json
from collections.abc import Iterator

from loguru import logger

from bloggen.providers.base import LLMProvider
from bloggen.providers.models import ChatChunk, ChatRequest, ChatResponse
from bloggen.cache.store import CacheStore


class CachedLLMProvider:
    """Cache deterministic non-streaming completion requests by prompt hash."""

    def __init__(self, provider: LLMProvider, store: CacheStore) -> None:
        self.provider = provider
        self.store = store
        self.name = provider.name

    def complete(self, request: ChatRequest) -> ChatResponse:
        """Return a cached response or call the underlying provider."""
        key = self.store.key(self.name, request.model_dump_json())
        cached = self.store.get_json(key)
        if cached is not None:
            logger.info("AI response cache hit provider={} key={}", self.name, key[:12])
            return ChatResponse.model_validate(cached)
        response = self.provider.complete(request)
        self.store.set_json(key, json.loads(response.model_dump_json()))
        return response

    def stream(self, request: ChatRequest) -> Iterator[ChatChunk]:
        """Delegate streams without caching partial responses."""
        yield from self.provider.stream(request)
