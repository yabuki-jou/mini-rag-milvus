"""验证 Alembic 基线可创建空库并安全接管旧 RAG Schema。"""

from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel

from app import models as _models  # noqa: F401  注册当前业务表。
from app.migration_service import build_alembic_config, upgrade_database
from app.models import User


EXPECTED_BUSINESS_TABLES = {
    "users",
    "knowledge_bases",
    "documents",
    "chat_sessions",
    "chat_messages",
    "employee_profiles",
    "leave_balances",
    "leave_requests",
}

LEGACY_TABLES = (
    "users",
    "knowledge_bases",
    "documents",
    "chat_sessions",
    "chat_messages",
)


def sqlite_url(path) -> str:
    """把 pytest 临时路径转换为跨工作目录稳定的 SQLite URL。"""
    return f"sqlite:///{path.as_posix()}"


def test_upgrade_creates_current_schema_in_empty_database(tmp_path) -> None:
    """空数据库升级后应包含业务表和 Alembic 版本表。"""
    database_path = tmp_path / "empty.db"
    target_url = sqlite_url(database_path)

    upgrade_database(target_url)

    engine = create_engine(target_url)
    table_names = set(inspect(engine).get_table_names())
    assert EXPECTED_BUSINESS_TABLES <= table_names
    assert "alembic_version" in table_names

    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert revision == "0002_leave_domain"
    engine.dispose()


def test_upgrade_preserves_data_in_legacy_schema(tmp_path) -> None:
    """create_all 创建的旧库应保留数据并被纳入迁移版本。"""
    database_path = tmp_path / "legacy.db"
    target_url = sqlite_url(database_path)
    engine = create_engine(target_url)
    # 只创建 Agent 迭代前的五张表，不能让当前 metadata 偷跑新迁移。
    for table_name in LEGACY_TABLES:
        SQLModel.metadata.tables[table_name].create(engine)

    user_id = uuid4()
    with Session(engine) as session:
        session.add(User(id=user_id, name="迁移测试用户"))
        session.commit()
    engine.dispose()

    upgrade_database(target_url)

    migrated_engine = create_engine(target_url)
    with Session(migrated_engine) as session:
        migrated_user = session.get(User, user_id)
    assert migrated_user is not None
    assert migrated_user.name == "迁移测试用户"
    assert "alembic_version" in inspect(migrated_engine).get_table_names()
    migrated_engine.dispose()


def test_upgrade_rejects_incompatible_legacy_table(tmp_path) -> None:
    """字段不匹配时必须停止，不能直接 stamp 掩盖 Schema 冲突。"""
    database_path = tmp_path / "incompatible.db"
    target_url = sqlite_url(database_path)
    engine = create_engine(target_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id TEXT PRIMARY KEY)"))
    engine.dispose()

    with pytest.raises((RuntimeError, SQLAlchemyError)) as exc_info:
        upgrade_database(target_url)

    assert "users" in str(exc_info.value)


def test_migration_head_matches_sqlmodel_metadata(tmp_path) -> None:
    """升级到 head 后，Alembic 不应再发现未迁移的模型差异。"""
    database_path = tmp_path / "metadata-check.db"
    target_url = sqlite_url(database_path)
    upgrade_database(target_url)

    command.check(build_alembic_config(target_url))
