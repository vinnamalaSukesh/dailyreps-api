"""Weekly AI analysis: gather stats -> AI JSON -> stored report.

Falls back to a rules-only summary when no AI provider is available.
"""

import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Literal

from bson import ObjectId

from app.db import get_db
from app.logic.dates import add_days
from app.services import ai, leetcode, stats

log = logging.getLogger(__name__)


async def gather(today: str, days: int = 7) -> dict[str, Any]:
    db = get_db()
    since = add_days(today, -(days - 1))
    plans = await db.plans.find({"date": {"$gte": since, "$lte": today}}).to_list(None)
    attempts = await db.attempts.find({"date": {"$gte": since, "$lte": today}}).to_list(None)
    qids = {a["questionId"] for a in attempts}
    qs ={str(q["_id"]): q for q in await db.questions.find({"_id": {"$in": [ObjectId(i) for i in qids]}}).to_list(None)}

    planned = done = 0
    done_by_day: dict[str, set[str]] = defaultdict(set)
    for a in attempts:
        done_by_day[a["date"]].add(a["questionId"])
    for p in plans:
        ids = set(p["newQs"]) | set(p["revisitQs"])
        planned += len(ids)
        done += len(ids & done_by_day[p["date"]])

    by_pattern: dict[str, dict[str, int]] = defaultdict(lambda: {"attempts": 0, "failed": 0, "hint": 0})
    comments = []
    for a in attempts:
        q = qs.get(a["questionId"], {})
        pat = q.get("pattern") or "unknown"
        by_pattern[pat]["attempts"] += 1
        by_pattern[pat]["failed"] += a["result"] == "failed"
        by_pattern[pat]["hint"] += a["result"] == "solved_with_hint"
        if a.get("comment"):
            comments.append({"date": a["date"], "question": q.get("title"), "result": a["result"], "comment": a["comment"]})

    topics = await db.topics.find({}).to_list(None)
    topic_comments = [
        {"topic": t["title"], "date": c["date"], "text": c["text"]}
        for t in topics for c in t.get("comments", []) if c["date"] >= since
    ]
    workouts = await stats.workout_days(since)

    return {
        "period": {"from": since, "to": today},
        "dsaCompletionPct": round(100 * done / planned) if planned else None,
        "attempts": len(attempts),
        "patterns": dict(by_pattern),
        "attemptComments": comments[-30:],
        "pendingTopics": [t["title"] for t in topics if t["status"] == "pending"],
        "allStudiedTopics": [{"title": t["title"], "status": t["status"]} for t in topics],
        "completedTopics": [t["title"] for t in topics if t.get("completedAt", "") >= since],
        "topicComments": topic_comments[-20:],
        "workoutDays": len(workouts),
        "streaks": await stats.streaks(today),
        "profile": await db.meta.find_one({"_id": "profile"}, {"_id": 0}) or {},
    }


SYSTEM = """You are an interview-prep coach for a software engineer aiming to switch jobs.
The data has their profile (skills, project highlights, target role/CTC/date), this week's DSA
stats and comments, and every topic they have already studied (allStudiedTopics).

suggestedTopics: 3-5 topics to study next, highest priority first. Mix:
 - depth: interview-level internals of tech they already use (they will be grilled on it), and
 - gaps: things interviewers for their target role expect that their skills don't show yet.
Never suggest a topic already in allStudiedTopics (pending or completed); go one level deeper instead.
Keep titles specific and study-sized (one or two sessions), e.g. "MongoDB indexes & explain plans".

Reply with JSON only:
{"summary": "3-5 sentences, specific and honest",
 "weakPatterns": ["pattern", ...],
 "suggestedTopics": [{"title": "...", "category": "system_design|devops|other", "why": "one line tied to their profile"}, ...],
 "suggestedQuestions": [LeetCode problem numbers (integers) that target the weak patterns, max 5],
 "focusNextWeek": ["concrete action", ...]}"""


def _rules_summary(s: dict[str, Any]) -> dict[str, Any]:
    weak = sorted(
        (p for p, v in s["patterns"].items() if v["attempts"] and (v["failed"] + v["hint"]) / v["attempts"] >= 0.5),
        key=lambda p: -s["patterns"][p]["failed"],
    )
    pct = s["dsaCompletionPct"]
    return {
        "summary": f"DSA plan completion {pct if pct is not None else 0}% over {s['attempts']} attempts; "
        f"{s['workoutDays']} workout days; {len(s['pendingTopics'])} topics pending. (AI unavailable: rules summary.)",
        "weakPatterns": weak,
        "suggestedTopics": [],
        "suggestedQuestions": [],
        "focusNextWeek": [f"Revisit {p} problems" for p in weak[:3]],
    }


def _clean_topics(items: Any) -> list[dict[str, str]]:
    """Normalise AI topic suggestions to {title, category, why}; tolerate plain strings."""
    out = []
    for t in items or []:
        if isinstance(t, str):
            t = {"title": t}
        if not isinstance(t, dict) or not str(t.get("title", "")).strip():
            continue
        cat = t.get("category")
        out.append({
            "title": str(t["title"]).strip(),
            "category": cat if cat in ("system_design", "devops", "other") else "other",
            "why": str(t.get("why", "")).strip(),
        })
    return out[:6]


async def _validate_questions(nums: Any) -> list[dict[str, Any]]:
    out = []
    for n in (nums or [])[:5]:
        try:
            out.append(await leetcode.lookup(str(int(n))))
        except Exception:
            continue  # drop anything that doesn't resolve to a real problem
    return out


async def generate(today: str, trigger: Literal["weekly", "manual"]) -> dict[str, Any]:
    s = await gather(today)
    res = await ai.complete_json(SYSTEM, json.dumps(s, default=str)) if ai.enabled() else None
    if res:
        data, source = res
    else:
        data, source = _rules_summary(s), "rules"
    doc = {
        "weekOf": s["period"]["from"],
        "createdAt": datetime.now(UTC),
        "createdOn": today,
        "trigger": trigger,
        "source": source,
        "summary": str(data.get("summary", "")),
        "weakPatterns": list(data.get("weakPatterns") or []),
        "suggestedTopics": _clean_topics(data.get("suggestedTopics")),
        "focusNextWeek": list(data.get("focusNextWeek") or []),
        "suggestedQuestions": await _validate_questions(data.get("suggestedQuestions")),
        "stats": s,
        "raw": data,
    }
    await get_db().reports.insert_one(doc)
    return doc
