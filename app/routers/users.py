"""提供用户相关的 API 路由。"""

from fastapi import APIRouter, status

from app.dependencies import SessionDep
from app.models import User
from app.schemas import UserCreate, UserRead


router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, session: SessionDep) -> User:
    """创建一个用于模拟身份校验的基础用户。

    Args:
        payload: 客户端提交的用户名称。
        session: 当前请求使用的数据库 Session。

    Returns:
        数据库提交并刷新后的用户记录。
    """
    # 请求模型只负责校验输入，数据库实体负责持久化用户字段。
    user = User(name=payload.name)

    # commit 写入数据库，refresh 读取数据库最终保存的字段值。
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
