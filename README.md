# Mini RAG Milvus Handwrite

从空目录手写的企业知识库 RAG 与只读 Agent 后端练习项目。当前版本使用
FastAPI、SQLModel、PostgreSQL、Alembic、LangChain/LangGraph、Milvus、
本地 BGE 与 DeepSeek，通过 Swagger 演示上传、解析、检索、引用问答、Agent
会话和脱敏工具审计。

工程企业标书解析、生成与合规审查是后续业务方向，当前尚未实现。原员工
请假领域已经删除，不再提供余额、申请、人工确认或决定接口。

## 架构

```mermaid
flowchart LR
    Client --> FastAPI
    FastAPI --> PostgreSQL[(PostgreSQL 业务库)]
    FastAPI --> Files[原文件]
    FastAPI --> Milvus[(Milvus 向量库)]
    FastAPI --> Graph[LangGraph Agent]
    Graph --> DeepSeek
    Graph --> Checkpoint[(Checkpoint SQLite)]
    Graph --> Milvus
```

- PostgreSQL：用户、知识库、文档、聊天、Agent 会话与审计。
- Milvus：Chunk、向量和 `user_id + kb_id` 隔离字段。
- 文件系统：上传原文件。
- SQLite：仅保存 LangGraph Checkpoint，不再作为业务数据库。

详细设计见：

- [需求说明](docs/requirements.md)
- [技术架构](docs/architecture.md)
- [数据库设计](docs/database-design.md)
- [API 设计](docs/api-design.md)
- [实施计划](docs/implementation-plan.md)
- [Agent 逻辑导览](docs/agent-guide.md)
- [Agent 演示步骤](docs/agent-demo.md)

## 主要能力

- TXT、Markdown、PDF、DOCX 上传与解析。
- BGE Embedding、Milvus 入库、Top-K/阈值/Top-N 检索。
- 无依据拒答，带文档名、页码、摘录和分数的结构化引用。
- Agent 会话所有权、LangGraph 多轮消息恢复、制度检索 Tool Calling。
- 工具参数/结果脱敏、耗时和稳定错误码审计。
- Alembic 管理 PostgreSQL Schema；Compose 部署 PostgreSQL 与 Milvus 依赖。

## 数据库表

PostgreSQL 当前包含七张业务表：

`users`、`knowledge_bases`、`documents`、`chat_sessions`、
`chat_messages`、`agent_sessions`、`agent_tool_call_logs`。

历史迁移 `0002_leave_domain` 曾创建三张请假表，前向迁移
`0004_remove_leave_domain` 会删除它们及 PostgreSQL Enum。新空库执行完整
迁移链后不会保留请假表。旧 SQLite 业务数据不会导入 PostgreSQL。

## 本地配置

要求 Python 3.11、Docker Compose，以及可用的本地 BGE 模型目录。

```powershell
Copy-Item .env.example .env
python -m pip install -r requirements-dev.txt
docker compose up -d postgres etcd minio standalone
python -m alembic upgrade head
python run.py
```

默认业务连接：

```text
postgresql+psycopg://mini_rag:mini_rag@localhost:5432/mini_rag
```

示例账号只用于本机开发。生产环境必须替换 `POSTGRES_USER`、
`POSTGRES_PASSWORD` 和 `POSTGRES_DB`，真实 `.env` 不得提交。
如果旧 `.env` 仍使用 `sqlite:///`，应用会拒绝启动；请根据 `.env.example`
手动更新，项目不会自动读取或覆盖你的真实配置文件。

完整容器启动：

```powershell
docker compose up --build
```

API 默认地址为 `http://127.0.0.1:8000`，Swagger 为 `/docs`。

## 核心接口

1. `POST /users`
2. `POST/GET /knowledge-bases`
3. `POST/GET /knowledge-bases/{kb_id}/documents`
4. `POST /knowledge-bases/{kb_id}/documents/{document_id}/parse`
5. `POST /knowledge-bases/{kb_id}/retrieval-test`
6. `POST /chat-sessions` 与聊天消息/历史接口
7. `POST /agent-sessions`
8. `POST /agent-sessions/{session_id}/messages`
9. `GET /agent-sessions/{session_id}/messages`
10. `GET /agent-sessions/{session_id}/tool-calls`

受保护接口当前使用 `X-User-ID`，仅适合学习演示。项目没有
`/agent-sessions/{session_id}/decisions`。

## 测试

快速测试允许使用隔离内存 SQLite，但它不代表运行时业务数据库。真实
PostgreSQL 迁移测试必须显式提供空的专用测试库：

```powershell
pytest -q
$env:POSTGRES_TEST_URL='postgresql+psycopg://user:password@localhost:5432/empty_test_db'
pytest -q tests/test_postgres_migrations.py
python -m compileall app tests migrations
docker compose config --quiet
```

`POSTGRES_TEST_URL` 测试会拒绝非空数据库，避免覆盖已有业务数据。

## 已知限制

- 尚未实现 JWT，`X-User-ID` 可伪造。
- Checkpoint SQLite 只适合单机运行。
- 同步解析不适合大文件和高并发。
- 没有 OCR、表格专用解析、混合检索、Rerank、多 Agent 或任务队列。
- 标书领域的字段模型、合规规则和评测集尚待需求设计。
