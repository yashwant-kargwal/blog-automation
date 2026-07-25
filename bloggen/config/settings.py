"""Validated application settings."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseModel):
    """Application identity and runtime mode."""

    model_config = ConfigDict(extra="ignore")

    name: str = "Bloggen"
    environment: str = "development"
    debug: bool = False


class LoggingSettings(BaseModel):
    """Logging configuration."""

    model_config = ConfigDict(extra="ignore")

    level: str = "INFO"
    log_directory: Path = Path("data/logs")
    error_file: str = "errors.log"
    debug_file: str = "debug.log"
    retention: str = "14 days"

    @field_validator("level")
    @classmethod
    def normalize_level(cls, value: str) -> str:
        normalized = value.upper()
        valid_levels = {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in valid_levels:
            raise ValueError(f"Unsupported log level: {value}")
        return normalized


class HTTPSettings(BaseModel):
    """HTTP client defaults."""

    model_config = ConfigDict(extra="ignore")

    base_url: str | None = None
    timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=3, ge=0)


class ProviderSettings(BaseModel):
    """Provider registry metadata used by the foundation CLI."""

    model_config = ConfigDict(extra="ignore")

    active: str = "openrouter"
    available: list[str] = Field(default_factory=lambda: ["openrouter"])
    openrouter: "OpenRouterSettings" = Field(default_factory=lambda: OpenRouterSettings())


class OpenRouterSettings(BaseModel):
    """OpenRouter connection settings."""

    model_config = ConfigDict(extra="ignore")

    api_key: SecretStr | None = None
    model: str = "openai/gpt-4o-mini"
    base_url: str = "https://openrouter.ai/api/v1"
    timeout_seconds: float = Field(default=60.0, gt=0)
    max_retries: int = Field(default=3, ge=0)
    app_name: str = "Bloggen"
    referer: str | None = None


ProviderSettings.model_rebuild()


class ResearchSettings(BaseModel):
    """Search engine defaults."""

    model_config = ConfigDict(extra="ignore")

    backends: list[str] = Field(default_factory=lambda: ["duckduckgo", "bing", "brave"], min_length=1)
    region: str = "us-en"
    safe_search: str = "moderate"
    default_top_n: int = Field(default=10, ge=1, le=100)
    default_depth: int = Field(default=1, ge=1, le=5)
    cache_directory: Path = Path("data/cache/search")
    cache_ttl_seconds: int = Field(default=86400, ge=0)
    timeout_seconds: float = Field(default=15.0, gt=0)
    output_directory: Path = Path("data/research")
    analysis_cache_ttl_seconds: int = Field(default=86400, ge=0)


class ScraperSettings(BaseModel):
    """Web scraper defaults."""

    model_config = ConfigDict(extra="ignore")

    timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=3, ge=0)
    retry_backoff_seconds: float = Field(default=0.5, ge=0)
    concurrency: int = Field(default=5, ge=1, le=20)
    cache_directory: Path = Path("data/cache/pages")
    cache_ttl_seconds: int = Field(default=86400, ge=0)
    user_agent: str = "Bloggen/0.1.0 (+https://github.com/bloggen/bloggen)"


class SEOSettings(BaseModel):
    """SEO planning defaults."""

    model_config = ConfigDict(extra="ignore")

    output_directory: Path = Path("data/seo")
    cache_ttl_seconds: int = Field(default=86400, ge=0)
    max_tokens: int = Field(default=8000, gt=0)


class WriterSettings(BaseModel):
    """Blog writing defaults and quality constraints."""

    model_config = ConfigDict(extra="ignore")

    default_style: str = "conversational"
    available_styles: list[str] = Field(default_factory=lambda: ["conversational", "technical", "editorial", "beginner-friendly", "how-to"], min_length=1)
    minimum_words: int = Field(default=1200, ge=300, le=20000)
    maximum_words: int = Field(default=3000, ge=300)
    max_tokens: int = Field(default=12000, gt=0)
    output_directory: Path = Path("data/blogs")
    cache_ttl_seconds: int = Field(default=86400, ge=0)

    @field_validator("maximum_words")
    @classmethod
    def maximum_must_cover_minimum(cls, value: int, info):
        minimum = info.data.get("minimum_words", 300)
        if value < minimum:
            raise ValueError("maximum_words must be greater than or equal to minimum_words")
        return value


class StorageSettings(BaseModel):
    """Project artifact storage defaults."""

    model_config = ConfigDict(extra="ignore")

    projects_directory: Path = Path("data/projects")
    timezone: str = "UTC"


class CacheSettings(BaseModel):
    """Shared cache defaults."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    directory: Path = Path("data/cache")
    ttl_seconds: int = Field(default=86400, ge=0)


class PipelineSettings(BaseModel):
    """Production pipeline defaults."""

    model_config = ConfigDict(extra="ignore")

    top_n: int = Field(default=10, ge=1, le=100)
    depth: int = Field(default=1, ge=1, le=5)
    max_articles: int = Field(default=5, ge=1, le=50)


class Settings(BaseSettings):
    """Complete Bloggen configuration."""

    model_config = SettingsConfigDict(
        env_prefix="BLOGGEN_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    http: HTTPSettings = Field(default_factory=HTTPSettings)
    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    research: ResearchSettings = Field(default_factory=ResearchSettings)
    scraper: ScraperSettings = Field(default_factory=ScraperSettings)
    seo: SEOSettings = Field(default_factory=SEOSettings)
    writer: WriterSettings = Field(default_factory=WriterSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
