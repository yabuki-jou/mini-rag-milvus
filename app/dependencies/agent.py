"""管理 FastAPI 请求使用的企业行政 Agent Runtime。"""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends

from app.agents.admin.runtime import AdminAgentRuntime, build_admin_runtime


def get_admin_agent_runtime() -> Generator[AdminAgentRuntime, None, None]:
    """为一个 HTTP 请求创建并关闭 Agent Runtime。

    Yields:
        连接共享 Checkpoint SQLite 的企业行政 Agent Runtime。
    """
    with build_admin_runtime() as runtime:
        yield runtime


# 测试可覆盖该依赖，从而使用确定性模型而不连接真实 DeepSeek。
AdminAgentRuntimeDep = Annotated[
    AdminAgentRuntime,
    Depends(get_admin_agent_runtime),
]
