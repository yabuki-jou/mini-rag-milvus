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
    """创建用户时允许客户端提交的字段。

    Attributes:
        name: 用户显示名称。
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)


class UserRead(BaseModel):
    """返回给客户端的用户信息。

    Attributes:
        id: 用户的全局唯一标识。
        name: 用户显示名称。
        created_at: 用户记录的创建时间。
        updated_at: 用户记录最后一次更新时间。
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseCreate(BaseModel):
    """创建知识库时允许客户端提交的字段。

    Attributes:
        name: 知识库显示名称。
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)


class KnowledgeBaseRead(BaseModel):
    """返回给客户端的知识库信息。

    Attributes:
        id: 知识库的全局唯一标识。
        owner_id: 知识库所有者的用户 ID。
        name: 知识库显示名称。
        created_at: 知识库记录的创建时间。
        updated_at: 知识库记录最后一次更新时间。
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class DocumentRead(BaseModel):
    """返回给客户端的文档信息，不暴露服务器存储路径。

    Attributes:
        id: 文档的全局唯一标识。
        kb_id: 文档所属知识库的 ID。
        filename: 已清理目录部分的原文件名。
        content_hash: 原文件内容的 SHA-256 摘要。
        status: 文档当前处理状态。
        chunk_count: 已成功写入 Milvus 的 Chunk 数量。
        error_message: 最近一次处理失败的安全错误摘要。
        created_at: 文档记录的创建时间。
        updated_at: 文档记录最后一次更新时间。
    """

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
