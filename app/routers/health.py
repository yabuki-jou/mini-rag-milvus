"""提供应用及其依赖组件的健康检查接口。"""

import logging

from fastapi import APIRouter, Response

from app.core.config import settings
from app.db import engine
from app.schemas import HealthComponent, HealthResponse
from app.services.model_service import get_embeddings
from app.services.vector_service import list_collections

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(response: Response) -> HealthResponse:
    """检查 API、数据库、Milvus 和 Embedding 是否可用。"""
    components: dict[str, HealthComponent] = {
        "api": HealthComponent(status="ok"),
    }

    # 每项检查相互独立，避免一个组件失败后跳过其他组件。
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1").scalar_one()
        components["database"] = HealthComponent(status="ok")
    except Exception:
        logger.exception("数据库健康检查失败。")
        components["database"] = HealthComponent(
            status="error",
            detail="数据库连接失败",
        )

    try:
        collections = list_collections()
        components["milvus"] = HealthComponent(
            status="ok",
            detail=f"collections={len(collections)}",
        )
    except Exception:
        logger.exception("Milvus 健康检查失败。")
        components["milvus"] = HealthComponent(
            status="error",
            detail="Milvus 连接失败",
        )

    try:
        vector = get_embeddings().embed_query("健康检查")
        if len(vector) != settings.embedding_dimension:
            raise RuntimeError("Embedding 向量维度不符合配置")
        components["embedding"] = HealthComponent(
            status="ok",
            detail=f"dimension={len(vector)}",
        )
    except Exception:
        logger.exception("Embedding 健康检查失败。")
        components["embedding"] = HealthComponent(
            status="error",
            detail="Embedding 模型不可用",
        )

    is_healthy = all(
        component.status == "ok" for component in components.values()
    )

    if not is_healthy:
        response.status_code = 503

    return HealthResponse(
        status="ok" if is_healthy else "degraded",
        components=components,
    )
