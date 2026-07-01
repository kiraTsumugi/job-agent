"""Shared Agent state types."""

from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    user_message: str
    resume_token: str | None
    jd_id: str | None
    conversation_history: list[dict]
    prompt_version: str
    resume_text: str | None
    jd_text: str | None
    plan: dict
    retrieved_jds: list[dict]
    gap_analysis: dict
    rewritten: dict | None
    error: str | None
