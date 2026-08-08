"""定义检索测试接口的数据结构。"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RetrievalTestRequest(BaseModel):
    """检索测试接口接收的问题。

    Attributes:
        question: 需要在当前知识库中检索的自然语言问题。
    """

    # 拒绝未声明字段，并在长度校验前清理问题两端的空白字符。
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    question: str = Field(min_length=1, max_length=2000)


class RetrievalResultRead(BaseModel):
    """返回给客户端的单个合格检索结果。

    Attributes:
        chunk_id: Chunk 的稳定 SHA-256 标识。
        document_id: Chunk 所属文档的 UUID。
        document_name: 用于来源展示的原文件名。
        page: Chunk 所属的原始页码，从 1 开始。
        content: Chunk 的完整正文。
        score: 兼容既有接口的 ``1 - Chroma cosine distance`` 分数。
    """

    # 允许从服务层 RetrievedChunk dataclass 的同名属性创建响应模型。
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str = Field(min_length=64, max_length=64)
    document_id: UUID
    document_name: str = Field(min_length=1)
    page: int = Field(ge=1)
    content: str = Field(min_length=1)
    score: float = Field(ge=-1.0, le=1.0)


class RetrievalTestResponse(BaseModel):
    """检索测试接口的完整响应。

    Attributes:
        question: 清理空白字符后的原始问题。
        results: 通过相似度阈值并截取 Top-N 后的 Chunk。
    """

    question: str
    results: list[RetrievalResultRead]
