"""Helpers for consistent email account identity handling."""

from sqlalchemy import func


def normalize_email_identity(email: str) -> str:
    """Normalize an email address for account identity comparisons/storage."""
    return str(email).strip().lower()


def email_identity_matches(column, email: str):  # type: ignore[no-untyped-def]
    """Return a SQL expression matching email identity case-insensitively."""
    return func.lower(column) == normalize_email_identity(email)
