"""执行知识库范围内的向量检索、分数过滤和结果转换。"""

from dataclasses import dataclass
from uuid import UUID

from app.core.config import settings
from app.core.errors import AppError
from app.services.vector_service import get_vector_store


@dataclass(frozen=True)
class RetrievedChunk:
    """表示一个通过相似度阈值的内部检索结果。

    Attributes:
        chunk_id: Chunk 的稳定 SHA-256 标识。
        document_id: Chunk 所属文档的 UUID。
        document_name: 用于来源展示的原文件名。
        page: Chunk 所属的原始页码。
        content: Chunk 的完整正文。
        score: Milvus 返回的原始 COSINE 相似度。
    """

    chunk_id: str
    document_id: UUID
    document_name: str
    page: int
    content: str
    score: float


def build_retrieval_filter(user_id: UUID, kb_id: UUID) -> str:
    """构造限制用户和知识库范围的 Milvus 标量过滤表达式。

    Args:
        user_id: 当前已验证用户的 UUID。
        kb_id: 当前已通过所有权校验的知识库 UUID。

    Returns:
        同时包含 ``user_id`` 和 ``kb_id`` 的 Milvus 过滤表达式。
    """
    # 两个条件必须在 Milvus 搜索前生效，避免无权数据占用候选名额。
    return (
        f'user_id == "{user_id}" '
        f'and kb_id == "{kb_id}"'
    )


def retrieve_chunks(
    user_id: UUID,
    kb_id: UUID,
    question: str,
) -> list[RetrievedChunk]:
    """在指定用户和知识库范围内检索合格 Chunk。

    Args:
        user_id: 当前已验证用户的 UUID。
        kb_id: 当前已通过所有权校验的知识库 UUID。
        question: 已通过请求模型校验的自然语言问题。

    Returns:
        按相似度从高到低排列、最多 Top-N 个检索结果。

    Raises:
        AppError: Milvus 检索失败或返回数据缺少必要字段。
    """

    # 在搜索前限制用户和知识库，避免无权数据进入候选结果。
    retrieval_filter = build_retrieval_filter(
        user_id=user_id,
        kb_id=kb_id,
    )
    vector_store = get_vector_store()

    try:
        # LangChain 会先用 BGE 生成问题向量，再执行 COSINE Top-K 检索。
        search_results = vector_store.similarity_search_with_score(
            query=question,
            k=settings.retrieval_top_k,
            expr=retrieval_filter,
            param={
                "metric_type": "COSINE",
                "params": {},
            },
        )
    except AppError:
        # 保留下层已经定义好的安全业务错误。
        raise
    except Exception as exc:
        # 不把 Milvus 或 Embedding 的内部错误直接暴露给客户端。
        raise AppError(
            status_code=503,
            code="MILVUS_SEARCH_FAILED",
            message="知识库向量检索失败。",
        ) from exc

    qualified_chunks: list[RetrievedChunk] = []

    # 只转换达到最低相似度的候选结果。
    for document, raw_score in search_results:
        try:
            score = float(raw_score)
        except (TypeError, ValueError) as exc:
            raise AppError(
                status_code=500,
                code="MILVUS_RESULT_INVALID",
                message="Milvus 返回了无效的相似度分数。",
            ) from exc

        # 使用小于号排除低分结果，因此等于阈值时仍会保留。
        if score < settings.retrieval_score_threshold:
            continue

        try:
            metadata = document.metadata

            # page_content 是 Chunk 正文，其余引用信息来自 Milvus 元数据。
            retrieved_chunk = RetrievedChunk(
                chunk_id=str(metadata["chunk_id"]),
                document_id=UUID(str(metadata["document_id"])),
                document_name=str(metadata["document_name"]),
                page=int(metadata["page"]),
                content=document.page_content,
                score=score,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError(
                status_code=500,
                code="MILVUS_RESULT_INVALID",
                message="Milvus 检索结果缺少必要字段。",
            ) from exc

        qualified_chunks.append(retrieved_chunk)

    # 明确按照分数降序排列，不依赖向量库返回顺序。
    qualified_chunks.sort(
        key=lambda chunk: chunk.score,
        reverse=True,
    )

    # 结果不足 Top-N 时直接返回已有结果，不使用低分 Chunk 补足。
    return qualified_chunks[: settings.retrieval_top_n]
