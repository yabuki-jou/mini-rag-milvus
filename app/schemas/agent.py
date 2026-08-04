"""定义企业知识库 Agent HTTP 接口的请求与响应契约。"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import AgentToolCallStatus, MessageRole
from app.schemas.chat import SourceRead


class AgentExecutionStatus(str, Enum):
    """表示一次 Agent HTTP 执行已经完成。

    Attributes:
        COMPLETED: 本轮 Graph 已经执行结束。
    """

    COMPLETED = "COMPLETED"


class AgentSessionCreate(BaseModel):
    """创建 Agent 会话时允许客户端提交的字段。

    Attributes:
        kb_id: 当前用户希望绑定的知识库 UUID。
    """

    model_config = ConfigDict(extra="forbid")
    kb_id: UUID


class AgentSessionRead(BaseModel):
    """返回给客户端的 Agent 会话基本信息。

    Attributes:
        id: Agent 会话 UUID。
        kb_id: 会话固定绑定的知识库 UUID。
        thread_id: 对应 LangGraph Checkpoint 的线程标识。
        created_at: 会话创建时间。
        updated_at: 最近一次成功执行时间。
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kb_id: UUID
    thread_id: str
    created_at: datetime
    updated_at: datetime


class AgentMessageCreate(BaseModel):
    """向 Agent 会话发送一条自然语言消息。

    Attributes:
        message: 当前用户输入的自然语言内容。
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=2000)


class AgentResponse(BaseModel):
    """发送消息后的 Agent 执行响应。

    Attributes:
        session_id: 本次执行所属的 Agent 会话。
        status: 当前只读执行已完成。
        answer: 当前可展示的回答或确认提示。
        sources: 本轮制度问答使用的结构化引用。
        request_id: 当前 HTTP 请求的链路追踪 ID。
    """

    session_id: UUID
    status: AgentExecutionStatus
    answer: str = Field(min_length=1)
    sources: list[SourceRead] = Field(default_factory=list)
    request_id: str = Field(min_length=1)


class AgentMessageRead(BaseModel):
    """从 Checkpoint 转换出的用户可见 Agent 消息。

    Attributes:
        role: 用户或助手角色。
        content: 用户输入或助手自然语言回答。
        sources: 当前助手回答使用的制度引用。
    """

    role: MessageRole
    content: str = Field(min_length=1)
    sources: list[SourceRead] = Field(default_factory=list)


class AgentToolCallLogRead(BaseModel):
    """返回给会话所有者的脱敏工具调用记录。

    Attributes:
        id: 日志记录 UUID。
        tool_call_id: 模型工具调用标识。
        tool_name: 工具名称。
        status: 调用当前状态。
        arguments_summary: 不包含身份字段的参数摘要。
        result_summary: 不包含制度正文的结果摘要。
        duration_ms: 工具耗时；A-08 精确观测前可能为空。
        error_code: 失败时的稳定错误代码。
        created_at: 首次记录时间。
        updated_at: 最近状态变化时间。
    """

    id: UUID
    tool_call_id: str
    tool_name: str
    status: AgentToolCallStatus
    arguments_summary: dict[str, Any] | None
    result_summary: dict[str, Any] | None
    duration_ms: float | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime
