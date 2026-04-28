"""Materials-library entitlement access helpers."""

from fastapi import Depends
from services.auth import get_current_active_user
from sqlmodel import Session

from core.permissions import FeatureNotIncludedException
from database import get_session
from models import User
from services.quota_service import quota_service


def require_materials_library_access(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> User:
    """Require access to the paid materials-library workspace."""
    if not quota_service.has_feature_access(
        session,
        current_user.id,
        "materials_library_access",
    ):
        raise FeatureNotIncludedException(feature_type="material_decompose")
    return current_user
