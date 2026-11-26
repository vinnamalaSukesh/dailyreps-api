"""Topic revision ladder. Pure functions over plain dicts.

Tag a topic for revision and it comes back after 1 day. Each time it's due you
try to explain it without notes and log correct or wrong:
correct -> next (longer) interval, wrong -> back to 1 day.
Unlike DSA questions, topics never "master" out: the last interval repeats,
so interview basics keep coming back every couple of months.
"""

from typing import Any

from app.logic.dates import add_days

INTERVALS = [1, 3, 7, 14, 30, 60]


def start(date: str) -> dict[str, Any]:
    return {"step": 0, "nextAt": add_days(date, INTERVALS[0]), "correct": 0, "wrong": 0, "lastAt": None}


def apply_review(rev: dict[str, Any], correct: bool, date: str) -> dict[str, Any]:
    step = min(rev["step"] + 1, len(INTERVALS) - 1) if correct else 0
    return {
        "step": step,
        "nextAt": add_days(date, INTERVALS[step]),
        "correct": rev["correct"] + (1 if correct else 0),
        "wrong": rev["wrong"] + (0 if correct else 1),
        "lastAt": date,
    }


def is_due(rev: dict[str, Any] | None, today: str) -> bool:
    return rev is not None and rev["nextAt"] <= today
