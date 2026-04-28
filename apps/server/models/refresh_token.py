"""
Refresh token persistence model.

Stores refresh token metadata for rotation and revocation.
"""

from datetime import datetime

from sqlalchemy import Index
from sqlmodel import Field, SQLModel

from config.datetime_utils import utcnow

from .utils import generate_uuid


class RefreshTokenRecord(SQLModel, table=True):
    """Persistent refresh token record (by token jti)."""

    __tablename__ = "refresh_token_record"
    __table_args__ = (
        Index("ix_refresh_token_user_active", "user_id", "revoked_at"),
        Index("ix_refresh_token_family_active", "family_id", "revoked_at"),
    )

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    token_jti: str = Field(unique=True, index=True, max_length=128)
    family_id: str = Field(index=True, max_length=128)
    issued_at: datetime = Field(default_factory=utcnow, index=True)
    expires_at: datetime = Field(index=True)
    revoked_at: datetime | None = Field(default=None, index=True)
    revoke_reason: str | None = Field(default=None, max_length=64)
    replaced_by_jti: str | None = Field(default=None, max_length=128)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
