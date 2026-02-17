# Development Guide

Guide for contributing to and developing Personal Manager.

## Development Environment Setup

### Prerequisites

- Python 3.11 or higher
- Git
- SQLite 3
- Google account (for calendar integration)
- OpenAI and/or Anthropic API keys

### Initial Setup

```bash
# Clone repository
git clone <repository-url>
cd PersonalManager

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies

# Copy example config
cp config.example.yaml config.yaml
cp .env.example .env

# Edit configuration
nano config.yaml
nano .env  # Add API keys

# Initialize database
alembic upgrade head

# Setup Google Calendar (follow prompts)
python scripts/setup_google_calendar.py

# Run tests to verify setup
pytest

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Project Structure

```
PersonalManager/
├── app/                          # Main application code
│   ├── __init__.py
│   ├── main.py                   # FastAPI application entry point
│   ├── config.py                 # Configuration management
│   ├── models.py                 # SQLAlchemy models
│   ├── schemas.py                # Pydantic schemas
│   ├── scheduler.py              # APScheduler setup
│   │
│   ├── calendar/                 # Calendar integration
│   │   ├── __init__.py
│   │   ├── google.py             # Google Calendar client
│   │   ├── caldav.py             # CalDAV client
│   │   ├── sync.py               # Sync engine
│   │   └── parser.py             # Event parsing
│   │
│   ├── agent/                    # LangGraph agent workflows
│   │   ├── __init__.py
│   │   ├── graphs.py             # Workflow definitions
│   │   ├── tools.py              # Agent tools
│   │   └── state.py              # State schemas
│   │
│   ├── integrations/             # External integrations
│   │   ├── __init__.py
│   │   ├── activity_tracker.py   # Activity Tracker queries
│   │   ├── git_monitor.py        # Git repository monitoring
│   │   └── session_watcher.py    # File watcher for sessions
│   │
│   ├── llm/                      # LLM clients
│   │   ├── __init__.py
│   │   ├── client.py             # Unified LLM client
│   │   └── prompts.py            # Prompt templates
│   │
│   ├── services/                 # Business logic
│   │   ├── __init__.py
│   │   ├── task_service.py
│   │   ├── schedule_service.py
│   │   ├── insights_service.py
│   │   └── project_service.py
│   │
│   ├── web/                      # Web UI
│   │   ├── __init__.py
│   │   ├── routes.py             # API routes
│   │   ├── templates/            # Jinja2 templates
│   │   │   ├── base.html
│   │   │   ├── dashboard.html
│   │   │   ├── tasks.html
│   │   │   └── ...
│   │   └── static/               # CSS, JS, images
│   │       ├── css/
│   │       ├── js/
│   │       └── img/
│   │
│   ├── cli.py                    # Typer CLI commands
│   └── utils.py                  # Utility functions
│
├── alembic/                      # Database migrations
│   ├── versions/
│   └── env.py
│
├── data/                         # Application data
│   ├── agent.db                  # Main SQLite database
│   ├── sessions/                 # Session exports
│   ├── logs/                     # Application logs
│   └── backups/                  # Database backups
│
├── scripts/                      # Utility scripts
│   ├── setup_google_calendar.py
│   ├── setup_caldav.py
│   ├── backup_database.py
│   └── ...
│
├── tests/                        # Test suite
│   ├── unit/
│   ├── integration/
│   └── conftest.py
│
├── docs/                         # Documentation
│
├── config.yaml                   # User configuration
├── .env                          # Environment variables
├── requirements.txt              # Production dependencies
├── requirements-dev.txt          # Development dependencies
├── pyproject.toml                # Project metadata
├── pytest.ini                    # Pytest configuration
└── README.md
```

## Code Style

### Python Style Guide

We follow PEP 8 with some modifications:

- Line length: 100 characters (not 79)
- Use type hints everywhere
- Use f-strings for string formatting
- Use `black` for auto-formatting
- Use `ruff` for linting

### Formatting

```bash
# Format code
black app/ tests/

# Check formatting
black --check app/ tests/

# Lint code
ruff check app/ tests/

# Sort imports
isort app/ tests/
```

### Type Checking

```bash
# Run mypy
mypy app/
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Testing

### Test Structure

```
tests/
├── unit/                       # Unit tests (fast, isolated)
│   ├── test_models.py
│   ├── test_parsers.py
│   └── test_services.py
│
├── integration/                # Integration tests (slower, with DB)
│   ├── test_calendar_sync.py
│   ├── test_task_workflow.py
│   └── test_api.py
│
└── conftest.py                 # Pytest fixtures
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_models.py

# Run specific test
pytest tests/unit/test_models.py::test_task_creation

# Run tests matching pattern
pytest -k "task"

# Run fast tests only (skip integration)
pytest -m "not integration"

# Verbose output
pytest -v

# Show print statements
pytest -s
```

### Writing Tests

#### Unit Test Example

```python
# tests/unit/test_task_service.py
import pytest
from datetime import datetime, timedelta
from app.services.task_service import TaskService
from app.models import Task

@pytest.fixture
def task_service(db_session):
    return TaskService(db_session)

def test_create_task(task_service):
    task_data = {
        "title": "Test task",
        "priority": "high",
        "due_date": datetime.now() + timedelta(days=7)
    }

    task = task_service.create_task(task_data)

    assert task.id is not None
    assert task.title == "Test task"
    assert task.priority == "high"
    assert task.status == "pending"

def test_update_task_status(task_service):
    task = task_service.create_task({"title": "Test"})

    updated = task_service.update_status(task.id, "completed")

    assert updated.status == "completed"
    assert updated.completed_at is not None
```

#### Integration Test Example

```python
# tests/integration/test_calendar_sync.py
import pytest
from app.calendar.sync import CalendarSync
from app.models import Task, Schedule

@pytest.mark.integration
async def test_inbox_event_creates_task(calendar_sync, google_calendar_mock):
    # Setup: Create inbox event
    event = google_calendar_mock.create_event(
        calendar_id="inbox",
        summary="Task: Test integration",
        description="Priority: High, Due: tomorrow"
    )

    # Execute: Sync calendar
    await calendar_sync.sync_inbox()

    # Assert: Task created in database
    tasks = Task.query.filter_by(title="Test integration").all()
    assert len(tasks) == 1
    assert tasks[0].priority == "high"

    # Assert: Inbox event deleted
    events = google_calendar_mock.list_events("inbox")
    assert event.id not in [e.id for e in events]
```

### Test Coverage

Target: 80% code coverage minimum

```bash
# Generate coverage report
pytest --cov=app --cov-report=term-missing

# HTML report
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

## Database Migrations

### Creating Migrations

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add session metadata field"

# Create empty migration for manual changes
alembic revision -m "Add custom indexes"

# Review generated migration
nano alembic/versions/XXX_add_session_metadata.py
```

### Running Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Upgrade to specific version
alembic upgrade abc123

# Downgrade one version
alembic downgrade -1

# Downgrade to specific version
alembic downgrade abc123

# Show current version
alembic current

# Show migration history
alembic history
```

### Migration Best Practices

1. **Review generated migrations**: Always check auto-generated migrations
2. **Test migrations**: Apply and rollback in development
3. **Backup before migrating**: Especially in production
4. **Small migrations**: One logical change per migration
5. **Add indexes**: Remember to add indexes in migrations
6. **Data migrations**: Separate data migrations from schema migrations

## Logging

### Log Levels

- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages
- `WARNING`: Warning messages (potential issues)
- `ERROR`: Error messages (failures)
- `CRITICAL`: Critical errors (application may crash)

### Using Logging

```python
from loguru import logger

# Basic logging
logger.info("Calendar sync completed")
logger.warning("Calendar API rate limit approaching")
logger.error("Failed to parse event", event_id=event.id)

# With context
logger.bind(task_id=task.id).info("Task status updated", status=task.status)

# Exception logging
try:
    result = risky_operation()
except Exception as e:
    logger.exception("Operation failed")
    raise
```

### Log Configuration

```python
# app/config.py
from loguru import logger
import sys

# Console logging (development)
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG"
)

# File logging (production)
logger.add(
    "data/logs/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",  # New file each day
    retention="30 days",
    compression="gz",
    level="INFO"
)
```

## API Development

### Adding New Endpoints

1. **Define Pydantic schema** in `app/schemas.py`:
```python
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    priority: str = Field(default="medium")
```

2. **Implement service logic** in `app/services/`:
```python
class TaskService:
    def create_task(self, task_data: TaskCreate) -> Task:
        # Business logic here
        pass
```

3. **Add route** in `app/web/routes.py`:
```python
@router.post("/api/tasks", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db)
):
    service = TaskService(db)
    created = service.create_task(task)
    return created
```

4. **Write tests**:
```python
def test_create_task_endpoint(client):
    response = client.post("/api/tasks", json={
        "title": "Test task",
        "priority": "high"
    })
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Test task"
```

## Background Jobs

### Creating Jobs

```python
# app/jobs/calendar_jobs.py
from app.calendar.sync import CalendarSync

async def sync_calendar_job():
    """Periodic job to sync calendar"""
    logger.info("Starting calendar sync job")

    try:
        sync = CalendarSync()
        result = await sync.sync_all_calendars()

        logger.info("Calendar sync completed", events_synced=result.events_synced)

    except Exception as e:
        logger.exception("Calendar sync failed")
        # Optionally notify user
```

### Registering Jobs

```python
# app/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.jobs.calendar_jobs import sync_calendar_job

scheduler = AsyncIOScheduler()

# Periodic jobs
scheduler.add_job(
    sync_calendar_job,
    'interval',
    minutes=2,
    id='calendar_sync',
    max_instances=1,  # Prevent overlapping runs
    coalesce=True  # Merge missed runs
)

# Scheduled jobs
scheduler.add_job(
    daily_plan_job,
    'cron',
    hour=7,
    minute=0,
    id='daily_plan'
)

scheduler.start()
```

## Debugging

### Interactive Debugging

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use ipdb for better experience
import ipdb; ipdb.set_trace()
```

### VS Code Debug Configuration

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "app.main:app",
        "--reload",
        "--host",
        "0.0.0.0",
        "--port",
        "8000"
      ],
      "jinja": true,
      "justMyCode": false
    },
    {
      "name": "Pytest",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": [
        "-v",
        "-s"
      ]
    }
  ]
}
```

### Database Debugging

```bash
# Open database in sqlite3
sqlite3 data/agent.db

# Useful queries
.tables
.schema tasks
SELECT * FROM tasks WHERE status = 'pending';
SELECT * FROM sync_state;

# Or use DB browser
sqlitebrowser data/agent.db
```

## Performance

### Database Optimization

```python
# Use indexes
from sqlalchemy import Index

Index('idx_task_status_due', Task.status, Task.due_date)

# Eager loading
tasks = db.query(Task).options(
    joinedload(Task.project),
    joinedload(Task.schedule_entries)
).all()

# Pagination
tasks = db.query(Task).limit(100).offset(200).all()
```

### Caching

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_active_projects():
    return db.query(Project).filter_by(active=True).all()

# Clear cache when data changes
get_active_projects.cache_clear()
```

### Profiling

```bash
# Profile with cProfile
python -m cProfile -o profile.stats app/main.py

# Analyze with snakeviz
pip install snakeviz
snakeviz profile.stats

# Memory profiling
pip install memory_profiler
python -m memory_profiler app/script.py
```

## Contributing

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/add-caldav-support

# Make changes and commit
git add .
git commit -m "feat: add CalDAV support"

# Keep branch updated
git fetch origin
git rebase origin/main

# Push and create PR
git push origin feature/add-caldav-support
```

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (formatting)
- `refactor`: Code refactoring
- `test`: Tests
- `chore`: Maintenance

**Examples**:
```
feat(calendar): add CalDAV support

Implemented CalDAV client for generic calendar integration.
Tested with NextCloud and Fastmail.

Closes #42
```

### Pull Request Process

1. Create feature branch
2. Write tests for changes
3. Ensure all tests pass
4. Update documentation
5. Submit PR with clear description
6. Address review comments
7. Squash commits before merge

## Troubleshooting

### Common Issues

**Import errors**:
```bash
# Ensure virtual environment activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

**Database locked**:
```bash
# Close all connections
# Or enable WAL mode
sqlite3 data/agent.db "PRAGMA journal_mode=WAL;"
```

**Calendar sync failing**:
```bash
# Check OAuth token
python scripts/refresh_google_token.py

# View logs
tail -f data/logs/calendar_sync.log
```

**Tests failing**:
```bash
# Clean test database
rm tests/test.db

# Run with verbose output
pytest -vv -s
```

---

Last updated: 2026-02-17
