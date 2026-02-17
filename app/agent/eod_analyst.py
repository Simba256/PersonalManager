"""End-of-day analyst — reviews the day's work and generates a forward plan.

Runs at 6 PM (or on demand). Analyzes:
  - Claude Code sessions from today
  - Task completions and status changes
  - Coding activity from Activity Tracker
  - Current state of tasks, goals, and blockers

Then generates:
  - What was accomplished today
  - Current standing (tasks, goals, blockers)
  - Concrete recommendations for tomorrow
"""

from __future__ import annotations

from datetime import datetime, timedelta, date
from typing import Optional
from loguru import logger

from app.llm.router import get_llm
from app.llm.prompts import SYSTEM_BASE


EOD_PROMPT_TEMPLATE = """Today: {date} ({weekday})

── TODAY'S CODING SESSIONS ──
{sessions_summary}

── TASK ACTIVITY TODAY ──
{task_activity}

── CURRENT TASK BOARD ──
Overdue ({overdue_count}):
{overdue_tasks}

High priority pending ({high_count}):
{high_tasks}

Other pending ({other_count}):
{other_tasks}

── CODING TIME TODAY ──
{coding_time}

── ACTIVE GOALS ──
{goals_summary}

── ACTIVE BLOCKERS ──
{blockers_summary}

Based on all of the above, provide an end-of-day analysis in this exact format:

## What Got Done Today
[Bullet points of actual accomplishments — be specific, reference project names and session content]

## Where Things Stand
[Current state of the most important work — what's in progress, what's blocked, what's overdue]

## Tomorrow's Focus
[3-5 specific, prioritized actions for tomorrow — reference actual task titles and deadlines]

## Watch Out For
[Any risks, blockers, or things that need attention soon]

Be direct and specific. Reference actual project names and task titles. Keep each section to 3-5 bullet points."""


class EODAnalyst:
    """Generates end-of-day analysis by combining session data, tasks, and activity."""

    def __init__(self, db=None):
        self._db = db
        self._llm = get_llm()

    def _get_db(self):
        if self._db is None:
            from app.database import SessionLocal
            self._db = SessionLocal()
        return self._db

    def analyze(self, target_date: Optional[date] = None) -> dict:
        """Run end-of-day analysis for a given date.

        Args:
            target_date: Date to analyze. Defaults to today.

        Returns:
            Dict with analysis_text, stats, and metadata
        """
        target = target_date or date.today()
        day_start = datetime.combine(target, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        db = self._get_db()

        # Import today's sessions first
        new_sessions = self._import_todays_sessions(day_start)

        # Gather all context
        sessions = self._get_todays_sessions(db, day_start, day_end)
        task_activity = self._get_task_activity(db, day_start, day_end)
        task_board = self._get_task_board(db)
        coding_time = self._get_coding_time(day_start, day_end)
        goals = self._get_goals(db)
        blockers = self._get_blockers(db)

        stats = {
            "date": target.isoformat(),
            "sessions_count": len(sessions),
            "new_sessions_imported": new_sessions,
            "tasks_completed_today": task_activity["completed_count"],
            "tasks_created_today": task_activity["created_count"],
            "coding_minutes": coding_time.get("total_minutes", 0),
            "overdue_count": len(task_board["overdue"]),
            "pending_count": len(task_board["pending"]),
        }

        analysis_text = None
        if self._llm.available:
            prompt = EOD_PROMPT_TEMPLATE.format(
                date=target.strftime("%B %d, %Y"),
                weekday=target.strftime("%A"),
                sessions_summary=self._format_sessions(sessions),
                task_activity=self._format_task_activity(task_activity),
                overdue_count=len(task_board["overdue"]),
                overdue_tasks=self._format_tasks(task_board["overdue"], limit=5),
                high_count=len(task_board["high_priority"]),
                high_tasks=self._format_tasks(task_board["high_priority"], limit=5),
                other_count=len(task_board["other"]),
                other_tasks=self._format_tasks(task_board["other"], limit=5),
                coding_time=self._format_coding_time(coding_time),
                goals_summary=self._format_goals(goals),
                blockers_summary=self._format_blockers(blockers),
            )
            analysis_text = self._llm.complete(
                prompt=prompt,
                system=SYSTEM_BASE,
                temperature=0.3,
                max_tokens=800,
            )
            if analysis_text:
                logger.info(f"EOD analysis generated for {target} (AI)")

        if not analysis_text:
            analysis_text = self._generate_fallback(task_activity, task_board, coding_time)
            logger.info(f"EOD analysis generated for {target} (fallback)")

        ai_generated = bool(self._llm.available and analysis_text and
                            analysis_text != self._generate_fallback(task_activity, task_board, coding_time))

        result = {
            "date": target.isoformat(),
            "analysis": analysis_text,
            "stats": stats,
            "ai_generated": ai_generated,
        }

        self._save(target, result)
        return result

    def get_saved(self, target_date: Optional[date] = None) -> Optional[dict]:
        """Load a previously saved EOD report."""
        target = target_date or date.today()
        path = self._report_path(target)
        if not path.exists():
            return None
        try:
            import json
            return json.loads(path.read_text())
        except Exception:
            return None

    def _report_path(self, target_date: date) -> "Path":
        from pathlib import Path
        from app.config import settings
        reports_dir = settings.data_dir / "eod"
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir / f"{target_date.isoformat()}.json"

    def _save(self, target_date: date, result: dict) -> None:
        import json
        try:
            path = self._report_path(target_date)
            # Make stats serializable
            safe = {**result, "stats": {k: str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v
                                         for k, v in result["stats"].items()}}
            path.write_text(json.dumps(safe, indent=2))
            logger.info(f"EOD report saved to {path}")
        except Exception as e:
            logger.warning(f"Could not save EOD report: {e}")

    # ── Data Gathering ────────────────────────────────────────────────────────

    def _import_todays_sessions(self, day_start: datetime) -> int:
        """Scan for new Claude Code sessions from today before analyzing."""
        try:
            from app.integrations.session_watcher import SessionWatcher
            watcher = SessionWatcher()
            result = watcher.scan_new(since=day_start)
            return result.get("total", 0)
        except Exception as e:
            logger.warning(f"Could not scan today's sessions: {e}")
            return 0

    def _get_todays_sessions(self, db, day_start: datetime, day_end: datetime) -> list:
        from app.models import Session as S, Project
        sessions = db.query(S).filter(
            S.started_at >= day_start,
            S.started_at < day_end,
        ).order_by(S.started_at.asc()).all()

        # Enrich with project names
        result = []
        for s in sessions:
            proj_name = None
            if s.project_id:
                proj = db.query(Project).filter(Project.id == s.project_id).first()
                proj_name = proj.name if proj else None
            elif s.working_directory:
                proj_name = s.working_directory.split("/")[-1]
            result.append({
                "project": proj_name or "unknown",
                "source": s.source,
                "started_at": s.started_at,
                "duration_minutes": s.duration_minutes,
                "summary": s.summary or "",
            })
        return result

    def _get_task_activity(self, db, day_start: datetime, day_end: datetime) -> dict:
        from app.models import Task
        completed = db.query(Task).filter(
            Task.completed_at >= day_start,
            Task.completed_at < day_end,
        ).all()
        created = db.query(Task).filter(
            Task.created_at >= day_start,
            Task.created_at < day_end,
        ).all()
        return {
            "completed": completed,
            "completed_count": len(completed),
            "created": created,
            "created_count": len(created),
        }

    def _get_task_board(self, db) -> dict:
        from app.models import Task
        from sqlalchemy import and_
        now = datetime.utcnow()

        overdue = db.query(Task).filter(
            and_(
                Task.due_date < now,
                Task.due_date.isnot(None),
                Task.status.notin_(["completed", "cancelled"])
            )
        ).order_by(Task.due_date.asc()).all()

        pending = db.query(Task).filter(
            Task.status.in_(["pending", "scheduled"])
        ).order_by(Task.due_date.asc().nullslast(), Task.priority.desc()).all()

        high_priority = [t for t in pending if t.priority in ("critical", "high")]
        other = [t for t in pending if t.priority not in ("critical", "high")]

        return {
            "overdue": overdue,
            "pending": pending,
            "high_priority": high_priority,
            "other": other,
        }

    def _get_coding_time(self, day_start: datetime, day_end: datetime) -> dict:
        try:
            from app.integrations.activity_tracker import ActivityTracker
            tracker = ActivityTracker()
            if not tracker.available:
                return {}
            items = tracker.get_coding_time(start_date=day_start, end_date=day_end)
            total = sum(i["total_minutes"] for i in items)
            return {"items": items, "total_minutes": total}
        except Exception as e:
            logger.warning(f"Could not get coding time: {e}")
            return {}

    def _get_goals(self, db) -> list:
        from app.models import Goal
        return db.query(Goal).filter(
            Goal.status.notin_(["completed", "abandoned"])
        ).all()

    def _get_blockers(self, db) -> list:
        from app.models import Blocker
        return db.query(Blocker).filter(Blocker.status == "open").all()

    # ── Formatters ────────────────────────────────────────────────────────────

    def _format_sessions(self, sessions: list) -> str:
        if not sessions:
            return "No Claude Code sessions recorded today."
        lines = []
        for s in sessions:
            dur = f"{s['duration_minutes']}min" if s.get("duration_minutes") else "?"
            summary = s["summary"][:120] if s["summary"] else "(no summary)"
            lines.append(f"  [{s['project']}] {dur} — {summary}")
        return "\n".join(lines)

    def _format_task_activity(self, activity: dict) -> str:
        lines = []
        if activity["completed"]:
            lines.append(f"Completed ({activity['completed_count']}):")
            for t in activity["completed"]:
                lines.append(f"  ✓ {t.title}")
        if activity["created"]:
            lines.append(f"Created ({activity['created_count']}):")
            for t in activity["created"]:
                lines.append(f"  + {t.title}")
        return "\n".join(lines) if lines else "No task changes recorded today."

    def _format_tasks(self, tasks: list, limit: int = 5) -> str:
        if not tasks:
            return "  (none)"
        lines = []
        for t in tasks[:limit]:
            due = t.due_date.strftime("%b %d") if t.due_date else "no deadline"
            est = f"{t.estimate_minutes}min" if t.estimate_minutes else "?"
            lines.append(f"  [{t.priority.upper()}] {t.title} | due: {due} | est: {est}")
        if len(tasks) > limit:
            lines.append(f"  ... and {len(tasks) - limit} more")
        return "\n".join(lines)

    def _format_coding_time(self, coding_time: dict) -> str:
        if not coding_time or not coding_time.get("items"):
            return "No coding activity recorded today."
        total_h = coding_time["total_minutes"] / 60
        lines = [f"Total: {total_h:.1f}h"]
        for item in coding_time["items"][:5]:
            proj = item["working_directory"].split("/")[-1]
            mins = item["total_minutes"]
            lines.append(f"  {proj}: {mins}min")
        return "\n".join(lines)

    def _format_goals(self, goals: list) -> str:
        if not goals:
            return "No active goals."
        lines = []
        for g in goals[:5]:
            target = g.target_date.strftime("%b %d, %Y") if g.target_date else "no deadline"
            lines.append(f"  • {g.title} | target: {target} | status: {g.status}")
        return "\n".join(lines)

    def _format_blockers(self, blockers: list) -> str:
        if not blockers:
            return "No active blockers."
        return "\n".join(f"  [{b.severity.upper()}] {b.description[:80]}" for b in blockers[:5])

    def _generate_fallback(self, task_activity: dict, task_board: dict, coding_time: dict) -> str:
        lines = ["End of Day Summary:"]
        c = task_activity["completed_count"]
        if c:
            lines.append(f"• Completed {c} task(s) today")
        else:
            lines.append("• No tasks completed today")

        total_h = coding_time.get("total_minutes", 0) / 60
        if total_h > 0:
            lines.append(f"• Coding time: {total_h:.1f}h")

        if task_board["overdue"]:
            lines.append(f"• {len(task_board['overdue'])} overdue task(s) need attention")

        if task_board["high_priority"]:
            lines.append(f"• Tomorrow: focus on {task_board['high_priority'][0].title}")

        return "\n".join(lines)

    def close(self):
        if self._db:
            self._db.close()
            self._db = None
