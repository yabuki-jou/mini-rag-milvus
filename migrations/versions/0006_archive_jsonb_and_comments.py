"""标准化归档 JSONB 字段，并补齐归档表与字段的 PostgreSQL 注释。"""

from collections.abc import Sequence

from alembic import op


revision: str = "0006_archive_jsonb_and_comments"
down_revision: str | Sequence[str] | None = "0005_archive_v1_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLE_COMMENTS = {
    "projects": "归档项目：普通用户的数据隔离边界，每个项目绑定一个知识库。",
    "archive_documents": "归档文档：记录面向用户的归档状态与正式可见性闸门。",
    "parsed_snapshots": "解析快照：可重现的规范化文本与定位结果的存储元数据。",
    "archive_field_values": "档案字段值：七个正式字段的草稿、来源与人工检查状态。",
    "field_evidences": "字段证据：字段建议或原文事实可追溯到解析快照的位置。",
    "checklist_items": "项目清单项：项目资料完整性检查的人工维护规则。",
    "checklist_links": "档案-清单项关联：人工确认后才可满足清单项。",
    "archive_operations": "归档操作：解析、建议、索引、删除的幂等与可恢复执行记录。",
    "archive_audit_logs": "归档审计：仅保留脱敏操作摘要，不保存原文或完整字段。",
}


COLUMN_COMMENTS = {
    "projects": {
        "id": "项目主键。",
        "owner_id": "项目所属用户；所有读写操作均以此校验所有权。",
        "kb_id": "项目唯一绑定的知识库；归档检索不得跨项目。",
        "name": "同一用户内去首尾空格后唯一的项目名称。",
        "description": "用户填写的项目说明，可为空。",
        "uses_demo_checklist": "创建时是否复制虚构演示清单模板。",
        "active_document_count": "当前未删除文档记录计数，用于每项目 100 份容量限制。",
        "version": "项目乐观锁版本。",
        "created_at": "项目创建 UTC 时间。",
        "updated_at": "项目最后修改 UTC 时间。",
    },
    "documents": {
        "file_hash": "原始上传文件字节的 SHA-256，用于同项目重复上传校验。",
        "project_id": "归档项目归属；旧知识库文档可为空。",
    },
    "archive_documents": {
        "document_id": "同时引用原文件 documents.id 的归档文档主键。",
        "status": "用户可见的七态归档处理状态。",
        "current_snapshot_id": "当前有效解析快照；正式确认时必须存在。",
        "confirmed_by": "最近一次正式确认的操作人。",
        "confirmed_at": "最近一次正式确认 UTC 时间。",
        "final_index_snapshot_hash": "进入正式 Milvus 索引的快照哈希。",
        "final_chunk_count": "当前正式索引中的 Chunk 数量。",
        "last_error_code": "最近一次稳定业务错误码。",
        "last_error_summary": "可向用户展示的脱敏失败摘要。",
        "version": "乐观锁版本，字段或证据修改后递增。",
        "created_at": "归档记录创建 UTC 时间。",
        "updated_at": "归档记录最后修改 UTC 时间。",
    },
    "parsed_snapshots": {
        "id": "解析快照主键。",
        "document_id": "对应归档文档。",
        "snapshot_storage_path": "规范化解析快照的受控存储路径。",
        "snapshot_hash": "规范化解析文本的 SHA-256，用于一致性与索引绑定。",
        "parser_name": "生成快照的解析器名称。",
        "parser_version": "生成快照的解析器版本。",
        "normalization_version": "换行和空白等文本规范化规则版本。",
        "text_character_count": "快照有效文本字符数。",
        "fragment_count": "快照中可定位片段的数量。",
        "created_at": "快照创建 UTC 时间。",
    },
    "archive_field_values": {
        "id": "字段值主键。",
        "document_id": "所属归档文档；每文档每字段仅一条。",
        "field_name": "七个固定正式字段之一。",
        "text_value": "文本类字段值；日期和关键词字段必须为空。",
        "date_value": "文档日期字段值；仅 DOCUMENT_DATE 使用。",
        "json_value": "关键词字符串数组；仅 KEYWORDS 使用。",
        "review_status": "人工检查状态：待检查、已确认值或接受为空。",
        "source": "字段来源：AI 建议或人工录入。",
        "no_source_evidence": "人工值无原文证据时为真，禁止作为问答依据。",
        "updated_by": "最近填写或修改字段的用户。",
        "updated_at": "字段最后修改 UTC 时间。",
    },
    "field_evidences": {
        "id": "字段证据主键。",
        "field_value_id": "对应的档案字段值。",
        "snapshot_id": "证据来自的解析快照。",
        "excerpt": "用于人工核对的原文摘录。",
        "location_type": "定位类型：PDF 页码、DOCX 段落或文本行范围。",
        "location_start": "从 1 开始的定位起点。",
        "location_end": "从 1 开始的定位终点；非行范围时与起点相同。",
        "normalized_anchor": "辅助定位的规范化文本锚点。",
        "created_at": "证据创建 UTC 时间。",
    },
    "checklist_items": {
        "id": "清单项主键。",
        "project_id": "该清单项仅属于一个项目。",
        "name": "用户可见的清单项名称。",
        "document_type": "建议关联的固定资料类型。",
        "is_required": "必需项未满足显示缺失；可选项未满足显示未提供。",
        "project_stage": "建议关联的固定项目阶段。",
        "description": "清单项说明，可为空。",
        "version": "乐观锁版本。",
        "created_at": "清单项创建 UTC 时间。",
        "updated_at": "清单项最后修改 UTC 时间。",
    },
    "checklist_links": {
        "id": "关联记录主键。",
        "document_id": "已确认或待重新确认的归档文档。",
        "checklist_item_id": "被满足或失效的项目清单项。",
        "status": "人工确认关联或因规则变化失效。",
        "confirmed_by": "确认关联的用户。",
        "confirmed_at": "确认关联 UTC 时间。",
        "invalidated_at": "关联失效 UTC 时间。",
        "invalidated_reason": "关联失效原因。",
        "version": "乐观锁版本。",
        "created_at": "关联创建 UTC 时间。",
        "updated_at": "关联最后修改 UTC 时间。",
    },
    "archive_operations": {
        "id": "内部操作主键。",
        "document_id": "被解析、建议、索引或删除的归档文档。",
        "operation_type": "内部操作类型：PARSE、SUGGEST、INDEX 或 DELETE。",
        "operation_status": "内部操作状态：RUNNING、SUCCEEDED 或 FAILED。",
        "visibility_blocking": "删除期间阻断正式检索和目录可见性的标志。",
        "attempt_no": "同一操作的尝试次数，从 1 开始。",
        "last_completed_step": "可恢复操作最近完成的步骤标识。",
        "failure_code": "受控的内部失败代码。",
        "failure_summary": "脱敏的失败摘要，不向客户端透出内部异常。",
        "started_at": "操作开始 UTC 时间。",
        "finished_at": "操作结束 UTC 时间。",
        "created_at": "操作记录创建 UTC 时间。",
        "updated_at": "操作记录最后修改 UTC 时间。",
    },
    "archive_audit_logs": {
        "id": "审计记录主键。",
        "project_id": "发生业务操作的项目。",
        "actor_id": "执行操作的用户。",
        "operation_type": "受控业务审计操作类型，不能由客户端自由传入。",
        "resource_type": "被操作资源的类型。",
        "resource_id": "被操作资源标识。",
        "operation_id": "可选内部操作标识，用于幂等审计去重。",
        "redacted_summary": "仅保存允许展示的脱敏摘要。",
        "created_at": "审计记录创建 UTC 时间。",
    },
}


def _add_postgres_comments() -> None:
    """写入 PostgreSQL 系统目录注释，供数据库客户端和运维核查使用。"""
    for table_name, comment in TABLE_COMMENTS.items():
        # 注释均为本迁移内的固定文案，不接受用户输入；这样离线 SQL 也可完整审阅。
        op.execute(f"COMMENT ON TABLE {table_name} IS '{comment}'")
    for table_name, column_comments in COLUMN_COMMENTS.items():
        for column_name, comment in column_comments.items():
            op.execute(
                f"COMMENT ON COLUMN {table_name}.{column_name} IS '{comment}'"
            )


def upgrade() -> None:
    """将 JSON 转为 JSONB，并写入归档字段说明。"""
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        "ALTER TABLE archive_field_values "
        "ALTER COLUMN json_value TYPE JSONB USING json_value::jsonb"
    )
    op.execute(
        "ALTER TABLE archive_audit_logs "
        "ALTER COLUMN redacted_summary TYPE JSONB USING redacted_summary::jsonb"
    )
    _add_postgres_comments()


def downgrade() -> None:
    """仅供尚未写入归档业务数据的本地开发环境回退。"""
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        "COMMENT ON TABLE projects IS NULL"
    )
    for table_name, column_comments in COLUMN_COMMENTS.items():
        for column_name in column_comments:
            op.execute(f"COMMENT ON COLUMN {table_name}.{column_name} IS NULL")
    for table_name in TABLE_COMMENTS:
        if table_name != "projects":
            op.execute(f"COMMENT ON TABLE {table_name} IS NULL")
    op.execute(
        "ALTER TABLE archive_field_values "
        "ALTER COLUMN json_value TYPE JSON USING json_value::json"
    )
    op.execute(
        "ALTER TABLE archive_audit_logs "
        "ALTER COLUMN redacted_summary TYPE JSON USING redacted_summary::json"
    )
