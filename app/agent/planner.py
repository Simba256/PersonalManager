"""Daily planning agent — generates AI-powered daily plans using task and activity data."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from loguru import logger

from app.llm.router import get_llm
from app.llm.prompts import SYSTEM_PLANNER, DAILY_PLAN_TEMPLATE


class DailyPlanner:
    """Generates intelligent daily plans by combining task data, calendar events,
    and coding activity patterns."""

    def __init__(self, db=None):
        self._db = db
        self._llm = get_llm()

    def _get_db(self):
        if self._db is None:
            from app.database import SessionLocal
            self._db = SessionLocal()
        return self._db

    def generate_plan(self, date: Optional[datetime] = None) -> dict:
        """Generate a daily plan for the given date.

        Returns:
            Dict with 'plan_text', 'tasks', 'meetings', 'activity' keys
        """
        target = date or datetime.now()
        db = self._get_db()

        from app.services.task_service import TaskService
        task_service = TaskService(db)

        pending = task_service.get_pending_for_schedule()
        due_soon = task_service.get_due_soon(days=3)
        overdue = task_service.get_overdue()

        tasks_summary = self._format_tasks(pending, due_soon, overdue)
        meetings_summary = self._get_meetings_summary(db, target)
        activity_summary, peak_hours = self._get_activity_context()

        plan_text = None
        ai_generated = False
        if self._llm.available:
            prompt = DAILY_PLAN_TEMPLATE.format(
                date=target.strftime("%A, %B %d, %Y"),
                time=target.strftime("%H:%M"),
                task_count=len(pending),
                tasks_summary=tasks_summary,
                meetings_summary=meetings_summary,
                activity_summary=activity_summary,
                peak_hours=peak_hours,
            )
            plan_text = self._llm.complete(
                prompt=prompt,
                system=SYSTEM_PLANNER,
                temperature=0.3,
                max_tokens=600,
            )
            if plan_text:
                ai_generated = True
                logger.info(f"AI daily plan generated for {target.date()}")

        if not plan_text:
            plan_text = self._generate_fallback_plan(pending, due_soon, overdue)
            logger.info(f"Fallback daily plan generated for {target.date()}")

        return {
            "date": target.date().isoformat(),
            "plan_text": plan_text,
            "pending_count": len(pending),
            "due_soon_count": len(due_soon),
            "overdue_count": len(overdue),
            "ai_generated": ai_generated,
        }

    def _format_tasks(self, pending, due_soon, overdue) -> str:
        lines = []

        if overdue:
            lines.append(f"OVERDUE ({len(overdue)}):")
            for t in overdue[:5]:
                days_ago = (datetime.now() - t.due_date).days if t.due_date else 0
                lines.append(f"  [{t.priority.upper()}] {t.title} ({days_ago}d overdue)")

        if due_soon:
            lines.append(f"\nDUE SOON ({len(due_soon)}):")
            for t in due_soon[:5]:
                due_str = t.due_date.strftime("%b %d") if t.due_date else "?"
                est = f"{t.estimate_minutes}min" if t.estimate_minutes else "?"
                lines.append(f"  [{t.priority.upper()}] {t.title} | due {due_str} | est {est}")

        if pending:
            lines.append(f"\nPENDING ({len(pending)}):")
            for t in pending[:8]:
                est = f"{t.estimate_minutes}min" if t.estimate_minutes else "?"
                lines.append(f"  [{t.priority.upper()}] {t.title} | est {est} | energy: {t.energy_level or '?'}")

        return "\n".join(lines) if lines else "No tasks."

    def _get_meetings_summary(self, db, date: datetime) -> str:
        from app.models import Meeting
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        meetings = db.query(Meeting).filter(
            Meeting.start_time >= day_start,
            Meeting.start_time < day_end
        ).order_by(Meeting.start_time).all()

        if not meetings:
            return "No meetings today."

        lines = []
        for m in meetings:
            time_str = m.start_time.strftime("%H:%M")
            dur = int((m.end_time - m.start_time).total_seconds() / 60) if m.end_time else "?"
            lines.append(f"  {time_str} — {m.title} ({dur}min)")
        return "\n".join(lines)

    def _get_activity_context(self) -> tuple[str, str]:
        try:
            from app.integrations.activity_tracker import ActivityTracker
            tracker = ActivityTracker()
            if not tracker.available:
                return "Activity Tracker not available.", "Unknown"

            start = datetime.now() - timedelta(days=14)
            coding_time = tracker.get_coding_time(start_date=start)
            peak_hours_data = tracker.get_peak_hours(days=14)

            if coding_time:
                top = coding_time[:3]
                lines = []
                for item in top:
                    proj = item["working_directory"].split("/")[-1]
                    hours = item["total_minutes"] / 60
                    lines.append(f"  {proj}: {hours:.1f}h")
                activity_summary = "\n".join(lines)
            else:
                activity_summary = "No coding data available."

            if peak_hours_data:
                top_hours = sorted(peak_hours_data, key=lambda x: x["avg_minutes"], reverse=True)[:3]
                peak_str = ", ".join(f"{h['hour']:02d}:00" for h in top_hours)
            else:
                peak_str = "Unknown"

            return activity_summary, peak_str

        except Exception as e:
            logger.warning(f"Could not get activity context: {e}")
            return "Activity data unavailable.", "Unknown"

    def _generate_fallback_plan(self, pending, due_soon, overdue) -> str:
        """Generate a simple rule-based plan when LLM is not available."""
        lines = ["Daily Plan (auto-generated):"]

        if overdue:
            lines.append(f"\n⚠️  OVERDUE ({len(overdue)} tasks) — address first:")
            for t in overdue[:3]:
                lines.append(f"  • [{t.priority.upper()}] {t.title}")

        # Split by energy level for morning/afternoon
        high_energy = [t for t in pending if t.energy_level == "high"]
        low_energy = [t for t in pending if t.energy_level in ("low", None)]
        medium_energy = [t for t in pending if t.energy_level == "medium"]

        if high_energy or due_soon:
            lines.append("\nMorning (peak focus):")
            for t in (due_soon + high_energy)[:3]:
                est = f"{t.estimate_minutes}min" if t.estimate_minutes else "~1h"
                lines.append(f"  • {t.title} ({est})")

        afternoon_tasks = (medium_energy + low_energy)[:3]
        if afternoon_tasks:
            lines.append("\nAfternoon:")
            for t in afternoon_tasks:
                est = f"{t.estimate_minutes}min" if t.estimate_minutes else "~1h"
                lines.append(f"  • {t.title} ({est})")

        if not pending and not overdue:
            lines.append("\nNo pending tasks — great time to tackle longer-term goals.")

        return "\n".join(lines)

    def close(self):
        if self._db:
            self._db.close()
            self._db = None
