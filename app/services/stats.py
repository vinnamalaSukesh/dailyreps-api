from collections import defaultdict
from typing import Any

from app.db import get_db
from app.logic.dates import add_days
from app.logic.streaks import allowed_excuses, best_streak, current_streak, excuse_left


async def dsa_done_days(since: str) -> set[str]:
    """Days with at least one attempt where every planned revisit was attempted.

    New problems come from an external sheet, so any newQs left in old plans are ignored.
    An empty plan (e.g. nothing due) still counts if you practised.
    """
    db = get_db()
    plans = await db.plans.find({"date": {"$gte": since}}).to_list(None)
    attempts = await db.attempts.find({"date": {"$gte": since}}, {"questionId": 1, "date": 1}).to_list(None)
    by_day: dict[str, set[str]] = defaultdict(set)
    for a in attempts:
        by_day[a["date"]].add(a["questionId"])
    planned = {p["date"]: set(p["revisitQs"]) for p in plans}
    return {day for day, done in by_day.items() if planned.get(day, set()) <= done}


async def topic_days(since: str) -> set[str]:
    """Days with real topic work: a note added, a topic completed or a topic revised (just adding one doesn't count)."""
    days = set()
    async for t in get_db().topics.find({}):
        if t.get("completedAt"):
            days.add(t["completedAt"])
        days.update(c["date"] for c in t.get("comments", []))
        days.update(r["date"] for r in t.get("reviews", []))
    return {d for d in days if d >= since}


async def workout_days(since: str) -> set[str]:
    logs = await get_db().workout_logs.find({"date": {"$gte": since}, "completed": True}).to_list(None)
    return {w["date"] for w in logs}


async def streaks(today: str) -> dict[str, Any]:
    """Per objective: current/best streak, whether today is done, and whether this week's excuse is unused."""
    since = add_days(today, -400)
    misses = await get_db().misses.find({"date": {"$gte": since, "$lte": today}}, {"date": 1, "objective": 1}).to_list(None)
    out = {}
    for name, fn in (("dsa", dsa_done_days), ("topics", topic_days), ("workout", workout_days)):
        days = await fn(since)
        missed = [m["date"] for m in misses if m["objective"] == name]
        excused = allowed_excuses(missed, days)
        out[name] = {
            "current": current_streak(days, today, excused),
            "best": best_streak(days, excused),
            "doneToday": today in days,
            "excuseLeft": excuse_left(missed, days, today),
        }
    return out
