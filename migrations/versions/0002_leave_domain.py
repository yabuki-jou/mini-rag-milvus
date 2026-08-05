"""新增员工、假期余额和请假申请业务表。"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_leave_domain"
down_revision: str | Sequence[str] | None = "0001_rag_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建确定性请假领域所需的三张业务表。"""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        postgresql.ENUM(
            "ANNUAL", "SICK", name="leavetype"
        ).create(bind, checkfirst=True)
        postgresql.ENUM(
            "SUBMITTED", name="leaverequeststatus"
        ).create(bind, checkfirst=True)
        leave_type_enum = postgresql.ENUM(
            "ANNUAL", "SICK", name="leavetype", create_type=False
        )
        request_status_enum = postgresql.ENUM(
            "SUBMITTED", name="leaverequeststatus", create_type=False
        )
    else:
        leave_type_enum = sa.Enum("ANNUAL", "SICK", name="leavetype")
        request_status_enum = sa.Enum(
            "SUBMITTED", name="leaverequeststatus"
        )
    op.create_table(
        "employee_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("employee_no", sa.String(length=32), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_no", name="uq_employee_profiles_employee_no"),
        sa.UniqueConstraint("user_id", name="uq_employee_profiles_user_id"),
    )
    op.create_index(
        "ix_employee_profiles_user_id", "employee_profiles", ["user_id"]
    )
    op.create_index(
        "ix_employee_profiles_employee_no",
        "employee_profiles",
        ["employee_no"],
    )
    op.create_index(
        "ix_employee_profiles_active", "employee_profiles", ["active"]
    )

    op.create_table(
        "leave_balances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column(
            "leave_type",
            leave_type_enum,
            nullable=False,
        ),
        sa.Column("total_days", sa.Integer(), nullable=False),
        sa.Column("used_days", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "total_days >= 0", name="ck_leave_balances_total_days"
        ),
        sa.CheckConstraint(
            "used_days >= 0", name="ck_leave_balances_used_days"
        ),
        sa.CheckConstraint(
            "used_days <= total_days",
            name="ck_leave_balances_used_not_over_total",
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employee_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employee_id",
            "leave_type",
            name="uq_leave_balances_employee_type",
        ),
    )
    op.create_index(
        "ix_leave_balances_employee_id", "leave_balances", ["employee_id"]
    )
    op.create_index(
        "ix_leave_balances_leave_type", "leave_balances", ["leave_type"]
    )

    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column(
            "leave_type",
            leave_type_enum,
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("leave_days", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            request_status_enum,
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "start_date <= end_date", name="ck_leave_requests_date_range"
        ),
        sa.CheckConstraint("leave_days > 0", name="ck_leave_requests_days"),
        sa.ForeignKeyConstraint(["employee_id"], ["employee_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_leave_requests_idempotency_key"
        ),
    )
    for name, columns in {
        "ix_leave_requests_employee_id": ["employee_id"],
        "ix_leave_requests_leave_type": ["leave_type"],
        "ix_leave_requests_start_date": ["start_date"],
        "ix_leave_requests_end_date": ["end_date"],
        "ix_leave_requests_status": ["status"],
        "ix_leave_requests_idempotency_key": ["idempotency_key"],
        "ix_leave_requests_created_at": ["created_at"],
    }.items():
        op.create_index(name, "leave_requests", columns)


def downgrade() -> None:
    """按外键依赖逆序删除请假领域表。"""
    op.drop_table("leave_requests")
    op.drop_table("leave_balances")
    op.drop_table("employee_profiles")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        postgresql.ENUM(name="leaverequeststatus").drop(bind, checkfirst=True)
        postgresql.ENUM(name="leavetype").drop(bind, checkfirst=True)
