import time
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Repository, CodeChunk, CodeChunk
from app.services.retrieval import RetrievalService
from app.services.llm import LLMProvider, ChatMessage, create_llm_provider, ExtractiveFallbackProvider
from app.services.embeddings import create_embedding_provider
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Citation:
    """A citation linking answer to source code."""
    chunk_id: uuid.UUID
    file_path: str
    start_line: int
    end_line: int
    language: Optional[str]
    relevance_score: Optional[float]
    excerpt: str


@dataclass
class ChatResult:
    """Result of a chat query."""
    answer: str
    citations: list[Citation]
    model_used: str
    retrieval_time_ms: int
    generation_time_ms: int
    used_fallback: bool


class ChatService:
    """Grounded code Q&A service with retrieval and LLM."""

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        embedding_provider=None,
    ):
        self.llm_provider = llm_provider or create_llm_provider()
        self.embedding_provider = embedding_provider or create_embedding_provider()
        self.retrieval = RetrievalService(self.embedding_provider)

    # System prompt for grounded code Q&A
    SYSTEM_PROMPT = """You are a code intelligence assistant. Your task is to answer questions about a codebase using ONLY the provided source code snippets as evidence.

Rules:
1. Answer ONLY from the supplied repository evidence. Do not use external knowledge.
2. If the evidence is insufficient, say so clearly.
3. Every code-specific claim MUST be accompanied by a citation to the provided sources.
4. Citations must reference the exact file path and line range from the sources.
5. Distinguish between what the code shows and what you infer.
6. If you cannot find relevant information in the sources, say "I couldn't find information about this in the provided code."
7. Never invent file paths, line numbers, symbols, tests, or security findings.
8. Keep answers concise and focused on the question.

The sources provided are from the user's repository. Each source shows the file path, line range, and code excerpt."""

    def _build_context_prompt(
        self,
        question: str,
        retrieved_chunks: list,
    ) -> tuple[str, list[Citation]]:
        """Build the context prompt with sources and prepare citations."""
        if not retrieved_chunks:
            return (
                f"Question: {question}\n\nNo relevant sources found in the repository.",
                []
            )

        sources_text = []
        citations = []

        for i, chunk in enumerate(retrieved_chunks):
            # Create excerpt (first 500 chars of chunk)
            excerpt = chunk.text[:500]
            if len(chunk.text) > 500:
                excerpt += "..."

            source_block = (
                f"[Source {i + 1}]\n"
                f"File: {chunk.file_path}\n"
                f"Lines: {chunk.start_line}-{chunk.end_line}\n"
                f"Language: {chunk.language or 'unknown'}\n"
                f"Code:\n```\n{excerpt}\n```\n"
            )
            sources_text.append(source_block)

            citations.append(Citation(
                chunk_id=chunk.chunk_id,
                file_path=chunk.file_path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                language=chunk.language,
                relevance_score=chunk.combined_score if chunk.combined_score > 0 else chunk.vector_score,
                excerpt=excerpt,
            ))

        context = (
            f"Question: {question}\n\n"
            f"Repository Sources:\n"
            f"{'=' * 50}\n"
            f"{chr(10).join(sources_text)}\n"
            f"{'=' * 50}\n\n"
            f"Answer the question using ONLY the sources above. Cite sources using [Source N] format."
        )

        return context, citations

    def _validate_citations(self, answer: str, citations: list[Citation]) -> list[Citation]:
        """Validate that cited sources actually exist in the answer."""
        # Simple validation: check if [Source N] references in answer match available citations
        valid_citations = []
        for i, citation in enumerate(citations):
            source_ref = f"[Source {i + 1}]"
            if source_ref in answer:
                valid_citations.append(citation)
            else:
                logger.warning("citation_not_used_in_answer", source=i + 1)

        return valid_citations

    async def ask(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        question: str,
        conversation_history: Optional[list[ChatMessage]] = None,
    ) -> ChatResult:
        """Ask a question about the repository and get a grounded answer."""
        start_time = time.time()

        # Check if repository exists
        repo = await session.get(Repository, repository_id)
        if not repo:
            raise ValueError(f"Repository {repository_id} not found")

        # Check if repository is indexed
        if repo.status.value != "indexed":
            raise ValueError(f"Repository is not indexed (status: {repo.status.value})")

        retrieval_start = time.time()

        # Retrieve relevant chunks
        retrieved_chunks = await self.retrieval.retrieve(
            session, repository_id, question
        )

        # Enrich with file paths
        retrieved_chunks = await self.retrieval.enrich_with_file_paths(
            session, retrieved_chunks
        )

        retrieval_time_ms = int((time.time() - retrieval_start) * 1000)

        # Build context and citations
        context, citations = self._build_context_prompt(question, retrieved_chunks)

        # Prepare messages
        messages = [ChatMessage(role="system", content=self.SYSTEM_PROMPT)]

        # Add conversation history if provided (bounded)
        if conversation_history:
            # Keep last 4 messages to stay within context
            for msg in conversation_history[-4:]:
                messages.append(msg)

        messages.append(ChatMessage(role="user", content=context))

        generation_start = time.time()

        # Check if LLM is available
        llm_available = await self.llm_provider.is_available()

        if not llm_available:
            # Use extractive fallback
            logger.info("using_extractive_fallback", repository_id=str(repository_id))
            fallback_provider = ExtractiveFallbackProvider()

            # Build extractive response with sources
            if citations:
                fallback_answer = (
                    f"I couldn't generate an AI answer (LLM provider unavailable). "
                    f"Here are the most relevant code snippets for your question:\n\n"
                )
                for i, citation in enumerate(citations):
                    fallback_answer += (
                        f"**Source {i + 1}**: `{citation.file_path}:{citation.start_line}-{citation.end_line}`\n"
                        f"```{citation.language or ''}\n{citation.excerpt}\n```\n\n"
                    )
                fallback_answer += (
                    "\n*Configure an LLM provider (LLM_PROVIDER=openai_compatible) for AI-powered answers.*"
                )
            else:
                fallback_answer = (
                    "I couldn't find relevant code in the repository for your question. "
                    "The LLM provider is also not configured, so I cannot generate an answer."
                )

            generation_time_ms = int((time.time() - generation_start) * 1000)

            return ChatResult(
                answer=fallback_answer,
                citations=citations,
                model_used=f"{self.llm_provider.model_name} (fallback)",
                retrieval_time_ms=retrieval_time_ms,
                generation_time_ms=generation_time_ms,
                used_fallback=True,
            )

        # Generate LLM response
        response = await self.llm_provider.chat(messages, temperature=0.1, max_tokens=2000)

        generation_time_ms = int((time.time() - generation_start) * 1000)

        # Validate citations against answer
        validated_citations = self._validate_citations(response.content, citations)

        logger.info(
            "chat_completed",
            repository_id=str(repository_id),
            question_length=len(question),
            answer_length=len(response.content),
            citations=len(validated_citations),
            retrieval_time_ms=retrieval_time_ms,
            generation_time_ms=generation_time_ms,
            model=response.model,
            used_fallback=False,
        )

        return ChatResult(
            answer=response.content,
            citations=validated_citations,
            model_used=response.model,
            retrieval_time_ms=retrieval_time_ms,
            generation_time_ms=generation_time_ms,
            used_fallback=False,
        )