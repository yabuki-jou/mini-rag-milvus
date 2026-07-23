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
    """为当前用户创建知识库。

    Args:
        payload: 客户端提交的知识库名称。
        current_user: 已通过身份校验的当前用户。
        session: 当前请求使用的数据库 Session。

    Returns:
        数据库提交并刷新后的知识库记录。

    Raises:
        AppError: 知识库记录无法写入数据库。
    """
    # owner_id 始终来自已校验用户，客户端不能替知识库指定所有者。
    try:
        knowledge_base = KnowledgeBase(
            owner_id=current_user.id,
            name=payload.name,
        )
        session.add(knowledge_base)
        session.commit()
    except Exception as exc:
        # 提交失败后先回滚 Session，再转换为不泄露底层细节的业务错误。
        session.rollback()
        raise AppError(
            status_code=500,
            code="KNOWLEDGE_BASE_CREATE_FAILED",
            message="知识库创建失败。",
        ) from exc

    # 读取数据库最终保存的 ID 和时间字段后再返回。
    session.refresh(knowledge_base)
    return knowledge_base


@router.get("", response_model=list[KnowledgeBaseRead])
def read_knowledge_bases(
    current_user: CurrentUserDep,
    session: SessionDep,
) -> list[KnowledgeBase]:
    """列出当前用户拥有的知识库。

    Args:
        current_user: 已通过身份校验的当前用户。
        session: 当前请求使用的数据库 Session。

    Returns:
        按创建时间倒序排列的知识库记录。
    """
    # 查询条件始终包含 owner_id，保证不同用户的知识库列表相互隔离。
    statement = (
        select(KnowledgeBase)
        .where(KnowledgeBase.owner_id == current_user.id)
        .order_by(KnowledgeBase.created_at.desc())
    )
    return list(session.exec(statement).all())
