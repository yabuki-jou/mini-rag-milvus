"""提供可选 Pixie 评测观测，生产环境未安装时保持无操作。"""

from typing import Any, Literal, TypeVar


T = TypeVar("T")


def eval_wrap(
    data: T,
    *,
    purpose: Literal["input", "output", "state"],
    name: str,
    description: str,
) -> T:
    """调用 Pixie wrap；未安装评测依赖时原样返回数据。

    Args:
        data: 需要注入或观测的值、函数。
        purpose: 输入依赖、最终输出或内部状态。
        name: 全项目唯一的评测数据点名称。
        description: 数据点的业务含义。

    Returns:
        Pixie 处理后的同类型对象；普通运行时返回原对象。
    """
    try:
        import pixie
    except ImportError:
        return data
    return pixie.wrap(
        data,
        purpose=purpose,
        name=name,
        description=description,
    )
