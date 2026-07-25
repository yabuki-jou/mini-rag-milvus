"""定义请求头用户身份校验依赖。"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header

from app.core.errors import AppError
from app.dependencies.database import SessionDep
from app.models import User


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
