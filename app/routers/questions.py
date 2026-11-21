from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pymongo.errors import DuplicateKeyError

from app.data.starter import STARTER
from app.db import get_db
from app.logic.dates import today_key
from app.logic.revisit import apply_result
from app.schemas import AttemptIn, QuestionIn, QuestionPatch, oid, out
from app.services import leetcode

router = APIRouter(tags=["questions"])


def _new_question(**fields) -> dict:
    doc = {
        "title": fields["title"],
        "level": fields["level"],
        "tags": fields.get("tags") or [],
        "pattern": (fields.get("pattern") or leetcode.pattern_from_tags(fields.get("tags") or [])).lower(),
        "step": 0,
        "nextRevisitAt": None,
        "failCount": 0,
        "lastAttemptAt": None,
        "mastered": False,
        "createdAt": datetime.now(UTC),
    }
    # Omit (not null) so the sparse unique index on lcNumber ignores manual entries.
    for k in ("lcNumber", "slug"):
        if fields.get(k) is not None:
            doc[k] = fields[k]
    return doc


@router.get("/leetcode/lookup")
async def lookup(ref: str):
    try:
        return await leetcode.lookup(ref)
    except leetcode.LookupError_ as e:
        raise HTTPException(422, str(e)) from e


@router.get("/questions")
async def list_questions():
    qs = await get_db().questions.find({}).sort("createdAt", 1).to_list(None)
    return [out(q) for q in qs]


@router.post("/questions", status_code=201)
async def create_question(body: QuestionIn):
    fields = body.model_dump(exclude_none=True)
    ref = body.ref or body.slug or (str(body.lcNumber) if body.lcNumber else None)
    if ref:
        try:
            fields = {**await leetcode.lookup(ref), **{k: v for k, v in fields.items() if v not in ("", [])}}
        except leetcode.LookupError_ as e:
            if not (body.title and body.level):
                raise HTTPException(422, str(e)) from e
    if not fields.get("title") or not fields.get("level"):
        raise HTTPException(422, "Title and difficulty are required for manual entry")
    doc = _new_question(**fields)
    try:
        res = await get_db().questions.insert_one(doc)
    except DuplicateKeyError as e:
        raise HTTPException(409, f"#{doc.get('lcNumber')} is already in your list") from e
    doc["_id"] = res.inserted_id
    return out(doc)


@router.post("/questions/seed")
async def seed():
    db = get_db()
    added = 0
    for num, slug, title, level, pattern in STARTER:
        doc = _new_question(lcNumber=num, slug=slug, title=title, level=level, pattern=pattern)
        try:
            await db.questions.insert_one(doc)
            added += 1
        except DuplicateKeyError:
            pass
    return {"added": added}


@router.get("/questions/{qid}")
async def get_question(qid: str):
    db = get_db()
    q = await db.questions.find_one({"_id": oid(qid)})
    if not q:
        raise HTTPException(404, "Question not found")
    attempts = await db.attempts.find({"questionId": qid}).sort("date", -1).to_list(None)
    return {**out(q), "attempts": [out(a) for a in attempts]}


@router.patch("/questions/{qid}")
async def patch_question(qid: str, body: QuestionPatch):
    changes = body.model_dump(exclude_none=True)
    if "pattern" in changes:
        changes["pattern"] = changes["pattern"].lower()
    if changes.get("mastered") is True:
        changes["nextRevisitAt"] = None
    q = await get_db().questions.find_one_and_update(
        {"_id": oid(qid)}, {"$set": changes}, return_document=True
    )
    if not q:
        raise HTTPException(404, "Question not found")
    return out(q)


@router.delete("/questions/{qid}", status_code=204)
async def delete_question(qid: str):
    db = get_db()
    await db.questions.delete_one({"_id": oid(qid)})
    await db.attempts.delete_many({"questionId": qid})
    await db.plans.update_many({}, {"$pull": {"newQs": qid, "revisitQs": qid}})


@router.post("/questions/{qid}/attempts", status_code=201)
async def log_attempt(qid: str, body: AttemptIn):
    db = get_db()
    q = await db.questions.find_one({"_id": oid(qid)})
    if not q:
        raise HTTPException(404, "Question not found")
    today = today_key()
    if await db.attempts.find_one({"questionId": qid, "date": today}):
        raise HTTPException(409, "Already logged today. Edit that attempt instead.")
    is_first = await db.attempts.count_documents({"questionId": qid}, limit=1) == 0
    attempt = {
        "questionId": qid,
        "date": today,
        "type": "new" if is_first else "revisit",
        **body.model_dump(),
        "createdAt": datetime.now(UTC),
    }
    await db.attempts.insert_one(attempt)
    updated = await db.questions.find_one_and_update(
        {"_id": q["_id"]}, {"$set": apply_result(q, body.result, today, is_first)}, return_document=True
    )
    return {"attempt": out(attempt), "question": out(updated)}


@router.patch("/attempts/{aid}")
async def edit_attempt(aid: str, body: dict):
    """Only comment and time are editable; result drives the ladder and is fixed."""
    changes = {k: v for k, v in body.items() if k in ("comment", "timeMin")}
    a = await get_db().attempts.find_one_and_update({"_id": oid(aid)}, {"$set": changes}, return_document=True)
    if not a:
        raise HTTPException(404, "Attempt not found")
    return out(a)
