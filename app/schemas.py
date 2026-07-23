"""定义 API 请求与响应使用的数据结构。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import DocumentStatus


class HealthComponent(BaseModel):
    """一个基础组件的健康状态。

    Attributes:
        status: 单个组件的 ``ok`` 或 ``error`` 状态。
        detail: 维度、Collection 数量或错误摘要。
    """

    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    """应用及其依赖组件的整体健康状态。

    Attributes:
        status: 全部正常时为 ``ok``，否则为 ``degraded``。
        components: API、数据库、Milvus 和 Embedding 的独立状态。
    """

    status: str
    components: dict[str, HealthComponent]


class UserCreate(BaseModel):
    """创建用户时允许客户端提交的字段。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)


class UserRead(BaseModel):
    """返回给客户端的用户信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseCreate(BaseModel):
    """创建知识库时允许客户端提交的字段。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)


class KnowledgeBaseRead(BaseModel):
    """返回给客户端的知识库信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class DocumentRead(BaseModel):
    """返回给客户端的文档信息，不暴露服务器存储路径。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kb_id: UUID
    filename: str
    content_hash: str
    status: DocumentStatus
    chunk_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
