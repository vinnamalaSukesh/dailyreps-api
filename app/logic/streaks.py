"""Streaks over sets of day keys.

Excused days (a miss reason was logged) bridge a streak: they don't add to it,
but they don't break it either. Use `allowed_excuses` to cap how many count.
"""

from collections.abc import Iterable

from app.logic.dates import add_days, week_start

EXCUSES_PER_WEEK = 1


def allowed_excuses(miss_days: Iterable[str], done_days: Iterable[str], per_week: int = EXCUSES_PER_WEEK) -> set[str]:
    """The earliest `per_week` missed-with-reason days in each Mon-Sun week.

    A day that was actually done never needs an excuse, so it doesn't use one up.
    """
    done = set(done_days)
    used: dict[str, int] = {}
    out = set()
    for d in sorted(set(miss_days) - done):
        wk = week_start(d)
        if used.get(wk, 0) < per_week:
            used[wk] = used.get(wk, 0) + 1
            out.add(d)
    return out


def current_streak(done_days: Iterable[str], today: str, excused: Iterable[str] = ()) -> int:
    """Consecutive done days ending today, walking through excused days.

    If today isn't done yet the streak still counts up to yesterday, so it
    only breaks once a whole day is missed without an excuse.
    """
    days, ok = set(done_days), set(excused)
    day = today if today in days or today in ok else add_days(today, -1)
    streak = 0
    while day in days or day in ok:
        streak += day in days
        day = add_days(day, -1)
    return streak


def best_streak(done_days: Iterable[str], excused: Iterable[str] = ()) -> int:
    days, ok = set(done_days), set(excused)
    best = run = 0
    prev: str | None = None
    for d in sorted(days | ok):
        if prev is None or add_days(prev, 1) != d:
            run = 0
        run += d in days
        best = max(best, run)
        prev = d
    return best


def excuse_left(miss_days: Iterable[str], done_days: Iterable[str], today: str) -> bool:
    """Whether this week still has an unused excuse (today's own excuse counts as used)."""
    wk = week_start(today)
    this_week = [d for d in allowed_excuses(miss_days, done_days) if week_start(d) == wk]
    return len(this_week) < EXCUSES_PER_WEEK
