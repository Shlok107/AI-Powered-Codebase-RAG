import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import Repository
from app.schemas import ChatRequest, ChatResponse, Citation
from app.services.chat import ChatService
from app.services.llm import ChatMessage

router = APIRouter()


class ChatRequestWithHistory(ChatRequest):
    conversation_history: Optional[list[dict]] = None


class ChatResponseDetailed(BaseModel):
    answer: str
    citations: list[Citation]
    conversation_id: uuid.UUID
    model_used: str
    retrieval_time_ms: int
    generation_time_ms: int
    used_fallback: bool


@router.post("/{repository_id}/chat", response_model=ChatResponseDetailed)
async def chat_with_repository(
    repository_id: uuid.UUID,
    request: ChatRequestWithHistory,
    session: AsyncSession = Depends(get_session),
):
    """Ask a question about a repository."""
    # Verify repository exists and is indexed
    result = await session.execute(
        select(Repository).where(Repository.id == repository_id)
    )
    repository = result.scalar_one_or_none()

    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Repository {repository_id} not found", "details": {}}
        )

    if repository.status.value != "indexed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "REPOSITORY_NOT_INDEXED",
                "message": f"Repository is not indexed (status: {repository.status.value}). Trigger indexing first.",
                "details": {"status": repository.status.value}
            }
        )

    # Convert conversation history
    history = []
    if request.conversation_history:
        for msg in request.conversation_history[-4:]:  # Keep last 4 messages
            history.append(ChatMessage(role=msg.get("role", "user"), content=msg.get("content", "")))

    # Create chat service and ask
    chat_service = ChatService()
    try:
        result = await chat_service.ask(
            session=session,
            repository_id=repository_id,
            question=request.question,
            conversation_history=history,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REQUEST", "message": str(e), "details": {}}
        )
    except Exception as e:
        logger.error("chat_failed", repository_id=str(repository_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Failed to process chat request", "details": {}}
        )

    return ChatResponseDetailed(
        answer=result.answer,
        citations=[Citation(**c.__dict__) for c in result.citations],
        conversation_id=uuid.uuid4(),  # In a real app, this would be persistent
        model_used=result.model_used,
        retrieval_time_ms=result.retrieval_time_ms,
        generation_time_ms=result.generation_time_ms,
        used_fallback=result.used_fallback,
    )


from app.core.logging import get_logger
logger = get_logger(__name__)
