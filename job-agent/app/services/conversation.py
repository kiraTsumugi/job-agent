"""Conversation persistence helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Conversation


DEFAULT_USER_ID = "anonymous"
HISTORY_CONTENT_LIMIT = 2000


async def get_or_create_conversation(
    db: AsyncSession,
    conversation_id: str | None,
    *,
    user_id: str = DEFAULT_USER_ID,
    title_seed: str = "",
) -> Conversation:
    if conversation_id:
        existing = await db.get(Conversation, conversation_id)
        if existing:
            return existing

    conversation = Conversation(
        id=conversation_id or str(uuid.uuid4()),
        user_id=user_id,
        title=_make_title(title_seed),
        messages=[],
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def append_message(
    db: AsyncSession,
    conversation: Conversation,
    *,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    message = {
        "role": role,
        "content": content,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    conversation.messages = [*(conversation.messages or []), message]
    await db.flush()


def recent_user_history(messages: list[dict] | None, *, limit: int = 6) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for message in messages or []:
        if message.get("role") != "user":
            continue
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        history.append({"role": "user", "content": content[:HISTORY_CONTENT_LIMIT]})
    return history[-limit:]


def _make_title(seed: str) -> str:
    title = " ".join(seed.strip().split())
    if not title:
        return "新对话"
    return title[:40]
