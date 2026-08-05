# Agent 逻辑导览

当前 Agent 是单图、只读的企业知识库检索 Agent。

| 层 | 文件 | 职责 |
|---|---|---|
| HTTP | `app/routers/agent.py`, `app/schemas/agent.py` | 会话、消息、历史、审计契约 |
| 应用服务 | `app/services/agent_service.py` | 所有权、Graph 调用、引用和审计转换 |
| Graph | `app/agents/admin/graph.py` | 上下文校验、模型与 ToolNode 闭环 |
| Runtime | `app/agents/admin/runtime.py` | SQLite Checkpoint 生命周期 |
| Tool | `app/agents/tools/policy_tools.py` | 使用注入范围调用 RAG 检索 |
| 存储 | PostgreSQL、Milvus、Checkpoint SQLite | 业务事实、向量索引、Graph 状态 |

调用过程：服务端从 `AgentSession` 注入 `user_id` 和 `kb_id` → Graph 校验
UUID → DeepSeek 决定是否调用 `search_company_policy(query)` → Tool 使用固定范围
检索 Milvus → 模型根据真实结果回答 → 应用服务返回引用并保存脱敏工具日志。

模型只能生成 `query`，不能生成或覆盖身份。工具日志仅记录是否提供查询、
查询长度、是否命中、结果数量、耗时和错误码，不保存制度正文与内部异常。

PostgreSQL 保存 Agent 会话和审计；Checkpoint SQLite 保存消息与授权范围。两者
不建立外键。当前没有写工具、`interrupt/resume` 或人工决定接口。
