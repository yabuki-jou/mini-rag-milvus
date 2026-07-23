"""定义 Mini RAG 的数据库实体和文档处理状态。"""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class DocumentStatus(str, Enum):
    """表示文档在上传、处理和删除过程中的状态。"""

    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    DELETING = "DELETING"
    DELETE_FAILED = "DELETE_FAILED"


class User(SQLModel, table=True):
    """表示可以创建和访问知识库的基础用户。

    Attributes:
        id: 用户的全局唯一标识。
        name: 用户显示名称。
        created_at: 用户记录的 UTC 创建时间。
        updated_at: 用户记录最后一次更新的 UTC 时间。
    """

    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(min_length=1, max_length=100, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class KnowledgeBase(SQLModel, table=True):
    """表示由一个用户拥有的独立知识库。

    Attributes:
        id: 知识库的全局唯一标识。
        owner_id: 知识库所有者的用户 ID。
        name: 知识库显示名称。
        created_at: 知识库记录的 UTC 创建时间。
        updated_at: 知识库记录最后一次更新的 UTC 时间。
    """

    __tablename__ = "knowledge_bases"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(foreign_key="users.id", index=True)
    name: str = Field(min_length=1, max_length=100, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Document(SQLModel, table=True):
    """表示知识库中已上传原文件的数据库记录。

    Attributes:
        id: 文档的全局唯一标识。
        kb_id: 文档所属知识库的 ID。
        filename: 清理目录部分后的安全文件名。
        storage_path: 原文件在服务器上的存储路径。
        content_hash: 原文件内容的 SHA-256 哈希值。
        status: 文档当前处理状态。
        chunk_count: 成功写入向量库的 Chunk 数量。
        error_message: 最近一次处理或删除失败的错误摘要。
        created_at: 文档记录的 UTC 创建时间。
        updated_at: 文档记录最后一次更新的 UTC 时间。
    """

    __tablename__ = "documents"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    kb_id: UUID = Field(foreign_key="knowledge_bases.id", index=True)
    filename: str = Field(min_length=1, max_length=255, index=True)
    storage_path: str = Field(min_length=1, max_length=1024)
    content_hash: str = Field(min_length=64, max_length=64, index=True)
    status: DocumentStatus = Field(default=DocumentStatus.UPLOADED, index=True)
    chunk_count: int = Field(default=0, ge=0)
    error_message: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
