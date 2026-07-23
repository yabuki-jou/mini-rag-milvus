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
    """在应用启动时创建尚未存在的数据库表。"""
    create_db_and_tables()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="从零手写的 FastAPI + LangChain + Milvus RAG 后端。",
    lifespan=lifespan,
)

register_exception_handlers(app)
app.include_router(health.router)
app.include_router(users.router)
app.include_router(knowledge_bases.router)
app.include_router(documents.router)
