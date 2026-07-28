"""企业行政 Agent 使用的只读请假业务工具。"""

from typing import Annotated, Any
from uuid import UUID

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import Field
from sqlmodel import Session

from app.agents.tools.context import require_state_uuid
from app.db import engine
from app.models import LeaveRequest, LeaveType
from app.services.leave_service import (
    get_leave_balance,
    get_leave_request,
    list_leave_requests,
)


def _serialize_request(
    leave_request: LeaveRequest,
    *,
    include_reason: bool,
) -> dict[str, Any]:
    """把数据库申请转换为可序列化的工具结果。"""
    result: dict[str, Any] = {
        "request_id": str(leave_request.id),
        "leave_type": leave_request.leave_type.value,
        "start_date": leave_request.start_date.isoformat(),
        "end_date": leave_request.end_date.isoformat(),
        "leave_days": leave_request.leave_days,
        "status": leave_request.status.value,
        "created_at": leave_request.created_at.isoformat(),
    }
    if include_reason:
        result["reason"] = leave_request.reason
    return result


@tool
def query_my_leave_balance(
    leave_type: Annotated[
        LeaveType,
        Field(description="需要查询的假期类型：ANNUAL 或 SICK"),
    ],
    state: Annotated[dict[str, Any], InjectedState],
) -> dict[str, Any]:
    """查询当前用户自己的指定假期余额。"""
    user_id = require_state_uuid(state, "user_id")
    with Session(engine) as session:
        balance = get_leave_balance(user_id, leave_type, session)

    return {
        "leave_type": balance.leave_type.value,
        "total_days": balance.total_days,
        "used_days": balance.used_days,
        "available_days": balance.total_days - balance.used_days,
    }


@tool
def list_my_leave_requests(
    state: Annotated[dict[str, Any], InjectedState],
) -> dict[str, Any]:
    """按创建时间倒序列出当前用户最近 20 条请假申请。"""
    user_id = require_state_uuid(state, "user_id")
    with Session(engine) as session:
        leave_requests = list_leave_requests(user_id, session, limit=20)

    return {
        "requests": [
            _serialize_request(item, include_reason=False)
            for item in leave_requests
        ]
    }


@tool
def get_my_leave_request(
    request_id: Annotated[
        UUID,
        Field(description="需要查看的请假申请 UUID"),
    ],
    state: Annotated[dict[str, Any], InjectedState],
) -> dict[str, Any]:
    """查看当前用户自己的一条请假申请详情。"""
    user_id = require_state_uuid(state, "user_id")
    with Session(engine) as session:
        leave_request = get_leave_request(user_id, request_id, session)
        return _serialize_request(leave_request, include_reason=True)
