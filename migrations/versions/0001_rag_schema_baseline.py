"""建立现有 RAG 业务表的兼容迁移基线。"""

from collections.abc import Callable, Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_rag_baseline"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_EXPECTED_COLUMNS = {
    "users": {"id", "name", "created_at", "updated_at"},
    "knowledge_bases": {
        "id", "owner_id", "name", "created_at", "updated_at",
    },
    "documents": {
        "id", "kb_id", "filename", "storage_path", "content_hash",
        "status", "chunk_count", "error_message", "created_at", "updated_at",
    },
    "chat_sessions": {
        "id", "user_id", "kb_id", "created_at", "updated_at",
    },
    "chat_messages": {
        "id", "session_id", "role", "content", "sources_json", "created_at",
    },
}


def _ensure_table(
    table_name: str,
    create_table: Callable[[], None],
) -> None:
    """创建缺失表，或拒绝把不兼容旧表直接标记为基线。"""
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        create_table()
        return

    actual_columns = {
        column["name"] for column in inspector.get_columns(table_name)
    }
    expected_columns = _EXPECTED_COLUMNS[table_name]
    if actual_columns != expected_columns:
        raise RuntimeError(
            f"旧表 {table_name} 与迁移基线不兼容："
            f"expected={sorted(expected_columns)}, actual={sorted(actual_columns)}"
        )


def _ensure_index(name: str, table_name: str, columns: list[str]) -> None:
    """为旧数据库补充当前模型声明但尚不存在的普通索引。"""
    inspector = sa.inspect(op.get_bind())
    existing_names = {
        index["name"] for index in inspector.get_indexes(table_name)
    }
    if name not in existing_names:
        op.create_index(name, table_name, columns, unique=False)


def upgrade() -> None:
    """创建空库，或验证并接管已有的当前 RAG Schema。"""
    _ensure_table(
        "users",
        lambda: op.create_table(
            "users",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        ),
    )
    _ensure_index("ix_users_name", "users", ["name"])

    _ensure_table(
        "knowledge_bases",
        lambda: op.create_table(
            "knowledge_bases",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("owner_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        ),
    )
    _ensure_index(
        "ix_knowledge_bases_owner_id", "knowledge_bases", ["owner_id"]
    )
    _ensure_index("ix_knowledge_bases_name", "knowledge_bases", ["name"])

    _ensure_table(
        "documents",
        lambda: op.create_table(
            "documents",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("kb_id", sa.Uuid(), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("storage_path", sa.String(length=1024), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column(
                "status",
                sa.Enum(
                    "UPLOADED", "PROCESSING", "READY", "FAILED",
                    "DELETING", "DELETE_FAILED", name="documentstatus",
                ),
                nullable=False,
            ),
            sa.Column("chunk_count", sa.Integer(), nullable=False),
            sa.Column("error_message", sa.String(length=1000), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"]),
            sa.PrimaryKeyConstraint("id"),
        ),
    )
    for name, columns in {
        "ix_documents_kb_id": ["kb_id"],
        "ix_documents_filename": ["filename"],
        "ix_documents_content_hash": ["content_hash"],
        "ix_documents_status": ["status"],
    }.items():
        _ensure_index(name, "documents", columns)

    _ensure_table(
        "chat_sessions",
        lambda: op.create_table(
            "chat_sessions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("kb_id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        ),
    )
    _ensure_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
    _ensure_index("ix_chat_sessions_kb_id", "chat_sessions", ["kb_id"])

    _ensure_table(
        "chat_messages",
        lambda: op.create_table(
            "chat_messages",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("session_id", sa.Uuid(), nullable=False),
            sa.Column(
                "role",
                sa.Enum("USER", "ASSISTANT", name="messagerole"),
                nullable=False,
            ),
            sa.Column("content", sa.String(), nullable=False),
            sa.Column("sources_json", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        ),
    )
    for name, columns in {
        "ix_chat_messages_session_id": ["session_id"],
        "ix_chat_messages_role": ["role"],
        "ix_chat_messages_created_at": ["created_at"],
    }.items():
        _ensure_index(name, "chat_messages", columns)


def downgrade() -> None:
    """只用于空测试库回退；真实旧库不得执行基线降级。"""
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("documents")
    op.drop_table("knowledge_bases")
    op.drop_table("users")
