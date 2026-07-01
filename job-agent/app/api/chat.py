"""SSE 流式对话端点."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agent.graph import AgentGraph
from app.core.trace import Tracer
from app.models.db import AsyncSessionLocal, Conversation
from app.models.schemas import ChatRequest, ConversationResponse, ConversationSummary
from app.services.conversation import (
    DEFAULT_USER_ID,
    append_message,
    get_or_create_conversation,
    recent_user_history,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def _stream_chat(request: ChatRequest):
    conversation_id, conversation_history = await _persist_user_message(request)
    yield {"event": "conversation", "data": json.dumps({"conversation_id": conversation_id})}

    tracer = Tracer(session_id=conversation_id)
    graph = AgentGraph(tracer=tracer)
    final_data = {}

    try:
        async for event in graph.astream(
            request.message,
            resume_token=request.resume_token,
            jd_id=request.jd_id,
            conversation_history=conversation_history,
        ):
            if event["type"] == "complete":
                final_data = event["data"]
            yield {"event": event["type"], "data": json.dumps(event["data"], ensure_ascii=False)}
        await _persist_assistant_message(conversation_id, final_data)
        yield {"event": "done", "data": "{}"}
    except Exception as e:
        logger.exception("Chat stream error")
        await _persist_assistant_message(conversation_id, {"error": str(e)}, error=str(e))
        yield {"event": "error", "data": json.dumps({"error": str(e)})}


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    return EventSourceResponse(_stream_chat(request))


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == DEFAULT_USER_ID)
        .order_by(Conversation.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return [_conversation_to_summary(conversation) for conversation in result.scalars()]


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation 不存在")
    return _conversation_to_response(conversation)


async def _persist_user_message(request: ChatRequest) -> tuple[str, list[dict[str, str]]]:
    async with AsyncSessionLocal() as db:
        conversation = await get_or_create_conversation(
            db,
            request.conversation_id,
            title_seed=request.message,
        )
        history = recent_user_history(conversation.messages)
        await append_message(
            db,
            conversation,
            role="user",
            content=request.message,
            metadata={
                "resume_token": request.resume_token,
                "jd_id": request.jd_id,
            },
        )
        await db.commit()
        return conversation.id, history


async def _persist_assistant_message(
    conversation_id: str,
    payload: dict,
    *,
    error: str | None = None,
) -> None:
    async with AsyncSessionLocal() as db:
        conversation = await get_or_create_conversation(db, conversation_id)
        await append_message(
            db,
            conversation,
            role="assistant",
            content=json.dumps(payload, ensure_ascii=False, default=str),
            metadata={
                "event": "error" if error else "complete",
                "error": error,
            },
        )
        await db.commit()


def _conversation_to_summary(conversation: Conversation) -> ConversationSummary:
    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        message_count=len(conversation.messages or []),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _conversation_to_response(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        messages=conversation.messages or [],
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )
