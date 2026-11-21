from collections import defaultdict
from typing import Any

from app.db import get_db
from app.logic.dates import add_days
from app.logic.streaks import best_streak, current_streak


async def dsa_done_days(since: str) -> set[str]:
    """Days where every question in that day's plan has an attempt that day."""
    db = get_db()
    plans = await db.plans.find({"date": {"$gte": since}}).to_list(None)
    attempts = await db.attempts.find({"date": {"$gte": since}}, {"questionId": 1, "date": 1}).to_list(None)
    by_day: dict[str, set[str]] = defaultdict(set)
    for a in attempts:
        by_day[a["date"]].add(a["questionId"])
    days = set()
    for p in plans:
        ids = set(p["newQs"]) | set(p["revisitQs"])
        if ids and ids <= by_day[p["date"]]:
            days.add(p["date"])
    return days


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
