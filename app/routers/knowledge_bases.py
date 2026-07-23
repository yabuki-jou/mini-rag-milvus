"""提供知识库创建和列表查询接口。"""

from fastapi import APIRouter, status
from sqlmodel import select

from app.core.errors import AppError
from app.dependencies import CurrentUserDep, SessionDep
from app.models import KnowledgeBase
from app.schemas import KnowledgeBaseCreate, KnowledgeBaseRead


router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


@router.post(
    "",
    response_model=KnowledgeBaseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> KnowledgeBase:
    """为当前用户创建知识库。"""
    try:
        knowledge_base = KnowledgeBase(
            owner_id=current_user.id,
            name=payload.name,
        )
        session.add(knowledge_base)
        session.commit()
    except Exception as exc:
        session.rollback()
        raise AppError(
            status_code=500,
            code="KNOWLEDGE_BASE_CREATE_FAILED",
            message="知识库创建失败。",
        ) from exc

    session.refresh(knowledge_base)
    return knowledge_base


@router.get("", response_model=list[KnowledgeBaseRead])
def read_knowledge_bases(
    current_user: CurrentUserDep,
    session: SessionDep,
) -> list[KnowledgeBase]:
    """列出当前用户拥有的知识库。"""
    statement = (
        select(KnowledgeBase)
        .where(KnowledgeBase.owner_id == current_user.id)
        .order_by(KnowledgeBase.created_at.desc())
    )
    return list(session.exec(statement).all())
