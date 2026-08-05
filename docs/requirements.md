# 需求说明

## 项目背景与目标

项目用于学习并演示 FastAPI、RAG、Tool Calling、LangGraph、Milvus 与
PostgreSQL 的完整 AI 应用链路。当前版本定位为“企业知识库检索 Agent
基座”，目标是可靠完成文档入库、隔离检索、带引用回答、会话恢复和工具
审计。工程企业标书解析、生成与合规审查是下一阶段业务方向，尚未实现。

员工请假领域已经撤销。原有员工资料、假期余额、请假申请、人工确认和
决定接口不再属于项目范围，`FR-024` 至 `FR-027` 保留为撤销编号且不复用。

## 用户角色

- 普通用户：创建自己的知识库、上传文档、进行 RAG 问答。
- Agent 用户：创建绑定自己知识库的 Agent 会话，查询制度并查看引用和审计。
- 系统维护者：配置 PostgreSQL、Milvus、Embedding、DeepSeek 和运行日志。

JWT 登录尚未实现，当前使用 `X-User-ID` 作为学习阶段的模拟身份。

## 功能需求

| 编号 | 需求 | 状态 |
|---|---|---|
| FR-001 | 创建基础用户并获得 UUID | 已实现 |
| FR-002 | 创建并列出当前用户的知识库 | 已实现 |
| FR-003 | 用户只能访问自己的知识库 | 已实现（模拟身份） |
| FR-004 | 上传 TXT、MD、PDF、DOCX | 已实现 |
| FR-005 | 上传后保存原文件与 `UPLOADED` 记录 | 已实现 |
| FR-006 | 同步解析、切分、Embedding 和 Milvus 入库 | 已实现 |
| FR-007 | 重复解析前清理旧 Chunk | 已实现 |
| FR-008 | 按 Top-K、阈值和 Top-N 检索 | 已实现 |
| FR-009 | 创建绑定知识库的聊天会话 | 已实现 |
| FR-010 | 有依据时调用模型并返回结构化引用 | 已实现 |
| FR-011 | 无依据时拒答且不调用模型 | 已实现 |
| FR-012 | 同一事务保存一轮问答与引用 | 已实现 |
| FR-013 | 返回会话最近 20 条消息 | 已实现 |
| FR-014 | 幂等删除文档、原文件和 Milvus Chunk | 已实现 |
| FR-015 | 检查 API、PostgreSQL、Milvus 和 Embedding | 已实现 |
| FR-016 | 响应请求 ID，并写控制台和轮转日志 | 已实现 |
| FR-019 | 修改自己的知识库 | 待设计 |
| FR-020 | 仅删除自己的空知识库 | 待设计 |
| FR-021 | 邮箱密码登录与 JWT Access/Refresh Token | 待设计 |
| FR-022 | 创建绑定自己知识库的 Agent 会话 | 已实现 |
| FR-023 | Agent 检索绑定知识库并返回结构化引用 | 已实现 |
| FR-024..027 | 原员工请假与人工确认需求 | 已撤销，不复用 |
| FR-028 | 读取自己的 Agent 历史和脱敏工具日志 | 已实现 |
| FR-029 | Agent 自动测试与真实模型评测 | 部分实现 |

## 非功能需求

- NFR-001：错误不得泄露密钥、数据库细节或第三方堆栈。
- NFR-002：相对文件路径统一以项目根目录解析。
- NFR-003：默认使用 CPU Embedding，适配 16 GB 学习环境。
- NFR-004：关键逻辑可自动测试，普通测试不调用真实 DeepSeek。
- NFR-005：API 所有权与 Milvus 标量过滤共同保证数据隔离。
- NFR-006：失败可通过状态、错误码、请求 ID 和日志观察。
- NFR-007：业务事实存入 PostgreSQL；LangGraph Checkpoint 暂存独立 SQLite。
- NFR-008：模型 Tool Schema 不得包含用户或知识库身份字段。
- NFR-009：工具日志不得保存完整制度正文、Token、密码或隐藏推理。
- NFR-010：业务 Schema 由 Alembic 管理；不迁移旧 SQLite 业务数据。

## 业务规则

- BR-001：知识库、文档、聊天和 Agent 会话都必须校验当前用户所有权。
- BR-002：Milvus 检索必须同时过滤 `user_id` 与 `kb_id`。
- BR-003：没有达到阈值的 Chunk 时直接拒答。
- BR-004：上传只保存文件；解析入库由独立接口显式触发。
- BR-005：正式启动先执行 Alembic，再接受请求。
- BR-006：Agent 只能使用服务端注入的授权范围。
- BR-007：业务 PostgreSQL 与 Checkpoint SQLite 不建立跨库外键。

## 异常场景

覆盖资源不存在或越权、无效文件、空解析结果、Embedding 异常、Milvus
连接/检索/写入失败、DeepSeek 未配置或返回无效内容、PostgreSQL 连接或
事务失败、Checkpoint 损坏以及引用 JSON 损坏。

## 本期范围

- 删除员工请假领域及其 API、Graph 分支、模型、Service、工具和测试。
- 新建空 PostgreSQL 业务库，不导入旧 SQLite 业务数据。
- 保留独立 Checkpoint SQLite、通用 RAG、制度检索 Agent、会话与审计。
- Compose 提供 PostgreSQL 16、Milvus、etcd、MinIO 和 API 服务。

## 本期不做

不实现标书字段抽取、章节生成、合规规则、合同审查、审批写入、OCR、表格
专用解析、混合检索、Rerank、多 Agent、后台任务、分布式和高可用。JWT、
知识库修改删除仍为后续需求。

## 验收标准

- AC-001：PostgreSQL 空库可执行 Alembic 到最新版本。
- AC-002：最终业务库不存在三张请假表及其 PostgreSQL Enum。
- AC-003：源码、路由、Schema、测试和文档不存在可执行请假能力。
- AC-004：Agent 只注册 `search_company_policy`，并返回真实引用。
- AC-005：业务 API 使用 PostgreSQL；Checkpoint 继续使用独立 SQLite。
- AC-006：相关测试、全量测试和 Python 编译检查通过；未运行项如实记录。
