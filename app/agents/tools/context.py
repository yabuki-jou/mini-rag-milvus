"""校验由 Agent 运行环境注入的可信上下文。"""

from typing import Any
from uuid import UUID


class AgentContextError(ValueError):
    """表示工具缺少有效的服务端授权上下文。"""


def require_state_uuid(state: dict[str, Any], field_name: str) -> UUID:
    """从 Graph State 读取并校验一个必需的 UUID 字段。

    参数:
        state: LangGraph 注入的可序列化状态。
        field_name: 需要读取的状态字段名。

    返回:
        规范化后的 UUID。

    异常:
        AgentContextError: 状态缺少字段或字段不是有效 UUID 时抛出。
    """
    raw_value = state.get(field_name)
    try:
        return raw_value if isinstance(raw_value, UUID) else UUID(str(raw_value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AgentContextError(
            f"缺少或无效的服务端上下文字段：{field_name}。"
        ) from exc
