"""通过真实 FastAPI 入口运行企业行政 Agent 的 Pixie 评测适配器。"""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID, uuid4

import httpx
import pixie
from pydantic import BaseModel, Field
from sqlmodel import Session, SQLModel, create_engine


class AppArgs(BaseModel):
    """定义每条评测样本能够改变的真实用户输入。"""

    user_message: str = Field(min_length=1, max_length=2000)


class AppRunnable(pixie.Runnable[AppArgs]):
    """串行驱动完整 HTTP、应用服务、Graph 与真实 LLM 链路。"""

    _client: httpx.AsyncClient
    _semaphore: asyncio.Semaphore
    _temporary_directory: TemporaryDirectory[str]
    _business_engine: Any
    _original_leave_engine: Any

    @classmethod
    def create(cls) -> "AppRunnable":
        """创建尚未初始化外部资源的 Runnable。"""
        instance = cls()
        instance._semaphore = asyncio.Semaphore(1)
        return instance

    async def setup(self) -> None:
        """建立隔离数据库并覆盖 FastAPI 的运行时依赖。"""
        from app.agents.tools import leave_tools
        from app.agents.admin.runtime import build_admin_runtime
        from app.db import get_session
        from app.dependencies.agent import get_admin_agent_runtime
        from app.main import app

        self._temporary_directory = TemporaryDirectory(prefix="mini-rag-pixie-")
        temporary_path = Path(self._temporary_directory.name)
        database_path = temporary_path / "business.db"
        checkpoint_path = temporary_path / "checkpoint.db"
        self._business_engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(self._business_engine)

        def override_session():
            with Session(self._business_engine) as session:
                yield session

        def override_runtime():
            with build_admin_runtime(checkpoint_path=checkpoint_path) as runtime:
                yield runtime

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_admin_agent_runtime] = override_runtime
        self._original_leave_engine = leave_tools.engine
        leave_tools.engine = self._business_engine


        transport = httpx.ASGITransport(app=app)
        self._client = httpx.AsyncClient(
            transport=transport,
            base_url="http://pixie.local",
            timeout=90.0,
        )

    async def run(self, args: AppArgs) -> None:
        """创建隔离会话、初始化演示余额并发送一条真实 Agent 消息。"""
        from app.models import LeaveType, User
        from app.services.leave_service import (
            create_employee_profile,
            set_leave_balance,
        )

        async with self._semaphore:
            run_id = uuid4().hex
            user_response = await self._client.post(
                "/users",
                json={"name": f"pixie-{run_id}"},
            )
            user_response.raise_for_status()
            user_id = user_response.json()["id"]
            headers = {"X-User-ID": user_id}

            knowledge_base_response = await self._client.post(
                "/knowledge-bases",
                headers=headers,
                json={"name": f"pixie-kb-{run_id}"},
            )
            knowledge_base_response.raise_for_status()
            kb_id = knowledge_base_response.json()["id"]

            with Session(self._business_engine) as session:
                user = session.get(User, UUID(user_id))
                if user is None:
                    raise RuntimeError("评测用户创建后无法从隔离数据库读取。")
                employee = create_employee_profile(
                    user=user,
                    employee_no=f"PX{run_id[:10]}",
                    department="评测部门",
                    session=session,
                )
                set_leave_balance(
                    employee=employee,
                    leave_type=LeaveType.ANNUAL,
                    total_days=15,
                    used_days=2,
                    session=session,
                )
                set_leave_balance(
                    employee=employee,
                    leave_type=LeaveType.SICK,
                    total_days=10,
                    used_days=1,
                    session=session,
                )

            agent_session_response = await self._client.post(
                "/agent-sessions",
                headers=headers,
                json={"kb_id": kb_id},
            )
            agent_session_response.raise_for_status()
            agent_session_id = agent_session_response.json()["id"]

            message_response = await self._client.post(
                f"/agent-sessions/{agent_session_id}/messages",
                headers=headers,
                json={"message": args.user_message},
            )
            message_response.raise_for_status()

    async def teardown(self) -> None:
        """恢复全局依赖并关闭评测期间创建的资源。"""
        from app.agents.tools import leave_tools
        from app.main import app

        await self._client.aclose()
        app.dependency_overrides.clear()
        leave_tools.engine = self._original_leave_engine
        self._business_engine.dispose()
        self._temporary_directory.cleanup()
