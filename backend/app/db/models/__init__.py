import enum
import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class RepositoryStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class RepositorySourceType(str, enum.Enum):
    ZIP_UPLOAD = "zip_upload"
    GIT_URL = "git_url"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, enum.Enum):
    INDEXING = "indexing"
    SECURITY_SCAN = "security_scan"


class ScanStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FindingSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingConfidence(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FindingStatus(str, enum.Enum):
    OPEN = "open"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


class FindingCategory(str, enum.Enum):
    SECRETS = "secrets"
    DANGEROUS_CODE = "dangerous_code"
    DEPENDENCIES = "dependencies"
    INFRASTRUCTURE = "infrastructure"
    CONFIGURATION = "configuration"


class Repository(Base, TimestampMixin):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[RepositorySourceType] = mapped_column(
        Enum(RepositorySourceType, values_callable=lambda x: [e.value for e in RepositorySourceType]),
        nullable=False
    )
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[RepositoryStatus] = mapped_column(
        Enum(RepositoryStatus, values_callable=lambda x: [e.value for e in RepositoryStatus]),
        default=RepositoryStatus.PENDING,
        nullable=False
    )
    detected_languages: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    files: Mapped[list["RepositoryFile"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    chunks: Mapped[list["CodeChunk"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    scans: Mapped[list["SecurityScan"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    jobs: Mapped[list["BackgroundJob"]] = relationship(back_populates="repository", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_repositories_status", "status"),
        Index("ix_repositories_created_at", "created_at"),
    )


class RepositoryFile(Base, TimestampMixin):
    __tablename__ = "repository_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    line_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    indexing_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    skip_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    repository: Mapped["Repository"] = relationship(back_populates="files")
    chunks: Mapped[list["CodeChunk"]] = relationship(back_populates="file", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("repository_id", "relative_path", name="uq_repo_file_path"),
        Index("ix_repository_files_repository_id", "repository_id"),
        Index("ix_repository_files_language", "language"),
        Index("ix_repository_files_indexing_status", "indexing_status"),
    )


class CodeChunk(Base, TimestampMixin):
    __tablename__ = "code_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repository_files.id", ondelete="CASCADE"), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    chunk_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384), nullable=True)
    chunk_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Relationships
    repository: Mapped["Repository"] = relationship(back_populates="chunks")
    file: Mapped["RepositoryFile"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_code_chunks_repository_id", "repository_id"),
        Index("ix_code_chunks_file_id", "file_id"),
        Index("ix_code_chunks_content_hash", "content_hash"),
        # Vector index will be created via migration
    )


class BackgroundJob(Base, TimestampMixin):
    __tablename__ = "background_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    job_type: Mapped[JobType] = mapped_column(
        Enum(JobType, values_callable=lambda x: [e.value for e in JobType]),
        nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, values_callable=lambda x: [e.value for e in JobStatus]),
        default=JobStatus.QUEUED,
        nullable=False
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    repository: Mapped["Repository"] = relationship(back_populates="jobs")

    __table_args__ = (
        Index("ix_background_jobs_repository_id", "repository_id"),
        Index("ix_background_jobs_status", "status"),
        Index("ix_background_jobs_job_type", "job_type"),
    )


class SecurityScan(Base, TimestampMixin):
    __tablename__ = "security_scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, values_callable=lambda x: [e.value for e in ScanStatus]),
        default=ScanStatus.QUEUED,
        nullable=False
    )
    findings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    high_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    medium_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    info_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    repository: Mapped["Repository"] = relationship(back_populates="scans")
    findings: Mapped[list["SecurityFinding"]] = relationship(back_populates="scan", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_security_scans_repository_id", "repository_id"),
        Index("ix_security_scans_status", "status"),
    )


class SecurityFinding(Base, TimestampMixin):
    __tablename__ = "security_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("security_scans.id", ondelete="CASCADE"), nullable=False)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[FindingCategory] = mapped_column(
        Enum(FindingCategory, values_callable=lambda x: [e.value for e in FindingCategory]),
        nullable=False
    )
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(FindingSeverity, values_callable=lambda x: [e.value for e in FindingSeverity]),
        nullable=False
    )
    confidence: Mapped[FindingConfidence] = mapped_column(
        Enum(FindingConfidence, values_callable=lambda x: [e.value for e in FindingConfidence]),
        nullable=False
    )
    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    start_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    redacted_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    remediation: Mapped[str] = mapped_column(Text, nullable=False)
    references: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[FindingStatus] = mapped_column(
        Enum(FindingStatus, values_callable=lambda x: [e.value for e in FindingStatus]),
        default=FindingStatus.OPEN,
        nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Relationships
    scan: Mapped["SecurityScan"] = relationship(back_populates="findings")
    repository: Mapped["Repository"] = relationship()

    __table_args__ = (
        Index("ix_security_findings_scan_id", "scan_id"),
        Index("ix_security_findings_repository_id", "repository_id"),
        Index("ix_security_findings_rule_id", "rule_id"),
        Index("ix_security_findings_severity", "severity"),
        Index("ix_security_findings_category", "category"),
        Index("ix_security_findings_status", "status"),
        Index("ix_security_findings_file_path", "file_path"),
        UniqueConstraint("scan_id", "rule_id", "file_path", "start_line", "content_hash", name="uq_finding_dedup"),
    )