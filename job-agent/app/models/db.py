from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings

async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(default="新对话")
    messages: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class JD(Base):
    """岗位描述存储"""

    __tablename__ = "jds"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(nullable=False)
    company: Mapped[str] = mapped_column(nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # LLM 提取的结构化字段
    source_url: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Resume(Base):
    """简历解析结果"""

    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    filename: Mapped[str] = mapped_column(nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # 教育/技能/项目等结构化字段
    upload_token: Mapped[str] = mapped_column(nullable=False, unique=True)  # 前端用 token 代称上传
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Trace(Base):
    """自研 Trace 记录"""

    __tablename__ = "traces"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    parent_id: Mapped[str | None] = mapped_column(nullable=True)
    input_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvalCase(Base):
    """评测样本"""

    __tablename__ = "eval_cases"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    jd_text: Mapped[str] = mapped_column(Text, nullable=False)
    expected_gaps: Mapped[list] = mapped_column(JSONB, nullable=True)  # 人工标注的预期 gap
    expected_rewrite_points: Mapped[list] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvalResult(Base):
    """评测结果"""

    __tablename__ = "eval_results"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(nullable=False)
    run_id: Mapped[str] = mapped_column(nullable=False)  # 同一次评测 run 的标识
    model_output: Mapped[dict] = mapped_column(JSONB, nullable=False)
    judge_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {factuality, relevance, completeness}
    prompt_version: Mapped[str] = mapped_column(nullable=False)
    chunking_strategy: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
