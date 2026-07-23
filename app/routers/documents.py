"""提供知识库文档上传、列表查询和解析入库接口。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, UploadFile, status
from sqlmodel import select

from app.dependencies import (
    OwnedDocumentDep,
    OwnedKnowledgeBaseDep,
    SessionDep,
)
from app.models import Document
from app.schemas import DocumentRead
from app.services.document_service import (
    create_uploaded_document,
    process_document,
)


router = APIRouter(
    prefix="/knowledge-bases/{kb_id}/documents",
    tags=["documents"],
)


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def create_document(
    upload: Annotated[
        UploadFile,
        File(description="TXT、Markdown、PDF 或 DOCX 原文件"),
    ],
    knowledge_base: OwnedKnowledgeBaseDep,
    session: SessionDep,
) -> Document:
    """保存原文件并创建 UPLOADED 状态的文档记录。

    Args:
        upload: 客户端上传的原文件。
        knowledge_base: 已通过当前用户所有权校验的知识库。
        session: 当前请求使用的数据库 Session。

    Returns:
        已保存但尚未解析和向量化的文档记录。
    """
    # 上传接口只委托保存服务，不在请求入口中编排文件和数据库操作。
    return await create_uploaded_document(
        upload=upload,
        knowledge_base=knowledge_base,
        session=session,
    )


@router.get("", response_model=list[DocumentRead])
def read_documents(
    knowledge_base: OwnedKnowledgeBaseDep,
    session: SessionDep,
) -> list[Document]:
    """列出目标知识库中的文档。

    Args:
        knowledge_base: 已通过当前用户所有权校验的知识库。
        session: 当前请求使用的数据库 Session。

    Returns:
        按创建时间倒序排列的文档记录。
    """
    # 只查询已经通过所有权校验的知识库，避免返回其他知识库文档。
    statement = (
        select(Document)
        .where(Document.kb_id == knowledge_base.id)
        .order_by(Document.created_at.desc())
    )
    return list(session.exec(statement).all())


@router.post("/{document_id}/parse", response_model=DocumentRead)
def parse_document_endpoint(
    document: OwnedDocumentDep,
    knowledge_base: OwnedKnowledgeBaseDep,
    session: SessionDep,
    document_id: UUID,
) -> Document:
    """解析文档并将生成的 Chunk 写入 Milvus。

    Args:
        document: 已通过知识库归属校验的文档。
        knowledge_base: 已通过当前用户所有权校验的知识库。
        session: 当前请求使用的数据库 Session。
        document_id: 路径中的文档 UUID；实际查询由 OwnedDocumentDep 完成。

    Returns:
        处理完成并更新状态后的文档记录。

    Raises:
        AppError: 由文档处理服务返回的解析、向量化或入库错误。
    """
    # document_id 显式保留给路由和 Swagger，OwnedDocumentDep 已使用它完成查询。
    del document_id

    # 路由只负责接收已校验的依赖，处理流程交给业务服务。
    return process_document(
        document=document,
        knowledge_base=knowledge_base,
        session=session,
    )
