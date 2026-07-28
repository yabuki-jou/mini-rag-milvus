# 实施计划

## 说明

这是依据现有代码和已确认的企业行政 Agent 目标整理的实施计划。原始 RAG 阶段已完成；Agent 一次只实施一个可独立验证的任务。

## 已完成任务

| 任务 | 依赖 | 需求 | 主要文件 | 独立完成标准 | 状态 |
| --- | --- | --- | --- | --- | --- |
| T-01 骨架与配置 | 无 | FR-015/016 | `main.py`, `core/*`, `db.py`, `run.py` | Swagger、SQLite、Milvus、Embedding 可检查 | 完成 |
| T-02 用户与知识库 | T-01 | FR-001..003 | account、users/kb routers、dependencies | 两用户知识库隔离 | 完成 |
| T-03 文件上传 | T-02 | FR-004/005 | document/file services/router | UPLOADED、文件与哈希存在 | 完成 |
| T-04 解析切分 | T-03 | FR-006/007 | parser/chunk services | 四类文件、页码位置、稳定 ID | 完成 |
| T-05 Embedding/入库 | T-04 | FR-006/007 | embedding/vector/document services | 512 维向量，重跑不累计 | 完成 |
| T-06 检索 | T-05 | FR-008 | retrieval schema/service/router | Top-K/阈值/Top-N 和隔离生效 | 完成 |
| T-07 问答历史 | T-06 | FR-009..013 | chat、rag_agent | 拒答不调模型，问答与引用保存 | 完成 |
| T-08 幂等删除 | T-05 | FR-014 | document/file/vector services | 三处资源清理，失败可重试 | 完成 |
| T-09 日志验收 | 全部 | FR-015/016 | logging/errors、tests、README | 请求 ID、轮转日志、测试 | 完成 |
| T-10 文档基线 | 全部 | 全部 | `AGENTS.md`, `docs/*` | 需求到测试可追踪 | 本次完成 |

## 企业行政 Agent 实施任务

| 任务 | 依赖 | 需求 | 主要范围 | 独立完成标准 | 状态 |
| --- | --- | --- | --- | --- | --- |
| A-01 文档与架构基线 | T-10 | FR-022..029 | `AGENTS.md`, `LEARNING_PLAN.md`, `docs/*` | 需求、架构、数据、API 和任务编号一致 | 完成：39 tests + compileall |
| A-02 Alembic 基线 | A-01 | NFR-010 | 迁移配置、现有 Schema 基线 | 旧数据库升级且原数据可读 | 完成：4 migration tests；42 full tests；compileall |
| A-03 Agent 业务领域 | A-02 | FR-024..026 | 员工、余额、申请模型与 Service | 规则、事务和幂等测试通过 | 完成：6 domain tests；49 full tests；compileall |
| A-04 只读 Agent 工具 | A-03 | FR-023..025 | 制度、余额、申请查询工具 | Schema 隐藏身份且隔离测试通过 | 未开始 |
| A-05 Graph 与 Checkpoint | A-04 | FR-027 | State、Prompt、Graph、Runtime | 多轮缺参和跨请求状态可恢复 | 未开始 |
| A-06 人工确认 | A-05 | FR-026/027 | 草稿、interrupt、resume、写入 | 拒绝零写入，重复批准只写一次 | 未开始 |
| A-07 Agent API | A-06 | FR-022..028 | Router、Schema、应用服务、依赖 | Swagger 完成消息与确认流程 | 未开始 |
| A-08 安全与观测 | A-07 | FR-028/NFR-008..009 | 权限、错误、重试、工具日志 | 越权和敏感信息检查通过 | 未开始 |
| A-09 测试与真实评测 | A-08 | FR-029 | 单元、Graph、API、迁移、评测 | 真实 DeepSeek 评测产生可分析结果 | 未开始 |
| A-10 交付验收 | A-09 | FR-022..029 | README、图、演示和验收报告 | 完整演示链路和追踪表通过 | 未开始 |

`app/agents/leave_graph.py`、`tool_calling_agent.py`、`tools/policy_tools.py` 当前是学习原型或中断后的半成品。它们没有 Agent API、业务表和完整测试，不计为任何 A 任务完成证据；后续按新模块边界重构。

## 已确认的其他后续任务（尚未进入实现）

| 候选 | 目的 | 前置确认 |
| --- | --- | --- |
| C-01 简单登录认证 | 唯一邮箱和密码；JWT Access/Refresh Token；SQLite 保存 Refresh Token 哈希；刷新不轮换；退出时撤销 | 实现前选择可配置的安全有效期和密码哈希库，不增加设备管理等扩展功能 |
| C-07 知识库修改与删除 | 修改名称；只允许删除没有文档和会话的空知识库 | 设计 409 错误契约并覆盖空库、非空库和越权测试 |

这些任务已经确认需要，但必须先完成需求细化、数据库设计和 API 契约，不能直接开始编码。

当前优先完成 A-01 至 A-10。`C-07` 和 `C-01` 保留；最终简历验收前必须完成 `C-01`，用 JWT 替换 Agent 的模拟身份依赖。

用户资料修改和账号删除不在计划中；原先误记的 `FR-017`、`FR-018` 已撤销。

## 尚未确认的工程候选

| 候选 | 目的 | 前置确认 |
| --- | --- | --- |
| C-03 异步解析 | 避免长文档阻塞请求 | `[ASK USER]` 是否新增队列/worker |
| C-04 上传限制 | 防止磁盘和内存耗尽 | `[ASK USER]` 最大文件大小 |
| C-05 超时重试 | 提升 DeepSeek/Milvus 韧性 | `[ASK USER]` 超时与重试预算 |

## 新任务模板

```text
Goal：对应 FR/NFR 和用户可见结果
Context：相关文档、代码、测试
Constraints：权限、一致性和禁止事项
Files：预计修改文件
Tests：正常、边界、异常、越权
Done when：相关测试、全量测试、compileall、文档一致
```

## 验证命令

```powershell
python -m pytest -q
python -m compileall -q app tests
```

当前无 lint、格式化和静态类型配置，不能把它们写成已通过项。

## 证据

- Git 提交 `45ccf71`、`8abaabe`、`fb7ef51`。
- 各阶段学习文档。
- `tests/` 自动化用例。
