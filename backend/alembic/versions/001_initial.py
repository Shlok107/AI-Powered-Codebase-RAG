"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2026-10-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create repositories table
    op.create_table(
        'repositories',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('source_type', sa.Enum('zip_upload', 'git_url', name='repository_source_type'), nullable=False),
        sa.Column('source_metadata', JSONB, nullable=False, server_default='{}'),
        sa.Column('status', sa.Enum('pending', 'processing', 'indexed', 'failed', name='repository_status'), nullable=False, server_default='pending'),
        sa.Column('detected_languages', JSONB, nullable=False, server_default='[]'),
        sa.Column('file_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('chunk_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('error_summary', sa.Text, nullable=True),
        sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_repositories_status', 'repositories', ['status'])
    op.create_index('ix_repositories_created_at', 'repositories', ['created_at'])

    # Create repository_files table
    op.create_table(
        'repository_files',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('repository_id', UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relative_path', sa.String(1024), nullable=False),
        sa.Column('language', sa.String(64), nullable=True),
        sa.Column('size_bytes', sa.BigInteger, nullable=False, server_default='0'),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('line_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('indexing_status', sa.String(32), nullable=False, server_default='pending'),
        sa.Column('skip_reason', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint('uq_repo_file_path', 'repository_files', ['repository_id', 'relative_path'])
    op.create_index('ix_repository_files_repository_id', 'repository_files', ['repository_id'])
    op.create_index('ix_repository_files_language', 'repository_files', ['language'])
    op.create_index('ix_repository_files_indexing_status', 'repository_files', ['indexing_status'])

    # Create code_chunks table
    op.create_table(
        'code_chunks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('repository_id', UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_id', UUID(as_uuid=True), sa.ForeignKey('repository_files.id', ondelete='CASCADE'), nullable=False),
        sa.Column('start_line', sa.Integer, nullable=False),
        sa.Column('end_line', sa.Integer, nullable=False),
        sa.Column('language', sa.String(64), nullable=True),
        sa.Column('chunk_type', sa.String(64), nullable=True),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.Column('chunk_metadata', JSONB, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_code_chunks_repository_id', 'code_chunks', ['repository_id'])
    op.create_index('ix_code_chunks_file_id', 'code_chunks', ['file_id'])
    op.create_index('ix_code_chunks_content_hash', 'code_chunks', ['content_hash'])

    # Create background_jobs table
    op.create_table(
        'background_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('repository_id', UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_type', sa.Enum('indexing', 'security_scan', name='job_type'), nullable=False),
        sa.Column('status', sa.Enum('queued', 'processing', 'completed', 'failed', name='job_status'), nullable=False, server_default='queued'),
        sa.Column('progress', sa.Integer, nullable=False, server_default='0'),
        sa.Column('total_items', sa.Integer, nullable=False, server_default='0'),
        sa.Column('processed_items', sa.Integer, nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_background_jobs_repository_id', 'background_jobs', ['repository_id'])
    op.create_index('ix_background_jobs_status', 'background_jobs', ['status'])
    op.create_index('ix_background_jobs_job_type', 'background_jobs', ['job_type'])

    # Create security_scans table
    op.create_table(
        'security_scans',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('repository_id', UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.Enum('queued', 'processing', 'completed', 'failed', name='scan_status'), nullable=False, server_default='queued'),
        sa.Column('findings_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('critical_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('high_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('medium_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('low_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('info_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('error_summary', sa.Text, nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_security_scans_repository_id', 'security_scans', ['repository_id'])
    op.create_index('ix_security_scans_status', 'security_scans', ['status'])

    # Create security_findings table
    op.create_table(
        'security_findings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('scan_id', UUID(as_uuid=True), sa.ForeignKey('security_scans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('repository_id', UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rule_id', sa.String(128), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('category', sa.Enum('secrets', 'dangerous_code', 'dependencies', 'infrastructure', 'configuration', name='finding_category'), nullable=False),
        sa.Column('severity', sa.Enum('critical', 'high', 'medium', 'low', 'info', name='finding_severity'), nullable=False),
        sa.Column('confidence', sa.Enum('high', 'medium', 'low', name='finding_confidence'), nullable=False),
        sa.Column('file_path', sa.String(1024), nullable=True),
        sa.Column('start_line', sa.Integer, nullable=True),
        sa.Column('end_line', sa.Integer, nullable=True),
        sa.Column('redacted_evidence', sa.Text, nullable=True),
        sa.Column('explanation', sa.Text, nullable=False),
        sa.Column('remediation', sa.Text, nullable=False),
        sa.Column('references', JSONB, nullable=False, server_default='[]'),
        sa.Column('status', sa.Enum('open', 'dismissed', 'resolved', name='finding_status'), nullable=False, server_default='open'),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_security_findings_scan_id', 'security_findings', ['scan_id'])
    op.create_index('ix_security_findings_repository_id', 'security_findings', ['repository_id'])
    op.create_index('ix_security_findings_rule_id', 'security_findings', ['rule_id'])
    op.create_index('ix_security_findings_severity', 'security_findings', ['severity'])
    op.create_index('ix_security_findings_category', 'security_findings', ['category'])
    op.create_index('ix_security_findings_status', 'security_findings', ['status'])
    op.create_index('ix_security_findings_file_path', 'security_findings', ['file_path'])
    op.create_unique_constraint('uq_finding_dedup', 'security_findings', ['scan_id', 'rule_id', 'file_path', 'start_line', 'content_hash'])

    # Create vector index for code_chunks (ivfflat for pgvector)
    # Note: This requires pgvector >= 0.5.0 and sufficient data
    # op.execute('CREATE INDEX ix_code_chunks_embedding ON code_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)')


def downgrade() -> None:
    op.drop_table('security_findings')
    op.drop_table('security_scans')
    op.drop_table('background_jobs')
    op.drop_table('code_chunks')
    op.drop_table('repository_files')
    op.drop_table('repositories')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS finding_status')
    op.execute('DROP TYPE IF EXISTS finding_confidence')
    op.execute('DROP TYPE IF EXISTS finding_severity')
    op.execute('DROP TYPE IF EXISTS finding_category')
    op.execute('DROP TYPE IF EXISTS scan_status')
    op.execute('DROP TYPE IF EXISTS job_status')
    op.execute('DROP TYPE IF EXISTS job_type')
    op.execute('DROP TYPE IF EXISTS repository_status')
    op.execute('DROP TYPE IF EXISTS repository_source_type')