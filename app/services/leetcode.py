"""LeetCode lookup via its unofficial GraphQL endpoint, cached in Mongo.

number -> slug: questionList search
slug -> details: question(titleSlug)
Unofficial, so every result is cached and manual entry stays possible.
"""

import re
from typing import Any

import httpx

from app.db import get_db

GQL_URL = "https://leetcode.com/graphql"
HEADERS = {"User-Agent": "Mozilla/5.0 (DailyReps personal study tracker)", "Referer": "https://leetcode.com"}
QUERY = """query q($titleSlug: String!) {
  question(titleSlug: $titleSlug) { questionFrontendId title titleSlug difficulty topicTags { name } }
}"""
SEARCH = """query s($f: QuestionListFilterInput) {
  questionList(categorySlug: "", limit: 10, skip: 0, filters: $f) { data { questionFrontendId titleSlug } }
}"""

_URL_RE = re.compile(r"leetcode\.com/problems/([a-z0-9-]+)")


class LookupError_(Exception):
    pass


def parse_ref(ref: str) -> tuple[int | None, str | None]:
    """Accepts '15', '3sum', or a problem URL."""
    ref = ref.strip()
    if m := _URL_RE.search(ref):
        return None, m.group(1)
    if ref.isdigit():
        return int(ref), None
    if re.fullmatch(r"[a-z0-9-]+", ref.lower()):
        return None, ref.lower()
    raise LookupError_("Enter a LeetCode number, slug or problem URL")


async def _slug_for_number(number: int) -> str:
    """number -> slug. Cache first, then GraphQL search (the old
    /api/problems/all/ endpoint now returns 403)."""
    if cached := await get_db().lc_cache.find_one({"lcNumber": number}):
        return cached["slug"]
    try:
        async with httpx.AsyncClient(timeout=20, headers=HEADERS) as c:
            r = await c.post(GQL_URL, json={"query": SEARCH, "variables": {"f": {"searchKeywords": str(number)}}})
            r.raise_for_status()
            rows = r.json()["data"]["questionList"]["data"]
    except Exception as e:
        raise LookupError_(f"LeetCode search failed ({e.__class__.__name__}); enter details manually") from e
    for row in rows:
        if row["questionFrontendId"] == str(number):
            return row["titleSlug"]
    raise LookupError_(f"No LeetCode problem #{number}")


async def _details(slug: str) -> dict[str, Any]:
    db = get_db()
    if cached := await db.lc_cache.find_one({"slug": slug}, {"_id": 0}):
        return cached
    try:
        async with httpx.AsyncClient(timeout=20, headers=HEADERS) as c:
            r = await c.post(GQL_URL, json={"query": QUERY, "variables": {"titleSlug": slug}})
            r.raise_for_status()
            q = r.json()["data"]["question"]
    except Exception as e:
        raise LookupError_(f"LeetCode lookup failed ({e.__class__.__name__}); enter details manually") from e
    if not q:
        raise LookupError_(f"No LeetCode problem '{slug}'")
    info = {
        "lcNumber": int(q["questionFrontendId"]),
        "slug": q["titleSlug"],
        "title": q["title"],
        "level": q["difficulty"].lower(),
        "tags": [t["name"] for t in q["topicTags"]],
    }
    await db.lc_cache.replace_one({"slug": slug}, info, upsert=True)
    return info


async def lookup(ref: str) -> dict[str, Any]:
    number, slug = parse_ref(ref)
    if slug is None:
        assert number is not None
        slug = await _slug_for_number(number)
    return await _details(slug)


# LeetCode's generic tags say little about the technique; prefer specific ones.
_GENERIC = {"array", "string", "hash table", "math", "sorting", "simulation", "matrix", "counting", "enumeration"}


def pattern_from_tags(tags: list[str]) -> str:
    specific = [t for t in tags if t.lower() not in _GENERIC]
    return (specific or tags or ["misc"])[0].lower()
