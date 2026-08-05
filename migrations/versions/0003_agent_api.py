"""新增 Agent 会话和脱敏工具调用日志表。"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_agent_api"
down_revision: str | Sequence[str] | None = "0002_leave_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 Agent API 所需的业务会话和审计表。"""
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns, unique in (
        ("ix_agent_sessions_user_id", ["user_id"], False),
        ("ix_agent_sessions_kb_id", ["kb_id"], False),
        ("ix_agent_sessions_thread_id", ["thread_id"], True),
    ):
        op.create_index(name, "agent_sessions", columns, unique=unique)

    op.create_table(
        "agent_tool_call_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_session_id", sa.Uuid(), nullable=False),
        sa.Column("tool_call_id", sa.String(length=200), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "COMPLETED",
                "FAILED",
                name="agenttoolcallstatus",
            ),
            nullable=False,
        ),
        sa.Column("arguments_summary_json", sa.String(), nullable=True),
        sa.Column("result_summary_json", sa.String(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_session_id"], ["agent_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "agent_session_id",
            "tool_call_id",
            name="uq_agent_tool_logs_session_call",
        ),
    )
    for name, columns in {
        "ix_agent_tool_call_logs_agent_session_id": ["agent_session_id"],
        "ix_agent_tool_call_logs_tool_call_id": ["tool_call_id"],
        "ix_agent_tool_call_logs_tool_name": ["tool_name"],
        "ix_agent_tool_call_logs_status": ["status"],
        "ix_agent_tool_call_logs_created_at": ["created_at"],
    }.items():
        op.create_index(name, "agent_tool_call_logs", columns)


def downgrade() -> None:
    """按外键依赖逆序删除 Agent API 业务表。"""
    op.drop_table("agent_tool_call_logs")
    op.drop_table("agent_sessions")
