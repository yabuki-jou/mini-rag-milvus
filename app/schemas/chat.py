"""定义聊天会话、提问、回答、引用和历史消息的数据结构。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import MessageRole


class ChatSessionCreate(BaseModel):
    """创建聊天会话时允许客户端提交的字段。

    Attributes:
        kb_id: 新会话绑定的知识库 UUID。
    """

    model_config = ConfigDict(extra="forbid")

    kb_id: UUID


class ChatSessionRead(BaseModel):
    """返回给客户端的聊天会话信息。

    Attributes:
        id: 会话的全局唯一标识。
        user_id: 会话所属用户的 UUID。
        kb_id: 会话绑定的知识库 UUID。
        created_at: 会话创建时间。
        updated_at: 会话最后一次更新时间。
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    kb_id: UUID
    created_at: datetime
    updated_at: datetime


class ChatQuestionRequest(BaseModel):
    """发送聊天消息时提交的问题。

    Attributes:
        question: 需要根据知识库回答的自然语言问题。
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    question: str = Field(min_length=1, max_length=2000)


class SourceRead(BaseModel):
    """回答中实际使用的一个引用来源。

    Attributes:
        source_id: 当前回答中的引用编号，例如 ``S1``。
        chunk_id: 引用 Chunk 的稳定 SHA-256 标识。
        document_id: Chunk 所属文档的 UUID。
        document_name: 用于展示的原文件名。
        page: Chunk 所属的原始页码。
        excerpt: 返回给客户端的原文摘录。
        score: Chunk 的原始 COSINE 相似度。
    """

    source_id: str = Field(min_length=2, max_length=20)
    chunk_id: str = Field(min_length=64, max_length=64)
    document_id: UUID
    document_name: str = Field(min_length=1, max_length=1024)
    page: int = Field(ge=1)
    excerpt: str = Field(min_length=1)
    score: float = Field(ge=-1.0, le=1.0)


class ChatAnswerResponse(BaseModel):
    """发送问题后返回的回答和引用。

    Attributes:
        answer: DeepSeek 生成的回答或系统预设的拒答文本。
        rejected: 是否因为没有合格 Chunk 而直接拒答。
        sources: 实际进入 Prompt 的 Chunk 引用。
    """

    answer: str = Field(min_length=1)
    rejected: bool
    sources: list[SourceRead]


class ChatMessageRead(BaseModel):
    """返回给客户端的一条历史聊天消息。

    Attributes:
        id: 消息的全局唯一标识。
        session_id: 消息所属会话的 UUID。
        role: 用户消息或助手消息。
        content: 问题或回答正文。
        sources: 助手回答使用的结构化引用；用户消息为空。
        created_at: 消息创建时间。
    """

    id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    sources: list[SourceRead] = Field(default_factory=list)
    created_at: datetime