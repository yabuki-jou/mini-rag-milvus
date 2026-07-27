"""定义聊天会话、消息角色和消息数据库实体。"""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.models.common import utc_now


class MessageRole(str, Enum):
    """表示聊天消息的发送角色。

    Attributes:
        USER: 用户发送的问题。
        ASSISTANT: 系统生成的回答。
    """

    USER = "USER"
    ASSISTANT = "ASSISTANT"


class ChatSession(SQLModel, table=True):
    """表示一个绑定用户和知识库的聊天会话。

    Attributes:
        id: 会话的全局唯一标识。
        user_id: 创建并拥有该会话的用户 ID。
        kb_id: 会话问答时使用的知识库 ID。
        created_at: 会话记录的 UTC 创建时间。
        updated_at: 会话记录最后一次更新的 UTC 时间。
    """

    __tablename__ = "chat_sessions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    kb_id: UUID = Field(foreign_key="knowledge_bases.id", index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ChatMessage(SQLModel, table=True):
    """表示聊天会话中的一条用户问题或助手回答。

    Attributes:
        id: 消息的全局唯一标识。
        session_id: 消息所属聊天会话的 ID。
        role: 消息由用户发送还是由助手生成。
        content: 问题或回答的完整正文。
        sources_json: 助手回答使用的引用信息 JSON；用户消息为空。
        created_at: 消息记录的 UTC 创建时间。
    """

    __tablename__ = "chat_messages"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    session_id: UUID = Field(
        foreign_key="chat_sessions.id",
        index=True,
    )
    role: MessageRole = Field(index=True)
    content: str = Field(min_length=1)
    sources_json: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=utc_now,
        index=True,
    )
