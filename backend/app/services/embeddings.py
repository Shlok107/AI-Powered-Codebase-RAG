import asyncio
import hashlib
import os
from abc import ABC, abstractmethod
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimension."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name."""
        pass

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        pass

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        pass

    async def embed_batch(
        self, texts: list[str], batch_size: int = 32
    ) -> list[list[float]]:
        """Embed texts in batches with concurrency control."""
        results = []
        semaphore = asyncio.Semaphore(3)  # Limit concurrent requests

        async def embed_batch_chunk(chunk: list[str]) -> list[list[float]]:
            async with semaphore:
                return await self.embed_texts(chunk)

        tasks = [
            embed_batch_chunk(texts[i:i + batch_size])
            for i in range(0, len(texts), batch_size)
        ]

        for task in asyncio.as_completed(tasks):
            chunk_results = await task
            results.extend(chunk_results)

        return results


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """OpenAI-compatible embedding provider (e.g., OpenAI, Ollama, vLLM)."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self.timeout = timeout

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError)),
    )
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        url = f"{self.base_url}/embeddings"
        payload = {
            "model": self._model,
            "input": texts,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()

            # Extract embeddings from response
            embeddings = []
            for item in data.get("data", []):
                embedding = item.get("embedding", [])
                if len(embedding) != self._dimensions:
                    logger.warning(
                        "embedding_dimension_mismatch",
                        expected=self._dimensions,
                        got=len(embedding),
                    )
                embeddings.append(embedding)

            return embeddings

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed_texts([text])
        return embeddings[0] if embeddings else []


class SentenceTransformersEmbeddingProvider(EmbeddingProvider):
    """Local sentence-transformers embedding provider."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: Optional[str] = None,
    ):
        self._model_name = model_name
        self._device = device
        self._model = None
        self._dimensions = 384  # Default for all-MiniLM-L6-v2

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model_name

    def _load_model(self):
        """Lazy load the sentence-transformers model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                import torch

                device = self._device
                if device is None:
                    device = "cuda" if torch.cuda.is_available() else "cpu"

                self._model = SentenceTransformer(self._model_name, device=device)
                # Get actual dimensions
                self._dimensions = self._model.get_sentence_embedding_dimension()
                logger.info(
                    "sentence_transformer_loaded",
                    model=self._model_name,
                    device=device,
                    dimensions=self._dimensions,
                )
            except ImportError:
                raise RuntimeError(
                    "sentence-transformers not installed. Install with: pip install sentence-transformers"
                )
            except Exception as e:
                logger.error("sentence_transformer_load_failed", error_type=type(e).__name__)
                raise

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        self._load_model()

        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False).tolist()
        )

        return embeddings

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed_texts([text])
        return embeddings[0] if embeddings else []


class NoOpEmbeddingProvider(EmbeddingProvider):
    """No-op provider that returns zero vectors (for testing or when embeddings disabled)."""

    def __init__(self, dimensions: int = 384):
        self._dimensions = dimensions
        self._model_name = "noop"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model_name

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self._dimensions for _ in texts]

    async def embed_text(self, text: str) -> list[float]:
        return [0.0] * self._dimensions


def create_embedding_provider() -> EmbeddingProvider:
    """Factory function to create embedding provider from settings."""
    if settings.embedding_provider == "openai_compatible":
        if not settings.embedding_base_url or not settings.embedding_model:
            logger.warning("openai_compatible_embedding_provider_not_configured")
            return NoOpEmbeddingProvider(settings.embedding_dimensions)

        return OpenAICompatibleEmbeddingProvider(
            base_url=settings.embedding_base_url,
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            timeout=settings.llm_timeout_seconds,
        )

    elif settings.embedding_provider == "sentence_transformers":
        return SentenceTransformersEmbeddingProvider(
            model_name=settings.embedding_model,
        )

    else:
        return NoOpEmbeddingProvider(settings.embedding_dimensions)
