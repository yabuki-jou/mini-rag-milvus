"""集中管理应用配置，并把相对路径统一解析到项目根目录。"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# 所有相对路径都以项目根目录为基准，不受终端启动位置影响。
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """从环境变量或项目根目录的 ``.env`` 文件读取运行参数。

    Attributes:
        app_name: Swagger 标题和应用名称。
        app_env: 当前运行环境，例如 ``development`` 或 ``production``。
        database_url: SQLModel 数据库连接地址。
        file_storage_dir: 上传原文件的本地存储目录。
        milvus_uri: Milvus 服务地址。
        milvus_token: Milvus 认证令牌。
        milvus_collection: 保存所有知识库 Chunk 的 Collection 名称。
        embedding_model_path: 本地 BGE 模型目录。
        embedding_device: Embedding 运行设备。
        embedding_dimension: Embedding 模型输出的向量维度。
        chunk_size: 每个 Chunk 的目标字符数。
        chunk_overlap: 相邻 Chunk 重复保留的字符数。
        deepseek_api_key: DeepSeek API 密钥。
        deepseek_base_url: DeepSeek 的 OpenAI 兼容接口地址。
        deepseek_model: 生成回答所使用的模型名称。
    """

    # 从项目根目录读取 .env；忽略暂未使用的变量，且变量名不区分大小写。
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用、SQLite 和原文件存储配置。
    app_name: str = "Mini RAG Milvus"
    app_env: str = "development"
    database_url: str = "sqlite:///./data/handwrite.db"
    file_storage_dir: Path = Path("./data/files")

    # Milvus 连接和单一 Chunk Collection 配置。
    milvus_uri: str = "http://localhost:19530"
    milvus_token: SecretStr | None = SecretStr("root:Milvus")
    milvus_collection: str = "mini_rag_handwrite_chunks"

    # 本地 Embedding 模型及其输出维度配置。
    embedding_model_path: Path = Path(
        "../py-doc-deepseek-server/models/bge-small-zh-v1.5"
    )
    embedding_device: str = "cpu"
    embedding_dimension: int = Field(default=512, gt=0)

    # 递归字符切分器使用的目标大小和重叠字符数。
    chunk_size: int = Field(default=800, gt=0)
    chunk_overlap: int = Field(default=150, ge=0)

    # 阶段五调用 DeepSeek 时使用的生成模型配置。
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    def resolve_path(self, path: Path) -> Path:
        """将配置路径解析为不依赖当前工作目录的绝对路径。

        Args:
            path: 环境变量或默认配置中读取到的路径。

        Returns:
            绝对路径；相对路径以项目根目录为基准。
        """
        # 绝对路径直接规范化；相对路径统一拼接项目根目录。
        if path.is_absolute():
            return path.resolve()
        return (PROJECT_ROOT / path).resolve()

    @property
    def embedding_path(self) -> Path:
        """本地 Embedding 模型目录的绝对路径。"""
        return self.resolve_path(self.embedding_model_path)

    @property
    def file_storage_path(self) -> Path:
        """上传原文件目录的绝对路径。"""
        return self.resolve_path(self.file_storage_dir)

    @property
    def milvus_connection_args(self) -> dict[str, str]:
        """构造 LangChain Milvus 和 PyMilvus 共用的连接参数。"""
        # token 仅在确实配置时传入，并在取值前始终由 SecretStr 保存。
        args: dict[str, str] = {"uri": self.milvus_uri}
        if self.milvus_token is not None:
            args["token"] = self.milvus_token.get_secret_value()
        return args


@lru_cache
def get_settings() -> Settings:
    """返回进程内唯一的应用配置对象。"""
    return Settings()


# 模块内共享同一配置对象，避免各服务重复解析 .env。
settings = get_settings()
