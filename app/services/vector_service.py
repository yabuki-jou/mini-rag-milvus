"""创建 Milvus 客户端，并提供只读连接检查。"""

from functools import lru_cache

from pymilvus import MilvusClient

from app.core.config import settings
from app.core.errors import AppError


@lru_cache
def get_milvus_client() -> MilvusClient:
    """创建并缓存连接现有 Milvus 服务的客户端。"""
    try:
        return MilvusClient(**settings.milvus_connection_args)
    except Exception as exc:
        raise AppError(
            status_code=503,
            code="MILVUS_UNAVAILABLE",
            message=f"无法连接 Milvus：{exc}",
        ) from exc


def list_collections() -> list[str]:
    """返回 Collection 名称，用只读请求验证 Milvus 连接。"""
    client = get_milvus_client()
    try:
        return list(client.list_collections())
    except Exception as exc:
        raise AppError(
            status_code=503,
            code="MILVUS_UNAVAILABLE",
            message=f"无法连接 Milvus：{exc}",
        ) from exc
