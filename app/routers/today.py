from bson import ObjectId
from fastapi import APIRouter

from app.db import get_db
from app.logic.dates import is_weekend, today_key
from app.schemas import out
from app.services import planner, stats

router = APIRouter(tags=["today"])


@router.get("/today")
async def today():
    """Everything the home screen needs in one call."""
    db = get_db()
    date = today_key()
    plan = await planner.ensure_plan(date)

    ids = plan["newQs"] + plan["revisitQs"]
    qs = {str(q["_id"]): q for q in await db.questions.find({"_id": {"$in": [ObjectId(i) for i in ids]}}).to_list(None)}
    done = {a["questionId"]: a for a in await db.attempts.find({"date": date, "questionId": {"$in": ids}}).to_list(None)}

    items = [
        {"kind": kind, "question": out(qs[i]), "attempt": out(done.get(i))}
        for kind, group in (("new", plan["newQs"]), ("revisit", plan["revisitQs"]))
        for i in group
        if i in qs
    ]
    topics = await db.topics.find({"status": "pending"}).sort([("createdAt", 1), ("order", 1)]).to_list(None)
    # All tagged topics, not just today's: the app schedules revision reminders days ahead.
    revision = await db.topics.find({"revision": {"$ne": None}}).sort("revision.nextAt", 1).to_list(None)
    workout = await db.workout_logs.find_one({"date": date, "completed": True})
    backlog = await db.questions.count_documents({"lastAttemptAt": None, "mastered": {"$ne": True}})
    misses = await db.misses.find({"date": date}).to_list(None)

    return {
        "date": date,
        "weekend": is_weekend(date),
        "plan": {"generatedBy": plan.get("generatedBy"), "aiReason": plan.get("aiReason"), "items": items},
        "backlogCount": backlog,
        "pendingTopics": [out(t) for t in topics],
        "revisionTopics": [out(t) for t in revision],
        "workoutDone": workout is not None,
        "misses": {m["objective"]: m["reason"] for m in misses},
        "streaks": await stats.streaks(date),
    }
