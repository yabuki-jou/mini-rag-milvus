"""定义用户和知识库数据库实体。"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.models.common import utc_now


class User(SQLModel, table=True):
    """表示可以创建和访问知识库的基础用户。

    Attributes:
        id: 用户的全局唯一标识。
        name: 用户显示名称。
        created_at: 用户记录的 UTC 创建时间。
        updated_at: 用户记录最后一次更新的 UTC 时间。
    """

    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(min_length=1, max_length=100, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class KnowledgeBase(SQLModel, table=True):
    """表示由一个用户拥有的独立知识库。

    Attributes:
        id: 知识库的全局唯一标识。
        owner_id: 知识库所有者的用户 ID。
        name: 知识库显示名称。
        created_at: 知识库记录的 UTC 创建时间。
        updated_at: 知识库记录最后一次更新的 UTC 时间。
    """

    __tablename__ = "knowledge_bases"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_id: UUID = Field(foreign_key="users.id", index=True)
    name: str = Field(min_length=1, max_length=100, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
