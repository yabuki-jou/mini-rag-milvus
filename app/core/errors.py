"""定义应用业务异常，并统一 FastAPI 的错误响应。"""

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


class AppError(Exception):
    """可安全返回给客户端的预期业务错误。

    Attributes:
        status_code: HTTP 响应状态码。
        code: 供客户端判断错误类型的稳定代码。
        message: 可展示给客户端的错误信息。
    """

    def __init__(self, status_code: int, code: str, message: str):
        """初始化业务错误。

        Args:
            status_code: HTTP 响应状态码。
            code: 供客户端判断错误类型的稳定代码。
            message: 可展示给客户端的错误信息。
        """
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    """为 FastAPI 应用注册统一的异常处理器。"""

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "请求参数校验失败。",
                    "details": jsonable_encoder(exc.errors()),
                }
            },
        )

    @app.exception_handler(Exception)
    async def exception(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled application error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "服务器内部错误，请查看日志。",
                }
            },
        )

