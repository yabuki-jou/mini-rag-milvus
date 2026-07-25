"""统一导出 FastAPI 依赖，保持路由层的导入入口稳定。"""

from app.dependencies.auth import CurrentUserDep, get_current_user
from app.dependencies.database import SessionDep
from app.dependencies.resources import (
    OwnedDocumentDep,
    OwnedKnowledgeBaseDep,
    get_document_in_knowledge_base,
    get_owned_knowledge_base,
)


__all__ = [
    "CurrentUserDep",
    "OwnedDocumentDep",
    "OwnedKnowledgeBaseDep",
    "SessionDep",
    "get_current_user",
    "get_document_in_knowledge_base",
    "get_owned_knowledge_base",
]
