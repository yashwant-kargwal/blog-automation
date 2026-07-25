"""Stable provider exception types exposed to the engine."""


class ProviderError(RuntimeError):
    """Base class for provider failures."""


class ProviderConfigurationError(ProviderError):
    """Raised when a provider is not configured correctly."""


class ProviderRequestError(ProviderError):
    """Raised when a provider rejects a request."""


class ProviderUnavailableError(ProviderError):
    """Raised after retryable provider failures are exhausted."""
