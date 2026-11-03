import hashlib
import uuid

import pytest
from sqlalchemy import select

from app.db.models import (
    FindingSeverity,
    RepositoryFile,
    RepositoryStatus,
    ScanStatus,
    SecurityFinding,
    SecurityScan,
)
from app.services.storage import RepositoryStorage
from app.workers.security_worker import SecurityScanner


pytestmark = [pytest.mark.integration, pytest.mark.database]


@pytest.mark.asyncio
async def test_security_scanner_persists_rule_findings_with_exact_location_and_counts(
    db_session, repository_factory, monkeypatch, tmp_path
) -> None:
    source = "# safe context\nvalue = eval(user_input)\n"
    repository = repository_factory(status=RepositoryStatus.INDEXED, file_count=1)
    scan = SecurityScan(repository_id=repository.id, status=ScanStatus.QUEUED)
    file = RepositoryFile(
        repository_id=repository.id,
        relative_path="src/unsafe.py",
        language="python",
        size_bytes=len(source.encode()),
        content_hash=hashlib.sha256(source.encode()).hexdigest(),
        line_count=2,
        indexing_status="completed",
    )
    db_session.add_all([repository, scan, file])
    await db_session.commit()

    storage = RepositoryStorage(str(tmp_path / "repositories"))
    source_dir, _ = storage.create_repo_storage(repository.id)
    (source_dir / "src").mkdir(parents=True)
    (source_dir / "src" / "unsafe.py").write_text(source, encoding="utf-8")
    monkeypatch.setattr("app.workers.security_worker.get_storage", lambda: storage)

    await SecurityScanner().scan(db_session, repository.id, scan.id)

    await db_session.refresh(scan)
    findings = (
        await db_session.execute(select(SecurityFinding).where(SecurityFinding.scan_id == scan.id))
    ).scalars().all()
    assert scan.status == ScanStatus.COMPLETED
    assert scan.findings_count == 1
    assert scan.high_count == 1
    assert len(findings) == 1
    assert findings[0].rule_id == "DANGEROUS_EVAL_EXEC"
    assert findings[0].file_path == "src/unsafe.py"
    assert findings[0].start_line == 2
    assert findings[0].severity == FindingSeverity.HIGH
    assert findings[0].remediation


@pytest.mark.asyncio
async def test_security_scanner_completes_empty_repository_without_inventing_findings(
    db_session, repository_factory
) -> None:
    repository = repository_factory(status=RepositoryStatus.INDEXED, file_count=0)
    scan = SecurityScan(repository_id=repository.id, status=ScanStatus.QUEUED)
    db_session.add_all([repository, scan])
    await db_session.commit()

    await SecurityScanner().scan(db_session, repository.id, scan.id)

    await db_session.refresh(scan)
    assert scan.status == ScanStatus.COMPLETED
    assert scan.findings_count == 0
    assert await db_session.scalar(select(SecurityFinding.id).where(SecurityFinding.scan_id == scan.id)) is None
