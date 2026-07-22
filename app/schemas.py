"""定义阶段一健康检查使用的响应结构。"""

from pydantic import BaseModel


class HealthComponent(BaseModel):
    """一个基础组件的健康状态。

    Attributes:
        status: 单个组件的 ``ok`` 或 ``error`` 状态。
        detail: 维度、Collection 数量或错误摘要。
    """

    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    """应用及其依赖组件的整体健康状态。

    Attributes:
        status: 全部正常时为 ``ok``，否则为 ``degraded``。
        components: API、数据库、Milvus 和 Embedding 的独立状态。
    """

    status: str
    components: dict[str, HealthComponent]
