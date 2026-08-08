"""补齐项目乐观锁版本字段的 PostgreSQL 注释。"""

from collections.abc import Sequence

from alembic import op


revision: str = "0007_project_version_comment"
down_revision: str | Sequence[str] | None = "0006_archive_jsonb_and_comments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """补齐已创建项目表的唯一遗漏字段说明。"""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("COMMENT ON COLUMN projects.version IS '项目乐观锁版本。'")


def downgrade() -> None:
    """仅供尚未写入归档业务数据的本地开发环境回退。"""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("COMMENT ON COLUMN projects.version IS NULL")
