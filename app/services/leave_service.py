"""实现与 LLM 无关的员工、余额和请假申请领域规则。"""

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.errors import AppError
from app.models import (
    EmployeeProfile,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    User,
    utc_now,
)


@dataclass(frozen=True)
class LeaveRequestDraft:
    """表示通过业务校验、但尚未写入数据库的申请草稿。"""

    user_id: UUID
    employee_id: UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    leave_days: int
    reason: str


def calculate_workdays(start_date: date, end_date: date) -> int:
    """按周一至周五计算包含首尾日期的整工作日数量。"""
    if end_date < start_date:
        raise AppError(
            status_code=422,
            code="LEAVE_DATE_RANGE_INVALID",
            message="请假结束日期不能早于开始日期。",
        )

    workdays = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:
            workdays += 1
        current_date += timedelta(days=1)

    if workdays == 0:
        raise AppError(
            status_code=422,
            code="LEAVE_WORKDAYS_EMPTY",
            message="请假日期范围内没有工作日。",
        )
    return workdays


def create_employee_profile(
    user: User,
    employee_no: str,
    department: str | None,
    session: Session,
) -> EmployeeProfile:
    """为现有用户创建唯一员工资料。"""
    normalized_no = employee_no.strip().upper()
    normalized_department = department.strip() if department else None
    if not normalized_no:
        raise AppError(422, "EMPLOYEE_NO_INVALID", "员工编号不能为空。")

    profile = EmployeeProfile(
        user_id=user.id,
        employee_no=normalized_no,
        department=normalized_department or None,
    )
    try:
        session.add(profile)
        session.commit()
        session.refresh(profile)
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            409,
            "EMPLOYEE_PROFILE_CONFLICT",
            "该用户或员工编号已经存在员工资料。",
        ) from exc
    return profile


def set_leave_balance(
    employee: EmployeeProfile,
    leave_type: LeaveType,
    total_days: int,
    used_days: int,
    session: Session,
) -> LeaveBalance:
    """创建或更新员工某类假期额度，供测试和演示数据初始化。"""
    if total_days < 0 or used_days < 0 or used_days > total_days:
        raise AppError(
            422,
            "LEAVE_BALANCE_INVALID",
            "假期总额度和已使用额度不合法。",
        )

    statement = select(LeaveBalance).where(
        LeaveBalance.employee_id == employee.id,
        LeaveBalance.leave_type == leave_type,
    )
    balance = session.exec(statement).first()
    if balance is None:
        balance = LeaveBalance(
            employee_id=employee.id,
            leave_type=leave_type,
            total_days=total_days,
            used_days=used_days,
        )
        session.add(balance)
    else:
        balance.total_days = total_days
        balance.used_days = used_days
        balance.updated_at = utc_now()

    try:
        session.commit()
        session.refresh(balance)
    except Exception as exc:
        session.rollback()
        raise AppError(
            500,
            "LEAVE_BALANCE_SAVE_FAILED",
            "假期余额保存失败。",
        ) from exc
    return balance


def get_employee_profile(user_id: UUID, session: Session) -> EmployeeProfile:
    """取得当前用户唯一且启用的员工资料。"""
    profile = session.exec(
        select(EmployeeProfile).where(EmployeeProfile.user_id == user_id)
    ).first()
    if profile is None:
        raise AppError(404, "EMPLOYEE_PROFILE_NOT_FOUND", "员工资料不存在。")
    if not profile.active:
        raise AppError(409, "EMPLOYEE_PROFILE_INACTIVE", "员工资料已停用。")
    return profile


def get_leave_balance(
    user_id: UUID,
    leave_type: LeaveType,
    session: Session,
) -> LeaveBalance:
    """查询当前用户自己的指定假期余额。"""
    employee = get_employee_profile(user_id, session)
    balance = session.exec(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == employee.id,
            LeaveBalance.leave_type == leave_type,
        )
    ).first()
    if balance is None:
        raise AppError(404, "LEAVE_BALANCE_NOT_FOUND", "假期余额不存在。")
    return balance


def build_leave_request_draft(
    user_id: UUID,
    leave_type: LeaveType,
    start_date: date,
    end_date: date,
    reason: str,
    session: Session,
) -> LeaveRequestDraft:
    """验证当前用户的申请参数并生成无副作用草稿。"""
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise AppError(422, "LEAVE_REASON_INVALID", "请假原因不能为空。")

    employee = get_employee_profile(user_id, session)
    leave_days = calculate_workdays(start_date, end_date)
    balance = get_leave_balance(user_id, leave_type, session)
    available_days = balance.total_days - balance.used_days
    if leave_days > available_days:
        raise AppError(
            409,
            "LEAVE_BALANCE_INSUFFICIENT",
            "当前假期余额不足。",
        )

    overlap = session.exec(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date,
        )
    ).first()
    if overlap is not None:
        raise AppError(
            409,
            "LEAVE_REQUEST_OVERLAP",
            "该日期范围与已有请假申请重叠。",
        )

    return LeaveRequestDraft(
        user_id=user_id,
        employee_id=employee.id,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        leave_days=leave_days,
        reason=normalized_reason,
    )


def submit_leave_request(
    draft: LeaveRequestDraft,
    idempotency_key: str,
    session: Session,
) -> LeaveRequest:
    """幂等提交已确认草稿，并在同一事务扣减可用额度。"""
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        raise AppError(422, "IDEMPOTENCY_KEY_INVALID", "幂等键不能为空。")

    existing = session.exec(
        select(LeaveRequest).where(
            LeaveRequest.idempotency_key == normalized_key
        )
    ).first()
    if existing is not None:
        if existing.employee_id != draft.employee_id:
            raise AppError(409, "IDEMPOTENCY_KEY_CONFLICT", "幂等键已被占用。")
        return existing

    # 草稿会跨越 Graph 的暂停与恢复，因此提交时必须重新验证授权上下文和业务事实。
    employee = get_employee_profile(draft.user_id, session)
    if employee.id != draft.employee_id:
        raise AppError(
            409,
            "LEAVE_DRAFT_OWNER_CONFLICT",
            "请假草稿与当前员工资料不匹配。",
        )

    balance = get_leave_balance(draft.user_id, draft.leave_type, session)
    available_days = balance.total_days - balance.used_days
    if draft.leave_days > available_days:
        raise AppError(409, "LEAVE_BALANCE_INSUFFICIENT", "当前假期余额不足。")

    overlap = session.exec(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == draft.employee_id,
            LeaveRequest.start_date <= draft.end_date,
            LeaveRequest.end_date >= draft.start_date,
        )
    ).first()
    if overlap is not None:
        raise AppError(
            409,
            "LEAVE_REQUEST_OVERLAP",
            "该日期范围与已有请假申请重叠。",
        )

    leave_request = LeaveRequest(
        employee_id=draft.employee_id,
        leave_type=draft.leave_type,
        start_date=draft.start_date,
        end_date=draft.end_date,
        leave_days=draft.leave_days,
        reason=draft.reason,
        idempotency_key=normalized_key,
    )
    balance.used_days += draft.leave_days
    balance.updated_at = utc_now()
    try:
        session.add(leave_request)
        session.add(balance)
        session.commit()
        session.refresh(leave_request)
    except IntegrityError as exc:
        session.rollback()
        existing = session.exec(
            select(LeaveRequest).where(
                LeaveRequest.idempotency_key == normalized_key
            )
        ).first()
        if existing is not None and existing.employee_id == draft.employee_id:
            return existing
        raise AppError(
            409,
            "LEAVE_REQUEST_CONFLICT",
            "请假申请与现有数据冲突。",
        ) from exc
    except Exception as exc:
        session.rollback()
        raise AppError(
            500,
            "LEAVE_REQUEST_SAVE_FAILED",
            "请假申请保存失败。",
        ) from exc
    return leave_request


def list_leave_requests(user_id: UUID, session: Session) -> list[LeaveRequest]:
    """按创建时间倒序列出当前用户自己的申请。"""
    employee = get_employee_profile(user_id, session)
    statement = (
        select(LeaveRequest)
        .where(LeaveRequest.employee_id == employee.id)
        .order_by(LeaveRequest.created_at.desc())
    )
    return list(session.exec(statement).all())


def get_leave_request(
    user_id: UUID,
    request_id: UUID,
    session: Session,
) -> LeaveRequest:
    """读取当前用户自己的申请，并隐藏其他用户申请是否存在。"""
    employee = get_employee_profile(user_id, session)
    leave_request = session.get(LeaveRequest, request_id)
    if leave_request is None or leave_request.employee_id != employee.id:
        raise AppError(404, "LEAVE_REQUEST_NOT_FOUND", "请假申请不存在。")
    return leave_request
