# 验收报告

## 验收范围

检查当前单机学习版的需求、实现、自动化测试和文档一致性。真实 Milvus、BGE、DeepSeek 端到端结果需结合运行环境另行记录。

## 需求追踪

| 需求 | 实现 | 测试 | 当前结论 |
| --- | --- | --- | --- |
| FR-001..003 用户/知识库/隔离 | routers + auth/resources deps | 越权场景间接覆盖 | 通过；创建接口独立测试不足 |
| FR-004/005 上传 | file/document services | file service 和路由场景 | 部分覆盖；四格式真实上传需人工 |
| FR-006/007 解析/入库/重跑 | parser/chunk/embedding/vector/document | `test_document_processing.py` | 通过（外部服务 Mock） |
| FR-008 检索 | retrieval service/router | `test_retrieval.py` | 通过 |
| FR-009..013 问答/历史 | chat service/router、rag_agent | chat 两个测试文件 | 通过（DeepSeek Mock） |
| FR-014 删除 | document/file/vector services | delete/file 测试 | 通过（Milvus Mock） |
| FR-015 健康 | health router | 无独立测试 | 需真实环境验证 |
| FR-016 日志 | logging middleware | 无独立测试 | 人工观察通过，自动覆盖缺失 |
| NFR-010 数据迁移 | Alembic `0001`/`0002`、启动迁移服务 | `test_migrations.py` | 通过（临时旧库与空库） |
| FR-024..026 请假领域基础 | leave models/service | `test_leave_service.py` | 领域层通过；写工具的人工确认和 API 尚未实现 |
| FR-023..025 Agent 只读工具 | policy/leave tools | `test_read_tools.py` | 工具通过；正式 Graph 与 API 尚未接入 |

## 自动化检查

| 检查 | 命令 | 本次结果 |
| --- | --- | --- |
| Pytest | `python -m pytest -q` | 通过：60 passed，1 warning，10.92s |
| Python 编译 | `python -m compileall -q app tests` | 通过 |
| Lint / 类型 | 无配置 | 未执行，不能判定通过 |
| 覆盖率 | 无配置 | 未统计 |

Pytest 的唯一警告来自 FastAPI TestClient 对当前 `httpx` 集成方式的弃用提示，
不是业务测试失败；后续升级 FastAPI/Starlette/httpx 时需要重新核对兼容组合。

## 接口与数据一致性

- `app/routers` 当前注册 12 个 HTTP 操作；字段来自 `app/schemas`。
- 解析前删除旧 Chunk，成功后才写 `READY/chunk_count`。
- 删除状态支持失败补偿，测试验证三字段 Milvus 过滤。
- `[TODO]` OpenAPI 未显式声明全部业务错误响应。
- `[TODO]` 自动化测试未连接独立 Milvus Collection 验证最终实体数。
- `[TODO]` 没有孤儿 Chunk 定期扫描/修复工具。
- `[TODO]` 已确认的空知识库删除规则尚未实现：非空知识库应拒绝删除且保持关联数据不变。
- `[TODO]` 已确认的登录会话存储尚未实现：数据库应只保存 Refresh Token 哈希，并能在退出后拒绝旧 Token。

## 未实现、部分实现、无法验证

- 未实现：已确认的完整登录认证和知识库修改删除，以及前端、异步任务、OCR、混合检索、Rerank、正式 Agent Graph/API、CI、lint、类型检查和覆盖率阈值。用户资料修改和账号删除不属于需求。
- 部分实现：员工、余额、申请领域层和四个只读工具已实现，但尚未接入正式 Graph；隔离逻辑完整但当前身份头可伪造；已确认使用 JWT Access Token + Refresh Token 替换但尚未实现。日志无指标/Tracing；跨存储一致性无原子事务。
- 当前自动测试无法证明：真实 BGE/Milvus/DeepSeek、三份制度材料 10 问的人工回归。

## 风险

1. 高：`X-User-ID` 不适用于公开网络；当前仅接受个人学习和可信朋友小范围使用，扩大范围前必须完成 FR-021。
2. 中：无上传大小限制，同步解析可能耗尽资源。
3. 中：SQLite、文件和 Milvus 无原子事务。
4. 中：已有 Alembic 迁移，但尚未在用户的真实业务库上执行升级；DeepSeek 仍缺少显式超时/重试。
5. 低：`pypdf`、`python-docx`、`langchain-text-splitters` 未锁定版本。

## 当前结论

代码满足“单机学习版完整 RAG 后端”的主要目标，并完成企业行政 Agent 的迁移、请假领域基础和四个只读工具。正式 Graph、人工确认和 API 尚未实现；Mock 测试也不能替代真实外部系统集成验收。

## 证据

- `tests/test_*.py`
- `app/routers/`、`app/schemas/`、`app/services/`
- `app/core/logging.py`、`app/core/errors.py`
