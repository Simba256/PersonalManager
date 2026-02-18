"""Main FastAPI application for Personal Manager."""

from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from app.config import settings
from app.schemas import HealthCheck

# Configure logging
logger.remove()  # Remove default handler
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level=settings.log_level
)
logger.add(
    settings.data_dir / "logs" / "app_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    compression="gz",
    level="INFO"
)

# Create FastAPI app
app = FastAPI(
    title="Personal Manager",
    description="AI-Powered Personal Assistant",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates and static files
templates = Jinja2Templates(directory="app/web/templates")


from app.scheduler import create_scheduler, register_jobs
from app.integrations.session_watcher import SessionWatcher
_scheduler = create_scheduler()
_session_watcher = SessionWatcher()


def _is_tracker_running() -> bool:
    """Check whether tracker.py is already running by scanning /proc cmdlines."""
    import os
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            cmdline = open(f"/proc/{pid}/cmdline").read().replace("\x00", " ")
            if "tracker.py" in cmdline:
                return True
        except OSError:
            pass
    return False


def _start_activity_tracker():
    """Start the ActivityTracker daemon as an independent background process."""
    import subprocess
    from pathlib import Path

    tracker_dir = Path(settings.activity_tracker_db).parent
    tracker_script = tracker_dir / "tracker.py"

    if not tracker_script.exists():
        logger.warning(f"Activity Tracker script not found: {tracker_script}")
        return

    log_path = tracker_dir / "tracker.log"
    with open(log_path, "a") as log_fh:
        subprocess.Popen(
            ["python3", str(tracker_script)],
            cwd=str(tracker_dir),
            stdout=log_fh,
            stderr=log_fh,
            # Detach completely — survives PM restarts
            start_new_session=True,
        )
    logger.info(f"Activity Tracker started (log: {log_path})")


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Starting Personal Manager...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Database: {settings.database_url}")

    # Create data directories if they don't exist
    (settings.data_dir / "logs").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "sessions").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "backups").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "notes").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "plans").mkdir(parents=True, exist_ok=True)
    memory_dir = settings.data_dir / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    profile_path = memory_dir / "profile.md"
    if not profile_path.exists():
        profile_path.write_text(
            "# User Profile\n\n"
            "## About\n"
            "<!-- Tell me about yourself and I'll remember it here -->\n\n"
            "## Notes\n"
            "<!-- Permanent facts get appended here automatically -->\n"
        )

    # Ensure Activity Tracker daemon is running
    if _is_tracker_running():
        logger.info("Activity Tracker already running")
    else:
        logger.info("Activity Tracker not running — starting it...")
        try:
            _start_activity_tracker()
        except Exception as e:
            logger.warning(f"Could not start Activity Tracker: {e}")

    # Import any session files dropped while offline
    _session_watcher.scan_existing()

    # Start session importer (no live watching, just marks ready for on-demand scans)
    _session_watcher.start()

    # Start background scheduler
    register_jobs(_scheduler)
    _scheduler.start()
    logger.info(f"Scheduler started with {len(_scheduler.get_jobs())} jobs")

    logger.info("Personal Manager started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Shutting down Personal Manager...")
    _scheduler.shutdown(wait=False)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint - dashboard."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Personal Manager",
            "version": "0.1.0"
        }
    )


@app.get("/api/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint.

    Returns:
        Health status of the application
    """
    # Check database connectivity
    try:
        from app.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "error"

    # Check Activity Tracker
    try:
        import sqlite3
        from pathlib import Path
        activity_db = Path(settings.activity_tracker_db)
        if activity_db.exists():
            conn = sqlite3.connect(activity_db)
            conn.execute("SELECT 1")
            conn.close()
            activity_status = "ok"
        else:
            activity_status = "not_found"
    except Exception as e:
        logger.error(f"Activity Tracker health check failed: {e}")
        activity_status = "error"

    return HealthCheck(
        status="healthy" if db_status == "ok" else "degraded",
        version="0.1.0",
        timestamp=datetime.utcnow(),
        checks={
            "database": db_status,
            "activity_tracker": activity_status
        }
    )


@app.get("/api/status")
async def status():
    """System status endpoint.

    Returns:
        Detailed system status
    """
    return JSONResponse({
        "success": True,
        "data": {
            "uptime_seconds": 0,  # TODO: Track actual uptime
            "environment": settings.environment,
            "debug": settings.debug,
            "database": {
                "url": settings.database_url.split("///")[-1],  # Hide credentials
                "type": "sqlite" if "sqlite" in settings.database_url else "postgresql"
            }
        }
    })


# Import and register routers
from app.web.routes import tasks_router, projects_router, activity_router, calendar_router, agent_router, chat_router, goals_router, planning_router
app.include_router(tasks_router)
app.include_router(projects_router)
app.include_router(activity_router)
app.include_router(calendar_router)
app.include_router(agent_router)
app.include_router(chat_router)
app.include_router(goals_router)
app.include_router(planning_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
