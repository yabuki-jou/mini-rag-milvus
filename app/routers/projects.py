"""提供 FR-030 项目管理 HTTP 接口。"""

from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.dependencies import CurrentUserDep, ProjectContextDep, SessionDep
from app.schemas import ProjectCreate, ProjectPageRead, ProjectRead, ProjectUpdate
from app.services.project_service import (
    create_project,
    delete_empty_project,
    list_projects,
    read_project,
    update_project,
)


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project_endpoint(
    payload: ProjectCreate,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> ProjectRead:
    """创建当前用户的项目和服务端管理的独立知识库范围。"""
    return create_project(current_user=current_user, payload=payload, session=session)


@router.get("", response_model=ProjectPageRead)
def list_projects_endpoint(
    current_user: CurrentUserDep,
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ProjectPageRead:
    """按稳定分页顺序列出当前用户项目。"""
    return list_projects(
        current_user=current_user,
        page=page,
        page_size=page_size,
        session=session,
    )


@router.get("/{project_id}", response_model=ProjectRead)
def get_project_endpoint(
    project_id: UUID,
    _: ProjectContextDep,
    session: SessionDep,
) -> ProjectRead:
    """读取已通过项目所有权校验的项目详情。"""
    return read_project(project_id=project_id, session=session)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project_endpoint(
    project_id: UUID,
    payload: ProjectUpdate,
    _: ProjectContextDep,
    session: SessionDep,
) -> ProjectRead:
    """以客户端版本号为前提修改项目名称或说明。"""
    return update_project(project_id=project_id, payload=payload, session=session)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_endpoint(
    project_id: UUID,
    _: ProjectContextDep,
    session: SessionDep,
) -> Response:
    """删除无文档项目及项目级清单，保留其内部知识库记录。"""
    delete_empty_project(project_id=project_id, session=session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
