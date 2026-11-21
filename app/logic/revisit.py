"""Spaced-revisit rules. Pure functions over plain dicts (Mongo documents)."""

from typing import Any, Literal

from app.logic.dates import add_days, diff_days

Result = Literal["solved", "solved_with_hint", "failed"]

INTERVALS = [1, 3, 7, 14, 30]
LEVEL_WEIGHT = {"hard": 2, "medium": 1, "easy": 0}
MAX_CANDIDATES = 8
PATTERN_COOLDOWN_DAYS = 2
NEARLY_DUE_DAYS = 1


def apply_result(q: dict[str, Any], result: Result, date: str, is_first: bool) -> dict[str, Any]:
    """Return the fields to $set on the question after an attempt.

    First attempt: always start the ladder at 1 day.
    Revisit: solved -> next step (solving the 30-day step = mastered),
    solved_with_hint -> same interval, failed -> back to 1 day.
    """
    step = q.get("step", 0)
    fail_count = q.get("failCount", 0)
    mastered = False

    if result == "failed":
        fail_count += 1

    if is_first or result == "failed":
        step = 0
    elif result == "solved":
        if step >= len(INTERVALS) - 1:
            mastered = True
        else:
            step += 1
    # solved_with_hint: keep step

    return {
        "step": step,
        "failCount": fail_count,
        "mastered": mastered,
        "lastAttemptAt": date,
        "nextRevisitAt": None if mastered else add_days(date, INTERVALS[step]),
    }


def score(q: dict[str, Any], today: str) -> int:
    days_overdue = diff_days(q["nextRevisitAt"], today)
    return days_overdue * 2 + q.get("failCount", 0) * 3 + LEVEL_WEIGHT.get(q.get("level", ""), 0)


def candidates(
    questions: list[dict[str, Any]],
    recent_patterns: set[str],
    today: str,
    exclude_ids: set[str],
) -> list[dict[str, Any]]:
    """Due or nearly-due questions, best first, skipping recently practiced patterns.

    If the pattern cooldown would leave nothing, fall back to ignoring it so a
    revisit still happens.
    """
    horizon = add_days(today, NEARLY_DUE_DAYS)
    due = [
        q
        for q in questions
        if not q.get("mastered")
        and q.get("nextRevisitAt")
        and q["nextRevisitAt"] <= horizon
        and str(q["_id"]) not in exclude_ids
    ]
    fresh = [q for q in due if q.get("pattern", "").lower() not in recent_patterns]
    pool = fresh or due
    pool.sort(key=lambda q: (-score(q, today), q["nextRevisitAt"]))
    return pool[:MAX_CANDIDATES]


def fill_with_top(
    picked: list[str], ranked: list[dict[str, Any]], count: int
) -> list[str]:
    """Keep valid AI picks, then top up from the score order."""
    valid_ids = {str(q["_id"]) for q in ranked}
    out = [p for p in dict.fromkeys(picked) if p in valid_ids][:count]
    for q in ranked:
        if len(out) >= count:
            break
        if str(q["_id"]) not in out:
            out.append(str(q["_id"]))
    return out
