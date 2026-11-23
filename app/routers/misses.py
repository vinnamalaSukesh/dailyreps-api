"""Reasons for missing an objective on a day ("couldn't work out: sore from yesterday")."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from app.db import get_db
from app.logic.dates import add_days, today_key
from app.logic.misses import OBJECTIVES, suggestions
from app.schemas import MissIn, Objective

router = APIRouter(prefix="/misses", tags=["misses"])

MAX_BACKFILL_DAYS = 7


@router.get("")
async def list_misses(days: int = 30):
    since = add_days(today_key(), -days)
    return await get_db().misses.find({"date": {"$gte": since}}, {"_id": 0}).sort("date", -1).to_list(None)


@router.get("/suggestions")
async def miss_suggestions():
    past = await get_db().misses.find({}, {"_id": 0, "objective": 1, "reason": 1}).to_list(None)
    return {o: suggestions((m["reason"] for m in past if m["objective"] == o), o) for o in OBJECTIVES}


@router.put("")
async def save_miss(body: MissIn):
    today = today_key()
    date = body.date or today
    if not add_days(today, -MAX_BACKFILL_DAYS) <= date <= today:
        raise HTTPException(422, f"Date must be within the last {MAX_BACKFILL_DAYS} days")
    doc = {"date": date, "objective": body.objective, "reason": body.reason.strip(), "updatedAt": datetime.now(UTC)}
    await get_db().misses.update_one({"date": date, "objective": body.objective}, {"$set": doc}, upsert=True)
    doc.pop("updatedAt")
    return doc


@router.delete("/{date}/{objective}", status_code=204)
async def delete_miss(date: str, objective: Objective):
    await get_db().misses.delete_one({"date": date, "objective": objective})
