import logging
import secrets
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Depends, FastAPI, Header, HTTPException

from app import db
from app.config import get_settings
from app.logic.dates import today_key, tz
from app.routers import misc, misses, questions, today, topics
from app.services import planner, reports

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("dailyreps")


async def daily_plan_job() -> None:
    plan = await planner.ensure_plan(today_key())
    log.info("Daily plan ready: %s (%s)", plan["date"], plan.get("generatedBy"))


async def weekly_report_job() -> None:
    doc = await reports.generate(today_key(), "weekly")
    log.info("Weekly report generated (%s)", doc["source"])


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.init_indexes()
    scheduler = None
    if get_settings().enable_scheduler:
        scheduler = AsyncIOScheduler(timezone=tz())
        scheduler.add_job(daily_plan_job, CronTrigger(hour=6, minute=50, timezone=tz()), misfire_grace_time=3600)
        scheduler.add_job(
            weekly_report_job, CronTrigger(day_of_week="sun", hour=21, minute=0, timezone=tz()), misfire_grace_time=3600
        )
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)
    await db.close()


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_api_key, get_settings().api_key):
        raise HTTPException(401, "Invalid API key")


app = FastAPI(title="DailyReps API", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"ok": True, "date": today_key()}


for r in (today.router, questions.router, topics.router, misses.router, misc.router):
    app.include_router(r, dependencies=[Depends(require_api_key)])
