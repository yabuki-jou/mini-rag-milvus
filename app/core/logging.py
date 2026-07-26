"""配置应用日志，并为每个 HTTP 请求注入稳定的请求 ID。"""

import logging
from contextvars import ContextVar
from re import fullmatch
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")
_REQUEST_ID_PATTERN = r"[A-Za-z0-9._-]{1,128}"

logger = logging.getLogger(__name__)


def get_request_id() -> str:
    """返回当前请求 ID；非 HTTP 调用返回 ``-``。"""
    return _REQUEST_ID.get()


class RequestIdFilter(logging.Filter):
    """把当前请求 ID 添加到每一条应用日志记录。"""

    def filter(self, record: logging.LogRecord) -> bool:
        """向日志记录写入格式化器需要的 ``request_id`` 字段。

        Args:
            record: Python 日志系统正在处理的记录。

        Returns:
            始终返回 ``True``，表示保留该日志记录。
        """
        record.request_id = get_request_id()
        return True


def configure_logging() -> None:
    """为应用安装一次包含请求 ID 的控制台日志处理器。"""
    root_logger = logging.getLogger()

    # 开发环境默认记录 INFO；重复导入应用时不重复添加处理器。
    if any(
        getattr(handler, "_mini_rag_handler", False)
        for handler in root_logger.handlers
    ):
        return

    handler = logging.StreamHandler()
    handler._mini_rag_handler = True  # type: ignore[attr-defined]
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s "
            "request_id=%(request_id)s %(message)s"
        )
    )
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


def _resolve_request_id(request: Request) -> str:
    """读取安全的客户端请求 ID，缺失或无效时生成新 ID。

    Args:
        request: 当前 FastAPI HTTP 请求。

    Returns:
        可安全写入响应头和日志的请求 ID。
    """
    candidate = request.headers.get("X-Request-ID", "").strip()
    if fullmatch(_REQUEST_ID_PATTERN, candidate):
        return candidate
    return str(uuid4())


class RequestContextMiddleware(BaseHTTPMiddleware):
    """为每个请求记录请求 ID、状态码和总耗时。"""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """建立请求日志上下文，并调用下一层 ASGI 应用。

        Args:
            request: 当前 HTTP 请求。
            call_next: 执行后续中间件、路由和异常处理器的函数。

        Returns:
            带 ``X-Request-ID`` 响应头的 HTTP 响应。

        Raises:
            Exception: 记录未处理异常后继续交给外层处理。
        """
        request_id = _resolve_request_id(request)
        request.state.request_id = request_id
        context_token = _REQUEST_ID.set(request_id)
        started_at = perf_counter()

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "http_request method=%s path=%s status=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                response.status_code,
                (perf_counter() - started_at) * 1000,
            )
            return response
        except Exception:
            logger.exception(
                "http_request_failed method=%s path=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                (perf_counter() - started_at) * 1000,
            )
            raise
        finally:
            # ContextVar 必须恢复，防止工作线程复用时串用上一个请求 ID。
            _REQUEST_ID.reset(context_token)
