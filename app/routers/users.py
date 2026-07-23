"""提供用户相关的 API 路由。"""

from fastapi import APIRouter, status

from app.dependencies import SessionDep
from app.models import User
from app.schemas import UserCreate, UserRead


router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, session: SessionDep) -> User:
    """创建一个基础用户。"""
    user = User(name=payload.name)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
