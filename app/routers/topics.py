from fastapi import APIRouter, HTTPException

from app.db import get_db
from app.logic import revise
from app.logic.dates import today_key
from app.schemas import CommentIn, ReviewIn, TopicIn, TopicPatch, oid, out

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("")
async def list_topics():
    # Pending first (they carry over day to day), then most recently completed.
    ts = await get_db().topics.find({}).sort([("status", -1), ("completedAt", -1), ("createdAt", 1), ("order", 1)]).to_list(None)
    return [out(t) for t in ts]


@router.post("", status_code=201)
async def create_topic(body: TopicIn):
    doc = {**body.model_dump(), "status": "pending", "comments": [], "createdAt": today_key()}
    res = await get_db().topics.insert_one(doc)
    doc["_id"] = res.inserted_id
    return out(doc)


@router.get("/{tid}")
async def get_topic(tid: str):
    t = await get_db().topics.find_one({"_id": oid(tid)})
    if not t:
        raise HTTPException(404, "Topic not found")
    return out(t)


@router.patch("/{tid}")
async def patch_topic(tid: str, body: TopicPatch):
    db = get_db()
    t = await db.topics.find_one({"_id": oid(tid)})
    if not t:
        raise HTTPException(404, "Topic not found")
    changes: dict = body.model_dump(exclude_none=True)
    tag = changes.pop("revise", None)
    if tag is True and not t.get("revision"):
        changes["revision"] = revise.start(today_key())  # re-tagging an active topic keeps its progress
    elif tag is False:
        changes["revision"] = None  # review history stays
    update: dict = {"$set": changes}
    if changes.get("status") == "completed":
        changes["completedAt"] = today_key()
    elif changes.get("status") == "pending":
        update["$unset"] = {"completedAt": ""}
    if not changes and "$unset" not in update:
        return out(t)
    t = await db.topics.find_one_and_update({"_id": t["_id"]}, update, return_document=True)
    return out(t)


@router.post("/{tid}/reviews")
async def review_topic(tid: str, body: ReviewIn):
    """Log whether you could explain the topic from memory; moves it along the revision ladder."""
    db = get_db()
    t = await db.topics.find_one({"_id": oid(tid)})
    if not t:
        raise HTTPException(404, "Topic not found")
    rev = t.get("revision")
    if not rev:
        raise HTTPException(409, "Turn on revision for this topic first")
    today = today_key()
    if rev.get("lastAt") == today:
        raise HTTPException(409, "Already revised today")
    t = await db.topics.find_one_and_update(
        {"_id": t["_id"]},
        {
            "$set": {"revision": revise.apply_review(rev, body.correct, today)},
            "$push": {"reviews": {"date": today, "correct": body.correct}},
        },
        return_document=True,
    )
    return out(t)


@router.post("/{tid}/comments", status_code=201)
async def add_comment(tid: str, body: CommentIn):
    comment = {"date": today_key(), "text": body.text.strip()}
    t = await get_db().topics.find_one_and_update(
        {"_id": oid(tid)}, {"$push": {"comments": comment}}, return_document=True
    )
    if not t:
        raise HTTPException(404, "Topic not found")
    return out(t)


@router.delete("/{tid}", status_code=204)
async def delete_topic(tid: str):
    await get_db().topics.delete_one({"_id": oid(tid)})
