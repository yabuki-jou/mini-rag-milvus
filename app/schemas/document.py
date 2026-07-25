"""定义文档接口的数据结构。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import DocumentStatus


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
