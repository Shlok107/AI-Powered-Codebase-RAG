import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db.models import RepositoryStatus
from app.services.chat import ChatService, Citation
from app.services.llm import ChatResponse
from app.services.retrieval import RetrievedChunk, RetrievalService


pytestmark = pytest.mark.unit


def chunk(chunk_id: uuid.UUID, *, path: str = "", vector: float = 0.0, keyword: float = 0.0) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        file_path=path,
        start_line=4,
        end_line=8,
        language="python",
        text="def calculate(): return 42",
        chunk_type="function",
        vector_score=vector,
        keyword_score=keyword,
        combined_score=0.0,
        metadata={"name": "calculate"},
    )


def test_rrf_combines_rankings_deduplicates_and_limits_results() -> None:
    shared, vector_only, keyword_only = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service = RetrievalService(embedding_provider=object())

    ranked = service._reciprocal_rank_fusion(
        [chunk(shared, vector=0.9), chunk(vector_only, vector=0.8)],
        [chunk(shared, keyword=0.4), chunk(keyword_only, keyword=1.0)],
        top_k=2,
    )

    assert [item.chunk_id for item in ranked] == [shared, vector_only]
    assert ranked[0].combined_score == pytest.approx(2 / 61)
    assert ranked[0].vector_score == pytest.approx(0.9)
    assert ranked[0].keyword_score == pytest.approx(0.0)
    assert len({item.chunk_id for item in ranked}) == 2


def test_rrf_returns_empty_for_empty_search_results() -> None:
    service = RetrievalService(embedding_provider=object())

    assert service._reciprocal_rank_fusion([], [], top_k=6) == []


def test_rrf_ties_use_stable_path_order_and_dedup_preserves_cross_file_sources() -> None:
    service = RetrievalService(embedding_provider=object())
    first = chunk(uuid.uuid4(), path="a.py")
    second = chunk(uuid.uuid4(), path="b.py")
    tied = service._reciprocal_rank_fusion([second, first], [], top_k=2)
    assert [item.file_path for item in tied] == ["a.py", "b.py"]
    assert len(service._deduplicate([first, chunk(uuid.uuid4(), path="a.py"), second])) == 2


@pytest.mark.asyncio
async def test_keyword_only_retrieval_when_embedding_provider_returns_zero_vector() -> None:
    class ZeroEmbeddingProvider:
        async def embed_text(self, _text: str) -> list[float]:
            return [0.0, 0.0]

    service = RetrievalService(ZeroEmbeddingProvider())
    expected = [chunk(uuid.uuid4(), path="src/search.py", keyword=0.6)]
    service._keyword_search = AsyncMock(return_value=expected)

    result = await service.retrieve(AsyncMock(), uuid.uuid4(), "find search")

    assert result == expected
    service._keyword_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_retrieval_fuses_vector_and_keyword_results() -> None:
    shared, vector_only, keyword_only = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    class NonzeroEmbeddingProvider:
        async def embed_text(self, _text: str) -> list[float]:
            return [0.25, 0.75]

    service = RetrievalService(NonzeroEmbeddingProvider())
    service._vector_search = AsyncMock(return_value=[chunk(shared, vector=0.9), chunk(vector_only, vector=0.8)])
    service._keyword_search = AsyncMock(return_value=[chunk(shared, keyword=0.4), chunk(keyword_only, keyword=1.0)])

    results = await service.retrieve(AsyncMock(), uuid.uuid4(), "calculate", top_k=3)

    assert [item.chunk_id for item in results] == [shared, vector_only, keyword_only]
    service._vector_search.assert_awaited_once()
    service._keyword_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_file_path_enrichment_updates_actual_chunk_objects() -> None:
    chunk_id = uuid.uuid4()
    retrieved = chunk(chunk_id)
    session = AsyncMock()
    session.execute.return_value = [SimpleNamespace(id=chunk_id, relative_path="src/core.py")]
    service = RetrievalService(embedding_provider=object())

    enriched = await service.enrich_with_file_paths(session, [retrieved])

    assert enriched[0].file_path == "src/core.py"
    assert await service.enrich_with_file_paths(session, []) == []


def test_context_prompt_carries_real_file_lines_and_source_citation() -> None:
    service = ChatService(llm_provider=object(), embedding_provider=object())
    source = chunk(uuid.uuid4(), path="src/core.py", vector=0.72)

    prompt, citations = service._build_context_prompt("Where is calculate?", [source])

    assert "File: src/core.py" in prompt
    assert "Lines: 4-8" in prompt
    assert "def calculate()" in prompt
    assert citations == [
        Citation(
            chunk_id=source.chunk_id,
            file_path="src/core.py",
            start_line=4,
            end_line=8,
            language="python",
            relevance_score=0.72,
            excerpt=source.text,
        )
    ]


def test_citation_validation_keeps_only_citations_named_in_answer() -> None:
    service = ChatService(llm_provider=object(), embedding_provider=object())
    valid, omitted = Citation(uuid.uuid4(), "a.py", 1, 3, "python", 0.4, "pass"), Citation(
        uuid.uuid4(), "b.py", 5, 6, "python", 0.2, "return 2"
    )

    assert service._validate_citations("The implementation is here [Source 1].", [valid, omitted]) == [valid]


@pytest.mark.asyncio
async def test_repository_citation_validation_checks_ownership_path_lines_and_current_content(monkeypatch) -> None:
    repository_id, chunk_id = uuid.uuid4(), uuid.uuid4()
    citation = Citation(chunk_id, "src/core.py", 1, 1, "python", 0.4, "def calculate(): return 42")
    row = SimpleNamespace(id=chunk_id, relative_path="src/core.py", start_line=1,
                          end_line=1, text="def calculate(): return 42")
    session = AsyncMock()
    session.execute.return_value = [row]
    monkeypatch.setattr("app.services.chat.get_storage", lambda: SimpleNamespace(
        read_file=lambda _repo, _path: "def calculate(): return 42\n"))
    service = ChatService(llm_provider=object(), embedding_provider=object())

    answer, valid = await service._validate_citations_in_repository(
        session, repository_id, "Answer [Source 1]. [Source 9]", [citation]
    )
    assert valid == [citation]
    assert "[Source 1]" in answer
    assert "[unverified source]" in answer


@pytest.mark.asyncio
async def test_repository_citation_validation_rejects_stale_or_foreign_source(monkeypatch) -> None:
    repository_id, chunk_id = uuid.uuid4(), uuid.uuid4()
    citation = Citation(chunk_id, "src/core.py", 1, 1, "python", 0.4, "old source")
    row = SimpleNamespace(id=chunk_id, relative_path="src/core.py", start_line=1,
                          end_line=1, text="old source")
    session = AsyncMock()
    session.execute.return_value = [row]
    monkeypatch.setattr("app.services.chat.get_storage", lambda: SimpleNamespace(
        read_file=lambda _repo, _path: "new source\n"))
    service = ChatService(llm_provider=object(), embedding_provider=object())

    answer, valid = await service._validate_citations_in_repository(
        session, repository_id, "Claim [Source 1]", [citation]
    )
    assert valid == []
    assert "[unverified source]" in answer


@pytest.mark.asyncio
async def test_chat_service_uses_grounded_fallback_when_llm_is_unavailable() -> None:
    class UnavailableLLM:
        model_name = "test-provider"

        async def is_available(self) -> bool:
            return False

        async def chat(self, *_args, **_kwargs):
            raise AssertionError("unavailable provider must not receive a generation request")

    service = ChatService(llm_provider=UnavailableLLM(), embedding_provider=object())
    service.retrieval.retrieve = AsyncMock(return_value=[chunk(uuid.uuid4(), path="src/core.py")])
    service.retrieval.enrich_with_file_paths = AsyncMock(side_effect=lambda _s, chunks: chunks)
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(status=RepositoryStatus.INDEXED)

    result = await service.ask(session, uuid.uuid4(), "Where is calculate?")

    assert result.used_fallback is True
    assert "src/core.py:4-8" in result.answer
    assert len(result.citations) == 1


@pytest.mark.asyncio
async def test_chat_abstains_without_sources_without_calling_llm() -> None:
    class MustNotCallLLM:
        model_name = "test-provider"

        async def is_available(self) -> bool:
            raise AssertionError("LLM availability should not be checked without evidence")

        async def chat(self, *_args, **_kwargs):
            raise AssertionError("LLM must not be called without evidence")

    service = ChatService(llm_provider=MustNotCallLLM(), embedding_provider=object())
    service.retrieval.retrieve = AsyncMock(return_value=[])
    service.retrieval.enrich_with_file_paths = AsyncMock(return_value=[])
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(status=RepositoryStatus.INDEXED)

    result = await service.ask(session, uuid.uuid4(), "Question not supported by evidence")

    assert "couldn't find relevant source evidence" in result.answer
    assert result.citations == []


@pytest.mark.asyncio
async def test_chat_service_propagates_llm_provider_failure() -> None:
    class FailingLLM:
        model_name = "test-provider"

        async def is_available(self) -> bool:
            return True

        async def chat(self, *_args, **_kwargs):
            raise RuntimeError("provider unavailable")

    service = ChatService(llm_provider=FailingLLM(), embedding_provider=object())
    service.retrieval.retrieve = AsyncMock(
        return_value=[chunk(uuid.uuid4(), path="src/core.py")]
    )
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(status=RepositoryStatus.INDEXED)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await service.ask(session, uuid.uuid4(), "question")

