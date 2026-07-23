"""管理 Milvus 连接、Chunk Collection、向量写入和精确删除。"""

from functools import lru_cache
from hashlib import sha256
from uuid import UUID

from langchain_milvus import Milvus
from pymilvus import DataType, MilvusClient

from app.core.config import settings
from app.core.errors import AppError
from app.services.embedding_service import EmbeddedChunk
from app.services.model_service import get_embeddings


@lru_cache
def get_milvus_client() -> MilvusClient:
    """创建并缓存连接现有 Milvus 服务的客户端。"""
    # 使用统一连接参数，避免各服务分别解析 URI 和认证信息。
    try:
        return MilvusClient(**settings.milvus_connection_args)
    except Exception as exc:
        raise AppError(
            status_code=503,
            code="MILVUS_UNAVAILABLE",
            message=f"无法连接 Milvus：{exc}",
        ) from exc


def list_collections() -> list[str]:
    """返回 Collection 名称，用只读请求验证 Milvus 连接。"""
    # 健康检查只执行只读请求，不隐式创建 Collection。
    client = get_milvus_client()
    try:
        return list(client.list_collections())
    except Exception as exc:
        raise AppError(
            status_code=503,
            code="MILVUS_UNAVAILABLE",
            message=f"无法连接 Milvus：{exc}",
        ) from exc


def ensure_chunk_collection() -> str:
    """确保 Chunk Collection 及其 COSINE 向量索引已经创建。

    Returns:
        当前项目使用的 Milvus Collection 名称。

    Raises:
        AppError: Milvus 不可用或 Collection 初始化失败。
    """
    # 获取缓存的 Milvus 客户端，并确定当前项目使用的 Collection。
    client = get_milvus_client()
    collection_name = settings.milvus_collection

    try:
        # Collection 已存在时直接复用，避免重复创建和破坏已有向量。
        if client.has_collection(collection_name=collection_name):
            return collection_name

        # 使用固定 Schema 禁止未声明字段，确保入库数据结构稳定。
        schema = MilvusClient.create_schema(
            auto_id=False,
            enable_dynamic_field=False,
            description="Mini RAG document chunks",
        )

        # 添加 Chunk 主键、数据隔离、引用位置和正文相关字段。
        schema.add_field(
            field_name="chunk_id",
            datatype=DataType.VARCHAR,
            is_primary=True,
            max_length=64,
        )
        schema.add_field(
            field_name="user_id",
            datatype=DataType.VARCHAR,
            max_length=36,
        )
        schema.add_field(
            field_name="kb_id",
            datatype=DataType.VARCHAR,
            max_length=36,
        )
        schema.add_field(
            field_name="document_id",
            datatype=DataType.VARCHAR,
            max_length=36,
        )
        schema.add_field(
            field_name="document_name",
            datatype=DataType.VARCHAR,
            max_length=1024,
        )
        schema.add_field(field_name="page", datatype=DataType.INT64)
        schema.add_field(field_name="start_index", datatype=DataType.INT64)
        schema.add_field(field_name="chunk_index", datatype=DataType.INT64)
        schema.add_field(
            field_name="content",
            datatype=DataType.VARCHAR,
            max_length=8192,
        )
        schema.add_field(
            field_name="content_hash",
            datatype=DataType.VARCHAR,
            max_length=64,
        )
        schema.add_field(
            field_name="embedding",
            datatype=DataType.FLOAT_VECTOR,
            dim=settings.embedding_dimension,
        )

        # 为 Embedding 创建自动选择实现的 COSINE 向量索引。
        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="AUTOINDEX",
            metric_type="COSINE",
        )

        # 创建 Collection；健康检查不会调用本函数，因此仍保持只读。
        client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params,
        )
        return collection_name
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            status_code=503,
            code="MILVUS_COLLECTION_INIT_FAILED",
            message="Milvus Collection 初始化失败。",
        ) from exc


@lru_cache
def get_vector_store() -> Milvus:
    """创建并缓存与固定 Chunk Schema 匹配的 LangChain 向量库。

    Returns:
        可用于后续向量写入和相似度检索的 Milvus 包装器。
    """
    # 确保固定 Schema 和 COSINE 索引已经存在。
    ensure_chunk_collection()

    # 获取缓存的 BGE 模型，供阶段四将用户问题转换成查询向量。
    hugging_face_embeddings = get_embeddings()

    # 创建与自定义主键、正文和向量字段名称匹配的包装器。
    milvus = Milvus(
        embedding_function=hugging_face_embeddings,
        collection_name=settings.milvus_collection,
        connection_args=settings.milvus_connection_args,
        auto_id=False,
        primary_field="chunk_id",
        text_field="content",
        vector_field="embedding",
        enable_dynamic_field=False,
        drop_old=False,
    )

    # @lru_cache 会让后续调用复用当前包装器，而不是重复初始化。
    return milvus


def insert_chunks(
    user_id: UUID,
    kb_id: UUID,
    document_id: UUID,
    document_name: str,
    embedded_chunks: list[EmbeddedChunk],
) -> int:
    """将已经生成向量的 Chunk 及其隔离、引用元数据写入 Milvus。

    Args:
        user_id: 文档所属用户的 UUID。
        kb_id: 文档所属知识库的 UUID。
        document_id: 当前文档的 UUID。
        document_name: 用于来源引用的原文件名。
        embedded_chunks: 已生成稳定 ID 和向量的文本块。

    Returns:
        Milvus 确认写入的 Chunk 数量。

    Raises:
        AppError: Milvus 写入失败或返回的主键数量不正确。
    """
    # 没有待写入 Chunk 时直接返回，避免调用 Milvus 空插入。
    if not embedded_chunks:
        return 0

    # 按相同顺序拆分主键、正文、向量和内容哈希，避免字段错位。
    texts = [embedded_chunk.content for embedded_chunk in embedded_chunks]
    embeddings = [
        embedded_chunk.embedding
        for embedded_chunk in embedded_chunks
    ]
    ids = [embedded_chunk.chunk_id for embedded_chunk in embedded_chunks]

    # 为 Chunk 准备用户隔离、文档归属、引用位置和内容哈希元数据。
    metadatas = [
        {
            "user_id": str(user_id),
            "kb_id": str(kb_id),
            "document_id": str(document_id),
            "document_name": document_name,
            "page": chunk.page,
            "start_index": chunk.start_index,
            "chunk_index": chunk.chunk_index,
            "content_hash": sha256(
                chunk.content.encode("utf-8")
            ).hexdigest(),
        }
        for chunk in embedded_chunks
    ]

    # 获取缓存的 LangChain Milvus 包装器，复用已有连接和 Schema。
    vector_store = get_vector_store()

    try:
        # 使用已经生成的向量批量写入，避免再次执行 Embedding。
        pks = vector_store.add_embeddings(
            texts=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

        # 提交新写入的 Segment，确保返回前其他客户端已经可以检索。
        get_milvus_client().flush(
            collection_name=settings.milvus_collection,
        )
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            status_code=503,
            code="MILVUS_INSERT_FAILED",
            message="Chunk 写入 Milvus 失败。",
        ) from exc

    # 校验返回主键数量，确认每个 Chunk 都得到了写入结果。
    if len(pks) != len(embedded_chunks):
        raise AppError(
            status_code=500,
            code="MILVUS_INSERT_RESULT_INVALID",
            message="Milvus 返回的写入数量不正确。",
        )

    # 返回实际写入数量，供调用方更新 SQLite 中的 chunk_count。
    return len(pks)


def delete_document_chunks(
    user_id: UUID,
    kb_id: UUID,
    document_id: UUID,
) -> int:
    """按用户、知识库和文档范围删除全部旧 Chunk。

    Args:
        user_id: 文档所属用户的 UUID。
        kb_id: 文档所属知识库的 UUID。
        document_id: 需要清理旧 Chunk 的文档 UUID。

    Returns:
        Milvus 确认删除的 Chunk 数量；没有匹配数据时返回 0。

    Raises:
        AppError: Milvus Collection 初始化、删除或提交失败。
    """
    # 确保目标 Collection 存在，支持文档第一次解析。
    ensure_chunk_collection()
    milvus_client = get_milvus_client()

    # 使用用户、知识库和文档三个字段构造精确删除范围。
    delete_filter = (
        f'user_id == "{user_id}" '
        f'and kb_id == "{kb_id}" '
        f'and document_id == "{document_id}"'
    )

    try:
        # 删除该文档的全部旧 Chunk。
        delete_result = milvus_client.delete(
            collection_name=settings.milvus_collection,
            filter=delete_filter,
        )
        # 提交删除操作，确保后续重新写入可以看到最新结果。
        milvus_client.flush(collection_name=settings.milvus_collection)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            status_code=503,
            code="MILVUS_DELETE_FAILED",
            message="文档旧 Chunk 删除失败。",
        ) from exc

    # 返回实际删除数量；没有旧 Chunk 时应返回 0。
    return int(delete_result.get("delete_count", 0))
