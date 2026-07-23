"""协调原文件上传、SQLite 状态变更和文档向量化入库。"""

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlmodel import Session

from app.core.errors import AppError
from app.models import Document, DocumentStatus, KnowledgeBase
from app.services.chunk_service import TextChunk, split_pages
from app.services.embedding_service import EmbeddedChunk, embed_chunks
from app.services.file_service import save_upload_file
from app.services.parser_service import ParsedPage, parse_document
from app.services.vector_service import delete_document_chunks, insert_chunks

logger = logging.getLogger(__name__)


def _cleanup_saved_file(path: Path) -> None:
    """数据库提交失败时尽量清理已经保存的原文件。

    Args:
        path: 已成功写入、但需要回滚清理的原文件路径。
    """
    # 清理属于补偿操作，失败时只记录日志，避免覆盖原始数据库异常。
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
    """保存上传文件，并创建状态为 UPLOADED 的文档记录。

    Args:
        upload: FastAPI 接收到的上传文件。
        knowledge_base: 已通过所有权校验的目标知识库。
        session: 当前请求使用的数据库 Session。

    Returns:
        数据库提交并刷新后的文档记录。

    Raises:
        AppError: 原文件保存失败或文档记录无法写入数据库。
    """
    # 预先生成文档 ID，使文件路径和数据库记录使用同一身份。
    document_id = uuid4()
    stored_file = await save_upload_file(
        upload=upload,
        document_id=document_id,
        kb_id=knowledge_base.id,
    )

    # 上传阶段只保存原文件和元数据，不执行解析、切分或向量化。
    document = Document(
        id=document_id,
        kb_id=knowledge_base.id,
        filename=stored_file.filename,
        storage_path=str(stored_file.path),
        content_hash=stored_file.content_hash,
    )
    # 数据库写入失败时同时回滚事务并清理已保存的孤立文件。
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


def process_document(
    document: Document,
    knowledge_base: KnowledgeBase,
    session: Session,
) -> Document:
    """解析文档、生成向量并同步写入 Milvus。

    Args:
        document: 已通过知识库归属校验的文档。
        knowledge_base: 文档所属且已通过权限校验的知识库。
        session: 当前请求使用的数据库 Session。

    Returns:
        更新为 READY 状态的文档记录。

    Raises:
        AppError: 文档正在处理，或处理链路中的任一步骤失败。
    """
    # 同一文档只能执行一个处理任务，避免重复删除和写入相同 Chunk。
    if document.status == DocumentStatus.PROCESSING:
        raise AppError(
            status_code=409,
            code="DOCUMENT_ALREADY_PROCESSING",
            message="文档正在处理中。",
        )

    # 先持久化 PROCESSING，使后续请求能够看到文档正在处理。
    document.status = DocumentStatus.PROCESSING
    document.chunk_count = 0
    document.error_message = None
    session.add(document)
    session.commit()
    session.refresh(document)

    try:
        # 重新解析前按文档范围清理旧 Chunk，避免向量数量不断累积。
        delete_document_chunks(
            user_id=knowledge_base.owner_id,
            kb_id=knowledge_base.id,
            document_id=document.id,
        )

        # 从服务器原文件中提取页面正文，再按页面生成带位置的 Chunk。
        storage_path = Path(document.storage_path)
        parsed_pages: list[ParsedPage] = parse_document(storage_path)
        text_chunks: list[TextChunk] = split_pages(parsed_pages)

        # 没有有效 Chunk 时不能把文档标记为可检索状态。
        if not text_chunks:
            raise AppError(
                status_code=422,
                code="DOCUMENT_CHUNKS_EMPTY",
                message="文档没有生成有效 Chunk。",
            )
        # 批量生成稳定 Chunk ID 和归一化向量。
        embedded_chunks = embed_chunks(document.id, text_chunks)

        # 将向量、正文、归属信息和引用位置统一写入 Milvus。
        chunk_count = insert_chunks(
            user_id=knowledge_base.owner_id,
            kb_id=knowledge_base.id,
            document_id=document.id,
            document_name=document.filename,
            embedded_chunks=embedded_chunks,
        )

        # Milvus 写入成功后再提交 READY，保证 SQLite 状态与向量库一致。
        document.status = DocumentStatus.READY
        document.chunk_count = chunk_count
        document.error_message = None
        session.add(document)
        session.commit()
        session.refresh(document)
    except AppError as exc:
        # 已知业务异常可以安全保存其摘要，同时保留原错误代码。
        session.rollback()
        document.status = DocumentStatus.FAILED
        document.chunk_count = 0
        document.error_message = exc.message[:1000]
        session.add(document)
        session.commit()
        session.refresh(document)
        raise
    except Exception as exc:
        # 未知异常记录完整堆栈，但数据库和接口只保留通用信息。
        session.rollback()
        logger.exception("文档处理发生未知异常。")
        document.status = DocumentStatus.FAILED
        document.chunk_count = 0
        document.error_message = "文档处理失败，请查看服务器日志。"
        session.add(document)
        session.commit()
        session.refresh(document)

        raise AppError(
            status_code=500,
            code="DOCUMENT_PROCESS_FAILED",
            message="文档处理失败。",
        ) from exc

    # 返回 refresh 后的记录，其中包含最终状态和实际 Chunk 数量。
    return document
