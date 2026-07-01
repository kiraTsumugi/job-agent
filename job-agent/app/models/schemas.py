from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ─── Chat ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # user | assistant
    content: str

class ConversationSummary(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime

class ConversationResponse(BaseModel):
    id: str
    title: str
    messages: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str
    resume_token: str | None = None  # 关联已上传的简历
    jd_id: str | None = None

class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    trace_id: str | None = None


# ─── Upload ────────────────────────────────────────────

class UploadResponse(BaseModel):
    token: str
    filename: str
    parsed_text: str
    structured: dict | None = None


# ─── JD ────────────────────────────────────────────────

class JDCreate(BaseModel):
    title: str
    company: str
    raw_text: str
    source_url: str | None = None

class JDResponse(BaseModel):
    id: str
    title: str
    company: str
    raw_text: str
    structured: dict | None = None
    source_url: str | None = None
    created_at: datetime


# ─── Search ────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    use_rerank: bool = True

class SearchHit(BaseModel):
    id: str
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─── Eval ──────────────────────────────────────────────

class EvalCaseCreate(BaseModel):
    resume_text: str
    jd_text: str
    expected_gaps: list[str] = Field(default_factory=list)
    expected_rewrite_points: list[str] = Field(default_factory=list)

class EvalRunRequest(BaseModel):
    run_id: str
    prompt_version: str
    chunking_strategy: str | None = None

class EvalRunResponse(BaseModel):
    run_id: str
    total: int
    scores: dict[str, float]  # {factuality, relevance, completeness} 均值


# ─── Trace ─────────────────────────────────────────────

class TraceSummary(BaseModel):
    id: str
    name: str
    duration_ms: int | None
    error: str | None
    created_at: datetime
