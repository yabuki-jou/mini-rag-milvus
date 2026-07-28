"""验证员工、假期余额和请假申请的确定性领域规则。"""

from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.errors import AppError
from app.models import LeaveRequest, LeaveType, User
from app.services.leave_service import (
    build_leave_request_draft,
    calculate_workdays,
    create_employee_profile,
    get_leave_balance,
    get_leave_request,
    list_leave_requests,
    set_leave_balance,
    submit_leave_request,
)


@pytest.fixture
def session() -> Session:
    """为每个用例提供独立的内存 SQLite 数据库。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def create_employee_with_balance(
    session: Session,
    *,
    name: str = "测试员工",
    employee_no: str = "EMP-001",
    total_days: int = 10,
    used_days: int = 0,
) -> tuple[User, object]:
    """建立领域测试所需的最小用户、员工和年假余额。"""
    user = User(name=name)
    session.add(user)
    session.commit()
    session.refresh(user)
    employee = create_employee_profile(user, employee_no, "研发部", session)
    set_leave_balance(
        employee,
        LeaveType.ANNUAL,
        total_days,
        used_days,
        session,
    )
    return user, employee


def assert_app_error(exc_info: pytest.ExceptionInfo[AppError], code: str) -> None:
    assert exc_info.value.code == code


def test_calculate_workdays_and_reject_invalid_ranges() -> None:
    assert calculate_workdays(date(2026, 8, 3), date(2026, 8, 9)) == 5

    with pytest.raises(AppError) as reversed_range:
        calculate_workdays(date(2026, 8, 4), date(2026, 8, 3))
    assert_app_error(reversed_range, "LEAVE_DATE_RANGE_INVALID")

    with pytest.raises(AppError) as weekend_only:
        calculate_workdays(date(2026, 8, 8), date(2026, 8, 9))
    assert_app_error(weekend_only, "LEAVE_WORKDAYS_EMPTY")


def test_employee_profile_is_normalized_and_unique(session: Session) -> None:
    user = User(name="员工甲")
    session.add(user)
    session.commit()
    session.refresh(user)

    employee = create_employee_profile(user, " emp-001 ", " 研发部 ", session)
    assert employee.employee_no == "EMP-001"
    assert employee.department == "研发部"

    with pytest.raises(AppError) as duplicate:
        create_employee_profile(user, "EMP-002", None, session)
    assert_app_error(duplicate, "EMPLOYEE_PROFILE_CONFLICT")


def test_build_draft_has_no_side_effect_and_checks_balance(session: Session) -> None:
    user, _ = create_employee_with_balance(session, total_days=3)

    draft = build_leave_request_draft(
        user.id,
        LeaveType.ANNUAL,
        date(2026, 8, 3),
        date(2026, 8, 5),
        "  项目休整  ",
        session,
    )

    assert draft.leave_days == 3
    assert draft.reason == "项目休整"
    assert session.exec(select(LeaveRequest)).all() == []

    with pytest.raises(AppError) as insufficient:
        build_leave_request_draft(
            user.id,
            LeaveType.ANNUAL,
            date(2026, 8, 3),
            date(2026, 8, 6),
            "超出余额",
            session,
        )
    assert_app_error(insufficient, "LEAVE_BALANCE_INSUFFICIENT")


def test_submit_is_idempotent_and_deducts_balance_once(session: Session) -> None:
    user, _ = create_employee_with_balance(session)
    draft = build_leave_request_draft(
        user.id,
        LeaveType.ANNUAL,
        date(2026, 8, 3),
        date(2026, 8, 5),
        "家庭事务",
        session,
    )

    first = submit_leave_request(draft, "action-001", session)
    second = submit_leave_request(draft, "action-001", session)

    assert first.id == second.id
    assert len(session.exec(select(LeaveRequest)).all()) == 1
    balance = get_leave_balance(user.id, LeaveType.ANNUAL, session)
    assert balance.used_days == 3


def test_submit_rechecks_owner_and_overlap_after_pause(session: Session) -> None:
    user, employee = create_employee_with_balance(session)
    original_draft = build_leave_request_draft(
        user.id,
        LeaveType.ANNUAL,
        date(2026, 8, 3),
        date(2026, 8, 5),
        "原草稿",
        session,
    )

    with pytest.raises(AppError) as wrong_owner:
        submit_leave_request(
            replace(original_draft, employee_id=User(name="伪造").id),
            "action-forged",
            session,
        )
    assert_app_error(wrong_owner, "LEAVE_DRAFT_OWNER_CONFLICT")

    newer_draft = build_leave_request_draft(
        user.id,
        LeaveType.ANNUAL,
        date(2026, 8, 4),
        date(2026, 8, 4),
        "确认期间的新申请",
        session,
    )
    submit_leave_request(newer_draft, "action-newer", session)

    with pytest.raises(AppError) as overlap:
        submit_leave_request(original_draft, "action-original", session)
    assert_app_error(overlap, "LEAVE_REQUEST_OVERLAP")
    assert len(session.exec(select(LeaveRequest)).all()) == 1
    assert employee.id == original_draft.employee_id


def test_request_queries_are_scoped_to_current_user(session: Session) -> None:
    owner, _ = create_employee_with_balance(session)
    other, _ = create_employee_with_balance(
        session,
        name="其他员工",
        employee_no="EMP-002",
    )
    draft = build_leave_request_draft(
        owner.id,
        LeaveType.ANNUAL,
        date(2026, 8, 3),
        date(2026, 8, 3),
        "私有申请",
        session,
    )
    leave_request = submit_leave_request(draft, "action-private", session)

    assert [item.id for item in list_leave_requests(owner.id, session)] == [
        leave_request.id
    ]
    assert list_leave_requests(other.id, session) == []
    with pytest.raises(AppError) as hidden:
        get_leave_request(other.id, leave_request.id, session)
    assert_app_error(hidden, "LEAVE_REQUEST_NOT_FOUND")
