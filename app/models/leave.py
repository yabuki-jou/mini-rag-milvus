"""定义企业行政 Agent 使用的员工和请假业务实体。"""

from datetime import date, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.common import utc_now


class LeaveType(str, Enum):
    """当前学习项目支持的假期类型。

    字段:
        ANNUAL: 年假。
        SICK: 病假。
    """

    # 说明 1：继承 str 后，枚举值可以方便地在 API 和 SQLite 中序列化。
    ANNUAL = "ANNUAL"
    SICK = "SICK"


class LeaveRequestStatus(str, Enum):
    """请假申请在当前迭代中的状态。

    字段:
        SUBMITTED: 已经由用户确认并写入业务数据库的申请。
    """

    # 说明 2：被用户拒绝的草稿不会写入业务表，因此这里不需要拒绝状态。
    SUBMITTED = "SUBMITTED"


class EmployeeProfile(SQLModel, table=True):
    """把应用用户一对一映射为行政业务中的员工。

    字段:
        id: 员工资料的内部主键。
        user_id: 与员工关联的可信应用用户 ID。
        employee_no: 用于业务展示的企业员工编号。
        department: 可选的部门名称。
        active: 员工资料是否可以继续使用请假业务。
        created_at: UTC 创建时间。
        updated_at: UTC 最后更新时间。
    """

    __tablename__ = "employee_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_employee_profiles_user_id"),
        UniqueConstraint("employee_no", name="uq_employee_profiles_employee_no"),
    )

    # 说明 3：user_id 唯一，保证一个应用用户最多映射一个员工身份。
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    # 说明 4：employee_no 只用于业务展示，不能作为 Agent 的授权依据。
    employee_no: str = Field(min_length=4, max_length=32, index=True)
    department: str | None = Field(default=None, max_length=100)
    active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class LeaveBalance(SQLModel, table=True):
    """保存员工某类假期的总额度和已使用额度。

    字段:
        id: 假期余额记录的内部主键。
        employee_id: 拥有该余额的员工 ID。
        leave_type: 年假或病假等假期类型。
        total_days: 授予员工的总天数。
        used_days: 已提交申请占用的天数。
        created_at: UTC 创建时间。
        updated_at: UTC 最后更新时间。
    """

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

    # 说明 5：可用天数由 total_days - used_days 动态计算，不重复保存。
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
    """表示用户明确确认后写入的请假申请。

    字段:
        id: 已提交申请的内部主键。
        employee_id: 申请所属的员工 ID。
        leave_type: 本次申请的假期类型。
        start_date: 请假范围包含的第一个日期。
        end_date: 请假范围包含的最后一个日期。
        leave_days: 提交申请时计算并保存的工作日数。
        reason: 去除两端空白后的用户请假原因。
        status: 当前业务状态。
        idempotency_key: 当前确认动作的唯一标识。
        created_at: UTC 创建时间。
        updated_at: UTC 最后更新时间。
    """

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

    # 说明 6：leave_days 保存提交时的计算结果，作为历史业务快照。
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
    # 说明 7：唯一幂等键可以防止 Graph 重复恢复时写入两次申请。
    idempotency_key: str = Field(min_length=1, max_length=100, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)
