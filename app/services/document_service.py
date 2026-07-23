"""协调原文件保存和 SQLite 文档记录创建。"""

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlmodel import Session

from app.core.errors import AppError
from app.models import Document, KnowledgeBase
from app.services.file_service import save_upload_file


logger = logging.getLogger(__name__)


def _cleanup_saved_file(path: Path) -> None:
    """数据库提交失败时尽量清理已经保存的原文件。"""
    try:
        path.unlink(missing_ok=True)
        path.parent.rmdir()
    except OSError:
        logger.exception("数据库写入失败后清理原文件失败。")


async def create_uploaded_document(
    upload: UploadFile,
    knowledge_base: KnowledgeBase,
    session: Session,
) -> Document:
    """保存上传文件，并创建状态为 UPLOADED 的文档记录。"""
    document_id = uuid4()
    stored_file = await save_upload_file(
        upload=upload,
        document_id=document_id,
        kb_id=knowledge_base.id,
    )

    document = Document(
        id=document_id,
        kb_id=knowledge_base.id,
        filename=stored_file.filename,
        storage_path=str(stored_file.path),
        content_hash=stored_file.content_hash,
    )
    try:
        session.add(document)
        session.commit()
    except Exception as exc:
        session.rollback()
        _cleanup_saved_file(stored_file.path)
        raise AppError(
            status_code=500,
            code="DOCUMENT_CREATE_FAILED",
            message="文档记录创建失败。",
        ) from exc

    session.refresh(document)
    return document
