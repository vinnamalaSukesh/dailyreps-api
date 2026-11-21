from collections.abc import Iterable

from app.logic.dates import add_days


def current_streak(done_days: Iterable[str], today: str) -> int:
    """Consecutive done days ending today.

    If today isn't done yet the streak still counts up to yesterday, so it
    only breaks once a whole day is missed.
    """
    days = set(done_days)
    day = today if today in days else add_days(today, -1)
    streak = 0
    while day in days:
        streak += 1
        day = add_days(day, -1)
    return streak


def best_streak(done_days: Iterable[str]) -> int:
    days = sorted(set(done_days))
    best = run = 0
    prev: str | None = None
    for d in days:
        run = run + 1 if prev is not None and add_days(prev, 1) == d else 1
        best = max(best, run)
        prev = d
    return best
