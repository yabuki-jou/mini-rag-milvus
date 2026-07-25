"""定义用户和知识库接口的数据结构。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    """创建用户时允许客户端提交的字段。

    Attributes:
        name: 用户显示名称。
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)


class UserRead(BaseModel):
    """返回给客户端的用户信息。

    Attributes:
        id: 用户的全局唯一标识。
        name: 用户显示名称。
        created_at: 用户记录的创建时间。
        updated_at: 用户记录最后一次更新时间。
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseCreate(BaseModel):
    """创建知识库时允许客户端提交的字段。

    Attributes:
        name: 知识库显示名称。
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)


class KnowledgeBaseRead(BaseModel):
    """返回给客户端的知识库信息。

    Attributes:
        id: 知识库的全局唯一标识。
        owner_id: 知识库所有者的用户 ID。
        name: 知识库显示名称。
        created_at: 知识库记录的创建时间。
        updated_at: 知识库记录最后一次更新时间。
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
