#!/usr/bin/env python3
"""Daily Planner — Scans all PROJECT_TRACKERs and pending tasks to generate a next-day plan.

Usage:
    python3 daily_planner.py              # Generate plan for tomorrow
    python3 daily_planner.py --today      # Generate plan for today
    python3 daily_planner.py --sync-index # Just update PROJECT_INDEX.md
"""

import argparse
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.tracker_parser import parse_tracker, find_trackers as _find_trackers

SHARED_ROOT = Path("/media/shared")
INDEX_PATH = SHARED_ROOT / "PROJECT_INDEX.md"
DB_PATH = Path(__file__).parent.parent / "data" / "agent.db"
PLANS_DIR = Path(__file__).parent.parent / "data" / "plans"

SEARCH_DIRS = [
    SHARED_ROOT / "personalProjects",
    SHARED_ROOT / "bld.ai",
    SHARED_ROOT / "Chameleon-Ideas",
    SHARED_ROOT / "Masters",
]


def find_trackers() -> list[dict]:
    """Find all PROJECT_TRACKER.md files under known project directories."""
    trackers = _find_trackers(SEARCH_DIRS)
    # Add relative path for index generation
    for t in trackers:
        try:
            t["path"] = str(Path(t["full_path"]).relative_to(SHARED_ROOT))
        except ValueError:
            t["path"] = t["full_path"]
    return trackers


def get_tasks_from_db() -> dict:
    """Get pending/overdue tasks from PersonalManager database."""
    if not DB_PATH.exists():
        return {"overdue": [], "due_today": [], "due_tomorrow": [], "upcoming": []}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    results = {"overdue": [], "due_today": [], "due_tomorrow": [], "upcoming": []}

    rows = conn.execute(
        """
        SELECT t.id, t.title, t.priority, t.due_date, p.name as project_name
        FROM tasks t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE t.status IN ('pending', 'in_progress')
        ORDER BY
            CASE t.priority
                WHEN 'critical' THEN 0
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END,
            t.due_date ASC
        """
    ).fetchall()

    for row in rows:
        task = dict(row)
        due = task.get("due_date")
        if due:
            due = due[:10]  # Strip time component, keep YYYY-MM-DD
            task["due_date"] = due

        if due and due < today:
            days_overdue = (datetime.strptime(today, "%Y-%m-%d") - datetime.strptime(due, "%Y-%m-%d")).days
            task["days_overdue"] = days_overdue
            results["overdue"].append(task)
        elif due == today:
            results["due_today"].append(task)
        elif due == tomorrow:
            results["due_tomorrow"].append(task)
        elif due:
            results["upcoming"].append(task)
        else:
            results["upcoming"].append(task)

    conn.close()
    return results


def generate_plan(target_date: str, trackers: list[dict], tasks: dict) -> str:
    """Generate the daily plan markdown."""
    lines = [
        f"# Daily Plan — {target_date}",
        f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    # Overdue tasks (urgent)
    if tasks["overdue"]:
        lines.append(f"## Overdue ({len(tasks['overdue'])} tasks)")
        lines.append("")
        for t in tasks["overdue"][:10]:
            lines.append(
                f"- [{t['priority'].upper()}] **{t['title']}** "
                f"({t['project_name'] or 'No project'}) — {t['days_overdue']}d overdue"
            )
        if len(tasks["overdue"]) > 10:
            lines.append(f"- ... and {len(tasks['overdue']) - 10} more")
        lines.append("")

    # Due today
    if tasks["due_today"]:
        lines.append(f"## Due Today ({len(tasks['due_today'])} tasks)")
        lines.append("")
        for t in tasks["due_today"]:
            lines.append(
                f"- [{t['priority'].upper()}] **{t['title']}** "
                f"({t['project_name'] or 'No project'})"
            )
        lines.append("")

    # Due tomorrow
    if tasks["due_tomorrow"]:
        lines.append(f"## Due Tomorrow ({len(tasks['due_tomorrow'])} tasks)")
        lines.append("")
        for t in tasks["due_tomorrow"]:
            lines.append(
                f"- [{t['priority'].upper()}] **{t['title']}** "
                f"({t['project_name'] or 'No project'})"
            )
        lines.append("")

    # Project status from trackers
    lines.append("## Project Status")
    lines.append("")

    active_trackers = [t for t in trackers if "Active" in t["status"]]
    for t in active_trackers:
        project_name = Path(t["path"]).name
        lines.append(f"### {project_name}")
        lines.append(f"_{t['summary']}_")

        if t["in_progress"]:
            for item in t["in_progress"][:3]:
                lines.append(f"- [ ] {item}")
        else:
            lines.append("- No active tasks in tracker")

        if t["blockers"]:
            lines.append(f"- **BLOCKED**: {t['blockers'][0]}")

        lines.append("")

    # Upcoming tasks (next 7 days)
    week_from_now = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    upcoming_soon = [
        t for t in tasks["upcoming"]
        if t.get("due_date") and t["due_date"] <= week_from_now
    ]
    if upcoming_soon:
        lines.append(f"## Coming Up (next 7 days)")
        lines.append("")
        for t in upcoming_soon[:10]:
            lines.append(
                f"- [{t['priority'].upper()}] **{t['title']}** "
                f"({t['project_name'] or 'No project'}) — due {t['due_date']}"
            )
        lines.append("")

    return "\n".join(lines)


def update_index(trackers: list[dict]):
    """Regenerate PROJECT_INDEX.md from discovered trackers."""
    lines = [
        "# Project Index",
        "",
        f"> Last updated: {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "Central registry of all projects with PROJECT_TRACKER.md files. Each project's tracker is the source of truth for detailed status.",
        "",
        "## Projects",
        "",
        "| Project | Path | Status | Last Updated |",
        "|---------|------|--------|--------------|",
    ]

    for t in sorted(trackers, key=lambda x: x["path"]):
        name = Path(t["path"]).name
        lines.append(f"| {name} | `{t['path']}/` | {t['status']} | {t['last_updated']} |")

    lines.append("")
    lines.append("## Quick Status")
    lines.append("")

    for t in sorted(trackers, key=lambda x: x["path"]):
        name = Path(t["path"]).name
        lines.append(f"### {name}")
        lines.append(f"{t['summary']}")

        if t["in_progress"]:
            lines.append(f"- **In Progress**: {t['in_progress'][0]}")
        if t["blockers"]:
            lines.append(f"- **Blocker**: {t['blockers'][0]}")
        elif not t["blockers"]:
            lines.append("- **Blocker**: None")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## How to Update",
        "When working on any project, update both:",
        "1. The project's own `PROJECT_TRACKER.md`",
        "2. Run `python3 daily_planner.py --sync-index` to regenerate this index",
    ])

    INDEX_PATH.write_text("\n".join(lines) + "\n")
    print(f"Updated {INDEX_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Daily Planner")
    parser.add_argument("--today", action="store_true", help="Generate plan for today")
    parser.add_argument("--sync-index", action="store_true", help="Update PROJECT_INDEX.md")
    args = parser.parse_args()

    print("Scanning PROJECT_TRACKER.md files...")
    trackers = find_trackers()
    print(f"Found {len(trackers)} projects")

    if args.sync_index:
        update_index(trackers)
        return

    # Generate plan
    if args.today:
        target_date = datetime.now().strftime("%Y-%m-%d")
    else:
        target_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    print("Reading tasks from database...")
    tasks = get_tasks_from_db()
    print(
        f"Tasks: {len(tasks['overdue'])} overdue, "
        f"{len(tasks['due_today'])} today, "
        f"{len(tasks['due_tomorrow'])} tomorrow, "
        f"{len(tasks['upcoming'])} upcoming"
    )

    plan = generate_plan(target_date, trackers, tasks)

    # Save plan
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    plan_file = PLANS_DIR / f"plan-{target_date}.md"
    plan_file.write_text(plan)
    print(f"\nPlan saved to: {plan_file}")
    print(f"\n{'=' * 60}")
    print(plan)


if __name__ == "__main__":
    main()
