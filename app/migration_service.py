"""以项目配置运行 Alembic 数据库迁移。"""

from alembic import command
from alembic.config import Config

from app.core.config import PROJECT_ROOT
from app.db import database_url


def build_alembic_config(target_url: str | None = None) -> Config:
    """构造可供应用启动和隔离测试复用的 Alembic 配置。"""
    config_path = PROJECT_ROOT / "alembic.ini"
    config = Config(str(config_path))
    config.attributes["database_url"] = target_url or database_url
    return config


def upgrade_database(target_url: str | None = None) -> None:
    """将指定数据库升级到最新迁移版本。"""
    command.upgrade(build_alembic_config(target_url), "head")
