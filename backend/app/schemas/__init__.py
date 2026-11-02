from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class RepositoryBase(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)
    source_type: Literal["zip_upload", "git_url"] = "zip_upload"
    source_metadata: dict = Field(default_factory=dict)


class RepositoryCreate(RepositoryBase):
    pass


class RepositoryRead(RepositoryBase):
    id: UUID
    status: Literal["pending", "processing", "indexed", "failed"]
    detected_languages: list[str]
    file_count: int
    chunk_count: int
    error_summary: Optional[str] = None
    indexed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RepositoryDetail(RepositoryRead):
    pass


class RepositoryListResponse(BaseModel):
    repositories: list[RepositoryRead]
    total: int


class FileRead(BaseModel):
    id: UUID
    repository_id: UUID
    relative_path: str
    language: Optional[str] = None
    size_bytes: int
    content_hash: str
    line_count: int
    indexing_status: str
    skip_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileContentRequest(BaseModel):
    path: str = Field(..., min_length=1)
    start_line: Optional[int] = Field(None, ge=1)
    end_line: Optional[int] = Field(None, ge=1)


class FileContentResponse(BaseModel):
    path: str
    language: Optional[str] = None
    content: str
    start_line: int
    end_line: int
    total_lines: int


class ChunkRead(BaseModel):
    id: UUID
    repository_id: UUID
    file_id: UUID
    start_line: int
    end_line: int
    language: Optional[str] = None
    chunk_type: Optional[str] = None
    content_hash: str
    text: str
    metadata: dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobRead(BaseModel):
    id: UUID
    repository_id: UUID
    job_type: Literal["indexing", "security_scan"]
    status: Literal["queued", "processing", "completed", "failed"]
    progress: int
    total_items: int
    processed_items: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IndexRequest(BaseModel):
    force: bool = False


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000)
    conversation_id: Optional[UUID] = None


class Citation(BaseModel):
    chunk_id: UUID
    file_path: str
    start_line: int
    end_line: int
    language: Optional[str] = None
    relevance_score: Optional[float] = None
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    conversation_id: UUID
    model_used: Optional[str] = None
    retrieval_time_ms: Optional[int] = None
    generation_time_ms: Optional[int] = None


class ConversationRead(BaseModel):
    id: UUID
    repository_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageRead(BaseModel):
    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SecurityScanRead(BaseModel):
    id: UUID
    repository_id: UUID
    status: Literal["queued", "processing", "completed", "failed"]
    findings_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    error_summary: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SecurityFindingRead(BaseModel):
    id: UUID
    scan_id: UUID
    repository_id: UUID
    rule_id: str
    title: str
    category: Literal["secrets", "dangerous_code", "dependencies", "infrastructure", "configuration"]
    severity: Literal["critical", "high", "medium", "low", "info"]
    confidence: Literal["high", "medium", "low"]
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    redacted_evidence: Optional[str] = None
    explanation: str
    remediation: str
    references: list[str]
    status: Literal["open", "dismissed", "resolved"]
    content_hash: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FindingFilter(BaseModel):
    severity: Optional[list[str]] = None
    category: Optional[list[str]] = None
    file_path: Optional[str] = None
    status: Optional[list[str]] = None
    rule_id: Optional[str] = None


class FindingsListResponse(BaseModel):
    findings: list[SecurityFindingRead]
    total: int


class FindingUpdate(BaseModel):
    status: Literal["open", "dismissed", "resolved"]


class ScanRequest(BaseModel):
    pass


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    database: Literal["connected", "disconnected"]
    llm_provider: Literal["configured", "unconfigured"]
    embedding_provider: Literal["configured", "unconfigured"]
    timestamp: datetime


class ErrorResponse(BaseModel):
    error: dict