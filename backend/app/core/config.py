import os
import json
from functools import lru_cache
from typing import Literal, Optional, Union, Annotated
from pydantic import Field, field_validator, BeforeValidator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

def parse_cors_origins(v: Union[str, list[str]]) -> list[str]:
    if isinstance(v, str):
        # Try to parse as JSON first, then fall back to comma-separated
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return [str(origin).strip() for origin in parsed]
        except (json.JSONDecodeError, TypeError):
            pass
        return [origin.strip() for origin in v.split(",")]
    return v

CorsOrigins = Annotated[list[str], BeforeValidator(parse_cors_origins)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    # Application
    app_env: Literal["development", "production", "test"] = "development"
    app_name: str = "Codebase RAG"
    api_prefix: str = "/api/v1"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # Database
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/codebase_rag"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # CORS
    cors_origins_str: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return parse_cors_origins(self.cors_origins_str)

    # Upload limits
    max_upload_mb: int = Field(default=50, ge=1)
    max_archive_files: int = Field(default=10000, ge=1)
    max_uncompressed_mb: int = Field(default=300, ge=1)
    max_single_file_mb: int = Field(default=5, ge=1)
    max_archive_path_length: int = Field(default=1024, ge=1)
    max_archive_compression_ratio: int = Field(default=1000, ge=1)
    max_dependency_queries: int = Field(default=1000, ge=1)
    max_dependency_advisories: int = Field(default=100, ge=1)
    osv_api_url: str = "https://api.osv.dev/v1/querybatch"
    osv_timeout_seconds: int = Field(default=5, ge=1, le=60)

    @model_validator(mode="after")
    def reject_default_database_url_in_production(self):
        if self.app_env == "production":
            database_url = make_url(self.database_url)
            if (
                self.database_url == "postgresql+psycopg://postgres:postgres@localhost:5432/codebase_rag"
                or (database_url.username == "postgres" and database_url.password == "postgres")
            ):
                raise ValueError("DATABASE_URL must not use the development default when APP_ENV=production")
        return self

    # Chunking
    chunk_size: int = 1200
    chunk_overlap: int = 150

    # Retrieval
    retrieval_top_k: int = 6

    # LLM Provider
    llm_provider: Literal["openai_compatible", "none"] = "none"
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_timeout_seconds: int = 60

    # Embedding Provider
    embedding_provider: Literal["openai_compatible", "sentence_transformers", "none"] = "none"
    embedding_base_url: Optional[str] = None
    embedding_api_key: Optional[str] = None
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    # AWS (optional, for cloud deployment)
    aws_region: Optional[str] = None
    s3_bucket: Optional[str] = None
    sqs_queue_url: Optional[str] = None

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def llm_configured(self) -> bool:
        return self.llm_provider == "openai_compatible" and bool(self.llm_base_url and self.llm_model)

    @property
    def embeddings_configured(self) -> bool:
        if self.embedding_provider == "openai_compatible":
            return bool(self.embedding_base_url and self.embedding_model)
        elif self.embedding_provider == "sentence_transformers":
            return True  # Local model, always available if dependencies installed
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
