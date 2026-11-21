"""Day keys are local calendar days ("YYYY-MM-DD") in the user's timezone.

Stored as strings so they compare correctly as text and never shift with UTC.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings


def tz() -> ZoneInfo:
    return ZoneInfo(get_settings().tz_name)


def today_key() -> str:
    return datetime.now(tz()).date().isoformat()


def parse(key: str) -> date:
    return date.fromisoformat(key)


def add_days(key: str, days: int) -> str:
    return (parse(key) + timedelta(days=days)).isoformat()


def diff_days(a: str, b: str) -> int:
    """Days from a to b (positive when b is later)."""
    return (parse(b) - parse(a)).days


def is_weekend(key: str) -> bool:
    return parse(key).weekday() >= 5


def week_start(key: str) -> str:
    """Monday of the week containing key."""
    d = parse(key)
    return (d - timedelta(days=d.weekday())).isoformat()
