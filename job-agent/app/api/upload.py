"""简历上传解析端点."""

import uuid
import logging

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import AsyncSessionLocal, Resume
from app.models.schemas import UploadResponse
from app.services.parser import parse_document

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


@router.post("/upload", response_model=UploadResponse)
async def upload_resume(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if file.content_type not in (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        raise HTTPException(400, "不支持的文件格式，请上传 PDF 或 DOCX")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB
        raise HTTPException(400, "文件大小不能超过 10MB")

    text = await parse_document(content, file.filename)
    token = str(uuid.uuid4())
    resume = Resume(
        filename=file.filename or "resume",
        raw_text=text,
        parsed=None,
        upload_token=token,
    )
    db.add(resume)
    await db.commit()

    logger.info("Uploaded resume token=%s filename=%s chars=%d", token, file.filename, len(text))

    return UploadResponse(token=token, filename=file.filename, parsed_text=text, structured=None)
