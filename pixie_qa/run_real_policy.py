"""使用真实 BGE、Milvus 和 DeepSeek 验证制度检索 Agent 链路。"""

import asyncio
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID

import httpx
import pixie
from pydantic import BaseModel, Field
from sqlmodel import Session, SQLModel, create_engine


REAL_USER_ID = UUID("0e95a440-f2e2-4bfb-982c-866c7ed08952")
REAL_KB_ID = UUID("744a9967-afbe-4832-9d0b-5d4bb5934ee1")
REAL_EMBEDDING_PATH = Path(
    r"C:\Users\失吹丈\Desktop\Langchain学习\GitHub_LanChain"
    r"\py-doc\py-doc-deepseek-server\models\bge-small-zh-v1.5"
)


class RealPolicyArgs(BaseModel):
    """定义真实制度检索评测的用户问题。"""

    user_message: str = Field(min_length=1, max_length=2000)


class RealPolicyRunnable(pixie.Runnable[RealPolicyArgs]):
    """通过完整 HTTP 入口运行真实 BGE、Milvus 与 DeepSeek。"""

    _client: httpx.AsyncClient
    _semaphore: asyncio.Semaphore
    _temporary_directory: TemporaryDirectory[str]
    _business_engine: Any

    @classmethod
    def create(cls) -> "RealPolicyRunnable":
        """创建串行执行的真实制度评测器。"""
        instance = cls()
        instance._semaphore = asyncio.Semaphore(1)
        return instance

    async def setup(self) -> None:
        """准备隔离业务库，同时保留真实外部检索与模型客户端。"""
        if not REAL_EMBEDDING_PATH.is_dir():
            raise RuntimeError(f"Embedding 模型目录不存在：{REAL_EMBEDDING_PATH}")
        os.environ["EMBEDDING_MODEL_PATH"] = str(REAL_EMBEDDING_PATH)

        from app.agents.admin.runtime import build_admin_runtime
        from app.db import get_session
        from app.dependencies.agent import get_admin_agent_runtime
        from app.main import app
        from app.models import KnowledgeBase, User

        self._temporary_directory = TemporaryDirectory(prefix="mini-rag-live-policy-")
        temporary_path = Path(self._temporary_directory.name)
        self._business_engine = create_engine(
            f"sqlite:///{(temporary_path / 'business.db').as_posix()}",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(self._business_engine)
        with Session(self._business_engine) as session:
            session.add(User(id=REAL_USER_ID, name="真实检索评测用户"))
            session.add(
                KnowledgeBase(
                    id=REAL_KB_ID,
                    owner_id=REAL_USER_ID,
                    name="真实 Milvus 制度知识库",
                )
            )
            session.commit()

        def override_session():
            with Session(self._business_engine) as session:
                yield session

        def override_runtime():
            checkpoint_path = temporary_path / "checkpoint.db"
            with build_admin_runtime(checkpoint_path=checkpoint_path) as runtime:
                yield runtime

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_admin_agent_runtime] = override_runtime
        self._client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://real-policy.local",
            timeout=120.0,
        )

    async def run(self, args: RealPolicyArgs) -> None:
        """创建隔离 AgentSession，并执行一条真实制度问题。"""
        async with self._semaphore:
            headers = {"X-User-ID": str(REAL_USER_ID)}
            session_response = await self._client.post(
                "/agent-sessions",
                headers=headers,
                json={"kb_id": str(REAL_KB_ID)},
            )
            session_response.raise_for_status()
            session_id = session_response.json()["id"]
            message_response = await self._client.post(
                f"/agent-sessions/{session_id}/messages",
                headers=headers,
                json={"message": args.user_message},
            )
            message_response.raise_for_status()

    async def teardown(self) -> None:
        """关闭临时资源，不修改原业务库与 Milvus 数据。"""
        from app.main import app

        await self._client.aclose()
        app.dependency_overrides.clear()
        self._business_engine.dispose()
        self._temporary_directory.cleanup()
