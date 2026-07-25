"""Provider construction boundary for the application engine."""

from bloggen.config.settings import Settings
from bloggen.providers.base import LLMProvider
from bloggen.providers.exceptions import ProviderConfigurationError
from bloggen.providers.openrouter import OpenRouterProvider


def create_provider(settings: Settings) -> LLMProvider:
    """Build the configured provider without exposing SDK details to the engine."""
    if settings.providers.active == "openrouter":
        return OpenRouterProvider(settings.providers.openrouter)
    raise ProviderConfigurationError(f"Unsupported active provider: {settings.providers.active}")
