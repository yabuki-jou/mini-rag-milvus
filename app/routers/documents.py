"""提供知识库文档上传和列表查询接口。"""

from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status
from sqlmodel import select

from app.dependencies import OwnedKnowledgeBaseDep, SessionDep
from app.models import Document
from app.schemas import DocumentRead
from app.services.document_service import create_uploaded_document


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
    """保存原文件并创建 UPLOADED 状态的文档记录。"""
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
    """列出目标知识库中的文档。"""
    statement = (
        select(Document)
        .where(Document.kb_id == knowledge_base.id)
        .order_by(Document.created_at.desc())
    )
    return list(session.exec(statement).all())
