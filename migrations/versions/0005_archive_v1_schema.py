"""创建智慧档案 V1 项目、归档、清单和审计 Schema。"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_archive_v1_schema"
down_revision: str | Sequence[str] | None = "0004_remove_leave_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum_check(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    """用跨方言 CHECK 固定 V1 枚举，避免 SQLite 验证与 PostgreSQL 生产语义分叉。"""
    options = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({options})", name=name)


def _create_partial_unique_index(name: str, table: str, columns: list[str], where: str) -> None:
    """按当前数据库方言创建部分唯一索引。"""
    dialect = op.get_bind().dialect.name
    kwargs: dict[str, object] = {}
    if dialect == "postgresql":
        kwargs["postgresql_where"] = sa.text(where)
    elif dialect == "sqlite":
        kwargs["sqlite_where"] = sa.text(where)
    op.create_index(name, table, columns, unique=True, **kwargs)


def _add_documents_archive_scope() -> None:
    """在保留旧 RAG 文档语义的前提下追加项目范围与原文件哈希命名。"""
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("documents") as batch:
            batch.drop_index("ix_documents_content_hash")
            batch.alter_column("content_hash", new_column_name="file_hash", existing_type=sa.String(length=64))
            batch.add_column(sa.Column("project_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key("fk_documents_project_kb", "projects", ["project_id", "kb_id"], ["id", "kb_id"])
    else:
        op.drop_index("ix_documents_content_hash", table_name="documents")
        op.alter_column("documents", "content_hash", new_column_name="file_hash", existing_type=sa.String(length=64))
        op.add_column("documents", sa.Column("project_id", sa.Uuid(), nullable=True))
        op.create_foreign_key("fk_documents_project_kb", "documents", "projects", ["project_id", "kb_id"], ["id", "kb_id"])

    op.create_index("uq_documents_project_file_hash", "documents", ["project_id", "file_hash"], unique=True)
    op.create_index("ix_documents_file_hash", "documents", ["file_hash"])
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index("ix_documents_project_created_id", "documents", ["project_id", "created_at", "id"])


def _add_snapshot_foreign_key() -> None:
    """补充 ArchiveDocument 与 ParsedSnapshot 的循环引用。"""
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("archive_documents") as batch:
            batch.create_foreign_key("fk_archive_documents_current_snapshot", "parsed_snapshots", ["current_snapshot_id"], ["id"])
    else:
        op.create_foreign_key("fk_archive_documents_current_snapshot", "archive_documents", "parsed_snapshots", ["current_snapshot_id"], ["id"])


def upgrade() -> None:
    """以空库和旧 0004 Schema 都兼容的顺序创建智慧档案 V1 表。"""
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("uses_demo_checklist", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active_document_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("name = trim(name) AND length(name) > 0", name="ck_projects_name_trimmed"),
        sa.CheckConstraint("active_document_count BETWEEN 0 AND 100", name="ck_projects_active_document_count"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_projects_owner_name"),
        sa.UniqueConstraint("id", "kb_id", name="uq_projects_id_kb_id"),
        sa.UniqueConstraint("kb_id", name="uq_projects_kb_id"),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])
    op.create_index("ix_projects_kb_id", "projects", ["kb_id"])
    op.create_index("ix_projects_owner_updated_id", "projects", ["owner_id", "updated_at", "id"])

    _add_documents_archive_scope()

    op.create_table(
        "archive_documents",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=22), nullable=False),
        sa.Column("current_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_index_snapshot_hash", sa.String(length=64), nullable=True),
        sa.Column("final_chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_summary", sa.String(length=500), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _enum_check("status", ("UPLOADED", "PARSE_FAILED", "PARSED", "SUGGESTION_FAILED", "PENDING_CONFIRMATION", "CONFIRMED", "PENDING_RECONFIRMATION"), "ck_archive_documents_status"),
        sa.CheckConstraint("final_chunk_count >= 0", name="ck_archive_documents_final_chunk_count"),
        sa.CheckConstraint("status != 'CONFIRMED' OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL AND current_snapshot_id IS NOT NULL AND length(final_index_snapshot_hash) = 64)", name="ck_archive_documents_confirmed_requirements"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index("ix_archive_documents_status", "archive_documents", ["status"])
    op.create_index("ix_archive_documents_current_snapshot_id", "archive_documents", ["current_snapshot_id"], unique=True)
    op.create_index("ix_archive_documents_status_confirmed_at_id", "archive_documents", ["status", "confirmed_at", "document_id"])
    op.create_index("ix_archive_documents_status_updated_at_id", "archive_documents", ["status", "updated_at", "document_id"])

    op.create_table(
        "parsed_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_storage_path", sa.String(length=1024), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("parser_name", sa.String(length=100), nullable=False),
        sa.Column("parser_version", sa.String(length=100), nullable=False),
        sa.Column("normalization_version", sa.String(length=50), nullable=False),
        sa.Column("text_character_count", sa.Integer(), nullable=False),
        sa.Column("fragment_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("text_character_count > 0", name="ck_parsed_snapshots_text_count"),
        sa.CheckConstraint("fragment_count > 0", name="ck_parsed_snapshots_fragment_count"),
        sa.ForeignKeyConstraint(["document_id"], ["archive_documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parsed_snapshots_document_id", "parsed_snapshots", ["document_id"], unique=True)
    op.create_index("ix_parsed_snapshots_snapshot_hash", "parsed_snapshots", ["snapshot_hash"])
    _add_snapshot_foreign_key()

    op.create_table(
        "archive_field_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=22), nullable=False),
        sa.Column("text_value", sa.Text(), nullable=True),
        sa.Column("date_value", sa.Date(), nullable=True),
        sa.Column("json_value", sa.JSON(), nullable=True),
        sa.Column("review_status", sa.String(length=15), nullable=False, server_default="PENDING_CHECK"),
        sa.Column("source", sa.String(length=6), nullable=True),
        sa.Column("no_source_evidence", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _enum_check("field_name", ("TITLE", "DOCUMENT_TYPE", "DOCUMENT_DATE", "AUTHORING_ORGANIZATION", "VERSION_NUMBER", "PROJECT_STAGE", "KEYWORDS"), "ck_archive_field_values_name"),
        _enum_check("review_status", ("PENDING_CHECK", "VALUE_CONFIRMED", "EMPTY_ACCEPTED"), "ck_archive_field_values_review_status"),
        _enum_check("source", ("AI", "MANUAL"), "ck_archive_field_values_source"),
        sa.CheckConstraint("(field_name = 'DOCUMENT_DATE' AND text_value IS NULL AND json_value IS NULL) OR (field_name = 'KEYWORDS' AND text_value IS NULL AND date_value IS NULL) OR (field_name NOT IN ('DOCUMENT_DATE', 'KEYWORDS') AND date_value IS NULL AND json_value IS NULL)", name="ck_archive_field_values_value_column_by_name"),
        sa.CheckConstraint("review_status != 'EMPTY_ACCEPTED' OR (text_value IS NULL AND date_value IS NULL AND json_value IS NULL)", name="ck_archive_field_values_empty_accepted"),
        sa.CheckConstraint("review_status != 'VALUE_CONFIRMED' OR (field_name = 'DOCUMENT_DATE' AND date_value IS NOT NULL) OR (field_name = 'KEYWORDS' AND json_value IS NOT NULL) OR (field_name NOT IN ('DOCUMENT_DATE', 'KEYWORDS') AND text_value IS NOT NULL AND length(trim(text_value)) > 0)", name="ck_archive_field_values_confirmed_value"),
        sa.ForeignKeyConstraint(["document_id"], ["archive_documents.document_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "field_name", name="uq_archive_field_values_document_field"),
    )
    op.create_index("ix_archive_field_values_document_id", "archive_field_values", ["document_id"])
    op.create_index("ix_archive_field_values_field_name", "archive_field_values", ["field_name"])

    op.create_table(
        "field_evidences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("field_value_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("location_type", sa.String(length=15), nullable=False),
        sa.Column("location_start", sa.Integer(), nullable=False),
        sa.Column("location_end", sa.Integer(), nullable=False),
        sa.Column("normalized_anchor", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _enum_check("location_type", ("PDF_PAGE", "DOCX_PARAGRAPH", "TEXT_LINE_RANGE"), "ck_field_evidences_location_type"),
        sa.CheckConstraint("location_start >= 1", name="ck_field_evidences_location_start"),
        sa.CheckConstraint("location_end >= location_start", name="ck_field_evidences_location_range"),
        sa.CheckConstraint("location_type = 'TEXT_LINE_RANGE' OR location_start = location_end", name="ck_field_evidences_point_location"),
        sa.ForeignKeyConstraint(["field_value_id"], ["archive_field_values.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["parsed_snapshots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_field_evidences_field_value_id", "field_evidences", ["field_value_id"])
    op.create_index("ix_field_evidences_snapshot_id", "field_evidences", ["snapshot_id"])

    op.create_table(
        "checklist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("document_type", sa.String(length=15), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("project_stage", sa.String(length=12), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _enum_check("document_type", ("CONTRACT", "DESIGN", "CONSTRUCTION", "MEETING_MINUTES", "ACCEPTANCE", "OTHER"), "ck_checklist_items_document_type"),
        _enum_check("project_stage", ("PREPARATION", "DESIGN", "CONSTRUCTION", "ACCEPTANCE", "CROSS_STAGE", "OTHER_STAGE"), "ck_checklist_items_project_stage"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_checklist_items_project_id", "checklist_items", ["project_id"])
    op.create_index("ix_checklist_items_project_updated_id", "checklist_items", ["project_id", "updated_at", "id"])
    op.create_index("ix_checklist_items_project_required_stage", "checklist_items", ["project_id", "is_required", "project_stage"])

    op.create_table(
        "checklist_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("checklist_item_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=11), nullable=False),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_reason", sa.String(length=200), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _enum_check("status", ("CONFIRMED", "INVALIDATED"), "ck_checklist_links_status"),
        sa.CheckConstraint("status != 'CONFIRMED' OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)", name="ck_checklist_links_confirmed_requirements"),
        sa.CheckConstraint("status != 'INVALIDATED' OR (invalidated_at IS NOT NULL AND invalidated_reason IS NOT NULL)", name="ck_checklist_links_invalidated_requirements"),
        sa.ForeignKeyConstraint(["document_id"], ["archive_documents.document_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["checklist_item_id"], ["checklist_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "checklist_item_id", name="uq_checklist_links_document_item"),
    )
    op.create_index("ix_checklist_links_document_id", "checklist_links", ["document_id"])
    op.create_index("ix_checklist_links_checklist_item_id", "checklist_links", ["checklist_item_id"])
    op.create_index("ix_checklist_links_item_status", "checklist_links", ["checklist_item_id", "status"])
    op.create_index("ix_checklist_links_document_status", "checklist_links", ["document_id", "status"])

    op.create_table(
        "archive_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("operation_type", sa.String(length=7), nullable=False),
        sa.Column("operation_status", sa.String(length=9), nullable=False),
        sa.Column("visibility_blocking", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attempt_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_completed_step", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_summary", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _enum_check("operation_type", ("PARSE", "SUGGEST", "INDEX", "DELETE"), "ck_archive_operations_type"),
        _enum_check("operation_status", ("RUNNING", "SUCCEEDED", "FAILED"), "ck_archive_operations_status"),
        sa.CheckConstraint("attempt_no >= 1", name="ck_archive_operations_attempt_no"),
        sa.CheckConstraint("visibility_blocking = FALSE OR operation_type = 'DELETE'", name="ck_archive_operations_visibility_blocking"),
        sa.ForeignKeyConstraint(["document_id"], ["archive_documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_archive_operations_document_id", "archive_operations", ["document_id"])
    op.create_index("ix_archive_operations_status_updated", "archive_operations", ["operation_status", "updated_at"])
    op.create_index("ix_archive_operations_document_type_created", "archive_operations", ["document_id", "operation_type", "created_at"])
    _create_partial_unique_index("uq_archive_operations_document_running", "archive_operations", ["document_id"], "operation_status = 'RUNNING'")
    _create_partial_unique_index("uq_archive_operations_delete_unfinished", "archive_operations", ["document_id"], "operation_type = 'DELETE' AND operation_status IN ('RUNNING', 'FAILED')")

    op.create_table(
        "archive_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=True),
        sa.Column("redacted_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_id", name="uq_archive_audit_logs_operation_id"),
    )
    op.create_index("ix_archive_audit_logs_project_id", "archive_audit_logs", ["project_id"])
    op.create_index("ix_archive_audit_logs_actor_id", "archive_audit_logs", ["actor_id"])
    op.create_index("ix_archive_audit_logs_resource_id", "archive_audit_logs", ["resource_id"])
    op.create_index("ix_archive_audit_logs_project_created_id", "archive_audit_logs", ["project_id", "created_at", "id"])
    op.create_index("ix_archive_audit_logs_actor_created", "archive_audit_logs", ["actor_id", "created_at"])


def downgrade() -> None:
    """仅供没有 V1 业务数据的本地开发库回退。"""
    op.drop_table("archive_audit_logs")
    op.drop_table("archive_operations")
    op.drop_table("checklist_links")
    op.drop_table("checklist_items")
    op.drop_table("field_evidences")
    op.drop_table("archive_field_values")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("archive_documents") as batch:
            batch.drop_constraint("fk_archive_documents_current_snapshot", type_="foreignkey")
    else:
        op.drop_constraint("fk_archive_documents_current_snapshot", "archive_documents", type_="foreignkey")
    op.drop_table("parsed_snapshots")
    op.drop_table("archive_documents")

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("documents") as batch:
            batch.drop_constraint("fk_documents_project_kb", type_="foreignkey")
            batch.drop_index("uq_documents_project_file_hash")
            batch.drop_column("project_id")
            batch.drop_index("ix_documents_file_hash")
            batch.drop_index("ix_documents_project_id")
            batch.drop_index("ix_documents_project_created_id")
            batch.alter_column("file_hash", new_column_name="content_hash", existing_type=sa.String(length=64))
            batch.create_index("ix_documents_content_hash", ["content_hash"])
    else:
        op.drop_constraint("fk_documents_project_kb", "documents", type_="foreignkey")
        op.drop_index("uq_documents_project_file_hash", table_name="documents")
        op.drop_index("ix_documents_project_created_id", table_name="documents")
        op.drop_index("ix_documents_project_id", table_name="documents")
        op.drop_index("ix_documents_file_hash", table_name="documents")
        op.drop_column("documents", "project_id")
        op.alter_column("documents", "file_hash", new_column_name="content_hash", existing_type=sa.String(length=64))
        op.create_index("ix_documents_content_hash", "documents", ["content_hash"])
    op.drop_table("projects")
