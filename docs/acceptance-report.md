# 验收报告

## 验收范围

2026-08-05 检查员工请假领域删除、业务库 PostgreSQL 化、Agent 收缩、迁移链、
测试和文档一致性。旧 SQLite 业务数据不迁移；Checkpoint SQLite 保留。

## 需求追踪

| 验收项 | 实现证据 | 验证结果 |
|---|---|---|
| AC-001 PostgreSQL 空库迁移 | Psycopg、Compose PostgreSQL、Alembic `0001..0004` | 离线 PostgreSQL SQL 生成通过；真实空库测试因无本机服务而跳过 |
| AC-002 无请假表/Enum | `0004_remove_leave_domain.py` | SQLModel metadata 无三表；离线 SQL 各生成一次 Enum create/drop |
| AC-003 无可执行请假能力 | 删除 model/service/tool/contracts、决定 API 和相关测试 | 运行时代码无请假导入；历史迁移和删除说明保留 |
| AC-004 Agent 只注册制度工具 | `app/agents/admin/graph.py` | Graph/Tool/API 测试通过 |
| AC-005 PostgreSQL 业务库、SQLite Checkpoint | 配置校验、`app/db.py`、Runtime | SQLite 业务 URL 会被拒绝；Checkpoint 恢复测试通过 |
| AC-006 自动检查 | pytest、compileall、OpenAPI/metadata 检查 | 通过；真实 PostgreSQL 与 Docker Compose CLI 未验证 |

## 自动化检查

| 检查 | 命令摘要 | 结果 |
|---|---|---|
| 全量测试 | `rag-study/python -m pytest -q`，进程级 PostgreSQL URL | `68 passed, 1 skipped, 1 warning` |
| PostgreSQL 专用测试 | `tests/test_postgres_migrations.py` | 跳过：未提供 `POSTGRES_TEST_URL` |
| Python 编译 | `python -m compileall -q app tests migrations` | 通过 |
| PostgreSQL 离线迁移 | `alembic upgrade head --sql` | 通过；head 为 `0004_remove_leave_domain` |
| OpenAPI/metadata | Python 断言 | 12 个路径；7 张表；无 decisions/请假表 |
| Compose YAML | PyYAML 结构断言 | 通过；包含 PostgreSQL 健康依赖 |
| Docker Compose CLI | `docker compose config --quiet` | 未执行成功：当前终端找不到 Docker CLI |
| Lint/类型/覆盖率 | 项目未配置 | 未执行 |

唯一警告来自 FastAPI TestClient 对 `httpx` 的弃用提示，不是业务失败。

## 已实现

- 业务 Engine 默认且强制使用 `postgresql+psycopg://`，启用连接预检查。
- Compose 新增 `postgres:16-alpine`、健康检查和持久化卷。
- Alembic 保留历史请假迁移，并用前向 `0004` 删除三表及 PostgreSQL Enum。
- Agent 只保留制度检索 Tool、会话、历史、引用、Checkpoint 和脱敏审计。
- `/agent-sessions/{session_id}/decisions` 与待确认响应契约已删除。
- 需求、架构、数据库、API、计划、README、导览和演示文档已同步。

## 无法验证与后续动作

- 本机当前未发现可调用的 Docker CLI、PostgreSQL 客户端或 PostgreSQL 服务，
  因此没有实际连接空 PostgreSQL 执行在线迁移，也没有启动完整 Compose。
- 本地私有 `.env` 仍覆盖为 SQLite。项目按安全规则没有读取或改写它；应用现在
  会明确拒绝旧 URL。需要用户参照 `.env.example` 手动更新。
- 更新 `.env` 并准备空测试库后，运行：

```powershell
$env:POSTGRES_TEST_URL='postgresql+psycopg://user:password@localhost:5432/empty_test_db'
python -m pytest -q tests/test_postgres_migrations.py
docker compose config --quiet
docker compose up -d postgres
python -m alembic upgrade head
```

`POSTGRES_TEST_URL` 必须是空的专用测试数据库；测试会拒绝非空库。

## 风险

1. 高：`X-User-ID` 可伪造，不适用于公开网络。
2. 中：Checkpoint SQLite 不能支持多实例部署。
3. 中：PostgreSQL、Milvus 和文件系统没有分布式事务。
4. 中：真实 PostgreSQL 在线迁移和完整 Compose 尚未验证。
5. 中：标书领域仍未完成需求、数据模型和质量评测设计。

## 结论

请假领域删除和 PostgreSQL 代码/配置迁移已经完成，并通过当前可运行的单元、
Graph、API、SQLite 迁移逻辑、离线 PostgreSQL SQL、编译和结构检查。由于缺少
本机 PostgreSQL/Docker 运行环境，不能把“真实 PostgreSQL 在线迁移、容器启动
和健康检查”写成已通过。
