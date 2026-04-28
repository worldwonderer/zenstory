"""
Permission checking for Agent tool execution.

Provides centralized permission validation for file operations:
- Project ownership verification
- User authorization
- Access control
"""


from sqlmodel import Session

from models import File, Project, User
from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)


class PermissionError(Exception):
    """Base exception for permission errors."""
    pass


class UnauthorizedError(PermissionError):
    """User is not authorized."""
    pass


class ForbiddenError(PermissionError):
    """User does not have permission."""
    pass


class NotFoundError(PermissionError):
    """Resource not found."""
    pass


def check_project_ownership(
    session: Session,
    project_id: str,
    user_id: str | None = None,
) -> Project:
    """
    Check if user owns the project.

    Args:
        session: Database session
        project_id: Project ID to check
        user_id: User ID (None if not authenticated)

    Returns:
        The Project object if authorized

    Raises:
        NotFoundError: If project doesn't exist
        ForbiddenError: If user doesn't own the project
    """
    project = session.get(Project, project_id)

    if not project:
        log_with_context(
            logger,
            40,  # ERROR
            "Project not found",
            project_id=project_id,
            user_id=user_id,
        )
        raise NotFoundError(f"Project not found: {project_id}")

    # Check if project is soft-deleted
    if project.is_deleted:
        log_with_context(
            logger,
            40,  # ERROR
            "Project is soft-deleted",
            project_id=project_id,
            user_id=user_id,
        )
        raise NotFoundError(f"Project not found: {project_id}")

    # If user_id is provided, check ownership
    if user_id is not None and project.owner_id != user_id:
        log_with_context(
            logger,
            40,  # ERROR
            "Permission denied: User does not own project",
            project_id=project_id,
            user_id=user_id,
            owner_id=project.owner_id,
        )
        raise ForbiddenError(f"You don't have permission to access project {project_id}")

    return project


def check_file_ownership(
    session: Session,
    file_id: str,
    project_id: str,
    user_id: str | None = None,
) -> File:
    """
    Check if file belongs to the specified project and user has access.

    Args:
        session: Database session
        file_id: File ID
        project_id: Project ID to verify
        user_id: User ID

    Returns:
        The File object if authorized

    Raises:
        NotFoundError: If file doesn't exist
        ForbiddenError: If file doesn't belong to project or user lacks access
    """
    # First check project access
    check_project_ownership(session, project_id, user_id)

    # Get the file
    file = session.get(File, file_id)

    if not file or file.is_deleted:
        raise NotFoundError(f"File not found: {file_id}")

    # Verify file belongs to the project
    if file.project_id != project_id:
        raise ForbiddenError(f"File {file_id} does not belong to project {project_id}")

    return file


def check_user_exists(
    session: Session,
    user_id: str,
) -> User:
    """
    Check if user exists.

    Args:
        session: Database session
        user_id: User ID

    Returns:
        The User object

    Raises:
        NotFoundError: If user doesn't exist
    """
    user = session.get(User, user_id)

    if not user:
        log_with_context(
            logger,
            40,  # ERROR
            "User not found",
            user_id=user_id,
        )
        raise NotFoundError(f"User not found: {user_id}")

    return user


class PermissionContext:
    """
    Context manager for checking permissions with automatic cleanup.
    """

    def __init__(
        self,
        session: Session,
        project_id: str,
        user_id: str | None = None,
    ):
        """
        Initialize permission context.

        Args:
            session: Database session
            project_id: Project ID
            user_id: User ID
        """
        self.session = session
        self.project_id = project_id
        self.user_id = user_id
        self._project = None

    def __enter__(self):
        """Check permissions on enter."""
        self._project = check_project_ownership(
            self.session,
            self.project_id,
            self.user_id,
        )
        return self._project

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup on exit."""
        pass


def format_permission_error(error: PermissionError) -> str:
    """
    Format a permission error for AI response.

    Args:
        error: The permission error

    Returns:
        User-friendly error message
    """
    if isinstance(error, NotFoundError):
        return f"错误：找不到请求的资源。{str(error)}"

    if isinstance(error, ForbiddenError):
        return f"错误：您没有权限执行此操作。{str(error)}"

    if isinstance(error, UnauthorizedError):
        return f"错误：未授权。请先登录。{str(error)}"

    return f"权限错误：{str(error)}"
