"""Reasons for missing a daily objective (DSA, topics, workout)."""

from collections import Counter
from collections.abc import Iterable

OBJECTIVES = ("dsa", "topics", "workout")

_COMMON = [
    "Sick / unwell",
    "Long work day / deadline",
    "Low sleep / exhausted",
    "Travelling",
    "Family / personal commitment",
]

DEFAULT_REASONS: dict[str, list[str]] = {
    "workout": [
        "Muscle soreness from yesterday",
        "Injury / pain",
        "Planned rest day",
        "No space / equipment",
        *_COMMON,
    ],
    "dsa": [
        "Stuck too long on one problem",
        "Spent the time on topics instead",
        "Couldn't focus",
        *_COMMON,
    ],
    "topics": [
        "Spent the time on DSA instead",
        "Couldn't focus",
        "Revised old topics instead",
        *_COMMON,
    ],
}


def suggestions(past_reasons: Iterable[str], objective: str, limit: int = 4) -> list[str]:
    """Your most used past reasons first (up to `limit`), then the defaults, without duplicates."""
    defaults = DEFAULT_REASONS[objective]
    known = {d.casefold() for d in defaults}
    counts = Counter(r.strip() for r in past_reasons if r.strip())
    mine = [r for r, _ in counts.most_common() if r.casefold() not in known][:limit]
    return mine + defaults
