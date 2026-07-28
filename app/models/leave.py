"""定义企业行政 Agent 使用的员工和请假业务实体。"""

from datetime import date, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.common import utc_now


class LeaveType(str, Enum):
    """当前学习项目支持的假期类型。"""

    ANNUAL = "ANNUAL"
    SICK = "SICK"


class LeaveRequestStatus(str, Enum):
    """请假申请在当前迭代中的状态。"""

    SUBMITTED = "SUBMITTED"


class EmployeeProfile(SQLModel, table=True):
    """把应用用户一对一映射为行政业务中的员工。"""

    __tablename__ = "employee_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_employee_profiles_user_id"),
        UniqueConstraint("employee_no", name="uq_employee_profiles_employee_no"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    employee_no: str = Field(min_length=4, max_length=32, index=True)
    department: str | None = Field(default=None, max_length=100)
    active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class LeaveBalance(SQLModel, table=True):
    """保存员工某类假期的总额度和已使用额度。"""

    __tablename__ = "leave_balances"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "leave_type",
            name="uq_leave_balances_employee_type",
        ),
        CheckConstraint("total_days >= 0", name="ck_leave_balances_total_days"),
        CheckConstraint("used_days >= 0", name="ck_leave_balances_used_days"),
        CheckConstraint(
            "used_days <= total_days",
            name="ck_leave_balances_used_not_over_total",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    employee_id: UUID = Field(
        foreign_key="employee_profiles.id",
        index=True,
    )
    leave_type: LeaveType = Field(index=True)
    total_days: int = Field(ge=0)
    used_days: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class LeaveRequest(SQLModel, table=True):
    """表示用户明确确认后写入的请假申请。"""

    __tablename__ = "leave_requests"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_leave_requests_idempotency_key",
        ),
        CheckConstraint("leave_days > 0", name="ck_leave_requests_days"),
        CheckConstraint(
            "start_date <= end_date",
            name="ck_leave_requests_date_range",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    employee_id: UUID = Field(
        foreign_key="employee_profiles.id",
        index=True,
    )
    leave_type: LeaveType = Field(index=True)
    start_date: date = Field(index=True)
    end_date: date = Field(index=True)
    leave_days: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=500)
    status: LeaveRequestStatus = Field(
        default=LeaveRequestStatus.SUBMITTED,
        index=True,
    )
    idempotency_key: str = Field(min_length=1, max_length=100, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)
