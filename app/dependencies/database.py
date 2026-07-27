"""定义路由共用的数据库 Session 依赖。"""

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.db import get_session


# 路由声明 SessionDep 后，FastAPI 会自动创建并注入数据库会话。
SessionDep = Annotated[Session, Depends(get_session)]
