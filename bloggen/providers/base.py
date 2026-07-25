"""Provider-neutral language model interface."""

from collections.abc import Iterator
from typing import Protocol

from bloggen.providers.models import ChatChunk, ChatRequest, ChatResponse


class LLMProvider(Protocol):
    """Contract consumed by the future Bloggen engine.

    Provider adapters implement this protocol; engine code never imports an SDK
    or provider-specific settings class.
    """

    name: str

    def complete(self, request: ChatRequest) -> ChatResponse:
        """Return one normalized completion."""
        ...

    def stream(self, request: ChatRequest) -> Iterator[ChatChunk]:
        """Yield normalized completion chunks."""
        ...
