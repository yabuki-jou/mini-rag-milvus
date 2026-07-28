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
    """表示通过业务校验、但尚未写入数据库的申请草稿。

    字段:
        user_id: 生成草稿时使用的可信用户 ID。
        employee_id: 根据可信用户解析出的员工 ID。
        leave_type: 本次申请的假期类型。
        start_date: 请假范围包含的第一个日期。
        end_date: 请假范围包含的最后一个日期。
        leave_days: 计算得到的完整工作日数。
        reason: 去除两端空白后的请假原因。

    说明 1：该 dataclass 不可变，防止通过校验的草稿在确认前被静默修改。
    """

    user_id: UUID
    employee_id: UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    leave_days: int
    reason: str


def calculate_workdays(start_date: date, end_date: date) -> int:
    """按周一至周五计算包含首尾日期的整工作日数量。

    参数:
        start_date: 需要计入范围的第一个日期。
        end_date: 需要计入范围的最后一个日期。

    返回:
        日期范围内周一至周五的总天数，包含开始日期和结束日期。

    异常:
        AppError: 日期范围反向或范围内没有工作日时抛出。

    说明 2：当前学习规则不处理法定节假日、调休或半天假。
    """
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
    """为现有用户创建唯一员工资料。

    参数:
        user: 员工资料所属的现有应用用户。
        employee_no: 用于业务展示的员工编号。
        department: 可选的部门名称。
        session: 执行本次事务的 SQLModel Session。

    返回:
        已经写入数据库并刷新后的员工资料。

    异常:
        AppError: 员工编号为空或唯一约束冲突时抛出。

    说明 3：后续授权从 user.id 开始，不能依赖 employee_no。
    """
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
    """创建或更新员工某类假期额度，供测试和演示数据初始化。

    参数:
        employee: 拥有该余额的员工资料。
        leave_type: 需要创建或更新的假期类型。
        total_days: 授予员工的总天数。
        used_days: 已经使用的天数。
        session: 执行本次事务的 SQLModel Session。

    返回:
        已经写入数据库并刷新后的假期余额。

    异常:
        AppError: 额度不合法或数据库保存失败时抛出。

    说明 4：employee 和 leave_type 共同定位一条余额记录。
    """
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
    """取得当前用户唯一且启用的员工资料。

    参数:
        user_id: 服务端提供的可信当前用户 ID。
        session: 执行查询的 SQLModel Session。

    返回:
        当前用户拥有并且处于启用状态的员工资料。

    异常:
        AppError: 员工资料不存在或已停用时抛出。

    说明 5：该查询是应用用户进入请假领域的授权桥梁。
    """
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
    """查询当前用户自己的指定假期余额。

    参数:
        user_id: 服务端提供的可信当前用户 ID。
        leave_type: 需要查询的假期类型。
        session: 执行查询的 SQLModel Session。

    返回:
        当前员工指定假期类型的余额记录。

    异常:
        AppError: 员工资料或假期余额不存在时抛出。

    说明 6：调用者不需要也不能提供其他员工的内部 ID。
    """
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
    """验证当前用户的申请参数并生成无副作用草稿。

    参数:
        user_id: 服务端提供的可信当前用户 ID。
        leave_type: 本次申请的假期类型。
        start_date: 请假范围包含的第一个日期。
        end_date: 请假范围包含的最后一个日期。
        reason: 用户提供的请假原因。
        session: 执行各项校验查询的 SQLModel Session。

    返回:
        已通过校验但尚未写入数据库的不可变草稿。

    异常:
        AppError: 原因、日期、余额、身份或日期重叠不合法时抛出。

    说明 7：人工确认将在后续发生，因此这里不会执行 commit。
    """
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
    """幂等提交已确认草稿，并在同一事务扣减可用额度。

    参数:
        draft: 用户确认后恢复执行的已校验草稿。
        idempotency_key: 当前确认动作的唯一标识。
        session: 执行恢复校验和事务提交的 SQLModel Session。

    返回:
        新写入的申请，或者同一确认动作先前已经写入的申请。

    异常:
        AppError: 幂等键、归属、最新余额、日期重叠或保存不合法时抛出。

    说明 8：恢复时使用数据库中的当前事实，不能依赖旧快照。
    说明 9：申请写入和余额扣减必须共享同一个事务。
    """
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


def list_leave_requests(
    user_id: UUID,
    session: Session,
    *,
    limit: int = 20,
) -> list[LeaveRequest]:
    """按创建时间倒序列出当前用户自己的申请。

    参数:
        user_id: 服务端提供的可信当前用户 ID。
        session: 执行查询的 SQLModel Session。
        limit: 最多返回的申请数量，仅由服务端调用方指定。

    返回:
        当前员工最多 limit 条申请，按照创建时间从新到旧排列。

    异常:
        AppError: 当前用户没有启用的员工资料，或 limit 不合法时抛出。

    说明 10：使用解析后的员工 ID 构造 SQL 条件，以保证数据归属隔离。
    """
    if limit <= 0:
        raise AppError(422, "LEAVE_REQUEST_LIMIT_INVALID", "申请数量限制必须大于零。")

    employee = get_employee_profile(user_id, session)
    statement = (
        select(LeaveRequest)
        .where(LeaveRequest.employee_id == employee.id)
        .order_by(LeaveRequest.created_at.desc())
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_leave_request(
    user_id: UUID,
    request_id: UUID,
    session: Session,
) -> LeaveRequest:
    """读取当前用户自己的申请，并隐藏其他用户申请是否存在。

    参数:
        user_id: 服务端提供的可信当前用户 ID。
        request_id: 需要读取的请假申请主键。
        session: 执行查询的 SQLModel Session。

    返回:
        申请属于当前员工时返回对应的请假申请。

    异常:
        AppError: 员工资料无效或当前员工不存在该申请时抛出。

    说明 11：把其他员工的申请统一报告为不存在，可以隐藏资源是否真实存在。
    """
    employee = get_employee_profile(user_id, session)
    leave_request = session.get(LeaveRequest, request_id)
    if leave_request is None or leave_request.employee_id != employee.id:
        raise AppError(404, "LEAVE_REQUEST_NOT_FOUND", "请假申请不存在。")
    return leave_request
