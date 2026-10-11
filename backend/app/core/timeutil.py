"""UTC timestamps as ISO 8601 strings with a Z suffix."""

from datetime import UTC, datetime


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    text = value.isoformat(timespec="microseconds")
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text
