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
    assert settings.max_upload_mb == 50
    assert settings.max_archive_files == 10000
    assert settings.max_uncompressed_mb == 300
    assert settings.max_single_file_mb == 5
    assert settings.max_archive_path_length == 1024
    assert settings.max_archive_compression_ratio == 1000


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
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://service:configured@db.example:5432/codebase_rag")
    monkeypatch.setenv("DATABASE_POOL_SIZE", "13")
    monkeypatch.setenv("CORS_ORIGINS_STR", "https://ui.example,https://admin.example")
    monkeypatch.setenv("MAX_ARCHIVE_PATH_LENGTH", "512")
    monkeypatch.setenv("MAX_ARCHIVE_COMPRESSION_RATIO", "250")

    settings = Settings(_env_file=None)

    assert settings.app_env == "production"
    assert settings.database_pool_size == 13
    assert settings.cors_origins == ["https://ui.example", "https://admin.example"]
    assert settings.max_archive_path_length == 512
    assert settings.max_archive_compression_ratio == 250


@pytest.mark.parametrize(
    "values",
    [
        {"app_env": "preview"},
        {"llm_provider": "unsupported"},
        {"max_archive_files": 0},
        {"max_archive_compression_ratio": 0},
        {"embedding_provider": "remote_magic"},
        {"embedding_dimensions": "not-an-integer"},
    ],
)
def test_settings_reject_invalid_enum_and_numeric_values(values) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://postgres:postgres@localhost:5432/codebase_rag",
        "postgresql+psycopg://postgres:postgres@db:5432/codebase_rag",
    ],
)
def test_production_settings_reject_development_database_defaults(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError, match="DATABASE_URL must not use the development default") as exc_info:
        Settings(_env_file=None, app_env="production", database_url=database_url)

    assert "postgresql+psycopg://" not in str(exc_info.value)


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

