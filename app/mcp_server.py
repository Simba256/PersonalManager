"""MCP server for Personal Manager.

Claude Code connects via stdio; pm chat continues calling execute_tool() directly.
Both hit the same SQLite DB so data is always consistent.
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from datetime import datetime, date
from typing import Optional

# ── Path / cwd bootstrap ───────────────────────────────────────────────────────
# MCP server is launched from an arbitrary cwd by Claude Code.
# os.chdir must run before any app.* import so pydantic-settings finds .env.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_DIR = os.path.join(_PROJECT_ROOT, "app")
os.chdir(_PROJECT_ROOT)
# When Python runs this script it sets sys.path[0] to the script's directory (app/).
# That makes `import calendar` find app/calendar/ instead of the stdlib's calendar.
# Fix: remove the app/ dir and any empty-string (cwd) entries; add project root at end.
sys.path = [p for p in sys.path if p not in ("", _APP_DIR)]
if _PROJECT_ROOT not in sys.path:
    sys.path.append(_PROJECT_ROOT)

# ── Imports ────────────────────────────────────────────────────────────────────
from mcp.server.fastmcp import FastMCP
from app.database import SessionLocal
from app.agent.tools import execute_tool

mcp = FastMCP("personal-manager")


# ── DB helper ─────────────────────────────────────────────────────────────────

@contextmanager
def _db():
    """Open a SessionLocal, yield it, then close — one per tool call."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _strip_none(d: dict) -> dict:
    """Remove keys whose value is None (avoids optional-field edge cases in handlers)."""
    return {k: v for k, v in d.items() if v is not None}


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def complete_task(task_id: int) -> str:
    """Mark a task as completed."""
    with _db() as db:
        return execute_tool("complete_task", {"task_id": task_id}, db)


@mcp.tool()
def add_task(
    title: str,
    project_id: int,
    priority: Optional[str] = None,
    estimate_minutes: Optional[int] = None,
    due_date: Optional[str] = None,
    notes: Optional[str] = None,
    project_name: Optional[str] = None,
) -> str:
    """Create a new task linked to a project."""
    args = _strip_none({
        "title": title,
        "project_id": project_id,
        "priority": priority,
        "estimate_minutes": estimate_minutes,
        "due_date": due_date,
        "notes": notes,
        "project_name": project_name,
    })
    with _db() as db:
        return execute_tool("add_task", args, db)


@mcp.tool()
def update_task(
    task_id: int,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    due_date: Optional[str] = None,
    estimate_minutes: Optional[int] = None,
    description: Optional[str] = None,
) -> str:
    """Update an existing task's priority, due date, estimate, status, or description."""
    args = _strip_none({
        "task_id": task_id,
        "priority": priority,
        "status": status,
        "due_date": due_date,
        "estimate_minutes": estimate_minutes,
        "description": description,
    })
    with _db() as db:
        return execute_tool("update_task", args, db)


@mcp.tool()
def add_blocker(
    description: str,
    severity: Optional[str] = None,
    task_id: Optional[int] = None,
) -> str:
    """Log a blocker or problem."""
    args = _strip_none({
        "description": description,
        "severity": severity,
        "task_id": task_id,
    })
    with _db() as db:
        return execute_tool("add_blocker", args, db)


@mcp.tool()
def add_goal(
    title: str,
    target_date: Optional[str] = None,
    category: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """Add a new long-term goal."""
    args = _strip_none({
        "title": title,
        "target_date": target_date,
        "category": category,
        "description": description,
    })
    with _db() as db:
        return execute_tool("add_goal", args, db)


@mcp.tool()
def save_note(content: str, category: Optional[str] = None) -> str:
    """Save an important note, decision, or piece of information."""
    args = _strip_none({"content": content, "category": category})
    with _db() as db:
        return execute_tool("save_note", args, db)


@mcp.tool()
def create_calendar_reminder(
    title: str,
    date: str,
    time: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    description: Optional[str] = None,
) -> str:
    """Create a reminder or event in Google Calendar."""
    args = _strip_none({
        "title": title,
        "date": date,
        "time": time,
        "duration_minutes": duration_minutes,
        "description": description,
    })
    with _db() as db:
        return execute_tool("create_calendar_reminder", args, db)


@mcp.tool()
def list_directory(path: str, recursive: Optional[bool] = None) -> str:
    """List files and folders in a directory."""
    args = _strip_none({"path": path, "recursive": recursive})
    with _db() as db:
        return execute_tool("list_directory", args, db)


@mcp.tool()
def read_file(path: str) -> str:
    """Read the contents of a text file."""
    with _db() as db:
        return execute_tool("read_file", {"path": path}, db)


@mcp.tool()
def create_project(
    name: str,
    description: Optional[str] = None,
    path: Optional[str] = None,
    tags: Optional[str] = None,
) -> str:
    """Create a new project."""
    args = _strip_none({
        "name": name,
        "description": description,
        "path": path,
        "tags": tags,
    })
    with _db() as db:
        return execute_tool("create_project", args, db)


@mcp.tool()
def delete_project(
    project_id: Optional[int] = None,
    project_name: Optional[str] = None,
) -> str:
    """Delete a project by ID or name. Tasks are unlinked but not deleted."""
    if project_id is None and project_name is None:
        return "Error: provide project_id or project_name to identify which project to delete."
    args = _strip_none({"project_id": project_id, "project_name": project_name})
    with _db() as db:
        return execute_tool("delete_project", args, db)


# ── Resources ──────────────────────────────────────────────────────────────────

@mcp.resource("tasks://pending")
def resource_pending_tasks() -> str:
    """All pending and in-progress tasks as a markdown table."""
    from app.models import Task, Project

    with _db() as db:
        tasks = (
            db.query(Task)
            .filter(Task.status.in_(["pending", "in_progress", "scheduled"]))
            .order_by(Task.priority.desc(), Task.due_date.asc().nullslast())
            .all()
        )

        if not tasks:
            return "No pending tasks."

        lines = ["| ID | Title | Priority | Due | Project |",
                 "|----|-------|----------|-----|---------|"]
        for t in tasks:
            due = t.due_date.strftime("%Y-%m-%d") if t.due_date else "—"
            proj = t.project.name if t.project else "—"
            title = (t.title[:50] + "…") if len(t.title) > 50 else t.title
            lines.append(f"| {t.id} | {title} | {t.priority} | {due} | {proj} |")

        return "## Pending Tasks\n\n" + "\n".join(lines)


@mcp.resource("tasks://overdue")
def resource_overdue_tasks() -> str:
    """Overdue tasks with days overdue as a markdown table."""
    from app.models import Task

    now = datetime.utcnow()

    with _db() as db:
        tasks = (
            db.query(Task)
            .filter(
                Task.status.in_(["pending", "in_progress", "scheduled"]),
                Task.due_date < now,
                Task.due_date.isnot(None),
            )
            .order_by(Task.due_date.asc())
            .all()
        )

        if not tasks:
            return "No overdue tasks."

        lines = ["| ID | Title | Priority | Due | Days Overdue | Project |",
                 "|----|-------|----------|-----|--------------|---------|"]
        for t in tasks:
            days = (now - t.due_date).days
            due = t.due_date.strftime("%Y-%m-%d")
            proj = t.project.name if t.project else "—"
            title = (t.title[:50] + "…") if len(t.title) > 50 else t.title
            lines.append(f"| {t.id} | {title} | {t.priority} | {due} | {days} | {proj} |")

        return "## Overdue Tasks\n\n" + "\n".join(lines)


@mcp.resource("projects://list")
def resource_projects() -> str:
    """All active projects with IDs, task counts, and paths."""
    from app.models import Project, Task
    from sqlalchemy import func

    with _db() as db:
        projects = (
            db.query(Project)
            .filter(Project.active == True)
            .order_by(Project.name.asc())
            .all()
        )

        if not projects:
            return "No active projects."

        lines = ["| ID | Name | Open Tasks | Path | Tags |",
                 "|----|------|------------|------|------|"]
        for p in projects:
            open_tasks = sum(
                1 for t in p.tasks
                if t.status in ("pending", "in_progress", "scheduled")
            )
            path = p.repo_path or "—"
            tags = p.tags or "—"
            lines.append(f"| {p.id} | {p.name} | {open_tasks} | {path} | {tags} |")

        return "## Active Projects\n\n" + "\n".join(lines)


@mcp.resource("goals://active")
def resource_active_goals() -> str:
    """All active goals as a markdown table."""
    from app.models import Goal

    with _db() as db:
        goals = (
            db.query(Goal)
            .filter(Goal.status == "active")
            .order_by(Goal.target_date.asc().nullslast())
            .all()
        )

        if not goals:
            return "No active goals."

        lines = ["| ID | Title | Category | Target Date | Progress |",
                 "|----|-------|----------|-------------|----------|"]
        for g in goals:
            target = g.target_date.strftime("%Y-%m-%d") if g.target_date else "—"
            cat = g.category or "—"
            title = (g.title[:50] + "…") if len(g.title) > 50 else g.title
            lines.append(f"| {g.id} | {title} | {cat} | {target} | {g.progress_percent}% |")

        return "## Active Goals\n\n" + "\n".join(lines)


@mcp.resource("eod://today")
def resource_eod_today() -> str:
    """Today's end-of-day report, or a message if none has been generated yet."""
    from app.config import settings
    from pathlib import Path

    today = date.today().strftime("%Y-%m-%d")
    eod_dir = settings.data_dir / "eod"
    eod_file = eod_dir / f"{today}.md"

    if eod_file.exists():
        content = eod_file.read_text(encoding="utf-8", errors="replace")
        return f"## EOD Report — {today}\n\n{content}"

    return f"No EOD report for {today} yet. Run `pm eod` to generate one."


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
