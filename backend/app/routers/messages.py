from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.schemas.correction import (
    HistoryResponse,
    SubmitRequest,
    SubmitResponse,
)
from app.services import correction_service
from app.services.auth_service import get_current_user
from app.services.llm_client import LLMClient, get_llm_client

router = APIRouter(prefix="/api/v1", tags=["messages"])


@router.post("/messages", response_model=SubmitResponse, status_code=200)
async def submit_message(
    payload: SubmitRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
):
    user_out, ai_out = await correction_service.submit_message(
        session, user.id, payload.content, llm_client
    )
    return SubmitResponse(user_message=user_out, assistant_message=ai_out)


@router.get("/messages", response_model=HistoryResponse)
async def get_messages(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    msgs = await correction_service.list_messages(session, user.id)
    return HistoryResponse(messages=msgs)
