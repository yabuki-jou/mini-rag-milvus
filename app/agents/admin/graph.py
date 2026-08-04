"""构建企业知识库 Agent 的只读 LangGraph 编排。"""

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agents.admin.observability import (
    TOOL_RETRY_POLICY,
    handle_tool_error,
    observe_tool_call,
)
from app.agents.admin.prompts import ADMIN_AGENT_SYSTEM_PROMPT
from app.agents.admin.state import AdminAgentState
from app.agents.tools import search_company_policy
from app.agents.tools.context import require_state_uuid
from app.core.evaluation import eval_wrap


AGENT_TOOLS: tuple[BaseTool, ...] = (search_company_policy,)


def route_model_action(state: AdminAgentState) -> str:
    """有工具调用时执行工具，否则结束当前 Graph。"""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


def validate_authorized_context(state: AdminAgentState) -> dict[str, str]:
    """校验并规范化应用服务写入 Graph 的用户和知识库范围。"""
    user_id = require_state_uuid(dict(state), "user_id")
    kb_id = require_state_uuid(dict(state), "kb_id")
    context = {"user_id": str(user_id), "kb_id": str(kb_id)}
    eval_wrap(
        context,
        purpose="state",
        name="authorized_context",
        description="应用服务注入且由 Graph 校验的用户与知识库范围",
    )
    return context


def build_admin_graph(
    model: Any,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
    tools: Sequence[BaseTool] | None = None,
) -> Any:
    """构建制度检索工具闭环并接入可选 Checkpointer。"""
    selected_tools = AGENT_TOOLS if tools is None else tuple(tools)
    model_with_tools = model.bind_tools(selected_tools)

    def call_model(state: AdminAgentState) -> dict[str, list[Any]]:
        response = model_with_tools.invoke(
            [SystemMessage(content=ADMIN_AGENT_SYSTEM_PROMPT), *state["messages"]]
        )
        return {"messages": [response]}

    builder = StateGraph(AdminAgentState)
    builder.add_node("validate_context", validate_authorized_context)
    builder.add_node("model", call_model)
    builder.add_edge(START, "validate_context")
    builder.add_edge("validate_context", "model")

    route_targets: dict[str, str] = {END: END}
    if selected_tools:
        builder.add_node(
            "tools",
            ToolNode(
                selected_tools,
                handle_tool_errors=handle_tool_error,
                wrap_tool_call=observe_tool_call,
            ),
            retry_policy=TOOL_RETRY_POLICY,
        )
        builder.add_edge("tools", "model")
        route_targets["tools"] = "tools"

    builder.add_conditional_edges("model", route_model_action, route_targets)
    return builder.compile(checkpointer=checkpointer)
