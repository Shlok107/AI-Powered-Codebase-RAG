import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Repository, RepositoryFile
from app.db.session import get_session
from app.services.dependency_graph import SourceFile, extract_import_graph, node_details
from app.services.storage import get_storage

router = APIRouter()


async def _repository_graph(repository_id: uuid.UUID, session: AsyncSession, *, query: str | None = None) -> tuple[Repository, dict]:
    repository = await session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repository.status.value != "indexed":
        raise HTTPException(status_code=409, detail="Repository must be indexed before graph analysis")
    result = await session.execute(
        select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
    )
    storage = get_storage()
    files = []
    for item in result.scalars().all():
        if item.language != "python":
            continue
        content = storage.read_file(repository_id, item.relative_path)
        if content is not None:
            files.append(SourceFile(path=item.relative_path, content=content))
    return repository, extract_import_graph(files, query=query)


@router.get("/{repository_id}/graph")
async def get_repository_graph(
    repository_id: uuid.UUID,
    query: str | None = Query(None, max_length=256),
    relationship_type: str | None = Query(None, pattern="^imports$"),
    language: str | None = Query(None, pattern="^python$"),
    session: AsyncSession = Depends(get_session),
):
    repository, data = await _repository_graph(repository_id, session, query=query)
    if relationship_type and relationship_type != "imports":
        data["edges"] = []
    if language and language != "python":
        data["nodes"], data["edges"] = [], []
    data.update({"repository_id": str(repository_id), "repository_name": repository.display_name})
    return data


@router.get("/{repository_id}/graph/impact")
async def get_graph_impact(
    repository_id: uuid.UUID,
    node_id: str = Query(..., min_length=1, max_length=1100),
    depth: int = Query(1, ge=1, le=8),
    session: AsyncSession = Depends(get_session),
):
    _, data = await _repository_graph(repository_id, session)
    details = node_details(data, node_id, depth=depth)
    if details is None:
        raise HTTPException(status_code=404, detail="Graph node not found")
    return {"repository_id": str(repository_id), "node_id": node_id,
            "depth": depth, "affected_dependents": details["dependents"],
            "direct_dependents": details["direct_dependents"]}


@router.get("/{repository_id}/graph/node")
async def get_graph_node(
    repository_id: uuid.UUID,
    node_id: str = Query(..., min_length=1, max_length=1100),
    depth: int = Query(1, ge=1, le=8),
    session: AsyncSession = Depends(get_session),
):
    _, data = await _repository_graph(repository_id, session)
    details = node_details(data, node_id, depth=depth)
    if details is None:
        raise HTTPException(status_code=404, detail="Graph node not found")
    details["repository_id"] = str(repository_id)
    details["depth"] = depth
    return details
