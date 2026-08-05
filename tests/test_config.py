"""验证业务数据库配置不会回退到 SQLite。"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_accept_psycopg_database_url() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:password@localhost:5432/test_db",
    )
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_settings_reject_sqlite_business_database() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL 必须使用"):
        Settings(_env_file=None, database_url="sqlite:///./data/legacy.db")
