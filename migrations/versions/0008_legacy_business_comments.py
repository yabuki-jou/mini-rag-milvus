"""为既有 RAG、聊天和 Agent 业务表补齐 PostgreSQL 注释。"""

from collections.abc import Sequence

from alembic import op


revision: str = "0008_legacy_business_comments"
down_revision: str | Sequence[str] | None = "0007_project_version_comment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLE_COMMENTS = {
    "users": "用户：业务资源与知识库的所有权主体。",
    "knowledge_bases": "知识库：用户拥有的原始文档与检索隔离边界。",
    "documents": "原始文档：上传文件的持久化身份与旧 RAG 处理状态。",
    "chat_sessions": "聊天会话：用户针对一个知识库的普通问答会话。",
    "chat_messages": "聊天消息：普通问答会话中的用户问题或助手回答。",
    "agent_sessions": "Agent 会话：授权用户、知识库与 LangGraph 线程的绑定。",
    "agent_tool_call_logs": "Agent 工具日志：可查询的脱敏只读工具调用审计。",
}


COLUMN_COMMENTS = {
    "users": {
        "id": "用户主键。",
        "name": "用户显示名称。",
        "created_at": "用户记录创建 UTC 时间。",
        "updated_at": "用户记录最后修改 UTC 时间。",
    },
    "knowledge_bases": {
        "id": "知识库主键。",
        "owner_id": "拥有该知识库的用户。",
        "name": "知识库显示名称。",
        "created_at": "知识库创建 UTC 时间。",
        "updated_at": "知识库最后修改 UTC 时间。",
    },
    "documents": {
        "id": "原始文档主键，也是跨 PostgreSQL、文件系统与 Milvus 的稳定标识。",
        "kb_id": "文档所属知识库。",
        "project_id": "归档项目归属；非归档旧文档为空。",
        "filename": "去除目录部分后的安全原始文件名。",
        "storage_path": "服务器受控原始文件存储路径。",
        "file_hash": "原始上传文件字节的 SHA-256，用于同项目重复上传校验。",
        "status": "旧 RAG 文档处理状态；智慧档案业务不以此作为归档状态。",
        "chunk_count": "旧 RAG 成功写入向量库的 Chunk 数量。",
        "error_message": "最近一次旧 RAG 处理或删除失败的受控摘要。",
        "created_at": "文档记录创建 UTC 时间。",
        "updated_at": "文档记录最后修改 UTC 时间。",
    },
    "chat_sessions": {
        "id": "聊天会话主键。",
        "user_id": "创建并拥有聊天会话的用户。",
        "kb_id": "会话问答限定使用的知识库。",
        "created_at": "会话创建 UTC 时间。",
        "updated_at": "会话最后修改 UTC 时间。",
    },
    "chat_messages": {
        "id": "聊天消息主键。",
        "session_id": "消息所属聊天会话。",
        "role": "消息角色：USER 或 ASSISTANT。",
        "content": "用户问题或助手回答正文。",
        "sources_json": "助手回答的引用信息 JSON；用户消息为空。",
        "created_at": "消息创建 UTC 时间。",
    },
    "agent_sessions": {
        "id": "对外暴露的 Agent 会话主键。",
        "user_id": "创建并拥有 Agent 会话的可信用户。",
        "kb_id": "Agent 会话固定检索的知识库。",
        "thread_id": "LangGraph Checkpoint 使用的唯一线程标识。",
        "created_at": "Agent 会话创建 UTC 时间。",
        "updated_at": "最近一次成功执行 Agent Graph 的 UTC 时间。",
    },
    "agent_tool_call_logs": {
        "id": "工具调用日志主键。",
        "agent_session_id": "工具调用所属 Agent 会话。",
        "tool_call_id": "模型生成的调用标识；同一会话内唯一。",
        "tool_name": "被调用的正式只读工具名称。",
        "status": "调用公开状态：COMPLETED 或 FAILED。",
        "arguments_summary_json": "不含身份字段和敏感信息的调用参数摘要 JSON。",
        "result_summary_json": "不含制度正文和内部异常的调用结果摘要 JSON。",
        "duration_ms": "工具调用耗时，单位为毫秒。",
        "error_code": "可安全展示的稳定错误代码；成功时为空。",
        "created_at": "首次观察到调用的 UTC 时间。",
        "updated_at": "日志记录最后修改 UTC 时间。",
    },
}


def upgrade() -> None:
    """为历史业务表写入固定 PostgreSQL 表和字段注释。"""
    if op.get_bind().dialect.name != "postgresql":
        return

    for table_name, comment in TABLE_COMMENTS.items():
        op.execute(f"COMMENT ON TABLE {table_name} IS '{comment}'")
    for table_name, column_comments in COLUMN_COMMENTS.items():
        for column_name, comment in column_comments.items():
            op.execute(
                f"COMMENT ON COLUMN {table_name}.{column_name} IS '{comment}'"
            )


def downgrade() -> None:
    """仅供尚未写入业务数据的本地开发环境回退。"""
    if op.get_bind().dialect.name != "postgresql":
        return

    for table_name, column_comments in COLUMN_COMMENTS.items():
        for column_name in column_comments:
            op.execute(f"COMMENT ON COLUMN {table_name}.{column_name} IS NULL")
    for table_name in TABLE_COMMENTS:
        op.execute(f"COMMENT ON TABLE {table_name} IS NULL")
