"""延迟加载本地 Embedding 模型。"""

from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import settings
from app.core.errors import AppError


@lru_cache
def get_embeddings() -> HuggingFaceEmbeddings:
    """加载并缓存生成归一化向量的本地 BGE 模型。"""
    embedding_path = settings.embedding_path

    if not embedding_path.exists():
        raise AppError(
            status_code=503,
            code="EMBEDDING_MODEL_NOT_FOUND",
            message=f"Embedding模型目录不存在：{embedding_path}",
        )

    return HuggingFaceEmbeddings(
        model_name=str(embedding_path),
        model_kwargs={"device": settings.embedding_device},
        encode_kwargs={"normalize_embeddings": True},
    )
