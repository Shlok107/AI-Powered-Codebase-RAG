import asyncio
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class ChatMessage:
    """A chat message."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class ChatResponse:
    """Response from chat completion."""
    content: str
    model: str
    usage: Optional[dict] = None
    finish_reason: Optional[str] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name."""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> ChatResponse:
        """Generate a chat completion."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is available."""
        pass


class OpenAICompatibleLLMProvider(LLMProvider):
    """OpenAI-compatible LLM provider (e.g., OpenAI, Ollama, vLLM, Nemotron)."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._model = model
        self.timeout = timeout

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
    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> ChatResponse:
        """Generate a chat completion."""
        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": False,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})

            return ChatResponse(
                content=message.get("content", ""),
                model=data.get("model", self._model),
                usage=data.get("usage"),
                finish_reason=choice.get("finish_reason"),
            )

    async def is_available(self) -> bool:
        """Check if the provider is available."""
        try:
            url = f"{self.base_url}/models"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self._get_headers())
                return response.status_code == 200
        except Exception:
            return False


class ExtractiveFallbackProvider(LLMProvider):
    """Extractive fallback that returns relevant source snippets when LLM is unavailable."""

    def __init__(self):
        self._model = "extractive-fallback"

    @property
    def model_name(self) -> str:
        return self._model

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> ChatResponse:
        """Return a fallback response indicating LLM is unavailable."""
        user_message = ""
        for msg in messages:
            if msg.role == "user":
                user_message = msg.content
                break

        fallback_content = (
            "I'm unable to generate an AI-powered answer because the LLM provider is not configured or unavailable. "
            "Here are the most relevant source code snippets from the repository that may help answer your question:\n\n"
        )

        # This will be populated by the caller with actual sources
        fallback_content += "[No LLM available - showing extractive fallback]"

        return ChatResponse(
            content=fallback_content,
            model=self._model,
            finish_reason="fallback",
        )

    async def is_available(self) -> bool:
        return True  # Always available as fallback


class NoOpLLMProvider(LLMProvider):
    """No-op provider that returns a clear error message."""

    def __init__(self):
        self._model = "none"

    @property
    def model_name(self) -> str:
        return self._model

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> ChatResponse:
        return ChatResponse(
            content=(
                "LLM provider is not configured. Please set LLM_PROVIDER=openai_compatible "
                "with LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL in your environment variables."
            ),
            model=self._model,
            finish_reason="not_configured",
        )

    async def is_available(self) -> bool:
        return False


def create_llm_provider() -> LLMProvider:
    """Factory function to create LLM provider from settings."""
    if settings.llm_provider == "openai_compatible":
        if not settings.llm_base_url or not settings.llm_model:
            logger.warning("openai_compatible_llm_provider_not_configured")
            return NoOpLLMProvider()

        return OpenAICompatibleLLMProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )

    else:
        return NoOpLLMProvider()