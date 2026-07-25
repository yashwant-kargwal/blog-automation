"""Configuration foundation tests."""

from bloggen.config.loader import load_settings


def test_default_configuration_is_valid() -> None:
    settings = load_settings()

    assert settings.app.name == "Bloggen"
    assert settings.http.timeout_seconds == 30
    assert settings.logging.level == "INFO"
