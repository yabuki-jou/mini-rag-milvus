"""创建并配置 Mini RAG 的 FastAPI 应用。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.db import create_db_and_tables
from app.routers import documents, health, knowledge_bases, users


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """管理 FastAPI 应用的启动和关闭生命周期。

    Args:
        _: 当前 FastAPI 应用；本阶段不需要直接使用。

    Yields:
        启动初始化完成后，将控制权交还给 FastAPI。
    """
    # 应用接收请求前先创建缺失的 SQLite 表，已有表不会被重建。
    create_db_and_tables()
    yield


# 集中创建 ASGI 应用，Uvicorn 通过 ``app.main:app`` 导入该对象。
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="从零手写的 FastAPI + LangChain + Milvus RAG 后端。",
    lifespan=lifespan,
)

# 先安装统一异常响应，再按业务领域注册各组路由。
register_exception_handlers(app)
app.include_router(health.router)
app.include_router(users.router)
app.include_router(knowledge_bases.router)
app.include_router(documents.router)
