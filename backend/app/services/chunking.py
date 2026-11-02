import ast
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class CodeChunk:
    """Represents a chunk of source code with metadata."""
    file_path: str
    start_line: int
    end_line: int
    language: str
    chunk_type: str
    text: str
    content_hash: str
    metadata: dict


class PythonChunker:
    """AST-aware chunker for Python files."""

    def __init__(self, chunk_size: int = 1200, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, file_path: str, content: str) -> list[CodeChunk]:
        """Chunk Python code using AST to identify functions, classes, etc."""
        chunks = []
        lines = content.splitlines()

        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Fall back to line-based chunking for invalid syntax
            return self._fallback_chunk(file_path, content, "python")

        # Extract top-level nodes (functions, classes, async functions)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Only process top-level definitions (not nested)
                if not self._is_nested(node, tree):
                    chunk = self._create_chunk_from_node(file_path, content, lines, node)
                    if chunk:
                        chunks.append(chunk)

        # If no AST chunks found or content between chunks, add fallback chunks
        if not chunks:
            return self._fallback_chunk(file_path, content, "python")

        # Sort by start line
        chunks.sort(key=lambda c: c.start_line)

        # Fill gaps between chunks with fallback chunks
        return self._fill_gaps(file_path, content, lines, chunks, "python")

    def _is_nested(self, node: ast.AST, tree: ast.AST) -> bool:
        """Check if a node is nested inside another function/class."""
        for parent in ast.walk(tree):
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if parent is not node:
                    # Check if node is in parent's body
                    for child in ast.iter_child_nodes(parent):
                        if child is node or (hasattr(node, 'lineno') and hasattr(child, 'lineno') and
                                             child.lineno <= node.lineno <= getattr(child, 'end_lineno', child.lineno)):
                            return True
        return False

    def _create_chunk_from_node(
        self, file_path: str, content: str, lines: list[str], node: ast.AST
    ) -> Optional[CodeChunk]:
        """Create a chunk from an AST node."""
        start_line = node.lineno
        end_line = getattr(node, 'end_lineno', start_line)

        # Get the source text for this node
        chunk_lines = lines[start_line - 1:end_line]
        chunk_text = "\n".join(chunk_lines)

        if not chunk_text.strip():
            return None

        # Determine chunk type
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chunk_type = "function"
            name = node.name
        elif isinstance(node, ast.ClassDef):
            chunk_type = "class"
            name = node.name
        else:
            chunk_type = "unknown"
            name = "unknown"

        content_hash = hashlib.sha256(chunk_text.encode()).hexdigest()

        return CodeChunk(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            language="python",
            chunk_type=chunk_type,
            text=chunk_text,
            content_hash=content_hash,
            metadata={"name": name},
        )

    def _fill_gaps(
        self, file_path: str, content: str, lines: list[str],
        chunks: list[CodeChunk], language: str
    ) -> list[CodeChunk]:
        """Fill gaps between AST chunks with line-based chunks."""
        result = []
        last_end = 0

        for chunk in chunks:
            # Add gap before this chunk
            if chunk.start_line > last_end + 1:
                gap_chunks = self._create_line_chunks(
                    file_path, lines, last_end + 1, chunk.start_line - 1, language
                )
                result.extend(gap_chunks)

            result.append(chunk)
            last_end = chunk.end_line

        # Add remaining content after last chunk
        if last_end < len(lines):
            gap_chunks = self._create_line_chunks(
                file_path, lines, last_end + 1, len(lines), language
            )
            result.extend(gap_chunks)

        return result

    def _create_line_chunks(
        self, file_path: str, lines: list[str], start: int, end: int, language: str
    ) -> list[CodeChunk]:
        """Create overlapping line-based chunks for a range."""
        chunks = []
        chunk_lines = lines[start - 1:end]
        total_lines = len(chunk_lines)

        if total_lines == 0:
            return chunks

        # If small enough, single chunk
        if total_lines <= self.chunk_size:
            chunk_text = "\n".join(chunk_lines)
            content_hash = hashlib.sha256(chunk_text.encode()).hexdigest()
            return [CodeChunk(
                file_path=file_path,
                start_line=start,
                end_line=end,
                language=language,
                chunk_type="block",
                text=chunk_text,
                content_hash=content_hash,
                metadata={},
            )]

        # Otherwise create overlapping chunks
        for i in range(0, total_lines, self.chunk_size - self.chunk_overlap):
            chunk_end = min(i + self.chunk_size, total_lines)
            chunk_text = "\n".join(chunk_lines[i:chunk_end])

            if not chunk_text.strip():
                continue

            chunk_start = start + i
            chunk_end_line = start + chunk_end - 1
            content_hash = hashlib.sha256(chunk_text.encode()).hexdigest()

            chunks.append(CodeChunk(
                file_path=file_path,
                start_line=chunk_start,
                end_line=chunk_end_line,
                language=language,
                chunk_type="block",
                text=chunk_text,
                content_hash=content_hash,
                metadata={},
            ))

            if chunk_end == total_lines:
                break

        return chunks

    def _fallback_chunk(self, file_path: str, content: str, language: str) -> list[CodeChunk]:
        """Fallback to simple line-based chunking."""
        lines = content.splitlines()
        return self._create_line_chunks(file_path, lines, 1, len(lines), language)


class LineChunker:
    """Fallback line-based chunker for non-Python files."""

    def __init__(self, chunk_size: int = 1200, chunk_overlap: int = 150, language: str = "unknown"):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.language = language

    def chunk(self, file_path: str, content: str) -> list[CodeChunk]:
        """Chunk content by lines with overlap."""
        lines = content.splitlines()
        return self._create_line_chunks(file_path, lines, 1, len(lines), self.language)

    def _create_line_chunks(
        self, file_path: str, lines: list[str], start: int, end: int, language: str
    ) -> list[CodeChunk]:
        chunks = []
        chunk_lines = lines[start - 1:end]
        total_lines = len(chunk_lines)

        if total_lines == 0:
            return chunks

        if total_lines <= self.chunk_size:
            chunk_text = "\n".join(chunk_lines)
            content_hash = hashlib.sha256(chunk_text.encode()).hexdigest()
            return [CodeChunk(
                file_path=file_path,
                start_line=start,
                end_line=end,
                language=language,
                chunk_type="block",
                text=chunk_text,
                content_hash=content_hash,
                metadata={},
            )]

        for i in range(0, total_lines, self.chunk_size - self.chunk_overlap):
            chunk_end = min(i + self.chunk_size, total_lines)
            chunk_text = "\n".join(chunk_lines[i:chunk_end])

            if not chunk_text.strip():
                continue

            chunk_start = start + i
            chunk_end_line = start + chunk_end - 1
            content_hash = hashlib.sha256(chunk_text.encode()).hexdigest()

            chunks.append(CodeChunk(
                file_path=file_path,
                start_line=chunk_start,
                end_line=chunk_end_line,
                language=language,
                chunk_type="block",
                text=chunk_text,
                content_hash=content_hash,
                metadata={},
            ))

            if chunk_end == total_lines:
                break

        return chunks


def get_chunker(language: str, chunk_size: int = None, chunk_overlap: int = None) -> PythonChunker | LineChunker:
    """Get appropriate chunker for a language."""
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap

    if language == "python":
        return PythonChunker(chunk_size, chunk_overlap)
    return LineChunker(chunk_size, chunk_overlap, language=language)