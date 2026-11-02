import os
import json
from functools import lru_cache
from typing import Literal, Optional, Union, Annotated
from pydantic import Field, field_validator, BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    max_upload_mb: int = 50
    max_archive_files: int = 10000
    max_uncompressed_mb: int = 300
    max_single_file_mb: int = 5

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