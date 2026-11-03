import uuid
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CodeChunk
from app.services.embeddings import EmbeddingProvider
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class RetrievedChunk:
    """A retrieved chunk with relevance scoring."""
    chunk_id: uuid.UUID
    file_path: str
    start_line: int
    end_line: int
    language: Optional[str]
    text: str
    chunk_type: Optional[str]
    vector_score: float
    keyword_score: float
    combined_score: float
    metadata: dict


class RetrievalService:
    """Hybrid retrieval combining vector similarity and keyword search."""

    def __init__(self, embedding_provider: EmbeddingProvider):
        self.embedding_provider = embedding_provider
        self.top_k = settings.retrieval_top_k

    @staticmethod
    def _deduplicate(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        unique: list[RetrievedChunk] = []
        seen: set[str] = set()
        for chunk in chunks:
            content = re.sub(r"\s+", " ", chunk.text).strip()
            key = f"{chunk.file_path}:{content}" if content and chunk.file_path else str(chunk.chunk_id)
            if key in seen:
                continue
            seen.add(key)
            unique.append(chunk)
        return unique

    async def retrieve(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        query: str,
        top_k: Optional[int] = None,
    ) -> list[RetrievedChunk]:
        """
        Retrieve relevant chunks using hybrid vector + keyword search.

        Strategy:
        1. Vector similarity search (cosine similarity)
        2. PostgreSQL full-text search (tsvector)
        3. Combine scores using reciprocal rank fusion (RRF)
        """
        k = top_k if top_k is not None else self.top_k
        if k < 1:
            raise ValueError("top_k must be positive")

        # Generate query embedding
        query_embedding = await self.embedding_provider.embed_text(query)

        if not query_embedding or all(v == 0.0 for v in query_embedding):
            # Fallback to keyword-only search if no embeddings
            keyword_results = await self._keyword_search(session, repository_id, query, k)
            keyword_results = await self.enrich_with_file_paths(session, keyword_results)
            return self._deduplicate(keyword_results)

        # Vector search
        vector_results = await self._vector_search(
            session, repository_id, query_embedding, k * 2
        )

        # Keyword search
        keyword_results = await self._keyword_search(session, repository_id, query, k * 2)

        # Combine using Reciprocal Rank Fusion
        combined = self._reciprocal_rank_fusion(vector_results, keyword_results, k)

        # Resolve paths before deduplication: identical code in different files
        # represents distinct sources and must remain separately citable.
        combined = await self.enrich_with_file_paths(session, combined)
        return self._deduplicate(combined)

    async def _vector_search(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        query_embedding: list[float],
        limit: int,
    ) -> list[RetrievedChunk]:
        """Perform vector similarity search using pgvector."""
        # Convert embedding to pgvector format
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        # Use cosine similarity (1 - cosine_distance)
        sql = text("""
            SELECT
                id,
                file_id,
                start_line,
                end_line,
                language,
                chunk_type,
                text,
                chunk_metadata,
                1 - (embedding <=> :embedding) as vector_score
            FROM code_chunks
            WHERE repository_id = :repo_id
              AND embedding IS NOT NULL
            ORDER BY embedding <=> :embedding
            LIMIT :limit
        """)

        result = await session.execute(
            sql,
            {
                "repo_id": repository_id,
                "embedding": embedding_str,
                "limit": limit,
            }
        )

        chunks = []
        for row in result:
            chunks.append(RetrievedChunk(
                chunk_id=row.id,
                file_path="",  # Will be filled later
                start_line=row.start_line,
                end_line=row.end_line,
                language=row.language,
                text=row.text,
                chunk_type=row.chunk_type,
                vector_score=float(row.vector_score),
                keyword_score=0.0,
                combined_score=0.0,
                metadata=row.chunk_metadata or {},
            ))

        return chunks

    async def _keyword_search(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        query: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        """Perform PostgreSQL full-text search."""
        # Use plainto_tsquery for simple keyword matching
        # We search in text and file_path via tsvector
        sql = text("""
            SELECT
                id,
                file_id,
                start_line,
                end_line,
                language,
                chunk_type,
                text,
                chunk_metadata,
                ts_rank_cd(
                    to_tsvector('english', text),
                    plainto_tsquery('english', :query)
                ) as keyword_score
            FROM code_chunks
            WHERE repository_id = :repo_id
              AND to_tsvector('english', text) @@ plainto_tsquery('english', :query)
            ORDER BY keyword_score DESC
            LIMIT :limit
        """)

        result = await session.execute(
            sql,
            {
                "repo_id": repository_id,
                "query": query,
                "limit": limit,
            }
        )

        chunks = []
        for row in result:
            chunks.append(RetrievedChunk(
                chunk_id=row.id,
                file_path="",
                start_line=row.start_line,
                end_line=row.end_line,
                language=row.language,
                text=row.text,
                chunk_type=row.chunk_type,
                vector_score=0.0,
                keyword_score=float(row.keyword_score),
                combined_score=0.0,
                metadata=row.chunk_metadata or {},
            ))

        return chunks

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[RetrievedChunk],
        keyword_results: list[RetrievedChunk],
        top_k: int,
        k: int = 60,
    ) -> list[RetrievedChunk]:
        """
        Combine results using Reciprocal Rank Fusion (RRF).

        RRF score = sum(1 / (k + rank)) for each result in each list
        """
        # Create ranking maps
        vector_ranks = {chunk.chunk_id: i + 1 for i, chunk in enumerate(vector_results)}
        keyword_ranks = {chunk.chunk_id: i + 1 for i, chunk in enumerate(keyword_results)}

        # Collect all unique chunks and remember stable first-seen rank order.
        all_chunks = {}
        first_seen_order = {}
        for position, chunk in enumerate(vector_results + keyword_results):
            if chunk.chunk_id not in all_chunks:
                all_chunks[chunk.chunk_id] = chunk
                first_seen_order[chunk.chunk_id] = position

        # Calculate RRF scores
        for chunk_id, chunk in all_chunks.items():
            vector_rank = vector_ranks.get(chunk_id)
            keyword_rank = keyword_ranks.get(chunk_id)

            rrf_score = 0.0
            if vector_rank:
                rrf_score += 1.0 / (k + vector_rank)
            if keyword_rank:
                rrf_score += 1.0 / (k + keyword_rank)

            chunk.combined_score = rrf_score
            # Keep original scores for debugging
            if vector_rank:
                chunk.vector_score = chunk.vector_score
            if keyword_rank:
                chunk.keyword_score = chunk.keyword_score

        # Sort by combined score and take top_k
        def tie_breaker(chunk: RetrievedChunk) -> tuple:
            # When paths are available, use them for a deterministic lexical
            # order. Before enrichment, preserve the original retrieval rank.
            if chunk.file_path:
                return (0, chunk.file_path, chunk.start_line, str(chunk.chunk_id))
            return (1, first_seen_order[chunk.chunk_id])

        sorted_chunks = sorted(
            all_chunks.values(),
            key=lambda c: (-c.combined_score, tie_breaker(c)),
        )

        return sorted_chunks[:top_k]

    async def enrich_with_file_paths(
        self,
        session: AsyncSession,
        chunks: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        """Enrich chunks with file paths by joining with repository_files."""
        if not chunks:
            return chunks

        chunk_ids = [c.chunk_id for c in chunks]

        # Use a subquery approach to avoid IN clause issues with tuples
        placeholders = ", ".join([f":chunk_id_{i}" for i in range(len(chunk_ids))])
        sql = text(f"""
            SELECT cc.id, rf.relative_path
            FROM code_chunks cc
            JOIN repository_files rf ON cc.file_id = rf.id
            WHERE cc.id IN ({placeholders})
        """)

        params = {f"chunk_id_{i}": chunk_id for i, chunk_id in enumerate(chunk_ids)}
        result = await session.execute(sql, params)
        path_map = {row.id: row.relative_path for row in result}

        for chunk in chunks:
            chunk.file_path = path_map.get(chunk.chunk_id, chunk.file_path)

        return chunks
