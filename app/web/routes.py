"""FastAPI API routes for Personal Manager."""

from __future__ import annotations
import asyncio
import json
import os
from datetime import datetime
from typing import Optional, AsyncIterator
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.schemas import TaskCreate, TaskUpdate, TaskResponse, GoalCreate, GoalResponse, ProjectResponse
from app.services.task_service import TaskService
from app.services.project_service import ProjectService
from app.models import Goal, Project
from app.integrations.activity_tracker import ActivityTracker

# ── Tasks ─────────────────────────────────────────────────────────────────────

tasks_router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@tasks_router.get("")
async def list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    project_id: Optional[int] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    service = TaskService(db)
    tasks, total = service.list(
        status=status, priority=priority,
        project_id=project_id, limit=limit, offset=offset
    )
    return {
        "success": True,
        "data": {
            "tasks": [_task_to_dict(t) for t in tasks],
            "total": total,
            "limit": limit,
            "offset": offset
        }
    }


@tasks_router.post("", status_code=201)
async def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    service = TaskService(db)
    created = service.create(**task.model_dump(exclude_none=True))
    return {"success": True, "data": _task_to_dict(created), "message": "Task created"}


@tasks_router.get("/{task_id}")
async def get_task(task_id: int, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "data": _task_to_dict(task)}


@tasks_router.put("/{task_id}")
async def update_task(task_id: int, task: TaskUpdate, db: Session = Depends(get_db)):
    service = TaskService(db)
    updated = service.update(task_id, **task.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "data": _task_to_dict(updated), "message": "Task updated"}


@tasks_router.patch("/{task_id}/status")
async def update_task_status(task_id: int, body: dict, db: Session = Depends(get_db)):
    status = body.get("status")
    if not status:
        raise HTTPException(status_code=400, detail="status field required")
    service = TaskService(db)
    task = service.set_status(task_id, status)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "data": _task_to_dict(task), "message": f"Task marked as {status}"}


@tasks_router.delete("/{task_id}")
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    service = TaskService(db)
    if not service.delete(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "message": "Task deleted"}


def _task_to_dict(task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "estimate_minutes": task.estimate_minutes,
        "actual_minutes": task.actual_minutes,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "energy_level": task.energy_level,
        "context_tags": task.context_tags,
        "project_id": task.project_id,
        "blocker_id": task.blocker_id,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


# ── Projects ──────────────────────────────────────────────────────────────────

projects_router = APIRouter(prefix="/api/projects", tags=["projects"])


@projects_router.get("")
async def list_projects(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    service = ProjectService(db)
    projects = service.list(active_only=active_only)
    return {
        "success": True,
        "data": {"projects": [_project_to_dict(p) for p in projects]}
    }


@projects_router.post("", status_code=201)
async def create_project(name: str, repo_path: Optional[str] = None, db: Session = Depends(get_db)):
    service = ProjectService(db)
    project = service.create(name=name, repo_path=repo_path)
    return {"success": True, "data": _project_to_dict(project), "message": "Project created"}


@projects_router.get("/discover")
async def discover_projects(db: Session = Depends(get_db)):
    """Discover git repositories and create projects automatically."""
    from app.config import settings
    import yaml
    from pathlib import Path

    # Load search paths from config, fall back to auto-detected paths
    default_paths = [
        "/media/shared/personalProjects",
        "/media/shared/bld.ai",
        "/media/shared/Chameleon-Ideas",
        "/media/shared/Chameleon Ideas",
        "/media/shared/Masters",
        "/media/shared/HamzaHasan",
        str(Path.home()),
    ]
    search_paths = [p for p in default_paths if Path(p).exists()]
    config_path = Path("config.yaml")
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
            configured = cfg.get("scheduler", {}).get("jobs", {}).get(
                "git_monitor", {}
            ).get("search_paths")
            if configured:
                search_paths = configured

    service = ProjectService(db)
    projects = service.discover_from_filesystem(search_paths)

    return {
        "success": True,
        "data": {
            "discovered": len(projects),
            "projects": [_project_to_dict(p) for p in projects]
        },
        "message": f"Discovered {len(projects)} projects"
    }


@projects_router.post("/sessions/backfill")
async def backfill_session_links(db: Session = Depends(get_db)):
    """Link unmatched sessions to projects using working_directory field."""
    from app.models import Session as SessionModel, Project
    from pathlib import Path as FsPath

    projects = db.query(Project).filter(Project.repo_path != None).all()
    project_by_path = {}
    for p in projects:
        try:
            project_by_path[str(FsPath(p.repo_path).resolve())] = p
        except Exception:
            pass

    unlinked = db.query(SessionModel).filter(SessionModel.project_id == None).all()
    linked = 0

    for session in unlinked:
        if not session.working_directory:
            continue
        try:
            normalized = str(FsPath(session.working_directory).resolve())
        except Exception:
            continue
        project = project_by_path.get(normalized)
        if project:
            session.project_id = project.id
            linked += 1

    if linked:
        db.commit()

    return {
        "success": True,
        "data": {"linked": linked, "still_unlinked": len(unlinked) - linked},
        "message": f"Linked {linked} sessions to projects"
    }


@projects_router.get("/{project_id}")
async def get_project(project_id: int, db: Session = Depends(get_db)):
    service = ProjectService(db)
    project = service.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"success": True, "data": _project_to_dict(project, include_sessions=True)}


def _project_to_dict(project, include_sessions: bool = False) -> dict:
    data = {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "repo_path": project.repo_path,
        "repo_url": project.repo_url,
        "active": project.active,
        "tags": project.tags,
        "primary_language": project.primary_language,
        "frameworks": project.frameworks,
        "last_activity_at": project.last_activity_at.isoformat() if project.last_activity_at else None,
        "total_commits": project.total_commits,
        "total_sessions": project.total_sessions,
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }
    if include_sessions:
        data["recent_sessions"] = [
            {
                "id": s.id,
                "source": s.source,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "duration_minutes": s.duration_minutes,
                "summary": s.summary
            }
            for s in sorted(project.sessions, key=lambda s: s.started_at, reverse=True)[:5]
        ]
    return data


# ── Activity ──────────────────────────────────────────────────────────────────

activity_router = APIRouter(prefix="/api/activity", tags=["activity"])


@activity_router.get("/today")
async def get_today_activity():
    """Get today's activity summary from Activity Tracker."""
    tracker = ActivityTracker()
    if not tracker.available:
        raise HTTPException(status_code=503, detail="Activity Tracker database not available")

    return {"success": True, "data": tracker.get_daily_summary()}


@activity_router.get("/coding")
async def get_coding_time(days: int = Query(default=7, le=90)):
    """Get coding time by project for the past N days."""
    tracker = ActivityTracker()
    from datetime import timedelta
    start = datetime.now() - timedelta(days=days)
    data = tracker.get_coding_time(start_date=start)
    return {"success": True, "data": {"coding_time": data, "period_days": days}}


@activity_router.get("/summary")
async def get_activity_summary(days: int = Query(default=7, le=90)):
    """Get full activity summary (apps, coding dirs, browser domains) for the past N days."""
    tracker = ActivityTracker()
    from datetime import timedelta
    start = datetime.now() - timedelta(days=days)
    return {
        "success": True,
        "data": {
            "app_usage":      tracker.get_app_usage(start_date=start),
            "coding_time":    tracker.get_coding_time(start_date=start),
            "browser_domains": tracker.get_browser_domains(start_date=start),
            "period_days":    days,
        },
    }


@activity_router.get("/peak-hours")
async def get_peak_hours():
    """Get peak productivity hours based on recent coding patterns."""
    tracker = ActivityTracker()
    data = tracker.get_peak_hours()
    return {"success": True, "data": {"peak_hours": data}}


# ── Calendar ──────────────────────────────────────────────────────────────────

calendar_router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@calendar_router.get("/status")
async def calendar_status():
    """Get Google Calendar integration status."""
    from app.calendar.google import GoogleCalendarClient
    client = GoogleCalendarClient()

    if not client.available:
        return {
            "success": True,
            "data": {
                "configured": False,
                "message": "Run: python scripts/setup_google_calendar.py"
            }
        }

    ids = client.load_calendar_ids()
    return {
        "success": True,
        "data": {
            "configured": True,
            "authenticated": client._token_path.exists(),
            "calendars": {k: bool(v) for k, v in ids.items()} if ids else {}
        }
    }


@calendar_router.post("/sync")
async def trigger_sync():
    """Manually trigger a calendar sync."""
    from app.calendar.sync import CalendarSync
    sync = CalendarSync()
    result = sync.sync_all()
    sync.close()
    return {"success": True, "data": result, "message": "Calendar sync triggered"}


@calendar_router.post("/setup")
async def trigger_calendar_setup():
    """Create agent calendars (requires credentials already configured)."""
    from app.calendar.google import GoogleCalendarClient
    client = GoogleCalendarClient()

    if not client.available:
        raise HTTPException(
            status_code=400,
            detail="Credentials not found. Run: python scripts/setup_google_calendar.py"
        )

    if not client.authenticate():
        raise HTTPException(status_code=401, detail="Authentication failed")

    ids = client.setup_agent_calendars()
    return {"success": True, "data": {"calendar_ids": ids}, "message": "Calendars created"}


@calendar_router.post("/jobs/{job_id}/run")
async def run_job_now(job_id: str):
    """Manually trigger a background job by ID."""
    valid_jobs = {
        "calendar_sync": "job_calendar_sync",
        "daily_plan": "job_daily_plan",
        "git_monitor": "job_git_monitor",
        "weekly_insights": "job_weekly_insights",
    }
    if job_id not in valid_jobs:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")

    import importlib
    module = importlib.import_module("app.scheduler")
    fn = getattr(module, valid_jobs[job_id])
    await fn()
    return {"success": True, "message": f"Job '{job_id}' executed"}


# ── Agent ─────────────────────────────────────────────────────────────────────

agent_router = APIRouter(prefix="/api/agent", tags=["agent"])


@agent_router.get("/status")
async def agent_status():
    """Get LLM availability and agent status."""
    from app.llm.router import get_llm
    llm = get_llm()
    return {
        "success": True,
        "data": {
            "llm_available": llm.available,
            "preferred_model": llm.preferred_model,
            "openai_configured": llm._openai_available,
            "anthropic_configured": llm._anthropic_available,
        }
    }


@agent_router.get("/plan")
async def get_daily_plan(db: Session = Depends(get_db)):
    """Generate or retrieve today's AI daily plan."""
    from app.agent.planner import DailyPlanner
    planner = DailyPlanner(db)
    plan = planner.generate_plan()
    return {"success": True, "data": plan}


@agent_router.get("/insights")
async def get_weekly_insights(week_offset: int = 0, db: Session = Depends(get_db)):
    """Generate weekly productivity insights.

    week_offset: 0 = current week, -1 = last week
    """
    from app.agent.insights import InsightsGenerator
    generator = InsightsGenerator(db)
    result = generator.generate_weekly(week_offset=week_offset)
    return {"success": True, "data": result}


@agent_router.post("/parse")
async def parse_event(body: dict):
    """Parse a calendar event or natural language into a structured task.

    Body: {"summary": "Task: Write docs, 2h, P1", "description": ""}
    """
    from app.agent.triage import InboxTriage
    triage = InboxTriage()
    summary = body.get("summary", "")
    description = body.get("description", "") or ""

    if not summary:
        raise HTTPException(status_code=400, detail="summary field required")

    result = triage.parse(summary, description)
    if not result:
        return {"success": True, "data": None, "message": "Not recognized as a task/goal/blocker"}

    return {"success": True, "data": result}


@agent_router.get("/eod")
async def get_eod_report(date: Optional[str] = None, db: Session = Depends(get_db)):
    """Get the saved EOD report for a given date (default: today).

    date: ISO format YYYY-MM-DD. Returns 404 if no report exists yet.
    """
    from app.agent.eod_analyst import EODAnalyst
    from datetime import date as date_type
    import datetime as dt

    target = None
    if date:
        try:
            target = dt.date.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")

    analyst = EODAnalyst(db)
    result = analyst.get_saved(target)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No EOD report for {(target or dt.date.today()).isoformat()}. Run POST /api/agent/eod to generate one."
        )
    return {"success": True, "data": result}


@agent_router.post("/eod")
async def run_eod_analysis(db: Session = Depends(get_db)):
    """Run end-of-day analysis now: imports today's sessions, analyzes the day,
    saves locally. Returns the full AI summary with tomorrow's recommendations."""
    from app.agent.eod_analyst import EODAnalyst
    analyst = EODAnalyst(db)
    result = analyst.analyze()
    return {"success": True, "data": result}


@agent_router.post("/sessions/import")
async def import_session_file(body: dict):
    """Manually import a session from a file path.

    Body: {"file_path": "/path/to/session.jsonl"}
    """
    from app.integrations.session_watcher import parse_session_file, import_session
    from pathlib import Path

    file_path = body.get("file_path")
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path required")

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    session = parse_session_file(path)
    if not session:
        raise HTTPException(status_code=422, detail="Could not parse session file")

    success = import_session(session)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to import session")

    return {"success": True, "data": {"source": session["source"], "summary": session.get("summary", "")[:100]}}


# ── Chat (SSE streaming) ───────────────────────────────────────────────────────

chat_router = APIRouter(prefix="/api/chat", tags=["chat"])


def _sanitise_history(history: list) -> list:
    """Keep only keys that litellm accepts; strip any UI-only fields."""
    allowed = {"role", "content", "tool_calls", "tool_call_id", "name"}
    result = []
    for msg in history:
        cleaned = {k: v for k, v in msg.items() if k in allowed and v is not None}
        if cleaned.get("role") and ("content" in cleaned or "tool_calls" in cleaned):
            result.append(cleaned)
    return result


async def _chat_stream(message: str, history: list) -> AsyncIterator[str]:
    """Async generator that runs the agentic tool loop, then streams the final reply."""
    import litellm
    from app.agent.tools import TOOLS, execute_tool
    from app.llm.router import get_llm
    from app.cli import _build_chat_context, _build_system_prompt
    from loguru import logger

    llm = get_llm()
    if not llm.available:
        yield f"data: {json.dumps({'type': 'error', 'text': 'No LLM configured. Add ANTHROPIC_API_KEY or OPENAI_API_KEY to .env'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    # Set API keys in environment
    model = llm.preferred_model
    api_key = llm._get_api_key(model)
    if api_key:
        if "anthropic/" in model:
            os.environ["ANTHROPIC_API_KEY"] = api_key
        else:
            os.environ["OPENAI_API_KEY"] = api_key

    db = SessionLocal()
    try:
        context = _build_chat_context(db)
        system_prompt = _build_system_prompt(context)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(_sanitise_history(history))
        messages.append({"role": "user", "content": message})

        # ── Agentic tool loop (max 5 rounds, non-streaming) ──────────────────
        last_msg = None
        for _ in range(5):
            # Retry up to 3 times on transient overload/rate-limit errors
            for attempt in range(3):
                try:
                    response = await asyncio.to_thread(
                        litellm.completion,
                        model=model,
                        messages=messages,
                        tools=TOOLS,
                        tool_choice="auto",
                        temperature=0.4,
                        max_tokens=1000,
                        stream=False,
                    )
                    break
                except Exception as exc:
                    err = str(exc).lower()
                    if attempt < 2 and ("overloaded" in err or "rate" in err or "529" in err or "429" in err):
                        await asyncio.sleep(2 ** attempt)  # 1s, 2s
                        continue
                    raise
            msg = response.choices[0].message
            last_msg = msg

            if not msg.tool_calls:
                break  # No tool call — final answer ready

            # Execute each tool call synchronously (fast local DB ops; avoids
            # passing the SQLAlchemy session across thread boundaries)
            messages.append(msg)
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                result = execute_tool(tc.function.name, args, db)
                yield f"data: {json.dumps({'type': 'tool', 'text': result})}\n\n"
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        # ── Stream final reply ────────────────────────────────────────────────
        if last_msg and not last_msg.tool_calls:
            # Tool loop ended cleanly — yield the content we already have
            content = last_msg.content or ""
            yield f"data: {json.dumps({'type': 'token', 'text': content})}\n\n"
        else:
            # Tool rounds exhausted — do a fresh streaming call for the summary
            chunks = await asyncio.to_thread(
                _collect_stream, model, messages
            )
            for chunk in chunks:
                yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"

    except Exception as e:
        logger.error(f"Chat stream error: {e}")
        msg_str = str(e)
        if "overloaded" in msg_str.lower():
            friendly = "Anthropic is overloaded right now — wait a few seconds and try again."
        elif "authentication" in msg_str.lower() or "api_key" in msg_str.lower():
            friendly = "API key error — check ANTHROPIC_API_KEY or OPENAI_API_KEY in .env."
        elif "rate" in msg_str.lower():
            friendly = "Rate limit hit — wait a moment and try again."
        else:
            friendly = f"LLM error: {msg_str}"
        yield f"data: {json.dumps({'type': 'error', 'text': friendly})}\n\n"
    finally:
        db.close()

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _collect_stream(model: str, messages: list, max_tokens: int = 2000) -> list[str]:
    """Run a streaming litellm call in a thread and return all chunks as a list.

    Returns a plain list so it can be safely passed back to the async context
    without touching asyncio primitives from within the thread.
    """
    import litellm
    tokens = []
    try:
        resp = litellm.completion(
            model=model,
            messages=messages,
            temperature=0.4,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in resp:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                tokens.append(delta.content)
    except Exception as e:
        tokens.append(f"[stream error: {e}]")
    return tokens


@chat_router.post("")
async def chat_endpoint(body: dict):
    """SSE streaming chat endpoint.

    Body: {"message": str, "history": [...litellm message dicts...]}
    Streams: text/event-stream with JSON events:
      {"type":"tool","text":"..."} — after each tool call
      {"type":"token","text":"..."} — streamed reply tokens
      {"type":"done"} — end of stream
    """
    message = (body.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message field required")

    history = body.get("history", []) or []

    return StreamingResponse(
        _chat_stream(message, history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Goals ─────────────────────────────────────────────────────────────────────

goals_router = APIRouter(prefix="/api/goals", tags=["goals"])


@goals_router.get("")
async def list_goals(
    status: str = Query(default="active"),
    db: Session = Depends(get_db),
):
    """List goals filtered by status.

    Query: ?status=active (default)
    Returns: [{id, title, category, target_date, progress_percent, status, description}]
    """
    goals = db.query(Goal).filter(Goal.status == status).order_by(Goal.created_at.desc()).all()
    return {
        "success": True,
        "data": {
            "goals": [
                {
                    "id": g.id,
                    "title": g.title,
                    "category": g.category,
                    "target_date": g.target_date.isoformat() if g.target_date else None,
                    "progress_percent": g.progress_percent,
                    "status": g.status,
                    "description": g.description,
                    "created_at": g.created_at.isoformat() if g.created_at else None,
                }
                for g in goals
            ]
        }
    }


# ── Planning ───────────────────────────────────────────────────────────────────

planning_router = APIRouter(prefix="/api/planning", tags=["planning"])


def _get_plan_date() -> "date":
    """Return today's date. Plans are always generated for the current day."""
    from datetime import date as date_type
    return date_type.today()


@planning_router.get("/status")
async def planning_status():
    """Check whether a plan exists for today."""
    from datetime import date as date_type
    from app.agent.nightly_planner import NightlyPlanner

    planner = NightlyPlanner()
    today = date_type.today()

    plan = planner.load(today)
    if plan is None:
        return {"success": True, "data": {"has_plan": False, "status": "none", "date": None}}

    return {
        "success": True,
        "data": {
            "has_plan": True,
            "status": plan.get("status", "draft"),
            "date": plan.get("date"),
        },
    }


@planning_router.get("/today")
async def get_today_plan():
    """Return the current plan (today's if exists, else tomorrow's)."""
    from app.agent.nightly_planner import NightlyPlanner

    target = _get_plan_date()
    planner = NightlyPlanner()
    plan = planner.load(target)
    if plan is None:
        raise HTTPException(status_code=404, detail="No plan found. Trigger /api/planning/regenerate to create one.")
    return {"success": True, "data": plan}


@planning_router.patch("/today")
async def patch_today_plan(body: dict):
    """Overwrite the slots in the current plan JSON file.

    Body: {"slots": [...]}
    """
    from app.agent.nightly_planner import NightlyPlanner

    slots = body.get("slots")
    if slots is None:
        raise HTTPException(status_code=400, detail="slots field required")

    target = _get_plan_date()
    planner = NightlyPlanner()
    plan = planner.load(target)
    if plan is None:
        raise HTTPException(status_code=404, detail="No plan found for today/tomorrow")

    plan["slots"] = slots
    planner.save(target, plan)
    return {"success": True, "data": {"date": str(target), "slot_count": len(slots)}}


@planning_router.post("/finalize")
async def finalize_plan():
    """Post all non-break slots to Google Calendar and mark plan as finalized."""
    import asyncio
    from app.agent.nightly_planner import NightlyPlanner

    target = _get_plan_date()
    planner = NightlyPlanner()
    plan = planner.load(target)
    if plan is None:
        raise HTTPException(status_code=404, detail="No plan found for today/tomorrow")

    slots = plan.get("slots", [])
    event_ids = await asyncio.to_thread(planner.finalize, target, slots)
    return {
        "success": True,
        "data": {"event_ids": event_ids, "count": len(event_ids)},
        "message": f"Posted {len(event_ids)} events to Google Calendar",
    }


@planning_router.post("/regenerate")
async def regenerate_plan():
    """Re-run NightlyPlanner for the target date (overwrites existing draft)."""
    import asyncio
    from app.agent.nightly_planner import NightlyPlanner

    target = _get_plan_date()
    planner = NightlyPlanner()
    plan = await asyncio.to_thread(planner.run, target)
    return {
        "success": True,
        "data": plan,
        "message": f"Plan regenerated for {target}: {len(plan['slots'])} slots",
    }


PLAN_CHAT_SYSTEM = """You are a schedule assistant. The user has a time-blocked daily plan and wants to refine it.

When the user describes changes or a new schedule:
- Return ONLY a JSON array of slot objects inside a ```json code fence, nothing else before or after.
- Each slot must have: id (string), start ("HH:MM"), duration_minutes (int), title (string), type ("task"|"break"|"meeting"|"admin"), task_id (int or null), notes (string).
- Preserve slot ids where slots are unchanged. Assign new ids (s1, s2, ...) sequentially.
- If the user asks a question rather than requesting a change, answer in plain text without a JSON block.
"""


async def _plan_chat_stream(message: str, slots: list, history: list):
    """SSE stream for plan refinement — no tools, higher token budget."""
    import litellm
    import os as _os
    from app.llm.router import get_llm
    from loguru import logger

    llm = get_llm()
    if not llm.available:
        yield f"data: {json.dumps({'type': 'error', 'text': 'No LLM configured.'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    model = llm.preferred_model
    api_key = llm._get_api_key(model)
    if api_key:
        if "anthropic/" in model:
            _os.environ["ANTHROPIC_API_KEY"] = api_key
        else:
            _os.environ["OPENAI_API_KEY"] = api_key

    slots_json = json.dumps(slots, indent=2)
    context_msg = {
        "role": "user",
        "content": (
            f"Current schedule:\n```json\n{slots_json}\n```\n\n"
            "I'll now describe my day or requested changes. "
            "Reply with the full updated schedule as a ```json block, or plain text if I ask a question."
        ),
    }
    context_ack = {
        "role": "assistant",
        "content": "Got it. Share your day or changes and I'll return the updated schedule.",
    }

    messages = [{"role": "system", "content": PLAN_CHAT_SYSTEM}]
    messages.append(context_msg)
    messages.append(context_ack)
    for h in history:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    try:
        chunks = await asyncio.to_thread(
            _collect_stream, model, messages, max_tokens=4000
        )
        for chunk in chunks:
            yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"
    except Exception as e:
        logger.error(f"Plan chat stream error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@planning_router.post("/chat")
async def plan_chat(body: dict):
    """SSE streaming chat endpoint scoped to plan refinement.

    Body: {"message": str, "slots": [...], "history": [...]}
    No tool calls — returns updated slot JSON in a ```json fence, or plain text.
    """
    message = (body.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message field required")

    slots = body.get("slots") or []
    history = body.get("history") or []

    return StreamingResponse(
        _plan_chat_stream(message, slots, history),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
