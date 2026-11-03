import asyncio
import sys
import types

import httpx
import pytest

from app.services.embeddings import (
    NoOpEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    SentenceTransformersEmbeddingProvider,
)


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_noop_provider_returns_correct_dimensions_and_handles_empty_input() -> None:
    provider = NoOpEmbeddingProvider(dimensions=4)

    assert provider.model_name == "noop"
    assert provider.dimensions == 4
    assert await provider.embed_texts([]) == []
    assert await provider.embed_text("sample") == [0.0, 0.0, 0.0, 0.0]
    assert await provider.embed_batch(["a", "b"], batch_size=1) == [[0.0] * 4, [0.0] * 4]


@pytest.mark.asyncio
async def test_sentence_transformer_loads_lazily_and_returns_model_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class Encoded:
        def tolist(self):
            return [[0.25, -0.5, 1.0] for _ in captured["texts"]]

    class Model:
        def __init__(self, name: str, device: str):
            captured["model_name"] = name
            captured["device"] = device

        def get_sentence_embedding_dimension(self) -> int:
            return 3

        def encode(self, texts, **_kwargs):
            captured["texts"] = texts
            return Encoded()

    fake_transformers = types.SimpleNamespace(SentenceTransformer=Model)
    fake_torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False))
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_transformers)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    provider = SentenceTransformersEmbeddingProvider("local-test-model")

    assert provider._model is None
    assert provider.dimensions == 384
    vectors = await provider.embed_texts(["first", "second"])

    assert vectors == [[0.25, -0.5, 1.0], [0.25, -0.5, 1.0]]
    assert provider.dimensions == 3
    assert captured["model_name"] == "local-test-model"
    assert captured["device"] == "cpu"


@pytest.mark.asyncio
async def test_sentence_transformer_surfaces_model_loading_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenModel:
        def __init__(self, *_args, **_kwargs):
            raise OSError("model is unavailable")

    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=BrokenModel))
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False)))
    provider = SentenceTransformersEmbeddingProvider()

    with pytest.raises(OSError, match="model is unavailable"):
        await provider.embed_texts(["content"])


@pytest.mark.asyncio
async def test_openai_compatible_provider_sends_batch_payload_and_parses_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}

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

    monkeypatch.setattr("app.services.embeddings.httpx.AsyncClient", Client)
    provider = OpenAICompatibleEmbeddingProvider(
        "https://embedding.example/v1/", api_key="test-key", model="test-embed", dimensions=2
    )

    vectors = await provider.embed_texts(["alpha", "beta"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["url"] == "https://embedding.example/v1/embeddings"
    assert captured["payload"] == {"model": "test-embed", "input": ["alpha", "beta"]}
    assert captured["headers"]["Authorization"] == "Bearer test-key"


@pytest.mark.asyncio
async def test_openai_compatible_provider_returns_empty_for_empty_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_client(**_kwargs):
        raise AssertionError("empty input must not make a provider request")

    monkeypatch.setattr("app.services.embeddings.httpx.AsyncClient", unexpected_client)
    provider = OpenAICompatibleEmbeddingProvider("https://embedding.example", dimensions=2)

    assert await provider.embed_texts([]) == []


def test_sentence_transformer_class_reports_default_embedding_dimensions() -> None:
    provider = SentenceTransformersEmbeddingProvider()

    assert provider.dimensions == 384
    assert provider.model_name == "sentence-transformers/all-MiniLM-L6-v2"

