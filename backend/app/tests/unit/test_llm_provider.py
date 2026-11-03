import pytest

from app.services.llm import ChatMessage, NoOpLLMProvider, OpenAICompatibleLLMProvider


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_openai_compatible_llm_provider_serializes_messages_and_parses_response(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "model": "nemotron-test",
                "choices": [{"message": {"content": "Grounded answer [Source 1]."}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 19},
            }

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, *, json, headers):
            captured.update(url=url, payload=json, headers=headers)
            return Response()

    monkeypatch.setattr("app.services.llm.httpx.AsyncClient", Client)
    provider = OpenAICompatibleLLMProvider("https://nim.example/v1/", model="nvidia/nemotron-test")

    response = await provider.chat(
        [ChatMessage("system", "Answer from evidence."), ChatMessage("user", "Question")],
        temperature=0.2,
        max_tokens=256,
    )

    assert captured["url"] == "https://nim.example/v1/chat/completions"
    assert captured["payload"] == {
        "model": "nvidia/nemotron-test",
        "messages": [
            {"role": "system", "content": "Answer from evidence."},
            {"role": "user", "content": "Question"},
        ],
        "temperature": 0.2,
        "stream": False,
        "max_tokens": 256,
    }
    assert response.content == "Grounded answer [Source 1]."
    assert response.model == "nemotron-test"
    assert response.usage == {"total_tokens": 19}
    assert response.finish_reason == "stop"


@pytest.mark.asyncio
async def test_noop_llm_is_unavailable_and_returns_explicit_configuration_message() -> None:
    provider = NoOpLLMProvider()

    assert provider.model_name == "none"
    assert await provider.is_available() is False
    response = await provider.chat([ChatMessage("user", "Question")])
    assert "LLM provider is not configured" in response.content
    assert response.finish_reason == "not_configured"

