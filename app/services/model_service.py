"""延迟加载本地 Embedding 模型。"""

from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import settings
from app.core.errors import AppError


@lru_cache
def get_embeddings() -> HuggingFaceEmbeddings:
    """加载并缓存生成归一化向量的本地 BGE 模型。

    Returns:
        配置为输出归一化向量的 LangChain Embedding 对象。

    Raises:
        AppError: 本地模型目录不存在。
    """
    # 配置层已经把相对目录转换为不依赖启动位置的绝对路径。
    embedding_path = settings.embedding_path

    # 在加载大模型文件前给出明确错误，避免底层库产生难懂的堆栈。
    if not embedding_path.exists():
        raise AppError(
            status_code=503,
            code="EMBEDDING_MODEL_NOT_FOUND",
            message=f"Embedding模型目录不存在：{embedding_path}",
        )

    # 模型只加载一次，并统一输出适用于 COSINE 的归一化向量。
    return HuggingFaceEmbeddings(
        model_name=str(embedding_path),
        model_kwargs={"device": settings.embedding_device},
        encode_kwargs={"normalize_embeddings": True},
    )
