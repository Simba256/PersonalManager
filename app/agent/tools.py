"""Agent tools — database actions the LLM can call during chat."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger

# ── Tool definitions (passed to LLM) ─────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark a task as completed. Use when the user says they finished, completed, or did a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "The task ID to mark complete"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Create a new task. Every task MUST be linked to a project. Use project_id (integer) from the context, or project_name (string) to match by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title (required — must always be provided)"},
                    "project_id": {"type": "integer", "description": "Project ID to link this task to (preferred — use the ID from context)"},
                    "project_name": {"type": "string", "description": "Project name to link this task to (used if project_id is unknown)"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Priority level",
                    },
                    "estimate_minutes": {"type": "integer", "description": "Estimated time in minutes"},
                    "due_date": {"type": "string", "description": "Due date as YYYY-MM-DD or relative like 'tomorrow', 'friday'"},
                    "notes": {"type": "string", "description": "Any additional context or description"},
                },
                "required": ["title", "project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update an existing task's priority, due date, estimate, or status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "The task ID to update"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "blocked", "cancelled"]},
                    "due_date": {"type": "string", "description": "New due date as YYYY-MM-DD"},
                    "estimate_minutes": {"type": "integer"},
                    "description": {"type": "string", "description": "Update the task description/notes"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_blocker",
            "description": "Log a blocker or problem the user is facing. Use when they mention being stuck, blocked, or having an issue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "What the blocker or problem is"},
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "How serious is this blocker",
                    },
                    "task_id": {"type": "integer", "description": "Related task ID if applicable"},
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_goal",
            "description": "Add a new goal. Use when the user mentions a longer-term objective or aspiration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Goal title"},
                    "target_date": {"type": "string", "description": "Target date as YYYY-MM-DD"},
                    "category": {"type": "string", "description": "Category e.g. education, career, health, project"},
                    "description": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "Save an important note, decision, or piece of information to memory. Use when the user shares something worth remembering that doesn't fit tasks or goals.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The note content"},
                    "category": {"type": "string", "description": "Category e.g. 'decision', 'context', 'idea', 'update'"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_reminder",
            "description": "Create a reminder or event in Google Calendar. Use when the user asks to be reminded about something, schedule something, or add something to their calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Event/reminder title"},
                    "date": {"type": "string", "description": "Date as YYYY-MM-DD or relative like 'tomorrow', 'friday', 'next monday'"},
                    "time": {"type": "string", "description": "Time as HH:MM (24h), e.g. '09:00', '14:30'. Omit for all-day reminders."},
                    "duration_minutes": {"type": "integer", "description": "Duration in minutes (default 30)"},
                    "description": {"type": "string", "description": "Optional event description or notes"},
                },
                "required": ["title", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders in a directory on the user's machine. Use when the user asks you to explore a folder or find files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the directory to list"},
                    "recursive": {"type": "boolean", "description": "If true, list files in subdirectories too (max depth 3)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a text file on the user's machine. Use when the user asks you to read, analyze, or summarize a file. Read-only — cannot write or modify files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file to read"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_project",
            "description": "Create a new project. Use when the user mentions a new project, codebase, or area of work that doesn't have a project yet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Project name"},
                    "description": {"type": "string", "description": "What the project is about"},
                    "path": {"type": "string", "description": "Absolute path to the project on disk, if known"},
                    "tags": {"type": "string", "description": "Comma-separated tags e.g. 'web,python,freelance'"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_project",
            "description": "Delete a project by ID or name. Tasks linked to it will be unlinked but not deleted. Use only when the user explicitly asks to remove a project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "Project ID to delete"},
                    "project_name": {"type": "string", "description": "Project name to delete (used if project_id unknown)"},
                },
            },
        },
    },
]


# ── Tool executor ─────────────────────────────────────────────────────────────

def execute_tool(name: str, arguments: dict, db) -> str:
    """Execute a tool call and return a human-readable result string."""
    try:
        if name == "complete_task":
            return _complete_task(arguments, db)
        elif name == "add_task":
            return _add_task(arguments, db)
        elif name == "update_task":
            return _update_task(arguments, db)
        elif name == "add_blocker":
            return _add_blocker(arguments, db)
        elif name == "add_goal":
            return _add_goal(arguments, db)
        elif name == "save_note":
            return _save_note(arguments)
        elif name == "create_calendar_reminder":
            return _create_calendar_reminder(arguments)
        elif name == "create_project":
            return _create_project(arguments, db)
        elif name == "delete_project":
            return _delete_project(arguments, db)
        elif name == "list_directory":
            return _list_directory(arguments)
        elif name == "read_file":
            return _read_file(arguments)
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        return f"Error: {e}"


def _complete_task(args: dict, db) -> str:
    from app.services.task_service import TaskService
    service = TaskService(db)
    task = service.set_status(args["task_id"], "completed")
    if not task:
        return f"Task #{args['task_id']} not found."
    return f"Marked task #{task.id} as completed: '{task.title}'"


def _add_task(args: dict, db) -> str:
    from app.services.task_service import TaskService
    from app.calendar.parser import parse_relative_date
    from app.models import Project

    # Accept title under several common field names the LLM might use
    title = args.get("title") or args.get("name") or args.get("task_title") or args.get("task")
    if not title:
        logger.warning(f"add_task called without title. Args keys: {list(args.keys())}")
        return f"Error: task title is required. Received fields: {list(args.keys())}"

    # Resolve project — required
    project_id = args.get("project_id")
    if not project_id and args.get("project_name"):
        name = args["project_name"].lower()
        project = db.query(Project).filter(
            Project.name.ilike(f"%{name}%")
        ).first()
        if project:
            project_id = project.id
        else:
            return f"Error: no project found matching '{args['project_name']}'. Check available projects and use project_id."
    if not project_id:
        projects = db.query(Project).filter(Project.active == True).all()
        names = ", ".join(f"#{p.id} {p.name}" for p in projects[:10])
        return f"Error: every task must be linked to a project. Available projects: {names}"

    due_date = None
    if args.get("due_date"):
        due_date = parse_relative_date(args["due_date"])
        if not due_date:
            try:
                due_date = datetime.strptime(args["due_date"], "%Y-%m-%d")
            except ValueError:
                pass

    service = TaskService(db)
    task = service.create(
        title=title,
        priority=args.get("priority", "medium"),
        estimate_minutes=args.get("estimate_minutes"),
        due_date=due_date,
        description=args.get("notes") or args.get("description"),
        project_id=project_id,
    )
    due_str = f", due {due_date.strftime('%b %d')}" if due_date else ""
    return f"Created task #{task.id}: '{task.title}' [{task.priority}]{due_str} → project #{project_id}"


def _update_task(args: dict, db) -> str:
    from app.services.task_service import TaskService

    service = TaskService(db)
    task_id = args.pop("task_id")

    # Handle due_date string
    if "due_date" in args and args["due_date"]:
        try:
            args["due_date"] = datetime.strptime(args["due_date"], "%Y-%m-%d")
        except ValueError:
            from app.calendar.parser import parse_relative_date
            args["due_date"] = parse_relative_date(args["due_date"])

    # Split status from other fields — set_status has side effects
    status = args.pop("status", None)
    if status:
        service.set_status(task_id, status)

    updates = {k: v for k, v in args.items() if v is not None}
    task = service.update(task_id, **updates) if updates else service.get(task_id)

    if not task:
        return f"Task #{task_id} not found."

    changed = list(args.keys()) + ([f"status={status}"] if status else [])
    return f"Updated task #{task_id} '{task.title}': {', '.join(changed)}"


def _add_blocker(args: dict, db) -> str:
    from app.models import Blocker
    blocker = Blocker(
        description=args["description"],
        severity=args.get("severity", "medium"),
        task_id=args.get("task_id"),
    )
    db.add(blocker)
    db.commit()
    return f"Logged blocker: '{args['description'][:80]}' [{args.get('severity', 'medium')}]"


def _add_goal(args: dict, db) -> str:
    from app.models import Goal

    target_date = None
    if args.get("target_date"):
        try:
            target_date = datetime.strptime(args["target_date"], "%Y-%m-%d")
        except ValueError:
            pass

    goal = Goal(
        title=args["title"],
        target_date=target_date,
        category=args.get("category"),
        description=args.get("description"),
        status="active",
    )
    db.add(goal)
    db.commit()
    return f"Added goal: '{goal.title}'" + (f", target: {target_date.strftime('%b %d, %Y')}" if target_date else "")


def _create_calendar_reminder(args: dict) -> str:
    from app.calendar.google import GoogleCalendarClient
    from app.calendar.parser import parse_relative_date

    # Parse date
    date_str = args["date"]
    parsed_dt = parse_relative_date(date_str)
    if not parsed_dt:
        try:
            parsed_dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return f"Could not parse date: '{date_str}'. Use YYYY-MM-DD or relative like 'tomorrow'."

    # Apply time if provided, otherwise default to 9:00 AM
    time_str = args.get("time")
    if time_str:
        try:
            h, m = map(int, time_str.split(":"))
            parsed_dt = parsed_dt.replace(hour=h, minute=m, second=0, microsecond=0)
        except Exception:
            return f"Could not parse time: '{time_str}'. Use HH:MM format."
    else:
        parsed_dt = parsed_dt.replace(hour=9, minute=0, second=0, microsecond=0)

    duration = args.get("duration_minutes", 30)
    end_dt = parsed_dt + timedelta(minutes=duration)

    from app.calendar.google import _local_tz
    event_data = {
        "summary": args["title"],
        "description": args.get("description", ""),
        "start": {"dateTime": parsed_dt.isoformat(), "timeZone": _local_tz()},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": _local_tz()},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 10},
            ],
        },
        "extendedProperties": {"private": {"agent_type": "reminder"}},
    }

    client = GoogleCalendarClient()
    if not client.available:
        return "Google Calendar not configured — reminder not created."
    try:
        if not client.authenticate():
            return "Google Calendar authentication failed."
        event = client.create_event("primary", event_data)
        if event:
            dt_str = parsed_dt.strftime("%b %d at %H:%M")
            return f"Created calendar reminder: '{args['title']}' on {dt_str}"
        return "Failed to create calendar event."
    except Exception as e:
        logger.error(f"Calendar reminder failed: {e}")
        return f"Error creating calendar reminder: {e}"


def _create_project(args: dict, db) -> str:
    from app.models import Project

    name = args.get("name", "").strip()
    if not name:
        return "Error: project name is required."

    existing = db.query(Project).filter(Project.name.ilike(name)).first()
    if existing:
        return f"Project already exists: #{existing.id} '{existing.name}'"

    project = Project(
        name=name,
        description=args.get("description"),
        repo_path=args.get("path"),
        tags=args.get("tags"),
        active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(project)
    db.commit()
    return f"Created project #{project.id}: '{project.name}'" + (f" at {project.repo_path}" if project.repo_path else "")


def _delete_project(args: dict, db) -> str:
    from app.models import Project, Task, Session as S

    project = None
    if args.get("project_id"):
        project = db.query(Project).filter(Project.id == args["project_id"]).first()
    elif args.get("project_name"):
        project = db.query(Project).filter(
            Project.name.ilike(f"%{args['project_name']}%")
        ).first()

    if not project:
        return f"No project found matching the given id/name."

    name, pid = project.name, project.id

    # Unlink tasks and sessions rather than cascade-deleting them
    unlinked_tasks = db.query(Task).filter(Task.project_id == pid).update({"project_id": None})
    unlinked_sessions = db.query(S).filter(S.project_id == pid).update({"project_id": None})

    db.delete(project)
    db.commit()
    return f"Deleted project #{pid} '{name}' — {unlinked_tasks} tasks and {unlinked_sessions} sessions unlinked."


def _save_note(args: dict) -> str:
    from pathlib import Path
    from app.config import settings

    notes_dir = settings.data_dir / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    note_file = notes_dir / f"{today}.md"

    timestamp = datetime.now().strftime("%H:%M")
    category = args.get("category", "note")
    entry = f"\n## {timestamp} [{category}]\n{args['content']}\n"

    with open(note_file, "a") as f:
        f.write(entry)

    return f"Note saved [{category}]: '{args['content'][:80]}'"


def _list_directory(args: dict) -> str:
    import os
    from pathlib import Path

    path = Path(args["path"]).expanduser()
    if not path.exists():
        return f"Path does not exist: {path}"
    if not path.is_dir():
        return f"Not a directory: {path}"

    recursive = args.get("recursive", False)
    entries = []

    if recursive:
        for root, dirs, files in os.walk(path):
            # Skip hidden dirs and common junk
            dirs[:] = [d for d in sorted(dirs) if not d.startswith(".") and d not in ("__pycache__", "node_modules", ".git")]
            depth = len(Path(root).relative_to(path).parts)
            if depth > 3:
                continue
            indent = "  " * depth
            rel_root = Path(root).relative_to(path)
            if depth > 0:
                entries.append(f"{indent[:-2]}{rel_root.name}/")
            for f in sorted(files):
                if not f.startswith("."):
                    entries.append(f"{indent}{f}")
    else:
        for item in sorted(path.iterdir()):
            if item.name.startswith("."):
                continue
            suffix = "/" if item.is_dir() else ""
            entries.append(f"  {item.name}{suffix}")

    if not entries:
        return f"Directory is empty: {path}"
    return f"Contents of {path}:\n" + "\n".join(entries[:200])


def _read_file(args: dict) -> str:
    from pathlib import Path

    path = Path(args["path"]).expanduser()
    if not path.exists():
        return f"File does not exist: {path}"
    if not path.is_file():
        return f"Not a file: {path}"

    # Size guard: skip files over 100KB
    size = path.stat().st_size
    if size > 100_000:
        return f"File too large to read ({size // 1024}KB). Only files under 100KB are supported."

    # Skip obvious binary formats
    binary_suffixes = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".tar", ".gz",
                       ".exe", ".bin", ".pyc", ".db", ".sqlite"}
    if path.suffix.lower() in binary_suffixes:
        return f"Binary file skipped ({path.suffix}). Only text files can be read."

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        # Trim to ~8000 chars to keep LLM context manageable
        if len(content) > 8000:
            content = content[:8000] + f"\n\n[... truncated, {len(content) - 8000} more chars ...]"
        return f"File: {path}\n\n{content}"
    except Exception as e:
        return f"Could not read file: {e}"
