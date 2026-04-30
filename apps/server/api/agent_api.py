"""
Agent API endpoints for external AI agents (e.g., OpenClaw).

Provides REST API endpoints for programmatic access using X-Agent-API-Key authentication.
All endpoints require valid API key with appropriate scopes.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import ClassVar, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import load_only
from sqlmodel import col, select

from agent.context.assembler import ContextAssembler
from api.agent_dependencies import AgentAuthContext, require_project_access, require_scope
from config.datetime_utils import utcnow
from core.error_codes import ErrorCode
from core.error_handler import APIException
from database import create_session
from middleware.rate_limit import require_rate_limit
from models import File, Project
from services.agent_auth_service import verify_project_access
from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["Agent API"])


# ==================== Request/Response Models ====================


class ProjectResponse(BaseModel):
    """Response model for a project."""

    id: str
    name: str
    description: str | None
    project_type: str | None
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileCreate(BaseModel):
    """Request body for creating a file."""

    title: str = Field(..., description="File title")
    file_type: str = Field(default="draft", description="File type (outline, draft, character, lore, etc.)")
    content: str = Field(default="", description="File content")
    parent_id: str | None = Field(default=None, description="Parent folder ID")
    metadata: dict | None = Field(default=None, description="Additional metadata")


class FileUpdate(BaseModel):
    """Request body for updating a file."""

    title: str | None = Field(default=None, description="New title")
    content: str | None = Field(default=None, description="New content")


class FileResponse(BaseModel):
    """Response model for a file."""

    id: str
    project_id: str
    title: str
    content: str
    file_type: str
    parent_id: str | None
    order: int
    file_metadata: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    # All valid fields for ?fields= parameter
    VALID_FIELDS: ClassVar[set[str]] = {
        "id", "project_id", "title", "content", "file_type",
        "parent_id", "order", "file_metadata", "created_at", "updated_at",
    }

    def to_filtered_dict(self, fields: set[str] | None = None) -> dict:
        """Return dict with only requested fields. None = all fields."""
        if fields is None:
            return self.model_dump()
        return {k: v for k, v in self.model_dump().items() if k in fields}


class _FilteredFileResponse(BaseModel):
    """Dynamic response for filtered file fields."""
    model_config = ConfigDict(extra="allow")


class FileListResponse(BaseModel):
    """Paginated response for file listing."""

    files: list[_FilteredFileResponse]
    total: int
    limit: int
    offset: int


class ProjectCreate(BaseModel):
    """Request body for creating a project."""

    name: str = Field(..., min_length=1, max_length=100, description="Project name")
    description: str | None = Field(default=None, max_length=500, description="Project description")
    project_type: Literal["novel", "short", "screenplay"] = Field(default="novel", description="Project type: novel, short, screenplay")


class ProjectUpdate(BaseModel):
    """Request body for updating a project."""

    name: str | None = Field(default=None, min_length=1, max_length=100, description="Project name")
    description: str | None = Field(default=None, max_length=500, description="Project description")


# ==================== Project Endpoints ====================


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    _rate_limit: int = Depends(require_rate_limit("agent_read", 2000, 3600)),
    context: AgentAuthContext = Depends(require_scope("read")),
):
    """
    Get all projects accessible by the API key.

    Requires scope: read
    """
    session, user_id, api_key = context

    # Get all projects owned by the user
    stmt = select(Project).where(
        Project.owner_id == user_id,
        Project.is_deleted.is_(False),
    )
    # Filter by API key project access if restricted
    if api_key.project_ids is not None:
        if not api_key.project_ids:
            projects: list[Project] = []
        else:
            stmt = stmt.where(Project.id.in_(api_key.project_ids))
            projects = session.exec(stmt).all()
    else:
        projects = session.exec(stmt).all()

    log_with_context(
        logger,
        logging.INFO,
        "Agent API: Listed projects",
        user_id=user_id,
        api_key_id=api_key.id,
        project_count=len(projects),
    )

    return projects


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    _rate_limit: int = Depends(require_rate_limit("agent_read", 2000, 3600)),
    context: AgentAuthContext = Depends(require_project_access("read")),
):
    """
    Get project details.

    Requires scope: read
    Requires project access
    """
    session, user_id, api_key = context

    project = session.get(Project, project_id)
    if not project or project.is_deleted:
        raise APIException(
            error_code=ErrorCode.PROJECT_NOT_FOUND,
            status_code=404,
        )

    return project


@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    _rate_limit: int = Depends(require_rate_limit("agent_write", 1000, 3600)),
    context: AgentAuthContext = Depends(require_scope("write")),
):
    """
    Create a new project.

    Requires scope: write
    """
    session, user_id, api_key = context

    project = Project(
        name=project_data.name,
        description=project_data.description,
        project_type=project_data.project_type,
        owner_id=user_id,
    )
    session.add(project)
    session.commit()
    session.refresh(project)

    log_with_context(
        logger,
        logging.INFO,
        "Agent API: Created project",
        user_id=user_id,
        api_key_id=api_key.id,
        project_id=project.id,
    )

    return project


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    _rate_limit: int = Depends(require_rate_limit("agent_write", 1000, 3600)),
    context: AgentAuthContext = Depends(require_project_access("write")),
):
    """
    Update project details.

    Requires scope: write
    Requires project access
    """
    session, user_id, api_key = context

    project = session.get(Project, project_id)
    if not project or project.is_deleted:
        raise APIException(
            error_code=ErrorCode.PROJECT_NOT_FOUND,
            status_code=404,
        )

    if project_data.name is not None:
        project.name = project_data.name
    if project_data.description is not None:
        project.description = project_data.description

    project.updated_at = utcnow()
    session.commit()
    session.refresh(project)

    log_with_context(
        logger,
        logging.INFO,
        "Agent API: Updated project",
        user_id=user_id,
        api_key_id=api_key.id,
        project_id=project_id,
    )

    return project


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    _rate_limit: int = Depends(require_rate_limit("agent_write", 1000, 3600)),
    context: AgentAuthContext = Depends(require_project_access("write")),
):
    """
    Delete a project (soft delete).

    Requires scope: write
    Requires project access
    """
    session, user_id, api_key = context

    project = session.get(Project, project_id)
    if not project or project.is_deleted:
        raise APIException(
            error_code=ErrorCode.PROJECT_NOT_FOUND,
            status_code=404,
        )

    project.is_deleted = True
    project.deleted_at = utcnow()
    session.commit()

    log_with_context(
        logger,
        logging.INFO,
        "Agent API: Deleted project",
        user_id=user_id,
        api_key_id=api_key.id,
        project_id=project_id,
    )

    return {"message": "Project deleted successfully"}


# ==================== File Endpoints ====================


@router.get("/projects/{project_id}/files", response_model=FileListResponse)
async def list_files(
    project_id: str,
    file_type: str | None = Query(None, description="Filter by file type"),
    parent_id: str | None = Query(None, description="Filter by parent ID"),
    fields: str | None = Query(None, description="Comma-separated fields to return (e.g. 'id,title,content')"),
    limit: int = Query(50, ge=1, le=200, description="Max results per page"),
    offset: int = Query(0, ge=0, description="Results offset"),
    _rate_limit: int = Depends(require_rate_limit("agent_read", 2000, 3600)),
    context: AgentAuthContext = Depends(require_project_access("read")),
):
    """
    Get files in a project (paginated).

    Requires scope: read
    Requires project access

    Query parameters:
    - file_type: Filter by file type (outline, draft, character, lore, etc.)
    - parent_id: Filter by parent folder ID
    - fields: Comma-separated fields to return (omit for all fields)
    - limit: Max results (1-200, default 50)
    - offset: Pagination offset (default 0)
    """
    session, user_id, api_key = context

    # Parse requested fields
    requested_fields = None
    if fields:
        requested_fields = {f.strip() for f in fields.split(",")}
        requested_fields &= FileResponse.VALID_FIELDS

    # Build column list for load_only based on requested fields
    include_content = requested_fields is None or "content" in requested_fields
    columns = [
        File.id,
        File.project_id,
        File.title,
        File.file_type,
        File.parent_id,
        File.order,
        File.file_metadata,
        File.created_at,
        File.updated_at,
    ]
    if include_content:
        columns.append(File.content)

    # Count query (no pagination, SQL COUNT only)
    count_stmt = select(func.count(File.id)).where(
        File.project_id == project_id,
        File.is_deleted.is_(False),
    )
    if file_type:
        count_stmt = count_stmt.where(File.file_type == file_type)
    if parent_id is not None:
        count_stmt = count_stmt.where(File.parent_id == parent_id)

    total = session.exec(count_stmt).one()

    # Data query with pagination
    query = (
        select(File)
        .options(load_only(*columns))
        .where(
            File.project_id == project_id,
            File.is_deleted.is_(False),
        )
    )

    if file_type:
        query = query.where(File.file_type == file_type)

    if parent_id is not None:
        query = query.where(File.parent_id == parent_id)

    query = query.order_by(File.order.asc(), col(File.created_at).desc())
    query = query.offset(offset).limit(limit)

    files = session.exec(query).all()

    file_responses = [FileResponse.model_validate(f).to_filtered_dict(requested_fields) for f in files]

    log_with_context(
        logger,
        logging.INFO,
        "Agent API: Listed files",
        user_id=user_id,
        api_key_id=api_key.id,
        project_id=project_id,
        file_count=len(file_responses),
        total=total,
        file_type_filter=file_type,
    )

    return FileListResponse(
        files=file_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/projects/{project_id}/files", response_model=FileResponse)
async def create_file(
    project_id: str,
    file_data: FileCreate,
    background_tasks: BackgroundTasks,
    _rate_limit: int = Depends(require_rate_limit("agent_write", 1000, 3600)),
    context: AgentAuthContext = Depends(require_project_access("write")),
):
    """
    Create a new file in a project.

    Requires scope: write
    Requires project access
    """
    session, user_id, api_key = context

    # Validate parent_id if provided
    if file_data.parent_id:
        parent = session.get(File, file_data.parent_id)
        if not parent or parent.is_deleted or parent.project_id != project_id:
            raise APIException(
                error_code=ErrorCode.FILE_NOT_FOUND,
                status_code=400,
                detail="Parent folder not found",
            )

    # Serialize metadata
    metadata_str = json.dumps(file_data.metadata) if file_data.metadata else None

    file = File(
        project_id=project_id,
        title=file_data.title,
        content=file_data.content,
        file_type=file_data.file_type,
        parent_id=file_data.parent_id,
        order=0,
        file_metadata=metadata_str,
    )

    session.add(file)
    session.commit()
    session.refresh(file)

    log_with_context(
        logger,
        logging.INFO,
        "Agent API: Created file",
        user_id=user_id,
        api_key_id=api_key.id,
        project_id=project_id,
        file_id=file.id,
        file_type=file_data.file_type,
    )

    # Fire-and-forget vector index upsert
    try:
        from services.llama_index import schedule_index_upsert

        extra_metadata = file_data.metadata or {}
        if file.parent_id:
            extra_metadata = {**extra_metadata, "parent_id": file.parent_id}

        background_tasks.add_task(
            schedule_index_upsert,
            project_id=project_id,
            entity_type=file.file_type,
            entity_id=file.id,
            title=file.title,
            content=file.content or "",
            extra_metadata=extra_metadata,
            user_id=user_id,
        )
    except Exception:
        log_with_context(
            logger,
            logging.DEBUG,
            "Failed to schedule vector index upsert for created file",
            project_id=project_id,
            file_id=file.id,
        )

    return file


@router.get("/files/{file_id}", response_model=_FilteredFileResponse)
async def get_file(
    file_id: str,
    fields: str | None = Query(None, description="Comma-separated fields to return (e.g. 'id,title,content')"),
    _rate_limit: int = Depends(require_rate_limit("agent_read", 2000, 3600)),
    context: AgentAuthContext = Depends(require_scope("read")),
):
    """
    Get file details.

    Requires scope: read
    Requires project access (via file ownership)

    Query parameters:
    - fields: Comma-separated fields to return (omit for all fields)
    """
    session, user_id, api_key = context

    # Parse requested fields for load_only optimization
    requested_fields = None
    if fields:
        requested_fields = {f.strip() for f in fields.split(",")}
        requested_fields &= FileResponse.VALID_FIELDS

    include_content = requested_fields is None or "content" in requested_fields
    columns = [
        File.id, File.project_id, File.title, File.file_type,
        File.parent_id, File.order, File.file_metadata,
        File.created_at, File.updated_at,
    ]
    if include_content:
        columns.append(File.content)

    file = session.exec(
        select(File).options(load_only(*columns)).where(File.id == file_id)
    ).first()
    if not file or file.is_deleted:
        raise APIException(
            error_code=ErrorCode.FILE_NOT_FOUND,
            status_code=404,
        )

    # Verify project access
    project = session.get(Project, file.project_id)
    if not project or project.owner_id != user_id or project.is_deleted:
        raise APIException(
            error_code=ErrorCode.FILE_NOT_FOUND,
            status_code=404,
        )

    if not verify_project_access(api_key, file.project_id):
        raise APIException(
            error_code=ErrorCode.NOT_AUTHORIZED,
            status_code=403,
            detail="API Key does not have access to this project",
        )

    return FileResponse.model_validate(file).to_filtered_dict(requested_fields)


@router.put("/files/{file_id}", response_model=FileResponse)
async def update_file(
    file_id: str,
    file_data: FileUpdate,
    background_tasks: BackgroundTasks,
    _rate_limit: int = Depends(require_rate_limit("agent_write", 1000, 3600)),
    context: AgentAuthContext = Depends(require_scope("write")),
):
    """
    Update file content.

    Requires scope: write
    Requires project access (via file ownership)
    """
    session, user_id, api_key = context

    file = session.get(File, file_id)
    if not file or file.is_deleted:
        raise APIException(
            error_code=ErrorCode.FILE_NOT_FOUND,
            status_code=404,
        )

    # Verify project access
    project = session.get(Project, file.project_id)
    if not project or project.owner_id != user_id or project.is_deleted:
        raise APIException(
            error_code=ErrorCode.FILE_NOT_FOUND,
            status_code=404,
        )

    if not verify_project_access(api_key, file.project_id):
        raise APIException(
            error_code=ErrorCode.NOT_AUTHORIZED,
            status_code=403,
            detail="API Key does not have access to this project",
        )

    # Update fields
    if file_data.title is not None:
        file.title = file_data.title

    if file_data.content is not None:
        file.content = file_data.content

    file.updated_at = utcnow()

    session.commit()
    session.refresh(file)

    log_with_context(
        logger,
        logging.INFO,
        "Agent API: Updated file",
        user_id=user_id,
        api_key_id=api_key.id,
        file_id=file_id,
        project_id=file.project_id,
    )

    # Fire-and-forget vector index upsert
    try:
        extra_metadata = {}
        if file.file_metadata:
            try:
                extra_metadata = json.loads(file.file_metadata)
            except Exception:
                extra_metadata = {}
        if file.parent_id:
            extra_metadata = {**extra_metadata, "parent_id": file.parent_id}

        from services.llama_index import schedule_index_upsert

        background_tasks.add_task(
            schedule_index_upsert,
            project_id=file.project_id,
            entity_type=file.file_type,
            entity_id=file.id,
            title=file.title,
            content=file.content or "",
            extra_metadata=extra_metadata,
            user_id=user_id,
        )
    except Exception:
        log_with_context(
            logger,
            logging.DEBUG,
            "Failed to schedule vector index upsert for updated file",
            file_id=file_id,
            project_id=file.project_id,
        )

    return file


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    background_tasks: BackgroundTasks,
    _rate_limit: int = Depends(require_rate_limit("agent_write", 1000, 3600)),
    context: AgentAuthContext = Depends(require_scope("write")),
):
    """
    Delete a file (soft delete).

    Requires scope: write
    Requires project access (via file ownership)
    """
    session, user_id, api_key = context

    file = session.get(File, file_id)
    if not file or file.is_deleted:
        raise APIException(
            error_code=ErrorCode.FILE_NOT_FOUND,
            status_code=404,
        )

    # Verify project access
    project = session.get(Project, file.project_id)
    if not project or project.owner_id != user_id or project.is_deleted:
        raise APIException(
            error_code=ErrorCode.FILE_NOT_FOUND,
            status_code=404,
        )

    if not verify_project_access(api_key, file.project_id):
        raise APIException(
            error_code=ErrorCode.NOT_AUTHORIZED,
            status_code=403,
            detail="API Key does not have access to this project",
        )

    # Soft delete
    file.is_deleted = True
    file.deleted_at = utcnow()

    session.commit()

    log_with_context(
        logger,
        logging.INFO,
        "Agent API: Deleted file",
        user_id=user_id,
        api_key_id=api_key.id,
        file_id=file_id,
        project_id=file.project_id,
    )

    # Fire-and-forget vector index delete
    try:
        from services.llama_index import schedule_index_delete

        background_tasks.add_task(
            schedule_index_delete,
            project_id=file.project_id,
            entity_type=file.file_type,
            entity_id=file.id,
            user_id=user_id,
        )
    except Exception:
        log_with_context(
            logger,
            logging.DEBUG,
            "Failed to schedule vector index delete for deleted file",
            file_id=file_id,
            project_id=file.project_id,
        )

    return {"message": "File deleted successfully"}


# ==================== Writing Context Endpoint ====================

MAX_CONTENT_SNIPPET = 500
MAX_PAYLOAD_BYTES = 50 * 1024  # 50KB


@router.get("/projects/{project_id}/writing-context")
async def get_writing_context(
    project_id: str,
    file_id: str | None = Query(None, description="Focus file ID"),
    query: str | None = Query(None, description="Query for context retrieval"),
    max_items: int = Query(10, ge=1, le=30, description="Max items to return"),
    _rate_limit: int = Depends(require_rate_limit("agent_context", 500, 3600)),
    context: AgentAuthContext = Depends(require_project_access("read")),
):
    """
    Get assembled writing context for a project.

    Requires scope: read
    Requires project access

    Returns structured context items (relevant chapters, characters, lore)
    assembled by the AI context engine. This is the primary differentiated
    endpoint — external agents get AI-curated writing context, not raw files.
    """
    session, user_id, api_key = context

    assembler = ContextAssembler()

    def _assemble_in_thread():
        thread_session = create_session()
        try:
            return assembler.assemble(
                session=thread_session,
                project_id=project_id,
                user_id=user_id,
                query=query,
                focus_file_id=file_id,
            )
        finally:
            thread_session.close()

    try:
        context_data = await asyncio.wait_for(
            asyncio.to_thread(_assemble_in_thread),
            timeout=10.0,
        )
    except TimeoutError:
        log_with_context(
            logger,
            logging.WARNING,
            "Agent API: Writing context timeout",
            project_id=project_id,
            user_id=user_id,
        )
        raise APIException(
            error_code=ErrorCode.INTERNAL_ERROR,
            status_code=504,
            detail="Writing context assembly timed out",
        ) from None

    # Build response with content_snippet cap
    items = []
    payload_size = 0
    for item in context_data.items[:max_items]:
        snippet = item.get("content", "")
        if snippet and len(snippet) > MAX_CONTENT_SNIPPET:
            snippet = snippet[:MAX_CONTENT_SNIPPET] + "..."

        entry = {
            "type": item.get("type", ""),
            "title": item.get("title", ""),
            "content_snippet": snippet,
            "source_file_id": item.get("id", ""),
            "relevance": item.get("relevance_score", 0),
        }

        entry_size = len(json.dumps(entry, ensure_ascii=False))
        if payload_size + entry_size > MAX_PAYLOAD_BYTES:
            break

        items.append(entry)
        payload_size += entry_size

    log_with_context(
        logger,
        logging.INFO,
        "Agent API: Writing context",
        user_id=user_id,
        api_key_id=api_key.id,
        project_id=project_id,
        items_returned=len(items),
        total_available=len(context_data.items),
    )

    return {
        "items": items,
        "refs": context_data.refs,
        "total_available": len(context_data.items),
        "returned": len(items),
        "token_estimate": context_data.token_estimate,
    }
