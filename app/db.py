"""创建 SQLModel Engine，并管理请求使用的数据库 Session。"""

from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import PROJECT_ROOT, settings


def _sqlite_path_from_url(url: str) -> Path | None:
    """从 SQLite 数据库地址中提取数据库文件路径。"""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return None

    raw_path = url[len(prefix) :]
    path = Path(raw_path)
    return path if path.is_absolute() else PROJECT_ROOT / path


sqlite_path = _sqlite_path_from_url(settings.database_url)
database_url = settings.database_url
if sqlite_path is not None:
    sqlite_path = sqlite_path.resolve()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite:///{sqlite_path.as_posix()}"

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
    """创建所有尚未存在的数据库表。"""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """创建数据库会话，并在使用结束后自动关闭。"""
    with Session(engine) as session:
        yield session
