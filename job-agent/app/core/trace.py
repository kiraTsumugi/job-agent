"""自研轻量 Trace 系统 —— 每次 Agent 调用写入 PG，含 token/耗时/输入输出."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.models.db import AsyncSessionLocal, Trace


class Span:
    def __init__(self, name: str, parent_id: str | None = None, metadata: dict | None = None):
        self.id = str(uuid.uuid4())
        self.name = name
        self.parent_id = parent_id
        self.metadata = metadata or {}
        self._start: float | None = None
        self._end: float | None = None
        self._input: Any = None
        self._output: Any = None

    async def start(self, input_data: Any = None):
        self._start = time.time()
        self._input = input_data

    async def end(self, output_data: Any = None, error: str | None = None) -> dict:
        self._end = time.time()
        self._output = output_data
        duration_ms = int((self._end - (self._start or self._end)) * 1000)

        record = {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "input": self._input,
            "output": self._output,
            "duration_ms": duration_ms,
            "error": error,
            "metadata": self.metadata,
            "created_at": datetime.now(timezone.utc),
        }

        async with AsyncSessionLocal() as session:
            trace = Trace(
                id=self.id,
                name=self.name,
                parent_id=self.parent_id,
                input_data=self._input,
                output_data=self._output,
                duration_ms=duration_ms,
                error=error,
                metadata_=self.metadata,
            )
            session.add(trace)
            await session.commit()

        return record


class Tracer:
    """简易 tracer，用于在 Agent 执行期间记录 span."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.spans: list[Span] = []
        self._current_parent: str | None = None

    def span(self, name: str, metadata: dict | None = None) -> Span:
        span = Span(name=name, parent_id=self._current_parent, metadata=metadata)
        self.spans.append(span)
        self._current_parent = span.id
        return span

    def pop(self) -> None:
        if self.spans:
            self.spans.pop()
        self._current_parent = self.spans[-1].id if self.spans else None
