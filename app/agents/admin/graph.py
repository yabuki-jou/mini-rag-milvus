"""构建企业行政 Agent 的只读 LangGraph 编排。"""

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agents.admin.observability import (
    TOOL_RETRY_POLICY,
    handle_tool_error,
    observe_tool_call,
)
from app.agents.admin.prompts import ADMIN_AGENT_SYSTEM_PROMPT
from app.agents.admin.state import AdminAgentState
from app.agents.tools import (
    get_my_leave_request,
    list_my_leave_requests,
    query_my_leave_balance,
    search_company_policy,
)
from app.agents.tools.context import require_state_uuid


READ_TOOLS: tuple[BaseTool, ...] = (
    search_company_policy,
    query_my_leave_balance,
    list_my_leave_requests,
    get_my_leave_request,
)


def validate_authorized_context(
    state: AdminAgentState,
) -> dict[str, str]:
    """校验并规范化应用服务写入 Graph 的授权范围。

    Args:
        state: 包含当前用户和知识库范围的 Agent 状态。

    Returns:
        可安全持久化的标准 UUID 字符串字段。

    Raises:
        AgentContextError: 用户或知识库字段缺失、格式无效时抛出。
    """
    user_id = require_state_uuid(dict(state), "user_id")
    kb_id = require_state_uuid(dict(state), "kb_id")
    return {"user_id": str(user_id), "kb_id": str(kb_id)}


def build_admin_graph(
    model: Any,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
    tools: Sequence[BaseTool] | None = None,
) -> Any:
    """构建并编译仅包含只读工具的企业行政 Agent。

    Args:
        model: 支持 ``bind_tools`` 和 ``invoke`` 的聊天模型；生产环境传入
            DeepSeek，测试传入确定性的模拟模型。
        checkpointer: 可选的 LangGraph 状态持久化器。
        tools: 可选的只读工具集合，主要用于隔离测试；默认注册四个
            正式企业行政只读工具。

    Returns:
        已编译、可通过 ``invoke`` 执行的 LangGraph 状态图。

    图只持有绑定后的模型引用，不把模型写入 Graph State 或 Checkpoint。
    """
    selected_tools = READ_TOOLS if tools is None else tuple(tools)
    model_with_tools = model.bind_tools(selected_tools)

    def call_model(state: AdminAgentState) -> dict[str, list[Any]]:
        """把系统规则和当前消息交给模型，并追加模型回复。"""
        response = model_with_tools.invoke(
            [
                SystemMessage(content=ADMIN_AGENT_SYSTEM_PROMPT),
                *state["messages"],
            ]
        )
        # MessagesState 的 reducer 会追加新消息，而不是覆盖历史消息。
        return {"messages": [response]}

    builder = StateGraph(AdminAgentState)
    builder.add_node("validate_context", validate_authorized_context)
    builder.add_node("model", call_model)
    builder.add_node(
        "tools",
        ToolNode(
            selected_tools,
            handle_tool_errors=handle_tool_error,
            wrap_tool_call=observe_tool_call,
        ),
        retry_policy=TOOL_RETRY_POLICY,
    )

    builder.add_edge(START, "validate_context")
    builder.add_edge("validate_context", "model")
    # 模型存在 tool_calls 时进入工具节点，否则 tools_condition 路由到 END。
    builder.add_conditional_edges("model", tools_condition)
    # 工具结果必须回到模型，才能转换成最终面向用户的回答。
    builder.add_edge("tools", "model")

    return builder.compile(checkpointer=checkpointer)
