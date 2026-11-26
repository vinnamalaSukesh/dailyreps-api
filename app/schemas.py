"""Request bodies. API and Mongo both use camelCase field names (matches the app)."""

from typing import Any, Literal

from bson import ObjectId
from fastapi import HTTPException
from pydantic import BaseModel, Field

Level = Literal["easy", "medium", "hard"]
TopicCategory = Literal["system_design", "devops", "other"]


class QuestionIn(BaseModel):
    # Either give a LeetCode ref (number, slug or URL) and let the server fill
    # the rest, or give title/level yourself (manual entry).
    ref: str | None = None
    lcNumber: int | None = None
    slug: str | None = None
    title: str | None = None
    level: Level | None = None
    tags: list[str] = []
    pattern: str | None = None


class QuestionPatch(BaseModel):
    title: str | None = None
    level: Level | None = None
    tags: list[str] | None = None
    pattern: str | None = None
    mastered: bool | None = None


class AttemptIn(BaseModel):
    result: Literal["solved", "solved_with_hint", "failed"]
    timeMin: int = Field(0, ge=0, le=600)
    comment: str = ""


class TopicIn(BaseModel):
    title: str = Field(min_length=1)
    category: TopicCategory = "other"


class TopicPatch(BaseModel):
    title: str | None = None
    category: TopicCategory | None = None
    status: Literal["pending", "completed"] | None = None
    # True tags the topic for spaced revision (first one tomorrow); False stops it.
    revise: bool | None = None


class ReviewIn(BaseModel):
    """Result of trying to explain a topic from memory."""

    correct: bool


Objective = Literal["dsa", "topics", "workout"]


class MissIn(BaseModel):
    """Why an objective was missed on a day. One per objective per day; saving again replaces it."""

    objective: Objective
    reason: str = Field(min_length=1, max_length=200)
    date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")  # default: today


class CommentIn(BaseModel):
    text: str = Field(min_length=1)


class ProfileIn(BaseModel):
    stack: str = ""
    experience: str = ""
    targetRole: str = ""
    targetCTC: str = ""
    targetDate: str = ""
    weakAreas: list[str] = []
    # Generic tech only (no company/client names): this is sent to free-tier AI.
    skills: list[str] = []
    highlights: list[str] = []


def oid(id_: str) -> ObjectId:
    if not ObjectId.is_valid(id_):
        raise HTTPException(404, "Not found")
    return ObjectId(id_)


def out(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Mongo doc -> JSON: _id becomes id (string)."""
    if doc is None:
        return None
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d
