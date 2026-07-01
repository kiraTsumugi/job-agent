"""文档解析：PDF (pymupdf) + DOCX (python-docx)."""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


async def parse_document(content: bytes, filename: str) -> str:
    """根据文件扩展名路由到对应解析器."""
    import asyncio

    if filename.lower().endswith(".pdf"):
        return await asyncio.to_thread(_parse_pdf, content)
    elif filename.lower().endswith((".docx", ".doc")):
        return await asyncio.to_thread(_parse_docx, content)
    else:
        # 纯文本 fallback
        return content.decode("utf-8", errors="replace")


def _parse_pdf(content: bytes) -> str:
    import fitz  # pymupdf

    doc = fitz.open(stream=content, filetype="pdf")
    texts = []
    for page in doc:
        texts.append(page.get_text())
    doc.close()
    return "\n\n".join(texts)


def _parse_docx(content: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(content))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
