# API 设计

## 通用约定

- 当前受保护接口使用 `X-User-ID` 模拟身份；无效身份返回 401。
- 资源不存在返回 404，越权返回 403，业务冲突返回 409。
- 错误统一包含稳定业务错误码，不返回堆栈、数据库地址或内部路径。
- 响应携带 `X-Request-ID`；列表排序和数量由各接口固定。

## 接口总览

| 需求 | 方法与路径 | 成功码 | 说明 |
|---|---|---|---|
| FR-015 | `GET /health` | 200/503 | 检查 API、PostgreSQL、Milvus、Embedding |
| FR-001 | `POST /users` | 201 | 创建模拟用户 |
| FR-002 | `POST /knowledge-bases` | 201 | 创建自己的知识库 |
| FR-002 | `GET /knowledge-bases` | 200 | 列出自己的知识库 |
| FR-004/005 | `POST /knowledge-bases/{kb_id}/documents` | 201 | 保存文件和 `UPLOADED` 记录 |
| FR-004 | `GET /knowledge-bases/{kb_id}/documents` | 200 | 列出文档 |
| FR-006/007 | `POST /knowledge-bases/{kb_id}/documents/{document_id}/parse` | 200 | 同步解析入库 |
| FR-014 | `DELETE /knowledge-bases/{kb_id}/documents/{document_id}` | 204 | 幂等删除 |
| FR-008 | `POST /knowledge-bases/{kb_id}/retrieval-test` | 200 | 返回检索结果 |
| FR-009 | `POST /chat-sessions` | 201 | 创建 RAG 会话 |
| FR-010..012 | `POST /chat-sessions/{session_id}/messages` | 200 | 问答或拒答 |
| FR-013 | `GET /chat-sessions/{session_id}/messages` | 200 | 最近 20 条历史 |
| FR-022 | `POST /agent-sessions` | 201 | 创建 Agent 会话 |
| FR-023 | `POST /agent-sessions/{session_id}/messages` | 200 | 制度检索 Agent |
| FR-028 | `GET /agent-sessions/{session_id}/messages` | 200 | Agent 历史 |
| FR-028 | `GET /agent-sessions/{session_id}/tool-calls` | 200 | 脱敏工具日志 |

已删除 `POST /agent-sessions/{session_id}/decisions`。该接口只服务于撤销的请假
人工确认流程，当前没有替代接口。

## Agent 接口

### `POST /agent-sessions`

Header：`X-User-ID`。请求：

```json
{"kb_id":"4b542bd7-433f-4757-adb2-2c7184551501"}
```

知识库必须属于当前用户。返回会话 `id`、`kb_id`、`thread_id`、创建和更新时间。

### `POST /agent-sessions/{session_id}/messages`

请求：

```json
{"message":"项目资料应当如何归档？"}
```

响应：

```json
{
  "session_id":"b48cb3fe-c92e-4eaf-9dca-05ad47293dc0",
  "status":"COMPLETED",
  "answer":"根据项目管理制度，资料应……[S1]",
  "sources":[{
    "source_id":"S1",
    "chunk_id":"...",
    "document_id":"...",
    "document_name":"项目管理制度.pdf",
    "page":2,
    "excerpt":"……",
    "score":0.88
  }],
  "request_id":"..."
}
```

模型可见参数只有 `query`。`user_id`、`kb_id` 和 `thread_id` 均由服务端注入。
当前响应没有 `pending_action`，状态只有 `COMPLETED`。

### 历史与工具日志

`GET /messages` 只返回用户和助手可见消息，不返回 ToolMessage、Graph 内部状态
或隐藏推理。`GET /tool-calls` 返回工具名、完成/失败状态、脱敏参数摘要、结果
数量、耗时和稳定错误码，不返回制度正文、身份、Token 或密码。

## 权限规则

创建 Agent 会话时验证知识库所有权；后续所有接口先验证 Agent 会话所有权。
制度 Tool 只能使用会话中固定的用户和知识库，客户端与模型不能覆盖。

## 主要错误

- `INVALID_USER`：模拟身份不存在。
- `KNOWLEDGE_BASE_NOT_FOUND/FORBIDDEN`：知识库不存在或越权。
- `AGENT_SESSION_NOT_FOUND/FORBIDDEN`：Agent 会话不存在或越权。
- `AGENT_CONTEXT_MISSING/INVALID`：Graph 授权范围缺失或损坏。
- `AGENT_CHECKPOINT_*`：Checkpoint 读取失败或暂时不可用。
- `AGENT_TIMEOUT/CONNECTION_FAILED/EXECUTION_FAILED`：Agent 执行分类错误。
- `AGENT_RESPONSE_INVALID`：Graph 未产生有效最终文本。
