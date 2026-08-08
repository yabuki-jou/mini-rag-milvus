"""通过 Uvicorn 启动 Mini RAG FastAPI 应用。"""

import uvicorn

from app.core.config import settings


def main() -> None:
    """启动本地开发服务器。"""
    # 使用模块导入字符串，使开发环境可以启用代码自动重载。
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=settings.app_env == "development",
    )


if __name__ == "__main__":
    # 直接运行本文件时启动服务；被测试代码导入时不会自动启动。
    main()
