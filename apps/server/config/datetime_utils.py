"""DateTime utilities for consistent timezone handling."""
from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return current UTC datetime with timezone info.

    This replaces datetime.utcnow() which is deprecated in Python 3.12+.
    The returned datetime includes timezone info (timezone.utc).
    """
    return datetime.now(UTC)


def normalize_datetime_to_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC-aware.

    The database currently stores some timestamps as naive UTC datetimes.
    When serialized to JSON, those values can be interpreted as local time
    in clients, leading to incorrect "future" timestamps in UTC- timezones.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
