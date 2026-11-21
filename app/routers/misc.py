"""Workout logs, profile and AI reports."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.db import get_db
from app.logic.dates import add_days, today_key
from app.schemas import ProfileIn, oid, out
from app.services import reports

router = APIRouter()


@router.post("/workout/complete", tags=["workout"])
async def complete_workout():
    date = today_key()
    await get_db().workout_logs.update_one(
        {"date": date}, {"$set": {"completed": True, "completedAt": datetime.now(UTC)}}, upsert=True
    )
    return {"date": date, "completed": True}


@router.get("/workout/logs", tags=["workout"])
async def workout_logs(days: int = 30):
    since = add_days(today_key(), -days)
    logs = await get_db().workout_logs.find({"date": {"$gte": since}}, {"_id": 0}).sort("date", -1).to_list(None)
    return logs


@router.get("/profile", tags=["profile"])
async def get_profile():
    return await get_db().meta.find_one({"_id": "profile"}, {"_id": 0}) or ProfileIn().model_dump()


@router.put("/profile", tags=["profile"])
async def put_profile(body: ProfileIn):
    await get_db().meta.replace_one({"_id": "profile"}, body.model_dump(), upsert=True)
    return body


_SUMMARY_FIELDS = {"stats": 0, "raw": 0}


@router.get("/reports", tags=["reports"])
async def list_reports():
    rs = await get_db().reports.find({}, _SUMMARY_FIELDS).sort("createdAt", -1).to_list(12)
    return [out(r) for r in rs]


@router.get("/reports/{rid}", tags=["reports"])
async def get_report(rid: str):
    r = await get_db().reports.find_one({"_id": oid(rid)}, {"raw": 0})
    if not r:
        raise HTTPException(404, "Report not found")
    return out(r)


@router.post("/reports/analyze", tags=["reports"], status_code=201)
async def analyze_now():
    today = today_key()
    used = await get_db().reports.count_documents({"trigger": "manual", "createdOn": today})
    limit = get_settings().analyze_now_daily_limit
    if used >= limit:
        raise HTTPException(429, f"Analyze now is limited to {limit} per day")
    doc = await reports.generate(today, "manual")
    doc.pop("raw", None)
    return out(doc)
