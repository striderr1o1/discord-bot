import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime

_scheduler: AsyncIOScheduler = None

DAY_MAP = {
    "mon": "mon", "tue": "tue", "wed": "wed",
    "thu": "thu", "fri": "fri", "sat": "sat", "sun": "sun",
}


def get_scheduler() -> AsyncIOScheduler:
    return _scheduler


def start_scheduler():
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone=pytz.utc)
    _scheduler.start()
    print("[Scheduler] Started")


def stop_scheduler():
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()


def schedule_reminder(job_id: str, run_at: datetime, callback, *args):
    """Schedule a one-time reminder."""
    if run_at <= datetime.now(pytz.utc):
        return  # Past time, skip
    _scheduler.add_job(
        callback,
        trigger=DateTrigger(run_date=run_at),
        id=job_id,
        args=args,
        replace_existing=True,
        misfire_grace_time=300,
    )


def schedule_routine(job_id: str, time_str: str, days: list[str], tz_name: str, callback, *args):
    """Schedule a recurring routine job."""
    hour, minute = map(int, time_str.split(":"))
    day_of_week = ",".join(DAY_MAP[d] for d in days if d in DAY_MAP)
    tz = pytz.timezone(tz_name)

    _scheduler.add_job(
        callback,
        trigger=CronTrigger(
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            timezone=tz,
        ),
        id=job_id,
        args=args,
        replace_existing=True,
        misfire_grace_time=300,
    )


def remove_job(job_id: str):
    try:
        _scheduler.remove_job(job_id)
    except Exception:
        pass


def remove_jobs_by_prefix(prefix: str):
    for job in _scheduler.get_jobs():
        if job.id.startswith(prefix):
            job.remove()
