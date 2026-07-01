"""多策略文本分块：固定窗口、语义分块、递归分块."""

from __future__ import annotations

import re
from typing import Protocol


class Chunker(Protocol):
    def chunk(self, text: str) -> list[dict]:
        """返回 [{"id": "chunk_0", "text": "...", "meta": {...}}, ...]"""
        ...


class FixedChunker:
    """固定窗口分块，重叠 sliding window."""

    def __init__(self, chunk_size: int = 512, overlap: int = 64):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[dict]:
        chunks = []
        start = 0
        idx = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk_text = text[start:end]
            chunks.append({"id": f"chunk_{idx}", "text": chunk_text, "meta": {"start": start, "end": end}})
            start += self.chunk_size - self.overlap
            idx += 1
        return chunks


class SemanticChunker:
    """基于分隔符的语义分块：按段落/标题切分后合并短块."""

    def __init__(self, min_chunk_size: int = 200, max_chunk_size: int = 1024):
        self.min_chunk = min_chunk_size
        self.max_chunk = max_chunk_size

    def chunk(self, text: str) -> list[dict]:
        # 按双换行 + Markdown 标题切分
        sections = re.split(r"(\n\n|\n#{1,3}\s)", text)
        merged = self._merge_short(sections)
        return [
            {"id": f"chunk_{i}", "text": c.strip(), "meta": {}}
            for i, c in enumerate(merged) if c.strip()
        ]

    def _merge_short(self, sections: list[str]) -> list[str]:
        result = []
        buf = ""
        for sec in sections:
            if len(buf) + len(sec) > self.max_chunk and buf:
                result.append(buf)
                buf = sec
            else:
                buf += sec
        if buf:
            result.append(buf)
        return result


class RecursiveChunker:
    """递归字符分割器（类似 LangChain 的 RecursiveCharacterTextSplitter）."""

    def __init__(self, chunk_size: int = 512, overlap: int = 64):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._separators = ["\n\n", "\n", "。", ".", " ", ""]

    def chunk(self, text: str) -> list[dict]:
        chunks = self._split(text, self._separators)
        return [
            {"id": f"chunk_{i}", "text": c, "meta": {}}
            for i, c in enumerate(chunks)
        ]

    def _split(self, text: str, separators: list[str]) -> list[str]:
        result = []
        sep = separators[0]
        remaining = separators[1:]

        if not sep:
            # 最终兜底：按字符切
            for i in range(0, len(text), self.chunk_size - self.overlap):
                result.append(text[i:i + self.chunk_size])
            return result

        splits = text.split(sep)
        buf = ""
        for s in splits:
            if len(buf) + len(s) <= self.chunk_size:
                buf += (sep if buf else "") + s
            else:
                if buf:
                    if remaining:
                        result.extend(self._split(buf, remaining))
                    else:
                        result.append(buf)
                buf = s
        if buf:
            if len(buf) > self.chunk_size and remaining:
                result.extend(self._split(buf, remaining))
            else:
                result.append(buf)
        return result


def get_chunker(strategy: str = "fixed", **kwargs) -> Chunker:
    strategies = {
        "fixed": FixedChunker,
        "semantic": SemanticChunker,
        "recursive": RecursiveChunker,
    }
    cls = strategies.get(strategy, FixedChunker)
    return cls(**kwargs)
