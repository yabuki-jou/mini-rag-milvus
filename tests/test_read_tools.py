"""验证企业行政 Agent 只读工具的 Schema、注入上下文和数据隔离。"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.agents.tools import (
    AgentContextError,
    get_my_leave_request,
    list_my_leave_requests,
    query_my_leave_balance,
    search_company_policy,
)
from app.agents.tools import leave_tools, policy_tools
from app.core.errors import AppError
from app.models import LeaveRequest, LeaveType, User
from app.services.leave_service import (
    create_employee_profile,
    list_leave_requests,
    set_leave_balance,
)


@pytest.fixture
def tool_engine(monkeypatch: pytest.MonkeyPatch):
    """让请假工具使用隔离的内存 SQLite，而不是项目业务库。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(leave_tools, "engine", engine)
    yield engine
    engine.dispose()


def create_employee(
    engine,
    *,
    name: str,
    employee_no: str,
) -> tuple[UUID, UUID]:
    """创建工具测试需要的用户、员工和年假余额。"""
    with Session(engine) as session:
        user = User(name=name)
        session.add(user)
        session.commit()
        session.refresh(user)
        employee = create_employee_profile(user, employee_no, "研发部", session)
        set_leave_balance(employee, LeaveType.ANNUAL, 10, 3, session)
        user_id = user.id
        employee_id = employee.id
    return user_id, employee_id


def visible_properties(agent_tool) -> set[str]:
    """读取实际提供给模型的 Tool Call JSON Schema 字段。"""
    schema = agent_tool.tool_call_schema.model_json_schema()
    return set(schema.get("properties", {}))


def test_tool_schemas_hide_all_authorization_fields() -> None:
    """模型只能看到业务参数，不能生成用户、员工或知识库身份。"""
    assert visible_properties(search_company_policy) == {"query"}
    assert visible_properties(query_my_leave_balance) == {"leave_type"}
    assert visible_properties(list_my_leave_requests) == set()
    assert visible_properties(get_my_leave_request) == {"request_id"}

    for agent_tool in (
        search_company_policy,
        query_my_leave_balance,
        list_my_leave_requests,
        get_my_leave_request,
    ):
        properties = visible_properties(agent_tool)
        assert "user_id" not in properties
        assert "kb_id" not in properties
        assert "employee_id" not in properties


def test_tool_schema_rejects_unknown_leave_type() -> None:
    """假期类型必须由枚举约束，不能让模型生成任意字符串。"""
    with pytest.raises(ValidationError):
        query_my_leave_balance.tool_call_schema.model_validate(
            {"leave_type": "VACATION"}
        )


def test_policy_tool_forwards_injected_scope_and_serializes_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """制度工具应把注入身份原样传给现有检索服务。"""
    user_id = uuid4()
    kb_id = uuid4()
    document_id = uuid4()
    retrieve_mock = Mock(
        return_value=[
            SimpleNamespace(
                chunk_id="a" * 64,
                document_id=document_id,
                document_name="休假制度.pdf",
                page=3,
                content="年假可以按照制度结转。",
                score=0.82,
            )
        ]
    )
    monkeypatch.setattr(policy_tools, "retrieve_chunks", retrieve_mock)

    result = search_company_policy.func(
        query="  年假如何结转？  ",
        state={"user_id": str(user_id), "kb_id": str(kb_id)},
    )

    retrieve_mock.assert_called_once_with(
        user_id=user_id,
        kb_id=kb_id,
        question="年假如何结转？",
    )
    assert result["found"] is True
    assert result["message"] is None
    assert result["results"][0]["document_id"] == str(document_id)
    assert result["results"][0]["page"] == 3


def test_policy_tool_returns_explicit_no_evidence_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """没有合格 Chunk 时必须明确拒答并返回空结果。"""
    monkeypatch.setattr(policy_tools, "retrieve_chunks", Mock(return_value=[]))

    result = search_company_policy.func(
        query="不存在的制度",
        state={"user_id": str(uuid4()), "kb_id": str(uuid4())},
    )

    assert result == {
        "query": "不存在的制度",
        "found": False,
        "message": "知识库中没有足够依据。",
        "results": [],
    }


def test_policy_tool_preserves_safe_retrieval_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """检索服务已经转换的安全业务错误不应被工具改写或泄露细节。"""
    safe_error = AppError(503, "MILVUS_SEARCH_FAILED", "知识库向量检索失败。")
    monkeypatch.setattr(
        policy_tools,
        "retrieve_chunks",
        Mock(side_effect=safe_error),
    )

    with pytest.raises(AppError) as raised:
        search_company_policy.func(
            query="年假制度",
            state={"user_id": str(uuid4()), "kb_id": str(uuid4())},
        )
    assert raised.value is safe_error


def test_read_tools_reject_missing_or_invalid_injected_context() -> None:
    """缺少服务端身份时不得尝试执行查询。"""
    with pytest.raises(AgentContextError):
        query_my_leave_balance.func(
            leave_type=LeaveType.ANNUAL,
            state={},
        )
    with pytest.raises(AgentContextError):
        search_company_policy.func(
            query="年假制度",
            state={"user_id": "invalid", "kb_id": str(uuid4())},
        )


def test_balance_tool_queries_current_user_only(tool_engine) -> None:
    """余额结果应来自注入用户对应的员工资料。"""
    user_id, _ = create_employee(
        tool_engine,
        name="余额员工",
        employee_no="EMP-101",
    )

    result = query_my_leave_balance.func(
        leave_type=LeaveType.ANNUAL,
        state={"user_id": str(user_id)},
    )

    assert result == {
        "leave_type": "ANNUAL",
        "total_days": 10,
        "used_days": 3,
        "available_days": 7,
    }


def test_list_tool_returns_latest_twenty_without_reasons(tool_engine) -> None:
    """列表固定返回当前员工最近 20 条，并省略详情字段。"""
    user_id, employee_id = create_employee(
        tool_engine,
        name="列表员工",
        employee_no="EMP-102",
    )
    other_user_id, other_employee_id = create_employee(
        tool_engine,
        name="其他员工",
        employee_no="EMP-103",
    )
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    with Session(tool_engine) as session:
        for index in range(25):
            request_date = datetime(2026, 2, 1, tzinfo=UTC).date() + timedelta(
                days=index
            )
            session.add(
                LeaveRequest(
                    employee_id=employee_id,
                    leave_type=LeaveType.ANNUAL,
                    start_date=request_date,
                    end_date=request_date,
                    leave_days=1,
                    reason=f"员工申请 {index}",
                    idempotency_key=f"owner-{index}",
                    created_at=base_time + timedelta(minutes=index),
                )
            )
        session.add(
            LeaveRequest(
                employee_id=other_employee_id,
                leave_type=LeaveType.ANNUAL,
                start_date=datetime(2026, 4, 1, tzinfo=UTC).date(),
                end_date=datetime(2026, 4, 1, tzinfo=UTC).date(),
                leave_days=1,
                reason="不应泄露",
                idempotency_key="other-request",
                created_at=base_time + timedelta(days=10),
            )
        )
        session.commit()

    result = list_my_leave_requests.func(state={"user_id": str(user_id)})

    assert len(result["requests"]) == 20
    assert [item["created_at"] for item in result["requests"]] == sorted(
        [item["created_at"] for item in result["requests"]],
        reverse=True,
    )
    assert all("reason" not in item for item in result["requests"])
    assert all("不应泄露" not in str(item) for item in result["requests"])
    assert other_user_id != user_id


def test_list_tool_returns_empty_array_when_user_has_no_requests(tool_engine) -> None:
    """没有申请是正常业务结果，不应虚构记录或抛出异常。"""
    user_id, _ = create_employee(
        tool_engine,
        name="无申请员工",
        employee_no="EMP-107",
    )

    result = list_my_leave_requests.func(state={"user_id": str(user_id)})

    assert result == {"requests": []}


def test_detail_tool_hides_another_users_request(tool_engine) -> None:
    """知道其他申请 UUID 也不能读取其详情。"""
    owner_id, employee_id = create_employee(
        tool_engine,
        name="申请所有者",
        employee_no="EMP-104",
    )
    other_id, _ = create_employee(
        tool_engine,
        name="越权访问者",
        employee_no="EMP-105",
    )
    with Session(tool_engine) as session:
        leave_request = LeaveRequest(
            employee_id=employee_id,
            leave_type=LeaveType.ANNUAL,
            start_date=datetime(2026, 5, 4, tzinfo=UTC).date(),
            end_date=datetime(2026, 5, 4, tzinfo=UTC).date(),
            leave_days=1,
            reason="家庭事务",
            idempotency_key="private-request",
        )
        session.add(leave_request)
        session.commit()
        session.refresh(leave_request)
        request_id = leave_request.id

    owner_result = get_my_leave_request.func(
        request_id=request_id,
        state={"user_id": str(owner_id)},
    )
    assert owner_result["reason"] == "家庭事务"

    with pytest.raises(AppError) as hidden:
        get_my_leave_request.func(
            request_id=request_id,
            state={"user_id": str(other_id)},
        )
    assert hidden.value.code == "LEAVE_REQUEST_NOT_FOUND"


def test_leave_request_service_rejects_non_positive_limit(tool_engine) -> None:
    """即使内部调用错误，也不能执行无界或无意义的列表查询。"""
    user_id, _ = create_employee(
        tool_engine,
        name="限制员工",
        employee_no="EMP-106",
    )
    with Session(tool_engine) as session:
        with pytest.raises(AppError) as invalid_limit:
            list_leave_requests(user_id, session, limit=0)
    assert invalid_limit.value.code == "LEAVE_REQUEST_LIMIT_INVALID"
