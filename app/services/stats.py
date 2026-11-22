from collections import defaultdict
from typing import Any

from app.db import get_db
from app.logic.dates import add_days
from app.logic.streaks import best_streak, current_streak


async def dsa_done_days(since: str) -> set[str]:
    """Days with at least one attempt where every planned question was attempted.

    An empty plan (e.g. a weekend with nothing due) still counts if you practised.
    """
    db = get_db()
    plans = await db.plans.find({"date": {"$gte": since}}).to_list(None)
    attempts = await db.attempts.find({"date": {"$gte": since}}, {"questionId": 1, "date": 1}).to_list(None)
    by_day: dict[str, set[str]] = defaultdict(set)
    for a in attempts:
        by_day[a["date"]].add(a["questionId"])
    planned = {p["date"]: set(p["newQs"]) | set(p["revisitQs"]) for p in plans}
    return {day for day, done in by_day.items() if planned.get(day, set()) <= done}


async def topic_days(since: str) -> set[str]:
    """Days with any topic activity: created, commented or completed."""
    days = set()
    async for t in get_db().topics.find({}):
        days.add(t["createdAt"])
        if t.get("completedAt"):
            days.add(t["completedAt"])
        days.update(c["date"] for c in t.get("comments", []))
    return {d for d in days if d >= since}


async def workout_days(since: str) -> set[str]:
    logs = await get_db().workout_logs.find({"date": {"$gte": since}, "completed": True}).to_list(None)
    return {w["date"] for w in logs}


async def streaks(today: str) -> dict[str, Any]:
    since = add_days(today, -400)
    out = {}
    for name, fn in (("dsa", dsa_done_days), ("topics", topic_days), ("workout", workout_days)):
        days = await fn(since)
        out[name] = {"current": current_streak(days, today), "best": best_streak(days)}
    return out
