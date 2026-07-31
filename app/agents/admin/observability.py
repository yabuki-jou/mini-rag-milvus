"""提供 Agent 工具调用的安全错误转换、重试和观测。"""

import logging
from collections.abc import Callable
from time import perf_counter

from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest, ToolInvocationError
from langgraph.types import Command, RetryPolicy

from app.agents.tools import AgentContextError
from app.core.errors import AppError


logger = logging.getLogger(__name__)


# 业务校验和权限错误重试没有意义，因此只重试短暂的连接与超时故障。
TOOL_RETRY_POLICY = RetryPolicy(
    initial_interval=0.2,
    backoff_factor=2.0,
    max_interval=1.0,
    max_attempts=3,
    jitter=False,
    retry_on=(TimeoutError, ConnectionError),
)


def handle_tool_error(error: Exception) -> str:
    """把工具异常转换成模型可见且不会泄露内部细节的消息。

    Args:
        error: ToolNode 捕获到的工具参数、上下文或业务异常。

    Returns:
        可安全提供给模型的简短中文错误消息。
    """
    # 临时故障必须继续抛给节点级 RetryPolicy；否则 ToolNode 在内部把它
    # 转成 ToolMessage 后，重试策略将永远看不到该异常。
    if isinstance(error, (TimeoutError, ConnectionError)):
        raise error
    if isinstance(error, ToolInvocationError):
        return "工具参数校验失败，请检查输入格式。"
    if isinstance(error, AgentContextError):
        return "缺少有效的 Agent 授权上下文。"
    if isinstance(error, AppError):
        return error.message
    return "工具执行失败，请稍后重试。"


def observe_tool_call(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    """记录工具名称、状态、耗时和异常类型，不记录参数与结果正文。

    Args:
        request: ToolNode 即将执行的工具调用请求。
        execute: 继续执行工具调用链的回调。

    Returns:
        工具产生的消息，或后续控制流工具产生的 Command。

    Raises:
        Exception: 工具执行异常会在记录安全摘要后原样抛出，以便
            RetryPolicy 或 ToolNode 的错误处理继续生效。
    """
    tool_name = request.tool_call["name"]
    started_at = perf_counter()

    try:
        result = execute(request)
    except Exception as exc:
        logger.warning(
            "agent_tool_call_failed tool=%s error_type=%s duration_ms=%.2f",
            tool_name,
            type(exc).__name__,
            (perf_counter() - started_at) * 1000,
        )
        raise

    status = (
        result.status
        if isinstance(result, ToolMessage)
        else "command"
    )
    logger.info(
        "agent_tool_call_finished tool=%s status=%s duration_ms=%.2f",
        tool_name,
        status,
        (perf_counter() - started_at) * 1000,
    )
    return result
