"""定义路由共用的数据库会话、身份和权限依赖。"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlmodel import Session

from app.core.errors import AppError
from app.db import get_session
from app.models import KnowledgeBase, User


SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    session: SessionDep,
    x_user_id: Annotated[UUID, Header(alias="X-User-ID")],
) -> User:
    """根据请求头中的用户 ID 查询当前用户。"""
    current_user = session.get(User, x_user_id)
    if current_user is None:
        raise AppError(
            status_code=401,
            code="INVALID_USER",
            message="X-User-ID 对应的用户不存在。",
        )
    return current_user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_owned_knowledge_base(
    kb_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> KnowledgeBase:
    """查询知识库，并验证它是否属于当前用户。"""
    knowledge_base = session.get(KnowledgeBase, kb_id)
    if knowledge_base is None:
        raise AppError(
            status_code=404,
            code="KNOWLEDGE_BASE_NOT_FOUND",
            message="知识库不存在。",
        )
    if knowledge_base.owner_id != current_user.id:
        raise AppError(
            status_code=403,
            code="KNOWLEDGE_BASE_FORBIDDEN",
            message="无权访问该知识库。",
        )
    return knowledge_base


OwnedKnowledgeBaseDep = Annotated[
    KnowledgeBase,
    Depends(get_owned_knowledge_base),
]
