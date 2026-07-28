# API 设计

## 通用约定

- Base URL：`http://127.0.0.1:8000`；Swagger：`/docs`。
- 除 `POST /users` 和 `GET /health` 外，要求 `X-User-ID: <UUID>`。
- 响应携带 `X-Request-ID`。
- JSON 模型拒绝未声明字段；问题长度 1..2000。

```json
{"error":{"code":"KNOWLEDGE_BASE_FORBIDDEN","message":"无权访问该知识库。"}}
```

校验错误额外含 `details`；未知异常为 HTTP 500 + `INTERNAL_ERROR`。

## 接口总览

| 需求 | 方法与路径 | 成功 | 功能 |
| --- | --- | --- | --- |
| FR-015 | `GET /health` | 200/503 | 检查 API、SQLite、Milvus、Embedding |
| FR-001 | `POST /users` | 201 | 创建模拟用户 |
| FR-002 | `POST /knowledge-bases` | 201 | 创建知识库 |
| FR-002 | `GET /knowledge-bases` | 200 | 列出自己的知识库 |
| FR-004/005 | `POST /knowledge-bases/{kb_id}/documents` | 201 | 保存原文件和 UPLOADED 记录 |
| FR-004 | `GET /knowledge-bases/{kb_id}/documents` | 200 | 列出文档 |
| FR-006/007 | `POST /knowledge-bases/{kb_id}/documents/{document_id}/parse` | 200 | 同步解析入库 |
| FR-014 | `DELETE /knowledge-bases/{kb_id}/documents/{document_id}` | 204 | 幂等删除 |
| FR-008 | `POST /knowledge-bases/{kb_id}/retrieval-test` | 200 | 返回合格检索结果 |
| FR-009 | `POST /chat-sessions` | 201 | 创建会话 |
| FR-010..012 | `POST /chat-sessions/{session_id}/messages` | 200 | 问答/拒答/保存 |
| FR-013 | `GET /chat-sessions/{session_id}/messages` | 200 | 最近 20 条历史 |
| FR-022 | `POST /agent-sessions` | 201 | 创建绑定知识库的 Agent 会话 |
| FR-023..027 | `POST /agent-sessions/{session_id}/messages` | 200 | 执行 Agent 或返回待确认动作 |
| FR-026/027 | `POST /agent-sessions/{session_id}/decisions` | 200 | 批准或拒绝当前待确认动作 |
| FR-028 | `GET /agent-sessions/{session_id}/messages` | 200 | 读取 Agent 对话历史 |
| FR-028 | `GET /agent-sessions/{session_id}/tool-calls` | 200 | 读取脱敏工具调用记录 |

## 详细契约

### `GET /health`

无必填 Header/Body。全部正常为 200 + `status=ok`；任一组件异常为 503 + `status=degraded`，仍返回所有组件状态。

### `POST /users`

Body：`{"name":"张三"}`（1..100）。201 返回 ID、名称和时间。当前允许同名用户。

### `POST /knowledge-bases` / `GET /knowledge-bases`

要求 `X-User-ID`。POST Body 为 `{"name":"企业制度"}`，服务端设置 `owner_id`；GET 按创建时间倒序返回自己的知识库。错误：401 `INVALID_USER`；POST 还可能 500 `KNOWLEDGE_BASE_CREATE_FAILED`。

### `POST /knowledge-bases/{kb_id}/documents`

要求 `X-User-ID` 和知识库所有权。`multipart/form-data` 字段名为 `upload`，支持 TXT、MD、Markdown、PDF、DOCX。201 返回 `UPLOADED` 的 Document，不暴露 `storage_path`。主要错误：文件名/类型/空文件/保存失败/记录创建失败。

### `GET /knowledge-bases/{kb_id}/documents`

按创建时间倒序返回授权知识库中的全部文档。当前无分页。

### `POST /knowledge-bases/{kb_id}/documents/{document_id}/parse`

无 Body。文档必须属于授权知识库。200 返回更新后的 Document，成功时为 `READY`。主要错误：404 `DOCUMENT_NOT_FOUND`；409 `DOCUMENT_ALREADY_PROCESSING`；422 解析/内容/Chunk 为空；503 Embedding/Milvus；500 `DOCUMENT_PROCESS_FAILED`。

### `DELETE /knowledge-bases/{kb_id}/documents/{document_id}`

无 Body。成功或目标已不存在均为 204。`PROCESSING` 返回 409 `DOCUMENT_PROCESSING`；清理失败返回 Milvus、文件或 `DOCUMENT_DELETE_FAILED` 错误。

### `POST /knowledge-bases/{kb_id}/retrieval-test`

Body：`{"question":"专业培训上限是多少？"}`。200 返回 `question` 和 `results`；每项包含 Chunk/文档 ID、文件名、页码、正文和原始 COSINE 分数。无结果为 `results=[]`。搜索前按当前 `user_id + kb_id` 过滤。

### `POST /chat-sessions`

Body：`{"kb_id":"<UUID>"}`。知识库必须属于当前用户。201 返回会话。错误：知识库 404/403，或 500 `CHAT_SESSION_CREATE_FAILED`。

### `POST /chat-sessions/{session_id}/messages`

Body：`{"question":"北京住宿上限是多少？"}`。200 返回：

```json
{"answer":"……[S1]","rejected":false,"sources":[{"source_id":"S1","chunk_id":"<64位哈希>","document_id":"<UUID>","document_name":"policy.pdf","page":1,"excerpt":"……","score":0.73}]}
```

无依据返回 `{"answer":"知识库中没有足够依据。","rejected":true,"sources":[]}`。主要错误：会话 404/403、DeepSeek 503/502、历史保存 500。

### `GET /chat-sessions/{session_id}/messages`

返回最近 20 条消息并按时间正序排列；用户消息 `sources=[]`。引用 JSON 无效时为 500 `CHAT_SOURCE_DATA_INVALID`。

## Agent API 契约（已确认，尚未实现）

所有 Agent 接口要求当前身份有效，并对 Agent 会话、知识库和员工数据执行所有权校验。JWT 实现前暂用 `X-User-ID`；JWT 上线后只替换身份依赖，不修改 Agent 请求体。

### `POST /agent-sessions`

Body：

```json
{"kb_id":"<UUID>"}
```

知识库必须属于当前用户。201 返回 `id`、`kb_id`、`thread_id`、创建和更新时间。错误：401 `INVALID_USER`、404 `KNOWLEDGE_BASE_NOT_FOUND`、403 `KNOWLEDGE_BASE_FORBIDDEN`、500 `AGENT_SESSION_CREATE_FAILED`。

### `POST /agent-sessions/{session_id}/messages`

Body：

```json
{"message":"我想从 2026-08-03 开始请三天年假"}
```

响应状态只有：

- `COMPLETED`：本轮已经结束，`answer` 非空，`pending_action=null`。
- `REQUIRES_CONFIRMATION`：Graph 已暂停，返回唯一待确认动作。

统一响应示例：

```json
{
  "session_id":"<UUID>",
  "status":"REQUIRES_CONFIRMATION",
  "answer":"请确认以下请假申请。",
  "sources":[],
  "pending_action":{
    "action_id":"<UUID>",
    "tool_name":"create_leave_request",
    "summary":"2026-08-03 至 2026-08-05，共 3 个工作日，年假",
    "arguments":{"leave_type":"ANNUAL","start_date":"2026-08-03","end_date":"2026-08-05","reason":"个人事务"}
  },
  "request_id":"<request-id>"
}
```

`sources` 使用现有 `SourceRead` 结构。模型可见参数不得包含 `user_id`、`kb_id`、`employee_id` 或 `thread_id`。主要错误：会话 404/403、上下文 409 `AGENT_CONTEXT_MISSING`、DeepSeek 503/502、Checkpoint 503 `AGENT_CHECKPOINT_FAILED`。

### `POST /agent-sessions/{session_id}/decisions`

Body：

```json
{"action_id":"<UUID>","decision":"APPROVE"}
```

`decision` 只允许 `APPROVE` 或 `REJECT`。`action_id` 必须等于该会话当前中断动作；无待确认动作、动作不匹配或已处理返回 409。批准后以幂等键最多创建一条申请；拒绝不创建申请。响应沿用 Agent 统一响应。

### `GET /agent-sessions/{session_id}/messages`

返回该 Agent 会话的用户可见消息，按时间正序排列；不返回内部 Graph 状态和模型隐藏推理。

### `GET /agent-sessions/{session_id}/tool-calls`

返回工具名、状态、耗时、安全参数摘要、结果摘要、错误码和时间。制度正文、密码、Token、隐藏推理和内部异常堆栈不得出现在响应中。

## 已知限制

- OpenAPI 未逐项声明全部 `AppError` 响应模型；本文记录实际代码行为。
- 列表无分页，上传无文件大小限制。
- 没有登录接口，`X-User-ID` 可被伪造。
- Agent API 当前只是已确认契约，尚无路由、业务表、Checkpoint 和验收测试。

## 已确认但尚未设计的接口

以下能力已经确定需要，但请求方法、路径、请求体、响应体和错误码必须在删除级联与认证方案确认后再设计：

- FR-019：修改当前用户拥有的知识库。
- FR-020：删除当前用户拥有的空知识库；如果仍有文档或聊天会话则返回冲突错误，且不删除任何数据。
- FR-021：唯一邮箱和密码登录，成功后返回 JWT Access Token 与 Refresh Token；受保护接口使用 `Authorization: Bearer <access_token>`。Refresh Token 仅保存哈希和登录会话状态；刷新必须校验会话有效，退出登录撤销对应会话。密码和 Token 明文不得出现在持久化数据或日志中。

为保持实现简单，刷新接口只返回新的 Access Token，不返回新的 Refresh Token；原 Refresh Token 可重复使用到过期或撤销。

在这些接口实现前，当前 API 总览仍是实际可用接口的唯一依据。

`FR-022` 至 `FR-029` 的 Agent API 已完成本轮契约基线，但只有对应实现步骤通过测试后才能写入实际可用接口清单。

用户资料修改和账号删除不在当前或后续接口范围内；完整登录功能只负责认证身份和退出登录。

FR-020 已确认知识库删除不级联。建议使用 HTTP 409 表示知识库非空，具体业务错误码将在接口实现前最终确定。

## 证据

- `app/routers/*.py`、`app/schemas/*.py`
- `app/dependencies/auth.py`、`resources.py`
- `app/core/errors.py`、`app/services/*.py`
