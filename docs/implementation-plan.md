# 实施计划

## 已有 RAG 与 Agent 基座

| 任务 | 需求 | 范围 | 状态 |
|---|---|---|---|
| T-01 项目骨架 | FR-015/016 | FastAPI、配置、日志、健康检查 | 完成 |
| T-02 用户与知识库 | FR-001..003 | 模型、所有权依赖、API | 完成 |
| T-03 文档上传 | FR-004/005 | 原文件、哈希、状态 | 完成 |
| T-04 解析切分 | FR-006/007 | 四类文档、页码、稳定 Chunk | 完成 |
| T-05 Embedding 与 Milvus | FR-006..008 | 512 维向量、隔离与重跑 | 完成 |
| T-06 RAG 问答 | FR-009..013 | 拒答、引用、历史 | 完成 |
| T-07 幂等删除 | FR-014 | PostgreSQL/文件/Milvus 清理 | 完成 |
| A-01 Agent 会话 | FR-022 | 会话、授权范围、Checkpoint | 完成 |
| A-02 制度检索工具 | FR-023 | Tool Schema、RAG Tool、Graph | 完成 |
| A-03 历史与审计 | FR-028 | 用户消息、引用、脱敏工具日志 | 完成 |

## 本次任务：删除请假领域并迁移 PostgreSQL

| 任务 | 依赖 | 目标与文件 | 验证 | 状态 |
|---|---|---|---|---|
| M-01 范围确认与备份 | 无 | 确认删除数据、保留通用 Agent/Checkpoint；备份源码测试文档 | ZIP 存在且不含 `.env`/数据/日志 | 完成 |
| M-02 文档同步 | M-01 | `docs/requirements.md`、架构、数据库、API、计划 | 请假标为撤销；标书标为未实现 | 完成 |
| M-03 删除领域代码 | M-02 | 删除 leave model/service/tool/contracts；简化 Graph/Runtime/Schema/Router | `rg` 无可执行请假引用 | 完成 |
| M-04 PostgreSQL 配置 | M-02 | `app/db.py`、配置、依赖、Compose | 默认 URL 使用 psycopg；Compose 有健康检查 | 完成（CLI 未验证） |
| M-05 前向迁移 | M-03/M-04 | `0004_remove_leave_domain` 与迁移兼容性 | 空 PostgreSQL 到 head；无请假表/Enum | 部分完成：离线 SQL 通过，在线空库待验证 |
| M-06 测试调整 | M-03/M-05 | 删除请假测试，保留 RAG/Agent 测试，增加 PostgreSQL 测试 | 受影响和全量测试 | 完成：68 passed，1 个 PostgreSQL 集成测试跳过 |
| M-07 文档与交付 | M-06 | README、Agent 导览、演示、验收报告 | 文档与实测一致 | 完成 |

本任务不包含旧 SQLite 业务数据导入，也不把 LangGraph Checkpoint 改为
PostgreSQL。SQLite 单元测试只作为快速隔离测试，不能替代 PostgreSQL 迁移证据。

## 后续业务方向（未实施）

下一阶段目标为工程企业标书与项目资料审查 Agent。开始编码前必须重新完成
需求澄清，至少确认目标文档、抽取字段、合规规则来源、生成范围、人工复核、
评测数据和验收指标。不得复用已删除请假流程来假装完成标书审批。

## 后续通用能力

- C-01：JWT 登录，替换可伪造的 `X-User-ID`。
- C-02：知识库修改与空库删除。
- C-03：Checkpoint PostgreSQL 或其他共享存储（需要多实例部署时再实施）。
- C-04：大文件异步解析与任务状态。
