# 数据库与存储设计

## 存储边界

| 存储 | 数据 | 定位 |
|---|---|---|
| PostgreSQL 16 | 用户、知识库、文档、聊天、Agent 会话与审计 | 业务事实来源 |
| Milvus | 文档 Chunk、向量和隔离字段 | 可重建检索索引 |
| 文件系统 | 上传原文件 | 可重新解析的源数据 |
| Checkpoint SQLite | LangGraph 消息、范围和执行快照 | 单机运行状态 |

旧 SQLite 业务数据不迁移，PostgreSQL 从空库执行 Alembic。Checkpoint SQLite
继续使用 `AGENT_CHECKPOINT_FILE`，不与 PostgreSQL 共用连接。

## PostgreSQL 实体关系

```mermaid
erDiagram
    USERS ||--o{ KNOWLEDGE_BASES : owns
    KNOWLEDGE_BASES ||--o{ DOCUMENTS : contains
    USERS ||--o{ CHAT_SESSIONS : creates
    KNOWLEDGE_BASES ||--o{ CHAT_SESSIONS : binds
    CHAT_SESSIONS ||--o{ CHAT_MESSAGES : contains
    USERS ||--o{ AGENT_SESSIONS : creates
    KNOWLEDGE_BASES ||--o{ AGENT_SESSIONS : binds
    AGENT_SESSIONS ||--o{ AGENT_TOOL_CALL_LOGS : records
```

## 表设计

| 表 | 关键字段和约束 | 用途 |
|---|---|---|
| `users` | UUID PK；`name` index；时间 | 学习阶段用户 |
| `knowledge_bases` | UUID PK；`owner_id` FK/index；`name` index；时间 | 用户知识库 |
| `documents` | UUID PK；`kb_id` FK/index；文件名、路径、哈希、状态、Chunk 数、错误、时间 | 文档处理事实 |
| `chat_sessions` | UUID PK；`user_id`/`kb_id` FK/index；时间 | RAG 会话 |
| `chat_messages` | UUID PK；`session_id` FK/index；角色、正文、引用 JSON、时间 | 问答历史 |
| `agent_sessions` | UUID PK；`user_id`/`kb_id` FK/index；`thread_id` unique；时间 | Agent 授权范围 |
| `agent_tool_call_logs` | UUID PK；会话 FK；会话+调用 ID unique；工具、状态、摘要、耗时、错误码、时间 | 脱敏审计 |

已删除表：`employee_profiles`、`leave_balances`、`leave_requests`。

## Milvus Collection

所有知识库共用一个 Collection，通过 `user_id` 和 `kb_id` 同时过滤。字段包括
稳定 `chunk_id`、`document_id`、文档名、页码、起始位置、正文、内容哈希、
`user_id`、`kb_id` 与 512 维向量。删除文档按 `user_id + kb_id + document_id`
精确删除。

## 跨存储对应

- `documents.id` → Milvus `document_id` 与文件目录。
- `users.id + knowledge_bases.id` → Milvus `user_id + kb_id`。
- `agent_sessions.thread_id` → Checkpoint SQLite `thread_id`。

跨存储不建立外键。PostgreSQL 是业务状态来源；Milvus 可以由原文件重建。

## 索引与删除

查询所有权字段、状态、时间和工具调用标识均有索引。业务表当前使用物理删除；
文档删除先标记 `DELETING`，依次清理 Milvus 与文件，再删除 PostgreSQL 记录。
删除失败保留可重试状态，不静默遗留孤立数据。

## 迁移策略

- `0001_rag_baseline`：建立原 RAG 表。
- `0002_leave_domain`：历史迁移，曾建立请假表。
- `0003_agent_api`：建立 Agent 会话和审计表。
- `0004_remove_leave_domain`：删除请假表及 PostgreSQL Enum。

保留历史迁移是为了让任何执行过 `0002` 的数据库也能前向删除领域；不通过
删除旧迁移伪造历史。新 PostgreSQL 空库依次执行到 `0004`。正式启动只使用
Alembic，`create_all()` 只用于隔离测试。

## 配置与安全

- 连接格式：`postgresql+psycopg://user:password@host:5432/database`。
- 示例账号只用于本地 Compose；生产密码不得提交到 Git。
- PostgreSQL 数据卷为 `postgres_data`。
- Checkpoint 文件、上传目录和日志仍位于 `app_data`/`app_logs` 卷。

## 一致性风险

- PostgreSQL、Milvus 与文件系统之间没有分布式事务。
- Checkpoint SQLite 不支持多实例共享和高并发写入。
- 旧业务 SQLite 不导入 PostgreSQL；需要的数据应重新创建或重新上传。
