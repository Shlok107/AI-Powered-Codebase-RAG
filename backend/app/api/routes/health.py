from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.schemas import HealthResponse

router = APIRouter()

settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check(session: AsyncSession = Depends(get_session)):
    """Health check endpoint for the application and its dependencies."""
    # Check database
    db_status: str = "disconnected"
    try:
        await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # Check LLM provider
    llm_status = "configured" if settings.llm_configured else "unconfigured"

    # Check embedding provider
    embedding_status = "configured" if settings.embeddings_configured else "unconfigured"

    overall_status = "healthy"
    if db_status == "disconnected":
        overall_status = "unhealthy"
    elif llm_status == "unconfigured" or embedding_status == "unconfigured":
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version="0.1.0",
        database=db_status,
        llm_provider=llm_status,
        embedding_provider=embedding_status,
        timestamp=datetime.utcnow(),
    )


from datetime import datetime