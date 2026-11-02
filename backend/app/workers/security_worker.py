import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Repository, RepositoryFile, SecurityScan, SecurityFinding, ScanStatus, FindingSeverity, FindingConfidence, FindingCategory, FindingStatus
from app.services.security_rules import registry, Finding as RuleFinding
from app.services.storage import get_storage
from app.core.logging import get_logger

logger = get_logger(__name__)


class SecurityScanner:
    """Security scanner that runs all registered rules against repository files."""

    def __init__(self):
        self.rules = registry.get_all()

    async def scan(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        scan_id: uuid.UUID,
    ) -> None:
        """Run security scan on repository."""
        scan = await session.get(SecurityScan, scan_id)
        if not scan:
            logger.error("scan_not_found", scan_id=str(scan_id))
            return

        repository = await session.get(Repository, repository_id)
        if not repository:
            logger.error("repository_not_found", repository_id=str(repository_id))
            return

        scan.status = ScanStatus.PROCESSING
        from datetime import datetime
        scan.started_at = datetime.utcnow()
        await session.commit()

        try:
            # Get all files
            files_result = await session.execute(
                select(RepositoryFile).where(
                    RepositoryFile.repository_id == repository_id,
                    RepositoryFile.indexing_status == "completed"
                )
            )
            files = files_result.scalars().all()

            if not files:
                logger.info("no_files_to_scan", repository_id=str(repository_id))
                scan.status = ScanStatus.COMPLETED
                scan.completed_at = datetime.utcnow()
                await session.commit()
                return

            storage = get_storage()
            total_findings = 0
            severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

            for repo_file in files:
                try:
                    # Read file content
                    content = storage.read_file(repository_id, repo_file.relative_path)
                    if content is None:
                        continue

                    language = repo_file.language or "unknown"

                    # Run all rules
                    for rule in self.rules:
                        try:
                            rule_findings = rule.check(repo_file.relative_path, content, language)
                            for finding in rule_findings:
                                # Create content hash for deduplication
                                content_hash = self._compute_finding_hash(finding)

                                # Check for existing finding in this scan
                                existing = await session.execute(
                                    select(SecurityFinding).where(
                                        SecurityFinding.scan_id == scan_id,
                                        SecurityFinding.rule_id == finding.rule_id,
                                        SecurityFinding.file_path == finding.file_path,
                                        SecurityFinding.start_line == finding.start_line,
                                        SecurityFinding.content_hash == content_hash,
                                    )
                                )
                                if existing.scalar_one_or_none():
                                    continue  # Duplicate

                                # Create finding record
                                severity = FindingSeverity(finding.severity)
                                confidence = FindingConfidence(finding.confidence)
                                category = FindingCategory(finding.category)

                                severity_counts[severity.value] += 1
                                total_findings += 1

                                finding_record = SecurityFinding(
                                    scan_id=scan_id,
                                    repository_id=repository_id,
                                    rule_id=finding.rule_id,
                                    title=finding.title,
                                    category=category,
                                    severity=severity,
                                    confidence=confidence,
                                    file_path=finding.file_path,
                                    start_line=finding.start_line,
                                    end_line=finding.end_line,
                                    redacted_evidence=finding.evidence,
                                    explanation=finding.explanation,
                                    remediation=finding.remediation,
                                    references=finding.references,
                                    status=FindingStatus.OPEN,
                                    content_hash=content_hash,
                                )
                                session.add(finding_record)

                        except Exception as e:
                            logger.error(
                                "rule_check_failed",
                                rule_id=rule.rule_id,
                                file=repo_file.relative_path,
                                error=str(e),
                            )

                except Exception as e:
                    logger.error(
                        "file_scan_failed",
                        repository_id=str(repository_id),
                        file=repo_file.relative_path,
                        error=str(e),
                    )

            # Update scan summary
            scan.findings_count = total_findings
            scan.critical_count = severity_counts["critical"]
            scan.high_count = severity_counts["high"]
            scan.medium_count = severity_counts["medium"]
            scan.low_count = severity_counts["low"]
            scan.info_count = severity_counts["info"]
            scan.status = ScanStatus.COMPLETED
            scan.completed_at = datetime.utcnow()

            await session.commit()
            logger.info(
                "scan_completed",
                repository_id=str(repository_id),
                scan_id=str(scan_id),
                findings=total_findings,
            )

        except Exception as e:
            scan.status = ScanStatus.FAILED
            scan.error_summary = str(e)
            scan.completed_at = datetime.utcnow()
            await session.commit()
            logger.error("scan_failed", repository_id=str(repository_id), scan_id=str(scan_id), error=str(e))

    def _compute_finding_hash(self, finding: RuleFinding) -> str:
        """Compute hash for finding deduplication."""
        content = f"{finding.rule_id}:{finding.file_path}:{finding.start_line}:{finding.evidence}"
        return hashlib.sha256(content.encode()).hexdigest()


import hashlib
from datetime import datetime


async def run_security_scan_job(repository_id: str, scan_id: str | None = None) -> None:
    """Background job to run security scan."""
    from app.db.session import session_context

    async with session_context() as session:
        repo_uuid = uuid.UUID(repository_id)
        scan_uuid = uuid.UUID(scan_id) if scan_id else None

        repository = await session.get(Repository, repo_uuid)
        if not repository:
            logger.error("repository_not_found", repository_id=repository_id)
            return

        # Create scan if not provided
        if not scan_uuid:
            scan = SecurityScan(
                repository_id=repo_uuid,
                status=ScanStatus.QUEUED,
            )
            session.add(scan)
            await session.commit()
            await session.refresh(scan)
            scan_uuid = scan.id
        else:
            scan = await session.get(SecurityScan, scan_uuid)
            if not scan:
                logger.error("scan_not_found", scan_id=scan_id)
                return

        scanner = SecurityScanner()
        await scanner.scan(session, repo_uuid, scan_uuid)