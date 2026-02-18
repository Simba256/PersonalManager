"""CLI interface for Personal Manager using Typer."""

import json
from datetime import datetime, timedelta
from typing import Optional
import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

app = typer.Typer(
    name="personal-manager",
    help="Personal Manager - AI-Powered Personal Assistant",
    add_completion=False
)
task_app = typer.Typer(help="Task management commands")
project_app = typer.Typer(help="Project management commands")
activity_app = typer.Typer(help="Activity Tracker commands")

app.add_typer(task_app, name="task")
app.add_typer(project_app, name="project")
app.add_typer(activity_app, name="activity")

console = Console()


def get_db():
    """Get database session."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


# ── Task Commands ─────────────────────────────────────────────────────────────

@task_app.command("add")
def task_add(
    title: str = typer.Argument(..., help="Task title"),
    priority: str = typer.Option("medium", "--priority", "-p", help="low/medium/high/critical"),
    due: Optional[str] = typer.Option(None, "--due", "-d", help="Due date (e.g. tomorrow, 2026-02-25)"),
    estimate: Optional[int] = typer.Option(None, "--estimate", "-e", help="Estimated minutes"),
    project: Optional[int] = typer.Option(None, "--project", "-j", help="Project ID")
):
    """Add a new task."""
    from app.services.task_service import TaskService

    due_date = _parse_date(due) if due else None

    db = get_db()
    try:
        service = TaskService(db)
        task = service.create(
            title=title,
            priority=priority,
            due_date=due_date,
            estimate_minutes=estimate,
            project_id=project
        )
        console.print(Panel(
            f"[bold green]Task created[/bold green]\n"
            f"ID: [cyan]{task.id}[/cyan]\n"
            f"Title: {task.title}\n"
            f"Priority: [yellow]{task.priority}[/yellow]\n"
            f"Due: {task.due_date.strftime('%Y-%m-%d') if task.due_date else 'Not set'}",
            title="New Task",
            border_style="green"
        ))
    finally:
        db.close()


@task_app.command("list")
def task_list(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    priority: Optional[str] = typer.Option(None, "--priority", "-p", help="Filter by priority"),
    all: bool = typer.Option(False, "--all", "-a", help="Include completed tasks")
):
    """List tasks."""
    from app.services.task_service import TaskService

    db = get_db()
    try:
        service = TaskService(db)

        if not all and not status:
            status_filter = None  # Will show non-completed
        else:
            status_filter = status

        tasks, total = service.list(status=status_filter, priority=priority)

        if not all:
            tasks = [t for t in tasks if t.status not in ("completed", "cancelled")]

        if not tasks:
            console.print("[yellow]No tasks found[/yellow]")
            return

        table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
        table.add_column("ID", style="dim", width=5)
        table.add_column("Title", min_width=30)
        table.add_column("Status", width=12)
        table.add_column("Priority", width=10)
        table.add_column("Due", width=12)
        table.add_column("Est.", width=8)

        priority_colors = {"low": "blue", "medium": "yellow", "high": "orange1", "critical": "red"}
        status_colors = {"pending": "white", "in_progress": "green", "blocked": "red", "completed": "dim"}

        for task in tasks:
            p_color = priority_colors.get(task.priority, "white")
            s_color = status_colors.get(task.status, "white")
            due_str = task.due_date.strftime("%b %d") if task.due_date else "-"
            est_str = f"{task.estimate_minutes}m" if task.estimate_minutes else "-"

            table.add_row(
                str(task.id),
                task.title[:50] + ("..." if len(task.title) > 50 else ""),
                f"[{s_color}]{task.status}[/{s_color}]",
                f"[{p_color}]{task.priority}[/{p_color}]",
                due_str,
                est_str
            )

        console.print(table)
        console.print(f"[dim]Showing {len(tasks)} tasks[/dim]")
    finally:
        db.close()


@task_app.command("done")
def task_done(task_id: int = typer.Argument(..., help="Task ID to mark complete")):
    """Mark a task as completed."""
    from app.services.task_service import TaskService

    db = get_db()
    try:
        service = TaskService(db)
        task = service.set_status(task_id, "completed")
        if not task:
            console.print(f"[red]Task {task_id} not found[/red]")
            raise typer.Exit(1)
        console.print(f"[green]✓[/green] Task [cyan]{task_id}[/cyan] marked as completed: {task.title}")
    finally:
        db.close()


@task_app.command("show")
def task_show(task_id: int = typer.Argument(..., help="Task ID")):
    """Show task details."""
    from app.services.task_service import TaskService

    db = get_db()
    try:
        service = TaskService(db)
        task = service.get(task_id)
        if not task:
            console.print(f"[red]Task {task_id} not found[/red]")
            raise typer.Exit(1)

        console.print(Panel(
            f"[bold]{task.title}[/bold]\n\n"
            f"Status: [cyan]{task.status}[/cyan]\n"
            f"Priority: [yellow]{task.priority}[/yellow]\n"
            f"Due: {task.due_date.strftime('%Y-%m-%d %H:%M') if task.due_date else 'Not set'}\n"
            f"Estimate: {task.estimate_minutes}min\n"
            f"Project: {task.project_id or 'None'}\n"
            f"Created: {task.created_at.strftime('%Y-%m-%d')}\n"
            + (f"\n[dim]{task.description}[/dim]" if task.description else ""),
            title=f"Task #{task.id}",
            border_style="cyan"
        ))
    finally:
        db.close()


# ── Project Commands ───────────────────────────────────────────────────────────

@project_app.command("list")
def project_list():
    """List all active projects."""
    from app.services.project_service import ProjectService

    db = get_db()
    try:
        service = ProjectService(db)
        projects = service.list()

        if not projects:
            console.print("[yellow]No projects found. Run 'project discover' to scan for repos.[/yellow]")
            return

        table = Table(box=box.ROUNDED, header_style="bold cyan")
        table.add_column("ID", style="dim", width=5)
        table.add_column("Name", min_width=20)
        table.add_column("Language", width=12)
        table.add_column("Sessions", width=10)
        table.add_column("Last Active", width=16)

        for project in projects:
            last_active = (
                project.last_activity_at.strftime("%b %d %H:%M")
                if project.last_activity_at else "Never"
            )
            table.add_row(
                str(project.id),
                project.name,
                project.primary_language or "-",
                str(project.total_sessions),
                last_active
            )

        console.print(table)
    finally:
        db.close()


@project_app.command("discover")
def project_discover():
    """Discover git repositories and register as projects."""
    from app.services.project_service import ProjectService

    console.print("[cyan]Scanning for git repositories...[/cyan]")
    db = get_db()
    try:
        service = ProjectService(db)
        projects = service.discover_from_filesystem([
            "/media/shared/personalProjects",
            str(__import__("pathlib").Path.home() / "projects")
        ])
        console.print(f"[green]Found {len(projects)} repositories[/green]")
        for p in projects:
            console.print(f"  [cyan]{p.name}[/cyan] → {p.repo_path}")
    finally:
        db.close()


# ── Activity Commands ──────────────────────────────────────────────────────────

@activity_app.command("today")
def activity_today():
    """Show today's activity summary."""
    from app.integrations.activity_tracker import ActivityTracker

    tracker = ActivityTracker()
    if not tracker.available:
        console.print("[red]Activity Tracker database not available[/red]")
        console.print(f"[dim]Expected at: {tracker.db_path}[/dim]")
        raise typer.Exit(1)

    summary = tracker.get_daily_summary()

    # Coding time
    console.print(Panel(
        "\n".join(
            f"  [cyan]{item['working_directory'].split('/')[-1]}[/cyan]: "
            f"[green]{item['total_minutes']:.0f}min[/green]"
            for item in summary["coding_time"][:10]
        ) or "  No coding activity recorded",
        title="Today's Coding Time",
        border_style="green"
    ))

    # Top apps
    top_apps = summary["app_usage"][:5]
    if top_apps:
        console.print(Panel(
            "\n".join(
                f"  [yellow]{item['app_name']}[/yellow]: {item['total_minutes']:.0f}min"
                for item in top_apps
            ),
            title="Top Apps",
            border_style="yellow"
        ))

    # Focus metrics
    metrics = summary["focus_metrics"]
    if metrics:
        console.print(
            f"Active: [green]{metrics.get('active_hours', 0):.1f}h[/green]  "
            f"Context switches: [yellow]{metrics.get('context_switches', 0)}[/yellow]"
        )


@activity_app.command("week")
def activity_week():
    """Show this week's coding time by project."""
    from app.integrations.activity_tracker import ActivityTracker

    tracker = ActivityTracker()
    if not tracker.available:
        console.print("[red]Activity Tracker database not available[/red]")
        raise typer.Exit(1)

    start = datetime.now() - timedelta(days=7)
    coding = tracker.get_coding_time(start_date=start)

    if not coding:
        console.print("[yellow]No coding activity found for this week[/yellow]")
        return

    table = Table(box=box.ROUNDED, header_style="bold cyan", title="This Week's Coding Time")
    table.add_column("Project", min_width=30)
    table.add_column("Time", width=12, justify="right")
    table.add_column("Hours", width=10, justify="right")

    total = 0
    for item in coding:
        mins = item["total_minutes"]
        total += mins
        table.add_row(
            item["working_directory"].split("/")[-1],
            f"{mins:.0f} min",
            f"{mins/60:.1f}h"
        )

    console.print(table)
    console.print(f"\n[bold]Total: [green]{total/60:.1f}h[/green][/bold]")


# ── Chat ───────────────────────────────────────────────────────────────────────

@app.command("chat")
def chat(
    one_shot: Optional[str] = typer.Argument(None, help="Ask a single question and exit"),
):
    """Chat with your personal AI agent.

    Knows your tasks, projects, sessions, goals, and activity.
    Type /help for commands, /exit or Ctrl+C to quit.
    """
    from app.llm.router import get_llm

    llm = get_llm()
    if not llm.available:
        console.print("[red]No LLM configured. Add ANTHROPIC_API_KEY or OPENAI_API_KEY to .env[/red]")
        raise typer.Exit(1)

    db = get_db()
    try:
        context = _build_chat_context(db)
        system_prompt = _build_system_prompt(context)
        history = []  # list of {"role": ..., "content": ...}

        if one_shot:
            # Single question mode
            response = _chat_turn(llm, system_prompt, history, one_shot, db=db)
            console.print(response)
            return

        # Interactive mode
        console.print(Panel(
            f"[bold cyan]Personal Manager — Chat[/bold cyan]\n"
            f"[dim]Model: {llm.preferred_model.split('/')[-1]}[/dim]\n\n"
            f"[dim]Tasks: {context['pending_count']} pending, {context['overdue_count']} overdue[/dim]\n"
            f"[dim]Projects: {context['project_count']}  |  Sessions today: {context['sessions_today']}[/dim]\n\n"
            f"[dim]/help  /clear  /status  /eod  /exit[/dim]",
            border_style="cyan",
            padding=(0, 1)
        ))

        while True:
            try:
                console.print("[bold green]you>[/bold green] ", end="")
                user_input = input().strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye.[/dim]")
                break

            if not user_input:
                continue

            cmd = user_input.lower()

            # Built-in slash commands
            if cmd in ("/exit", "/quit", "/q"):
                console.print("[dim]Goodbye.[/dim]")
                break

            elif cmd == "/clear":
                history.clear()
                # Refresh context
                db.close()
                db = get_db()
                context = _build_chat_context(db)
                system_prompt = _build_system_prompt(context)
                console.print("[dim]Context refreshed.[/dim]")
                continue

            elif cmd == "/status":
                _print_chat_status(context)
                continue

            elif cmd == "/eod":
                _print_eod(db)
                continue

            elif cmd == "/help":
                console.print(
                    "[dim]/clear[/dim]  — refresh context and clear history\n"
                    "[dim]/status[/dim] — show current task/project summary\n"
                    "[dim]/eod[/dim]    — show today's end-of-day report\n"
                    "[dim]/exit[/dim]   — quit"
                )
                continue

            # Send to LLM
            with console.status("[dim]thinking...[/dim]", spinner="dots"):
                response = _chat_turn(llm, system_prompt, history, user_input, db=db)

            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})

            # Keep history bounded (last 20 turns = 10 exchanges)
            if len(history) > 20:
                history = history[-20:]

            console.print(f"\n[bold blue]pm>[/bold blue] {response}\n")

    finally:
        db.close()


def _chat_turn(llm, system_prompt: str, history: list, user_input: str, db=None) -> str:
    """Send a message to the LLM with conversation history and tool calling."""
    try:
        import litellm
        import os
        from app.agent.tools import TOOLS, execute_tool

        api_key = llm._get_api_key(llm.preferred_model)
        if api_key:
            if "anthropic/" in llm.preferred_model:
                os.environ["ANTHROPIC_API_KEY"] = api_key
            else:
                os.environ["OPENAI_API_KEY"] = api_key

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        # Agentic loop: LLM → tool calls → results → LLM response
        for _ in range(5):  # max 5 tool rounds
            response = litellm.completion(
                model=llm.preferred_model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.4,
                max_tokens=1000,
            )
            msg = response.choices[0].message

            # No tool calls — final answer
            if not msg.tool_calls:
                return msg.content or "(no response)"

            # Execute each tool call
            messages.append(msg)
            tool_results = []
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                result = execute_tool(tc.function.name, args, db) if db else f"Tool {tc.function.name} called (no db)"
                tool_results.append(f"  ✓ {result}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        return msg.content or "(no response)"

    except Exception as e:
        logger.error(f"Chat turn failed: {e}")
        return f"Error: {e}"


def _build_chat_context(db) -> dict:
    """Gather current state for the system prompt."""
    from app.services.task_service import TaskService
    from app.services.project_service import ProjectService
    from app.models import Session as S, Goal
    from datetime import date

    task_service = TaskService(db)
    project_service = ProjectService(db)

    pending, _ = task_service.list(status="pending")
    overdue = task_service.get_overdue()
    due_soon = task_service.get_due_soon(days=3)
    completed_today = [
        t for t in (task_service.list(status="completed")[0])
        if t.completed_at and t.completed_at.date() == date.today()
    ]
    projects = project_service.list()
    goals = db.query(Goal).filter(Goal.status.notin_(["completed", "abandoned"])).all()

    today_start = datetime.combine(date.today(), datetime.min.time())
    sessions_today = db.query(S).filter(S.started_at >= today_start).count()

    # Load today's EOD if available
    eod_text = None
    try:
        from app.agent.eod_analyst import EODAnalyst
        analyst = EODAnalyst(db)
        saved = analyst.get_saved()
        if saved:
            eod_text = saved.get("analysis", "")
    except Exception:
        pass

    # Load persistent user profile
    from app.config import settings
    from pathlib import Path
    profile_text = None
    profile_path = settings.data_dir / "memory" / "profile.md"
    if profile_path.exists():
        try:
            profile_text = profile_path.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    # Load today's and yesterday's notes (what save_note wrote)
    notes_text = None
    notes_dir = settings.data_dir / "notes"
    if notes_dir.exists():
        try:
            from datetime import date, timedelta
            parts = []
            for d in [date.today(), date.today() - timedelta(days=1)]:
                note_file = notes_dir / f"{d}.md"
                if note_file.exists():
                    content = note_file.read_text(encoding="utf-8").strip()
                    if content:
                        parts.append(f"[{d}]\n{content}")
            if parts:
                notes_text = "\n\n".join(parts)
        except Exception:
            pass

    return {
        "pending": pending,
        "pending_count": len(pending),
        "overdue": overdue,
        "overdue_count": len(overdue),
        "due_soon": due_soon,
        "completed_today": completed_today,
        "projects": projects,
        "project_count": len(projects),
        "goals": goals,
        "sessions_today": sessions_today,
        "eod_text": eod_text,
        "profile_text": profile_text,
        "notes_text": notes_text,
    }


def _build_system_prompt(ctx: dict) -> str:
    """Build the system prompt with full current context."""
    now = datetime.now()

    # Build a project lookup for annotating tasks
    project_by_id = {p.id: p.name for p in ctx["projects"]}

    lines = [
        f"You are a personal AI assistant.",
        f"Today is {now.strftime('%A, %B %d, %Y')} and the time is {now.strftime('%H:%M')} PKT.",
        "",
    ]

    if ctx.get("profile_text"):
        lines.append("═══ USER PROFILE & MEMORY ═══")
        lines.append(ctx["profile_text"])
        lines.append("")

    if ctx.get("notes_text"):
        lines.append("═══ RECENT NOTES ═══")
        lines.append(ctx["notes_text"])
        lines.append("")

    lines += [
        "═══ TOOL USAGE RULES — follow these exactly ═══",
        "",
        "complete_task",
        "  ONLY call this when the user EXPLICITLY states they finished a specific task.",
        "  Required triggers: 'I did X', 'I've done X', 'finished X', 'X is complete',",
        "  'mark X as done', 'tick off #ID'.",
        "  NEVER call it because:",
        "    • a task is being mentioned or discussed",
        "    • the user asks 'what tasks do I have' or similar",
        "    • you think the task sounds finished based on context",
        "    • the user says 'I need to do X' (that's the opposite — they haven't done it)",
        "  When in doubt, ask: 'Did you complete that, or is it still pending?'",
        "",
        "add_task",
        "  Call proactively when the user mentions something new that should be tracked.",
        "  Always pick the most relevant project from the list below — do not guess randomly.",
        "  If genuinely unclear which project, ask once before creating.",
        "",
        "add_goal / add_blocker / save_note",
        "  Call proactively. Goals for longer-term objectives, blockers for things preventing",
        "  progress, notes for decisions or info worth saving.",
        "",
        "update_task",
        "  Use to change priority, due date, estimate, or status (pending/in_progress/blocked).",
        "  Do NOT use status='completed' here — only complete_task marks a task done.",
        "",
        "delete_project",
        "  Always confirm with the user before calling. This cannot be undone.",
        "",
        "list_directory / read_file",
        "  Use list_directory first to explore, then read_file to read. Read-only — you",
        "  cannot create or modify files.",
        "",
        "═══ RESPONSE STYLE ═══",
        "• Be direct and concise. Skip filler phrases ('Great!', 'Of course!', 'Absolutely!').",
        "• Reference tasks by ID and title, e.g. '#12 Contact professors'.",
        "• When you call a tool, briefly confirm the outcome in one line.",
        "• If you're unsure what the user wants, ask a short clarifying question.",
        "• Do not repeat information the user just told you.",
        "",
        "═══ CURRENT STATE ═══",
    ]

    # Overdue — highest urgency, show all
    if ctx["overdue"]:
        lines.append(f"OVERDUE ({len(ctx['overdue'])}) — needs immediate attention:")
        for t in ctx["overdue"]:
            due = t.due_date.strftime("%b %d") if t.due_date else "?"
            proj = project_by_id.get(t.project_id, "")
            proj_str = f" [{proj}]" if proj else ""
            lines.append(f"  [{t.priority.upper()}] #{t.id} {t.title}{proj_str} (due {due})")

    # Due soon
    if ctx["due_soon"]:
        lines.append(f"DUE IN 3 DAYS ({len(ctx['due_soon'])}):")
        for t in ctx["due_soon"]:
            due = t.due_date.strftime("%b %d") if t.due_date else "?"
            proj = project_by_id.get(t.project_id, "")
            proj_str = f" [{proj}]" if proj else ""
            lines.append(f"  [{t.priority.upper()}] #{t.id} {t.title}{proj_str} (due {due})")

    # Pending (cap at 15 to keep context manageable)
    if ctx["pending"]:
        lines.append(f"PENDING ({ctx['pending_count']} total, showing up to 15):")
        for t in ctx["pending"][:15]:
            est = f"{t.estimate_minutes}min" if t.estimate_minutes else "—"
            proj = project_by_id.get(t.project_id, "")
            proj_str = f" [{proj}]" if proj else ""
            lines.append(f"  [{t.priority.upper()}] #{t.id} {t.title}{proj_str} | est {est}")

    # Completed today — for reference only, do NOT infer these are real completions
    if ctx["completed_today"]:
        lines.append(f"COMPLETED TODAY ({len(ctx['completed_today'])}) — shown for reference:")
        for t in ctx["completed_today"]:
            lines.append(f"  ✓ #{t.id} {t.title}")

    lines.append("")
    lines.append("PROJECTS (every task must link to one — use the ID):")
    for p in ctx["projects"]:
        last = p.last_activity_at.strftime("%b %d") if p.last_activity_at else "never"
        lines.append(f"  #{p.id} {p.name} | last active: {last}")

    if ctx["goals"]:
        lines.append("")
        lines.append("ACTIVE GOALS:")
        for g in ctx["goals"][:8]:
            target = g.target_date.strftime("%b %d, %Y") if g.target_date else "no deadline"
            lines.append(f"  • #{g.id} {g.title} | {g.category or 'general'} | target: {target}")

    lines.append("")
    lines.append(f"Coding sessions today: {ctx['sessions_today']}")

    if ctx["eod_text"]:
        lines.append("")
        lines.append("TODAY'S EOD SUMMARY:")
        lines.append(ctx["eod_text"][:600])

    return "\n".join(lines)


def _print_chat_status(ctx: dict):
    console.print(
        f"[bold]Tasks:[/bold] {ctx['pending_count']} pending, "
        f"[red]{ctx['overdue_count']} overdue[/red], "
        f"{len(ctx['completed_today'])} done today\n"
        f"[bold]Projects:[/bold] {ctx['project_count']}  "
        f"[bold]Sessions today:[/bold] {ctx['sessions_today']}"
    )


def _print_eod(db):
    try:
        from app.agent.eod_analyst import EODAnalyst
        analyst = EODAnalyst(db)
        saved = analyst.get_saved()
        if not saved:
            console.print("[yellow]No EOD report for today. Run `pm eod` to generate one.[/yellow]")
        else:
            console.print(Panel(saved["analysis"], title=f"EOD Report — {saved['date']}", border_style="blue"))
    except Exception as e:
        console.print(f"[red]Could not load EOD report: {e}[/red]")


# ── EOD ────────────────────────────────────────────────────────────────────────

@app.command("eod")
def eod_report(
    date: Optional[str] = typer.Option(None, "--date", "-d", help="Date (YYYY-MM-DD), default: today"),
    generate: bool = typer.Option(False, "--generate", "-g", help="Generate fresh report even if one exists"),
):
    """Show or generate the end-of-day report."""
    from app.agent.eod_analyst import EODAnalyst
    import datetime as dt

    target = None
    if date:
        try:
            target = dt.date.fromisoformat(date)
        except ValueError:
            console.print("[red]Date must be YYYY-MM-DD[/red]")
            raise typer.Exit(1)

    db = get_db()
    try:
        analyst = EODAnalyst(db)

        if not generate:
            saved = analyst.get_saved(target)
            if saved:
                console.print(Panel(
                    saved["analysis"],
                    title=f"EOD Report — {saved['date']} ({'AI' if saved.get('ai_generated') else 'rule-based'})",
                    border_style="blue"
                ))
                stats = saved.get("stats", {})
                console.print(
                    f"[dim]Sessions: {stats.get('sessions_count', '?')}  "
                    f"Completed: {stats.get('tasks_completed_today', '?')}  "
                    f"Coding: {stats.get('coding_minutes', '?')}min[/dim]"
                )
                return

        # Generate fresh
        console.print("[dim]Generating EOD analysis...[/dim]")
        result = analyst.analyze(target)
        console.print(Panel(
            result["analysis"],
            title=f"EOD Report — {result['date']} ({'AI' if result.get('ai_generated') else 'rule-based'})",
            border_style="blue"
        ))
        stats = result.get("stats", {})
        console.print(
            f"[dim]Sessions: {stats.get('sessions_count', '?')}  "
            f"Completed: {stats.get('tasks_completed_today', '?')}  "
            f"Coding: {stats.get('coding_minutes', '?')}min[/dim]"
        )
    finally:
        db.close()


# ── Status ─────────────────────────────────────────────────────────────────────

@app.command("status")
def status():
    """Show overall system status."""
    from app.integrations.activity_tracker import ActivityTracker
    from app.services.task_service import TaskService
    from app.services.project_service import ProjectService

    db = get_db()
    try:
        task_service = TaskService(db)
        project_service = ProjectService(db)
        tracker = ActivityTracker()

        pending_tasks, _ = task_service.list(status="pending")
        due_soon = task_service.get_due_soon(days=3)
        projects = project_service.list()

        console.print(Panel(
            f"[bold]Tasks[/bold]\n"
            f"  Pending: [cyan]{len(pending_tasks)}[/cyan]\n"
            f"  Due in 3 days: [red]{len(due_soon)}[/red]\n\n"
            f"[bold]Projects[/bold]\n"
            f"  Active: [cyan]{len(projects)}[/cyan]\n\n"
            f"[bold]Activity Tracker[/bold]\n"
            f"  {'[green]Connected[/green]' if tracker.available else '[red]Not available[/red]'}",
            title="Personal Manager Status",
            border_style="cyan"
        ))

        if due_soon:
            console.print("\n[red]Due Soon:[/red]")
            for task in due_soon[:5]:
                due_str = task.due_date.strftime("%b %d") if task.due_date else "?"
                console.print(f"  [{task.priority}] {task.title} (due {due_str})")
    finally:
        db.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse a date string into a datetime object."""
    date_str = date_str.lower().strip()
    now = datetime.now()

    if date_str in ("today",):
        return now.replace(hour=23, minute=59)
    elif date_str in ("tomorrow",):
        return (now + timedelta(days=1)).replace(hour=23, minute=59)
    elif date_str == "next week":
        return (now + timedelta(weeks=1)).replace(hour=23, minute=59)
    elif date_str == "friday":
        days_ahead = 4 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return (now + timedelta(days=days_ahead)).replace(hour=23, minute=59)

    # Try ISO format
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


if __name__ == "__main__":
    app()
