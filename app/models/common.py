"""提供数据库模型共用的时间辅助函数。"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)
