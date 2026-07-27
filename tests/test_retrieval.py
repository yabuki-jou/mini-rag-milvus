"""验证检索阈值、数据隔离、结果转换和安全异常。"""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest

from app.core.config import settings
from app.core.errors import AppError
from app.routers import retrieval as retrieval_router
from app.schemas import RetrievalTestRequest
from app.services import retrieval_service
from app.services.retrieval_service import RetrievedChunk


def make_document(
    *,
    chunk_id: str,
    document_id: UUID,
    page: int,
    content: str,
) -> SimpleNamespace:
    """构造与 LangChain Document 结构一致的轻量测试对象。"""
    return SimpleNamespace(
        page_content=content,
        metadata={
            "chunk_id": chunk_id,
            "document_id": str(document_id),
            "document_name": "policy.pdf",
            "page": page,
        },
    )


def test_build_retrieval_filter_contains_user_and_kb() -> None:
    """过滤表达式必须同时限制用户和知识库。"""
    user_id = uuid4()
    kb_id = uuid4()

    result = retrieval_service.build_retrieval_filter(user_id, kb_id)

    assert result == (
        f'user_id == "{user_id}" '
        f'and kb_id == "{kb_id}"'
    )


def test_retrieve_chunks_applies_threshold_order_and_top_n(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """等于阈值的结果应保留，低分应过滤，最终按分数截取。"""
    user_id = uuid4()
    kb_id = uuid4()
    document_id = uuid4()
    vector_store = Mock()
    vector_store.similarity_search_with_score.return_value = [
        (
            make_document(
                chunk_id="a" * 64,
                document_id=document_id,
                page=1,
                content="阈值边界",
            ),
            0.50,
        ),
        (
            make_document(
                chunk_id="b" * 64,
                document_id=document_id,
                page=2,
                content="最高分",
            ),
            0.90,
        ),
        (
            make_document(
                chunk_id="c" * 64,
                document_id=document_id,
                page=3,
                content="低于阈值",
            ),
            0.49,
        ),
        (
            make_document(
                chunk_id="d" * 64,
                document_id=document_id,
                page=4,
                content="第二名",
            ),
            0.80,
        ),
    ]

    # 固定测试参数，避免本机 .env 改变测试预期。
    monkeypatch.setattr(settings, "retrieval_top_k", 10)
    monkeypatch.setattr(settings, "retrieval_top_n", 2)
    monkeypatch.setattr(settings, "retrieval_score_threshold", 0.50)
    monkeypatch.setattr(
        retrieval_service,
        "get_vector_store",
        lambda: vector_store,
    )

    results = retrieval_service.retrieve_chunks(
        user_id=user_id,
        kb_id=kb_id,
        question="测试问题",
    )

    assert [result.score for result in results] == [0.90, 0.80]
    call_kwargs = vector_store.similarity_search_with_score.call_args.kwargs
    assert call_kwargs["k"] == 10
    assert f'user_id == "{user_id}"' in call_kwargs["expr"]
    assert f'kb_id == "{kb_id}"' in call_kwargs["expr"]


def test_retrieve_chunks_keeps_score_equal_to_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """相似度等于阈值时必须保留该 Chunk。"""
    document_id = uuid4()
    vector_store = Mock()
    vector_store.similarity_search_with_score.return_value = [
        (
            make_document(
                chunk_id="a" * 64,
                document_id=document_id,
                page=1,
                content="边界结果",
            ),
            0.50,
        )
    ]
    monkeypatch.setattr(settings, "retrieval_score_threshold", 0.50)
    monkeypatch.setattr(settings, "retrieval_top_n", 3)
    monkeypatch.setattr(
        retrieval_service,
        "get_vector_store",
        lambda: vector_store,
    )

    results = retrieval_service.retrieve_chunks(
        user_id=uuid4(),
        kb_id=uuid4(),
        question="边界测试",
    )

    assert len(results) == 1
    assert results[0].score == 0.50


def test_retrieve_chunks_returns_empty_list_for_low_scores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """没有候选达到阈值时应返回空列表而不是补足 Top-N。"""
    document_id = uuid4()
    vector_store = Mock()
    vector_store.similarity_search_with_score.return_value = [
        (
            make_document(
                chunk_id="a" * 64,
                document_id=document_id,
                page=1,
                content="无关结果",
            ),
            0.20,
        )
    ]
    monkeypatch.setattr(settings, "retrieval_score_threshold", 0.50)
    monkeypatch.setattr(
        retrieval_service,
        "get_vector_store",
        lambda: vector_store,
    )

    results = retrieval_service.retrieve_chunks(
        user_id=uuid4(),
        kb_id=uuid4(),
        question="无答案问题",
    )

    assert results == []


def test_retrieve_chunks_converts_search_failure_to_safe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """底层检索异常应转换为不泄露内部细节的 AppError。"""
    vector_store = Mock()
    vector_store.similarity_search_with_score.side_effect = RuntimeError(
        "internal secret"
    )
    monkeypatch.setattr(
        retrieval_service,
        "get_vector_store",
        lambda: vector_store,
    )

    with pytest.raises(AppError) as exc_info:
        retrieval_service.retrieve_chunks(
            user_id=uuid4(),
            kb_id=uuid4(),
            question="异常测试",
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "MILVUS_SEARCH_FAILED"
    assert "internal secret" not in exc_info.value.message


def test_retrieval_endpoint_converts_internal_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """路由应把内部结果转换为包含问题和来源的响应模型。"""
    user_id = uuid4()
    kb_id = uuid4()
    document_id = uuid4()
    internal_result = RetrievedChunk(
        chunk_id="a" * 64,
        document_id=document_id,
        document_name="policy.pdf",
        page=1,
        content="制度正文",
        score=0.75,
    )
    monkeypatch.setattr(
        retrieval_router,
        "retrieve_chunks",
        lambda **_: [internal_result],
    )

    response = retrieval_router.retrieval_test_endpoint(
        current_user=SimpleNamespace(id=user_id),
        knowledge_base=SimpleNamespace(id=kb_id),
        kb_id=kb_id,
        payload=RetrievalTestRequest(question="  制度问题  "),
    )

    assert response.question == "制度问题"
    assert len(response.results) == 1
    assert response.results[0].document_id == document_id
    assert response.results[0].score == 0.75
