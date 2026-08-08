"""创建 PostgreSQL SQLModel Engine，并管理请求使用的数据库 Session。"""

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app import models as _models  # noqa: F401  导入后将业务表注册到 metadata。
from app.core.config import settings


database_url = settings.database_url
engine = create_engine(database_url, pool_pre_ping=True)


def create_db_and_tables() -> None:
    """为隔离测试创建当前模型表；正式运行使用 Alembic 迁移。"""
    # metadata 已通过导入 models 注册全部 SQLModel 表。
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """为一次请求提供数据库会话，并在请求结束后自动关闭。

    Yields:
        当前请求共享使用的 SQLModel Session。
    """
    # with 块确保请求完成或异常退出后都会关闭会话。
    with Session(engine) as session:
        yield session
