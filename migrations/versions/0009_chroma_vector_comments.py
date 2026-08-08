"""将已迁移业务表中的旧 Milvus 注释更新为 Chroma。"""

from collections.abc import Sequence

from alembic import op


revision: str = "0009_chroma_vector_comments"
down_revision: str | Sequence[str] | None = "0008_legacy_business_comments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """只修正 PostgreSQL 系统目录中的注释，不改业务数据或表结构。"""
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        "COMMENT ON COLUMN documents.id IS "
        "'原始文档主键，也是跨 PostgreSQL、文件系统与 Chroma 的稳定标识。'"
    )
    op.execute(
        "COMMENT ON COLUMN archive_documents.final_index_snapshot_hash IS "
        "'进入正式 Chroma 索引的快照哈希。'"
    )


def downgrade() -> None:
    """恢复上一版注释；仅供未写入归档业务数据的本地开发环境回退。"""
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        "COMMENT ON COLUMN documents.id IS "
        "'原始文档主键，也是跨 PostgreSQL、文件系统与 Milvus 的稳定标识。'"
    )
    op.execute(
        "COMMENT ON COLUMN archive_documents.final_index_snapshot_hash IS "
        "'进入正式 Milvus 索引的快照哈希。'"
    )
