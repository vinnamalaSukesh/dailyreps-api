"""Daily DSA plan: weekdays 2 new + 1 revisit, weekends 2 revisits.

Rules pick the candidates; AI (if configured) chooses among them; anything the
AI returns that isn't a candidate is ignored and the top-scored one is used.
"""

import json
import logging
from typing import Any

from app.db import get_db
from app.logic import revisit
from app.logic.dates import add_days, is_weekend
from app.services import ai

log = logging.getLogger(__name__)


def targets(date: str) -> tuple[int, int]:
    """(new, revisit) counts for the day."""
    return (0, 2) if is_weekend(date) else (2, 1)


async def _ai_pick(cands: list[dict[str, Any]], need: int, date: str) -> tuple[list[str], str] | None:
    db = get_db()
    profile = await db.meta.find_one({"_id": "profile"}, {"_id": 0}) or {}
    labelled = []
    for i, q in enumerate(cands, 1):
        history = await db.attempts.find(
            {"questionId": str(q["_id"])}, {"_id": 0, "date": 1, "result": 1, "timeMin": 1, "comment": 1}
        ).sort("date", -1).to_list(4)
        labelled.append({
            "key": f"c{i}",
            "title": q["title"],
            "level": q["level"],
            "pattern": q.get("pattern"),
            "failCount": q.get("failCount", 0),
            "dueOn": q["nextRevisitAt"],
            "recentAttempts": history,
        })
    system = (
        "You are a DSA interview coach choosing which problems to revisit today. "
        'Reply with JSON only: {"picks": ["c1", ...], "reason": "one or two sentences"}. '
        f"Pick exactly {need} keys from the candidate list, never anything else."
    )
    user = json.dumps({"today": date, "profile": profile, "candidates": labelled}, default=str)
    res = await ai.complete_json(system, user)
    if not res:
        return None
    data, provider = res
    keys = data.get("picks") or ([data["pick"]] if data.get("pick") else [])
    by_key = {f"c{i}": str(q["_id"]) for i, q in enumerate(cands, 1)}
    ids = [by_key[k] for k in keys if isinstance(k, str) and k in by_key]
    if not ids:
        return None
    return ids, f"{data.get('reason', '').strip()} ({provider})"


async def ensure_plan(date: str) -> dict[str, Any]:
    """Create today's plan, or top up empty slots (e.g. questions added later)."""
    db = get_db()
    plan = await db.plans.find_one({"date": date}) or {
        "date": date, "newQs": [], "revisitQs": [], "generatedBy": "rules", "aiReason": None,
    }
    new_target, rev_target = targets(date)
    if len(plan["newQs"]) >= new_target and len(plan["revisitQs"]) >= rev_target and "_id" in plan:
        return plan

    questions = await db.questions.find({"mastered": {"$ne": True}}).sort("createdAt", 1).to_list(None)
    attempted = set(await db.attempts.distinct("questionId"))
    in_plan = set(plan["newQs"]) | set(plan["revisitQs"])

    # New: oldest never-attempted questions first.
    for q in questions:
        if len(plan["newQs"]) >= new_target:
            break
        qid = str(q["_id"])
        if qid not in attempted and qid not in in_plan:
            plan["newQs"].append(qid)
            in_plan.add(qid)

    # Revisit
    need = rev_target - len(plan["revisitQs"])
    if need > 0:
        by_id = {str(q["_id"]): q for q in questions}
        recent = await db.attempts.find(
            {"date": {"$gte": add_days(date, -revisit.PATTERN_COOLDOWN_DAYS)}}, {"questionId": 1, "date": 1}
        ).to_list(None)
        done_today = {a["questionId"] for a in recent if a["date"] == date}
        recent_ids = {a["questionId"] for a in recent} | set(plan["newQs"])
        recent_patterns = {by_id[i].get("pattern", "").lower() for i in recent_ids if i in by_id}

        cands = revisit.candidates(questions, recent_patterns, date, in_plan | done_today)
        picks: list[str] = []
        if len(cands) > need and ai.enabled():
            try:
                res = await _ai_pick(cands, need, date)
            except Exception as e:
                log.warning("AI pick failed: %s", e)
                res = None
            if res:
                picks, plan["aiReason"] = res
                plan["generatedBy"] = "ai"
            else:
                plan["generatedBy"] = "fallback"
        plan["revisitQs"] += revisit.fill_with_top(picks, cands, need)

    plan.pop("_id", None)
    await db.plans.update_one({"date": date}, {"$set": plan}, upsert=True)
    return await db.plans.find_one({"date": date})  # type: ignore[return-value]
