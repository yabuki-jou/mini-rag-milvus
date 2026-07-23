"""定义路由共用的数据库会话、身份和权限依赖。"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlmodel import Session

from app.core.errors import AppError
from app.db import get_session
from app.models import Document, KnowledgeBase, User


# 路由声明 SessionDep 后，FastAPI 会自动创建并注入数据库会话。
SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    session: SessionDep,
    x_user_id: Annotated[UUID, Header(alias="X-User-ID")],
) -> User:
    """根据请求头中的用户 ID 查询当前用户。

    Args:
        session: 当前请求使用的数据库 Session。
        x_user_id: ``X-User-ID`` 请求头中的用户 UUID。

    Returns:
        请求所代表的用户记录。

    Raises:
        AppError: 请求头对应的用户不存在。
    """
    # 请求头只携带身份 ID，真实用户必须以 SQLite 记录为准。
    current_user = session.get(User, x_user_id)
    if current_user is None:
        raise AppError(
            status_code=401,
            code="INVALID_USER",
            message="X-User-ID 对应的用户不存在。",
        )
    return current_user


# 路由声明 CurrentUserDep 后，会自动执行请求头身份校验。
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_owned_knowledge_base(
    kb_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> KnowledgeBase:
    """查询知识库，并验证它是否属于当前用户。

    Args:
        kb_id: 请求路径中的知识库 UUID。
        session: 当前请求使用的数据库 Session。
        current_user: 已通过身份校验的当前用户。

    Returns:
        当前用户拥有的知识库记录。

    Raises:
        AppError: 知识库不存在或不属于当前用户。
    """
    # 先确认知识库存在，再单独判断当前用户是否拥有它。
    knowledge_base = session.get(KnowledgeBase, kb_id)
    if knowledge_base is None:
        raise AppError(
            status_code=404,
            code="KNOWLEDGE_BASE_NOT_FOUND",
            message="知识库不存在。",
        )
    # 所有权不匹配时禁止继续注入知识库，后续路由无法绕过此检查。
    if knowledge_base.owner_id != current_user.id:
        raise AppError(
            status_code=403,
            code="KNOWLEDGE_BASE_FORBIDDEN",
            message="无权访问该知识库。",
        )
    return knowledge_base


# 先验证当前用户，再把其有权访问的知识库注入路由。
OwnedKnowledgeBaseDep = Annotated[
    KnowledgeBase,
    Depends(get_owned_knowledge_base),
]


def get_document_in_knowledge_base(
    document_id: UUID,
    knowledge_base: OwnedKnowledgeBaseDep,
    session: SessionDep,
) -> Document:
    """查询文档，并验证它是否属于已经授权的知识库。

    Args:
        document_id: 请求路径中的文档 UUID。
        knowledge_base: 已通过当前用户所有权校验的知识库。
        session: 当前请求使用的数据库 Session。

    Returns:
        属于目标知识库的文档记录。

    Raises:
        AppError: 文档不存在或不属于目标知识库。
    """
    # 按主键查询文档，避免扫描整个文档表。
    document = session.get(Document, document_id)

    # 文档不存在时返回 404。
    if document is None:
        raise AppError(
            status_code=404,
            code="DOCUMENT_NOT_FOUND",
            message="该文档不存在。",
        )

    # 归属不一致时同样返回 404，避免泄露其他知识库的数据是否存在。
    if document.kb_id != knowledge_base.id:
        raise AppError(
            status_code=404,
            code="DOCUMENT_NOT_FOUND",
            message="该文档不存在。",
        )

    return document


# 将已完成知识库归属校验的 Document 注入后续路由。
OwnedDocumentDep = Annotated[
    Document,
    Depends(get_document_in_knowledge_base),
]
