from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.config import get_settings

_client: AsyncMongoClient | None = None


def get_db() -> AsyncDatabase:
    global _client
    if _client is None:
        _client = AsyncMongoClient(get_settings().mongodb_uri, tz_aware=True)
    return _client[get_settings().mongodb_db]


async def init_indexes() -> None:
    db = get_db()
    await db.questions.create_index("lcNumber", unique=True, sparse=True)
    await db.questions.create_index("nextRevisitAt")
    await db.attempts.create_index([("questionId", ASCENDING), ("date", DESCENDING)])
    await db.attempts.create_index("date")
    await db.plans.create_index("date", unique=True)
    await db.workout_logs.create_index("date", unique=True)
    await db.reports.create_index("weekOf")
    await db.lc_cache.create_index("slug", unique=True)
    await db.misses.create_index([("date", ASCENDING), ("objective", ASCENDING)], unique=True)


async def close() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
