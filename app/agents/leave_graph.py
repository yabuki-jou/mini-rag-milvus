"""使用 LangGraph 编排请假业务模型与工具。"""

import logging
from collections.abc import Callable
from time import perf_counter
from typing import NotRequired
from uuid import UUID

from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.prebuilt.tool_node import (
    ToolCallRequest,
    ToolInvocationError,
)
from langgraph.types import Command, RetryPolicy

from app.agents.tools import query_leave_balance, search_company_policy
from app.agents.tools.leave_tools import EmployeeNotFoundError
from app.agents.tools.policy_tools import AgentContextError
from app.core.errors import AppError
from app.services.model_service import get_chat_model

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """
你是企业行政助手。

只有当用户明确要求查询假期余额，并且提供了员工编号时，
才调用 query_leave_balance。

不得猜测员工编号，不得编造假期余额。
缺少员工编号时，应要求用户补充，而不是调用工具。

只有当用户询问公司制度、规定或流程时，才调用
search_company_policy。检索所需的用户和知识库身份由系统注入，
不得要求用户提供，也不得自行猜测。

工具执行成功后，根据工具返回的真实数据生成最终回答。
工具返回错误时，不要使用相同参数反复调用工具。
应根据错误说明问题，并要求用户核对或补充信息。
"""

_TOOLS = [query_leave_balance, search_company_policy]


class AgentState(MessagesState):
    """保存对话消息以及服务端注入的授权检索范围。"""

    # 保持字段可选，让原有只查询假期余额的调用方式继续可用。
    user_id: NotRequired[UUID]
    kb_id: NotRequired[UUID]

TOOL_RETRY_POLICY = RetryPolicy(
    initial_interval=0.2,
    backoff_factor=2.0,
    max_interval=1.0,
    max_attempts=3,
    jitter=False,
    retry_on=(TimeoutError, ConnectionError),
)

def handle_tool_error(
    error: Exception,
) -> str:
    """把已知工具错误转换成可供模型处理的安全消息。"""
    if isinstance(error, ToolInvocationError):
        return "工具参数校验失败，请检查输入格式。"

    if isinstance(error, AgentContextError):
        return str(error)

    if isinstance(error, AppError):
        return error.message

    if isinstance(error, EmployeeNotFoundError):
        return str(error)

    return "工具执行失败，请稍后重试。"

def observe_tool_call(
    request: ToolCallRequest,
    execute: Callable[
        [ToolCallRequest],
        ToolMessage | Command,
    ],
) -> ToolMessage | Command:
    """记录一次工具执行的名称、参数、结果、耗时和错误。"""
    tool_call = request.tool_call
    tool_name = tool_call["name"]
    tool_args = tool_call.get("args", {})
    started_at = perf_counter()

    try:
        result = execute(request)
    except Exception as exc:
        # 未处理异常需要保留堆栈，但仍交给 RetryPolicy 或上层处理。
        logger.exception(
            "tool_call_failed tool=%s args=%r "
            "error_type=%s duration_ms=%.2f",
            tool_name,
            tool_args,
            type(exc).__name__,
            (perf_counter() - started_at) * 1000,
        )
        raise

    duration_ms = (perf_counter() - started_at) * 1000

    if isinstance(result, ToolMessage):
        if result.status == "error":
            logger.warning(
                "tool_call_finished tool=%s args=%r "
                "status=error error=%r duration_ms=%.2f",
                tool_name,
                tool_args,
                result.content,
                duration_ms,
            )
        else:
            logger.info(
                "tool_call_finished tool=%s args=%r "
                "status=success result=%r duration_ms=%.2f",
                tool_name,
                tool_args,
                result.content,
                duration_ms,
            )
    else:
        # 当前工具返回 ToolMessage；保留 Command 分支以兼容后续控制流工具。
        logger.info(
            "tool_call_finished tool=%s args=%r "
            "status=command result=%r duration_ms=%.2f",
            tool_name,
            tool_args,
            result,
            duration_ms,
        )

    return result

def call_model(state: AgentState) -> dict:
    """调用绑定了业务工具的 DeepSeek，并把回复追加到状态。"""
    model_with_tools = get_chat_model().bind_tools(_TOOLS)

    response = model_with_tools.invoke(
        [
            SystemMessage(content=_SYSTEM_PROMPT),
            *state["messages"],
        ]
    )

    # MessagesState 会把新消息追加到已有消息，而不是覆盖整个列表。
    return {"messages": [response]}


def build_leave_graph():
    """构建并编译假期业务 Agent 状态图。"""
    builder = StateGraph(AgentState)

    builder.add_node("model", call_model)
    builder.add_node(
        "tools",
        ToolNode(
            _TOOLS,
            handle_tool_errors=handle_tool_error,
            wrap_tool_call=observe_tool_call,
        ),
        retry_policy=TOOL_RETRY_POLICY,
    )

    builder.add_edge(START, "model")

    # 模型生成 tool_calls 时进入 tools，否则路由到 END。
    builder.add_conditional_edges(
        "model",
        tools_condition,
    )

    # 工具执行结果必须返回模型，才能生成面向用户的最终回答。
    builder.add_edge("tools", "model")

    return builder.compile()


leave_graph = build_leave_graph()
