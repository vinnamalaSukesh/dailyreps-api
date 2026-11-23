from fastapi import APIRouter, HTTPException

from app.db import get_db
from app.logic.dates import today_key
from app.schemas import CommentIn, TopicIn, TopicPatch, oid, out

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
    changes: dict = body.model_dump(exclude_none=True)
    update: dict = {"$set": changes}
    if changes.get("status") == "completed":
        changes["completedAt"] = today_key()
    elif changes.get("status") == "pending":
        update["$unset"] = {"completedAt": ""}
    t = await get_db().topics.find_one_and_update({"_id": oid(tid)}, update, return_document=True)
    if not t:
        raise HTTPException(404, "Topic not found")
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
