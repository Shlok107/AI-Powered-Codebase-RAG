import pytest
from pydantic import ValidationError

from app.core.config import Settings, parse_cors_origins


pytestmark = pytest.mark.unit


def test_settings_defaults_are_safe_for_local_optional_providers() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "test"
    assert settings.llm_provider == "none"
    assert settings.embedding_provider == "none"
    assert settings.embedding_dimensions == 384
    assert settings.cors_origins == ["http://localhost:5173"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('["https://app.example", "http://localhost:5173"]', ["https://app.example", "http://localhost:5173"]),
        ("https://app.example, http://localhost:5173", ["https://app.example", "http://localhost:5173"]),
        (["https://app.example"], ["https://app.example"]),
    ],
)
def test_cors_origins_support_json_comma_separated_and_list_values(raw, expected) -> None:
    assert parse_cors_origins(raw) == expected


def test_settings_parse_environment_values_without_loading_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_POOL_SIZE", "13")
    monkeypatch.setenv("CORS_ORIGINS_STR", "https://ui.example,https://admin.example")

    settings = Settings(_env_file=None)

    assert settings.app_env == "production"
    assert settings.database_pool_size == 13
    assert settings.cors_origins == ["https://ui.example", "https://admin.example"]


@pytest.mark.parametrize(
    "values",
    [
        {"app_env": "preview"},
        {"llm_provider": "unsupported"},
        {"embedding_provider": "remote_magic"},
        {"embedding_dimensions": "not-an-integer"},
    ],
)
def test_settings_reject_invalid_enum_and_numeric_values(values) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_provider_factories_fall_back_to_noop_when_openai_compatible_provider_is_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.embeddings as embeddings
    import app.services.llm as llm

    monkeypatch.setattr(
        embeddings,
        "settings",
        Settings(_env_file=None, embedding_provider="openai_compatible", embedding_base_url=None),
    )
    monkeypatch.setattr(
        llm,
        "settings",
        Settings(_env_file=None, llm_provider="openai_compatible", llm_base_url=None, llm_model=None),
    )

    assert isinstance(embeddings.create_embedding_provider(), embeddings.NoOpEmbeddingProvider)
    assert isinstance(llm.create_llm_provider(), llm.NoOpLLMProvider)

