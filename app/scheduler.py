"""APScheduler background jobs for Personal Manager."""

from __future__ import annotations
from datetime import datetime
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import pytz

from app.config import settings


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    jobstore = SQLAlchemyJobStore(url="sqlite:///data/jobs.db")

    try:
        tz = pytz.timezone(settings.timezone)
    except Exception:
        logger.warning(f"Unknown timezone '{settings.timezone}', falling back to UTC")
        tz = pytz.utc

    scheduler = AsyncIOScheduler(
        jobstores={"default": jobstore},
        job_defaults={
            "coalesce": True,       # Merge missed runs
            "max_instances": 1,     # Prevent overlapping runs
            "misfire_grace_time": 300  # 5 min grace period
        },
        timezone=tz
    )
    return scheduler


def register_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all background jobs."""

    # ── Periodic Jobs ──────────────────────────────────────────────────────

    scheduler.add_job(
        job_calendar_sync,
        "interval",
        minutes=2,
        id="calendar_sync",
        replace_existing=True,
        name="Calendar Sync"
    )

    scheduler.add_job(
        job_git_monitor,
        "interval",
        minutes=10,
        id="git_monitor",
        replace_existing=True,
        name="Git Monitor"
    )

    # ── Daily Jobs ─────────────────────────────────────────────────────────

    scheduler.add_job(
        job_nightly_planning,
        "cron",
        hour=2, minute=0,
        id="nightly_planning",
        replace_existing=True,
        name="Nightly Interactive Planning"
    )

    scheduler.add_job(
        job_eod_checkin,
        "cron",
        hour=4, minute=0,
        id="eod_checkin",
        replace_existing=True,
        name="End-of-Day Check-in"
    )

    # ── Weekly Jobs ────────────────────────────────────────────────────────

    scheduler.add_job(
        job_weekly_insights,
        "cron",
        day_of_week="mon", hour=8, minute=0,
        id="weekly_insights",
        replace_existing=True,
        name="Weekly Insights"
    )

    logger.info("All background jobs registered")


# ── Job Functions ─────────────────────────────────────────────────────────────

async def job_calendar_sync():
    """Sync calendar events every 2 minutes."""
    try:
        from app.calendar.sync import CalendarSync
        sync = CalendarSync()
        result = sync.sync_all()
        if not result.get("skipped"):
            processed = result.get("inbox_processed", 0)
            if processed:
                logger.info(f"Calendar sync: processed {processed} inbox events")
        sync.close()
    except Exception as e:
        logger.error(f"Calendar sync job failed: {e}")


async def job_git_monitor():
    """Monitor git repositories for recent commits every 10 minutes."""
    try:
        from app.integrations.git_monitor import GitMonitor
        from app.services.project_service import ProjectService
        from app.database import SessionLocal

        monitor = GitMonitor()
        commits = monitor.get_all_recent_commits()

        if not commits:
            return

        db = SessionLocal()
        try:
            service = ProjectService(db)
            projects = service.list()
            project_by_path = {p.repo_path: p for p in projects if p.repo_path}

            sessions_created = 0
            for commit in commits:
                repo_path = commit["repo_path"]
                project = project_by_path.get(repo_path)
                if project:
                    service.add_session(
                        project.id,
                        source="git",
                        started_at=commit["timestamp"],
                        ended_at=commit["timestamp"],
                        summary=commit["message"][:200],
                        commit_hashes=[commit["hash"]]
                    )
                    sessions_created += 1
                    project.total_commits += 1

            if sessions_created:
                db.commit()
                logger.info(f"Git monitor: recorded {sessions_created} commit sessions")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Git monitor job failed: {e}")


async def job_nightly_planning():
    """Generate interactive daily plan at 2 AM for the current day.

    At 2 AM the calendar date has already rolled over, so date.today() is
    already the day we want to plan for (e.g. running at 02:00 Thursday
    produces a plan for Thursday).
    """
    import asyncio
    from datetime import date

    try:
        from app.agent.nightly_planner import NightlyPlanner

        today = date.today()
        planner = NightlyPlanner()
        plan = await asyncio.to_thread(planner.run, today)
        logger.info(
            f"Nightly plan generated for {today}: "
            f"{len(plan['slots'])} slots, status={plan['status']}"
        )
    except Exception as e:
        logger.error(f"Nightly planning job failed: {e}")


async def job_eod_checkin():
    """End-of-day analysis at 6 PM: import today's sessions and save analysis locally."""
    try:
        from app.agent.eod_analyst import EODAnalyst
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            analyst = EODAnalyst(db)
            result = analyst.analyze()
            stats = result["stats"]
            ai_label = "AI" if result.get("ai_generated") else "rule-based"
            logger.info(
                f"EOD analysis saved ({ai_label}): "
                f"{stats['sessions_count']} sessions, "
                f"{stats['tasks_completed_today']} tasks done, "
                f"{stats['coding_minutes']}min coding"
            )
            analyst.close()
        finally:
            db.close()

    except Exception as e:
        logger.error(f"EOD check-in job failed: {e}")


async def job_weekly_insights():
    """Generate and post weekly insights to calendar."""
    try:
        from app.agent.insights import InsightsGenerator
        from app.calendar.sync import CalendarSync
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            generator = InsightsGenerator(db)
            result = generator.generate_weekly()

            week_label = result["week_label"]
            insights_text = result["insights_text"]
            ai_label = "AI" if result.get("ai_generated") else "rule-based"
            logger.info(f"Weekly insights generated ({ai_label}) for {week_label}")

            sync = CalendarSync()
            sync.create_insights_event(week_label, insights_text)
            sync.close()

            generator.close()
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Weekly insights job failed: {e}")
