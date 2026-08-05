"""提供 Agent 工具调用的安全错误转换、重试和观测。"""

import logging
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock
from time import perf_counter
from uuid import uuid4

from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest, ToolInvocationError
from langgraph.types import Command, RetryPolicy

from app.agents.tools import AgentContextError
from app.core.errors import AppError
from app.core.evaluation import eval_wrap


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolObservation:
    """保存一次工具执行尝试的安全观测数据。

    Attributes:
        tool_call_id: 模型生成的工具调用标识。
        tool_name: 工具名称。
        status: 本次尝试成功或失败。
        duration_ms: 本次尝试的墙钟耗时毫秒数。
        error_code: 失败时的稳定错误分类；成功时为空。
    """

    tool_call_id: str
    tool_name: str
    status: str
    duration_ms: float
    error_code: str | None


# ToolNode 在线程池中执行工具。ContextVar 负责把 scope ID 复制到工作
# 线程；带锁注册表负责把工作线程结果安全地汇总回请求线程。
_OBSERVATION_SCOPE: ContextVar[str | None] = ContextVar(
    "agent_tool_observation_scope",
    default=None,
)
_OBSERVATION_REGISTRY: dict[str, list[ToolObservation]] = {}
_OBSERVATION_LOCK = Lock()


# 业务校验和权限错误重试没有意义，因此只重试短暂的连接与超时故障。
TOOL_RETRY_POLICY = RetryPolicy(
    initial_interval=0.2,
    backoff_factor=2.0,
    max_interval=1.0,
    max_attempts=3,
    jitter=False,
    retry_on=(TimeoutError, ConnectionError),
)


def begin_tool_observation() -> None:
    """清空当前请求中上一次 Graph 执行留下的工具观测。"""
    scope_id = str(uuid4())
    _OBSERVATION_SCOPE.set(scope_id)
    with _OBSERVATION_LOCK:
        _OBSERVATION_REGISTRY[scope_id] = []


def consume_tool_observations() -> tuple[ToolObservation, ...]:
    """取出并清空当前 Graph 执行产生的工具观测。

    Returns:
        按实际尝试顺序排列的不可变观测集合。
    """
    scope_id = _OBSERVATION_SCOPE.get()
    _OBSERVATION_SCOPE.set(None)
    if scope_id is None:
        return ()
    with _OBSERVATION_LOCK:
        return tuple(_OBSERVATION_REGISTRY.pop(scope_id, []))


def classify_tool_error(error: Exception) -> str:
    """把工具异常转换为稳定且不包含异常正文的错误代码。

    Args:
        error: 工具执行或参数注入阶段产生的异常。

    Returns:
        可写入审计表和用于指标聚合的错误代码。
    """
    if isinstance(error, TimeoutError):
        return "AGENT_TOOL_TIMEOUT"
    if isinstance(error, ConnectionError):
        return "AGENT_TOOL_CONNECTION_FAILED"
    if isinstance(error, ToolInvocationError):
        return "AGENT_TOOL_ARGUMENT_INVALID"
    if isinstance(error, AgentContextError):
        return "AGENT_CONTEXT_MISSING"
    if isinstance(error, AppError):
        return error.code
    return "AGENT_TOOL_FAILED"


def _append_tool_observation(observation: ToolObservation) -> None:
    """把一条安全观测追加到当前请求上下文。

    Args:
        observation: 不包含工具参数、结果正文或异常消息的观测数据。
    """
    scope_id = _OBSERVATION_SCOPE.get()
    if scope_id is None:
        return
    with _OBSERVATION_LOCK:
        observations = _OBSERVATION_REGISTRY.get(scope_id)
        if observations is not None:
            observations.append(observation)


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
    error_code = classify_tool_error(error)
    eval_wrap(
        error_code,
        purpose="state",
        name="tool_error",
        description="不包含异常正文的工具失败分类",
    )
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
        duration_ms = (perf_counter() - started_at) * 1000
        _append_tool_observation(
            ToolObservation(
                tool_call_id=str(request.tool_call.get("id", "")),
                tool_name=tool_name,
                status="FAILED",
                duration_ms=duration_ms,
                error_code=classify_tool_error(exc),
            )
        )
        logger.warning(
            "agent_tool_call_failed tool=%s error_type=%s duration_ms=%.2f",
            tool_name,
            type(exc).__name__,
            duration_ms,
        )
        raise

    duration_ms = (perf_counter() - started_at) * 1000
    status = (
        result.status
        if isinstance(result, ToolMessage)
        else "command"
    )
    _append_tool_observation(
        ToolObservation(
            tool_call_id=str(request.tool_call.get("id", "")),
            tool_name=tool_name,
            status="COMPLETED",
            duration_ms=duration_ms,
            error_code=None,
        )
    )
    logger.info(
        "agent_tool_call_finished tool=%s status=%s duration_ms=%.2f",
        tool_name,
        status,
        duration_ms,
    )
    return result
