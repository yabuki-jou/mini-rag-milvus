"""创建 SQLModel Engine，并管理请求使用的数据库 Session。"""

from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app import models as _models  # noqa: F401  导入后将业务表注册到 metadata。
from app.core.config import PROJECT_ROOT, settings


def _sqlite_path_from_url(url: str) -> Path | None:
    """从数据库地址中提取 SQLite 文件路径。

    Args:
        url: SQLAlchemy 格式的数据库连接地址。

    Returns:
        SQLite 文件路径；非 SQLite 地址返回 ``None``。
    """
    # 只解析本项目使用的三斜杠 SQLite 文件地址。
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return None

    raw_path = url[len(prefix) :]
    path = Path(raw_path)
    return path if path.is_absolute() else PROJECT_ROOT / path


# SQLite 不会自动创建父目录，因此在创建 Engine 前先准备目录。
sqlite_path = _sqlite_path_from_url(settings.database_url)
database_url = settings.database_url
if sqlite_path is not None:
    sqlite_path = sqlite_path.resolve()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite:///{sqlite_path.as_posix()}"

# FastAPI 的同步依赖可能运行在不同线程，SQLite 需要允许跨线程使用连接。
connect_args = (
    {"check_same_thread": False}
    if database_url.startswith("sqlite")
    else {}
)
engine = create_engine(
    database_url,
    connect_args=connect_args,
)


def create_db_and_tables() -> None:
    """为隔离测试创建当前模型表；正式启动使用 Alembic 迁移。"""
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
