import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_session
from app.db.models import Repository, SecurityScan, SecurityFinding, ScanStatus
from app.schemas import (
    SecurityScanRead,
    SecurityFindingRead,
    FindingFilter,
    FindingsListResponse,
    FindingUpdate,
    ScanRequest,
)
from app.workers.security_worker import run_security_scan_job

router = APIRouter()


@router.get("/{repository_id}/scans", response_model=list[SecurityScanRead])
async def list_security_scans(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List security scans for a repository."""
    # Verify repository exists
    repo_result = await session.execute(
        select(Repository.id).where(Repository.id == repository_id)
    )
    if not repo_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Repository {repository_id} not found", "details": {}}
        )

    result = await session.execute(
        select(SecurityScan)
        .where(SecurityScan.repository_id == repository_id)
        .order_by(SecurityScan.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    scans = result.scalars().all()

    return [SecurityScanRead.model_validate(s) for s in scans]


@router.post("/{repository_id}/scans", response_model=SecurityScanRead, status_code=status.HTTP_201_CREATED)
async def run_security_scan(
    repository_id: uuid.UUID,
    request: ScanRequest,
    session: AsyncSession = Depends(get_session),
):
    """Trigger a security scan for a repository."""
    # Verify repository exists
    repo_result = await session.execute(
        select(Repository).where(Repository.id == repository_id).with_for_update()
    )
    repository = repo_result.scalar_one_or_none()

    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Repository {repository_id} not found", "details": {}}
        )

    # Check if there's already a running scan
    running_scan = await session.execute(
        select(SecurityScan).where(
            SecurityScan.repository_id == repository_id,
            SecurityScan.status.in_([ScanStatus.QUEUED, ScanStatus.PROCESSING])
        )
    )
    if running_scan.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "SCAN_IN_PROGRESS", "message": "A scan is already running for this repository", "details": {}}
        )

    # Create scan record
    scan = SecurityScan(
        repository_id=repository_id,
        status=ScanStatus.QUEUED,
    )
    session.add(scan)
    await session.commit()
    await session.refresh(scan)

    # Trigger background job
    import asyncio
    asyncio.create_task(run_security_scan_job(str(repository_id), str(scan.id)))

    return SecurityScanRead.model_validate(scan)


@router.get("/{repository_id}/findings", response_model=FindingsListResponse)
async def list_security_findings(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    severity: Optional[list[str]] = Query(None),
    category: Optional[list[str]] = Query(None),
    file_path: Optional[str] = Query(None, max_length=1024),
    finding_status: Optional[list[str]] = Query(None),
    rule_id: Optional[str] = Query(None, max_length=128),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List security findings for a repository with filters."""
    # Verify repository exists
    repo_result = await session.execute(
        select(Repository.id).where(Repository.id == repository_id)
    )
    if not repo_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Repository {repository_id} not found", "details": {}}
        )

    # Build query
    query = select(SecurityFinding).where(SecurityFinding.repository_id == repository_id)

    if severity:
        query = query.where(SecurityFinding.severity.in_(severity))
    if category:
        query = query.where(SecurityFinding.category.in_(category))
    if file_path:
        query = query.where(SecurityFinding.file_path.ilike(f"%{file_path}%"))
    if finding_status:
        query = query.where(SecurityFinding.status.in_(finding_status))
    if rule_id:
        query = query.where(SecurityFinding.rule_id == rule_id)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total = count_result.scalar_one()

    # Get findings
    query = query.order_by(SecurityFinding.severity.desc(), SecurityFinding.created_at.desc())
    query = query.limit(limit).offset(offset)
    result = await session.execute(query)
    findings = result.scalars().all()

    return FindingsListResponse(
        findings=[SecurityFindingRead.model_validate(f) for f in findings],
        total=total,
    )


@router.patch("/findings/{finding_id}", response_model=SecurityFindingRead)
async def update_finding(
    finding_id: uuid.UUID,
    request: FindingUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update finding triage status."""
    result = await session.execute(
        select(SecurityFinding).where(SecurityFinding.id == finding_id)
    )
    finding = result.scalar_one_or_none()

    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Finding {finding_id} not found", "details": {}}
        )

    finding.status = request.status
    from datetime import datetime
    finding.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(finding)

    return SecurityFindingRead.model_validate(finding)


@router.get("/{repository_id}/scan-status", response_model=Optional[SecurityScanRead])
async def get_latest_scan_status(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the latest scan status for a repository."""
    repo_result = await session.execute(
        select(Repository.id).where(Repository.id == repository_id)
    )
    if not repo_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Repository {repository_id} not found", "details": {}}
        )

    result = await session.execute(
        select(SecurityScan)
        .where(SecurityScan.repository_id == repository_id)
        .order_by(SecurityScan.created_at.desc())
        .limit(1)
    )
    scan = result.scalar_one_or_none()

    if not scan:
        return None

    return SecurityScanRead.model_validate(scan)
