"""Weekly insights agent — generates AI-powered productivity reports."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from loguru import logger

from app.llm.router import get_llm
from app.llm.prompts import SYSTEM_INSIGHTS, WEEKLY_INSIGHTS_TEMPLATE


class InsightsGenerator:
    """Generates weekly productivity insights by combining task completion data,
    coding activity, and goal progress."""

    def __init__(self, db=None):
        self._db = db
        self._llm = get_llm()

    def _get_db(self):
        if self._db is None:
            from app.database import SessionLocal
            self._db = SessionLocal()
        return self._db

    def generate_weekly(self, week_offset: int = 0) -> dict:
        """Generate insights for a given week.

        Args:
            week_offset: 0 = current week, -1 = last week, etc.

        Returns:
            Dict with 'insights_text', 'stats', and metadata
        """
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday() + 7 * abs(week_offset))
        week_end = week_start + timedelta(days=7)
        week_num = week_start.isocalendar()[1]
        week_label = f"Week {week_num}, {week_start.year}"

        db = self._get_db()

        task_stats = self._get_task_stats(db, week_start, week_end)
        coding_stats = self._get_coding_stats(week_start, week_end)
        goal_summary = self._get_goal_summary(db)

        stats = {
            **task_stats,
            **coding_stats,
            "week_label": week_label,
            "week_start": week_start.date().isoformat(),
            "week_end": week_end.date().isoformat(),
        }

        insights_text = None
        if self._llm.available:
            prompt = WEEKLY_INSIGHTS_TEMPLATE.format(
                week_label=week_label,
                completed_count=task_stats["completed_count"],
                pending_count=task_stats["pending_count"],
                overdue_count=task_stats["overdue_count"],
                completion_rate=task_stats["completion_rate"],
                coding_summary=coding_stats["coding_summary"],
                top_projects=coding_stats["top_projects_text"],
                goals_summary=goal_summary,
            )
            insights_text = self._llm.complete(
                prompt=prompt,
                system=SYSTEM_INSIGHTS,
                temperature=0.4,
                max_tokens=500,
            )
            if insights_text:
                logger.info(f"AI weekly insights generated for {week_label}")

        if not insights_text:
            insights_text = self._generate_fallback_insights(task_stats, coding_stats)

        return {
            "week_label": week_label,
            "insights_text": insights_text,
            "stats": stats,
            "ai_generated": self._llm.available and insights_text != self._generate_fallback_insights(task_stats, coding_stats),
        }

    def _get_task_stats(self, db, week_start: datetime, week_end: datetime) -> dict:
        from app.services.task_service import TaskService
        service = TaskService(db)

        completed, _ = service.list(status="completed")
        completed_this_week = [
            t for t in completed
            if t.completed_at and week_start <= t.completed_at < week_end
        ]

        pending, _ = service.list(status="pending")
        overdue = service.get_overdue()

        total = len(completed_this_week) + len(pending)
        completion_rate = (len(completed_this_week) / total * 100) if total > 0 else 0.0

        # Categorize by priority
        critical_pending = [t for t in pending if t.priority == "critical"]
        high_pending = [t for t in pending if t.priority == "high"]

        return {
            "completed_count": len(completed_this_week),
            "pending_count": len(pending),
            "overdue_count": len(overdue),
            "completion_rate": completion_rate,
            "critical_pending": len(critical_pending),
            "high_pending": len(high_pending),
            "completed_tasks": [{"title": t.title, "priority": t.priority} for t in completed_this_week[:10]],
        }

    def _get_coding_stats(self, week_start: datetime, week_end: datetime) -> dict:
        try:
            from app.integrations.activity_tracker import ActivityTracker
            tracker = ActivityTracker()
            if not tracker.available:
                return {
                    "total_coding_hours": 0.0,
                    "coding_summary": "Activity Tracker not available.",
                    "top_projects_text": "No data.",
                    "top_projects": [],
                }

            coding_time = tracker.get_coding_time(start_date=week_start, end_date=week_end)
            total_minutes = sum(item["total_minutes"] for item in coding_time)
            total_hours = total_minutes / 60

            if coding_time:
                top = coding_time[:5]
                lines = []
                for item in top:
                    proj = item["working_directory"].split("/")[-1]
                    hours = item["total_minutes"] / 60
                    pct = (item["total_minutes"] / total_minutes * 100) if total_minutes > 0 else 0
                    lines.append(f"  {proj}: {hours:.1f}h ({pct:.0f}%)")
                top_projects_text = "\n".join(lines)
                coding_summary = f"Total: {total_hours:.1f}h across {len(coding_time)} projects"
            else:
                top_projects_text = "No coding data."
                coding_summary = "No coding activity recorded."

            return {
                "total_coding_hours": total_hours,
                "coding_summary": coding_summary,
                "top_projects_text": top_projects_text,
                "top_projects": coding_time[:5],
            }

        except Exception as e:
            logger.warning(f"Could not get coding stats: {e}")
            return {
                "total_coding_hours": 0.0,
                "coding_summary": "Coding data unavailable.",
                "top_projects_text": "No data.",
                "top_projects": [],
            }

    def _get_goal_summary(self, db) -> str:
        try:
            from app.models import Goal
            goals = db.query(Goal).filter(Goal.status != "completed").all()
            if not goals:
                return "No active goals."

            lines = []
            for g in goals[:5]:
                target = g.target_date.strftime("%b %d, %Y") if g.target_date else "No deadline"
                lines.append(f"  • {g.title} | target: {target} | status: {g.status}")
            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"Could not get goal summary: {e}")
            return "Goal data unavailable."

    def _generate_fallback_insights(self, task_stats: dict, coding_stats: dict) -> str:
        lines = [f"Weekly Summary:"]
        lines.append(f"• Tasks completed: {task_stats['completed_count']}")
        lines.append(f"• Completion rate: {task_stats['completion_rate']:.0f}%")
        lines.append(f"• Coding time: {coding_stats['total_coding_hours']:.1f}h")

        if task_stats["overdue_count"] > 0:
            lines.append(f"⚠️  {task_stats['overdue_count']} overdue tasks need attention")

        if task_stats["critical_pending"] > 0:
            lines.append(f"• {task_stats['critical_pending']} critical tasks pending")

        return "\n".join(lines)

    def close(self):
        if self._db:
            self._db.close()
            self._db = None
