from __future__ import annotations

import pytest
from sqlmodel import Session

from api.materials.helpers import _get_novel_or_404
from core.error_handler import APIException
from models.material_models import Novel


def _create_novel(db_session: Session, *, user_id: str, deleted: bool = False) -> Novel:
    novel = Novel(user_id=user_id, title="Materials Novel", author="Author")
    if deleted:
        from config.datetime_utils import utcnow

        novel.deleted_at = utcnow()
    db_session.add(novel)
    db_session.commit()
    db_session.refresh(novel)
    return novel


def test_get_novel_or_404_returns_owned_novel(db_session: Session):
    novel = _create_novel(db_session, user_id="user-1")

    result = _get_novel_or_404(db_session, novel.id, "user-1")

    assert result.id == novel.id


@pytest.mark.parametrize(
    "owner_id, request_user_id, deleted",
    [
        ("user-1", "user-2", False),
        ("user-1", "user-1", True),
    ],
)
def test_get_novel_or_404_rejects_unauthorized_or_deleted(
    db_session: Session,
    owner_id: str,
    request_user_id: str,
    deleted: bool,
):
    novel = _create_novel(db_session, user_id=owner_id, deleted=deleted)

    with pytest.raises(APIException):
        _get_novel_or_404(db_session, novel.id, request_user_id)
