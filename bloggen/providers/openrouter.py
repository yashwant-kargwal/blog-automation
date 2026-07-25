"""OpenRouter adapter using the OpenAI-compatible SDK."""

from collections.abc import Iterator
from time import sleep
from typing import Any

from loguru import logger
from openai import APIConnectionError, APIStatusError, APITimeoutError, InternalServerError, OpenAI, RateLimitError

from bloggen.config.settings import OpenRouterSettings
from bloggen.providers.exceptions import ProviderConfigurationError, ProviderRequestError, ProviderUnavailableError
from bloggen.providers.models import ChatChunk, ChatRequest, ChatResponse


class OpenRouterProvider:
    """OpenRouter implementation of the provider-neutral LLM contract."""

    name = "openrouter"

    def __init__(self, settings: OpenRouterSettings, client: OpenAI | None = None) -> None:
        if settings.api_key is None or not settings.api_key.get_secret_value().strip():
            raise ProviderConfigurationError("OPENROUTER_API_KEY is not configured.")
        self.settings = settings
        self.client = client or OpenAI(
            api_key=settings.api_key.get_secret_value(),
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
            max_retries=0,
            default_headers=self._default_headers(),
        )

    def _default_headers(self) -> dict[str, str]:
        headers = {"X-Title": self.settings.app_name}
        if self.settings.referer:
            headers["HTTP-Referer"] = self.settings.referer
        return headers

    def complete(self, request: ChatRequest) -> ChatResponse:
        """Execute a retried non-streaming completion."""
        response = self._call(request, stream=False)
        choice = response.choices[0]
        usage = response.usage
        return ChatResponse(
            content=choice.message.content or "",
            model=response.model,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )

    def stream(self, request: ChatRequest) -> Iterator[ChatChunk]:
        """Execute a retried streaming completion."""
        response = self._call(request, stream=True)
        for chunk in response:
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue
            delta = choice.delta.content or ""
            yield ChatChunk(content=delta, finish_reason=choice.finish_reason)

    def _call(self, request: ChatRequest, *, stream: bool) -> Any:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": [message.model_dump() for message in request.messages],
            "stream": stream,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        attempts = self.settings.max_retries + 1
        for attempt in range(attempts):
            try:
                logger.debug("OpenRouter request model={} stream={} attempt={}", self.settings.model, stream, attempt + 1)
                return self.client.chat.completions.create(**payload)
            except (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError) as exc:
                if attempt == attempts - 1:
                    logger.error("OpenRouter retries exhausted: {}", exc)
                    raise ProviderUnavailableError("OpenRouter is unavailable after retrying the request.") from exc
                delay = min(2**attempt, 8)
                logger.warning("OpenRouter request failed; retrying in {}s: {}", delay, exc)
                sleep(delay)
            except APIStatusError as exc:
                if exc.status_code >= 500 and attempt < attempts - 1:
                    delay = min(2**attempt, 8)
                    logger.warning("OpenRouter returned {}; retrying in {}s", exc.status_code, delay)
                    sleep(delay)
                    continue
                logger.error("OpenRouter rejected request with status {}", exc.status_code)
                raise ProviderRequestError(f"OpenRouter rejected the request with status {exc.status_code}.") from exc
            except Exception as exc:
                logger.exception("Unexpected OpenRouter error")
                raise ProviderRequestError("Unexpected error while calling OpenRouter.") from exc
        raise ProviderUnavailableError("OpenRouter request did not complete.")
