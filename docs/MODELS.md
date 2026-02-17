# Data Models Documentation

This document describes the database schema and data models for Personal Manager.

## Database Overview

- **Engine**: SQLite (with optional PostgreSQL migration path)
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Location**: `data/agent.db`
- **Attached DB**: Activity Tracker (`data/activity.db` - read-only)

## Schema Diagram

```
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│   Project   │◄──────│     Task     │──────►│   Blocker   │
└─────────────┘       └──────────────┘       └─────────────┘
       │                      │
       │                      │
       ▼                      ▼
┌─────────────┐       ┌──────────────┐
│   Session   │       │   Schedule   │
└─────────────┘       └──────────────┘
                              │
                              ▼
                      ┌──────────────┐
                      │   Meeting    │
                      └──────────────┘

┌─────────────┐       ┌──────────────┐
│     Goal    │       │  SyncState   │
└─────────────┘       └──────────────┘
```

## Core Models

### Task

Represents a single actionable item with deadline and priority.

```python
class Task(Base):
    __tablename__ = "tasks"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)

    # Core fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        index=True
    )  # pending, scheduled, in_progress, blocked, completed, cancelled

    # Scheduling
    priority: Mapped[str] = mapped_column(
        String(10),
        default="medium"
    )  # low, medium, high, critical
    estimate_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    actual_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)

    # Energy/context
    energy_level: Mapped[str] = mapped_column(
        String(10),
        default="medium"
    )  # low, medium, high (cognitive load required)
    context_tags: Mapped[Optional[str]] = mapped_column(String(200))  # JSON array

    # Relationships
    project_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("projects.id")
    )
    blocker_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("blockers.id")
    )
    parent_task_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("tasks.id")
    )  # For subtasks

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    project: Mapped[Optional["Project"]] = relationship(back_populates="tasks")
    blocker: Mapped[Optional["Blocker"]] = relationship()
    parent_task: Mapped[Optional["Task"]] = relationship(remote_side=[id])
    subtasks: Mapped[list["Task"]] = relationship(back_populates="parent_task")
    schedule_entries: Mapped[list["Schedule"]] = relationship(back_populates="task")
```

**Indexes**:
```sql
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_project_id ON tasks(project_id);
```

### Goal

Hierarchical goals with target dates and progress tracking.

```python
class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Core fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20),
        default="active"
    )  # active, paused, completed, abandoned

    # Hierarchy
    parent_goal_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("goals.id")
    )
    level: Mapped[int] = mapped_column(Integer, default=0)  # 0=top, 1=sub, etc.

    # Tracking
    target_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[Optional[str]] = mapped_column(String(50))  # career, education, health, etc.

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    parent_goal: Mapped[Optional["Goal"]] = relationship(remote_side=[id])
    sub_goals: Mapped[list["Goal"]] = relationship(back_populates="parent_goal")
```

**Example hierarchy**:
```
Goal: Get into Masters Program (level=0)
  ├─ Goal: Complete applications (level=1)
  │   ├─ Task: Write SoP
  │   ├─ Task: Get recommendation letters
  │   └─ Task: Submit application
  ├─ Goal: Prepare for interviews (level=1)
  └─ Goal: Secure funding (level=1)
```

### Blocker

Obstacles preventing task completion.

```python
class Blocker(Base):
    __tablename__ = "blockers"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Core fields
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(10),
        default="medium"
    )  # low, medium, high, critical

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="open"
    )  # open, in_progress, resolved

    # Resolution
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationship
    task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id"))
```

### Project

Code projects being tracked.

```python
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Core fields
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Paths
    repo_path: Mapped[Optional[str]] = mapped_column(String(500))
    repo_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Status
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    tags: Mapped[Optional[str]] = mapped_column(String(200))  # JSON array

    # Language/framework detection
    primary_language: Mapped[Optional[str]] = mapped_column(String(50))
    frameworks: Mapped[Optional[str]] = mapped_column(String(200))  # JSON array

    # Activity
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    total_commits: Mapped[int] = mapped_column(Integer, default=0)
    total_sessions: Mapped[int] = mapped_column(Integer, default=0)

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    tasks: Mapped[list["Task"]] = relationship(back_populates="project")
    sessions: Mapped[list["Session"]] = relationship(back_populates="project")
```

**Indexes**:
```sql
CREATE INDEX idx_projects_active ON projects(active);
CREATE INDEX idx_projects_last_activity ON projects(last_activity_at);
```

### Session

Coding/work sessions from various sources.

```python
class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Core fields
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )  # git, claude_code, opencode, manual, activity_tracker

    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)

    # Content
    summary: Mapped[Optional[str]] = mapped_column(Text)
    topics: Mapped[Optional[str]] = mapped_column(String(500))  # JSON array
    transcript_path: Mapped[Optional[str]] = mapped_column(String(500))
    commit_hashes: Mapped[Optional[str]] = mapped_column(String(500))  # JSON array

    # Metadata
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("projects.id")
    )
    project: Mapped[Optional["Project"]] = relationship(back_populates="sessions")
```

**Indexes**:
```sql
CREATE INDEX idx_sessions_started_at ON sessions(started_at);
CREATE INDEX idx_sessions_project_id ON sessions(project_id);
CREATE INDEX idx_sessions_source ON sessions(source);
```

### Schedule

Scheduled focus blocks for tasks.

```python
class Schedule(Base):
    __tablename__ = "schedule"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Core fields
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), nullable=False)
    calendar_event_id: Mapped[str] = mapped_column(String(200), unique=True)
    calendar_id: Mapped[str] = mapped_column(String(200))  # Which calendar

    # Timing
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="scheduled"
    )  # scheduled, completed, cancelled, rescheduled

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    task: Mapped["Task"] = relationship(back_populates="schedule_entries")
```

**Indexes**:
```sql
CREATE INDEX idx_schedule_start_time ON schedule(start_time);
CREATE INDEX idx_schedule_task_id ON schedule(task_id);
CREATE UNIQUE INDEX idx_schedule_calendar_event ON schedule(calendar_event_id);
```

### Meeting

Calendar meetings synced from external calendars.

```python
class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Calendar sync
    calendar_event_id: Mapped[str] = mapped_column(String(200), unique=True)
    calendar_id: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(50))  # google, caldav

    # Core fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Timing
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)

    # Participants
    attendees: Mapped[Optional[str]] = mapped_column(Text)  # JSON array
    organizer: Mapped[Optional[str]] = mapped_column(String(200))

    # Location
    location: Mapped[Optional[str]] = mapped_column(String(500))
    meeting_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Notes
    notes_doc_id: Mapped[Optional[str]] = mapped_column(String(200))  # Future: link to notes

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
```

**Indexes**:
```sql
CREATE INDEX idx_meetings_start_time ON meetings(start_time);
CREATE UNIQUE INDEX idx_meetings_calendar_event ON meetings(calendar_event_id);
```

### SyncState

Tracks calendar synchronization state.

```python
class SyncState(Base):
    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Calendar identification
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # google, caldav
    calendar_id: Mapped[str] = mapped_column(String(200), nullable=False)
    calendar_name: Mapped[str] = mapped_column(String(200))

    # Sync tokens
    sync_token: Mapped[Optional[str]] = mapped_column(String(500))
    page_token: Mapped[Optional[str]] = mapped_column(String(500))
    etag: Mapped[Optional[str]] = mapped_column(String(200))

    # Status
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_sync_status: Mapped[str] = mapped_column(
        String(20),
        default="success"
    )  # success, partial, failed
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Stats
    events_synced: Mapped[int] = mapped_column(Integer, default=0)
    last_event_count: Mapped[int] = mapped_column(Integer, default=0)

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint('provider', 'calendar_id', name='uix_provider_calendar'),
    )
```

## Activity Tracker Schema (Read-Only)

These tables are from the existing Activity Tracker and attached read-only.

### window_activity

```sql
CREATE TABLE window_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    window_title TEXT,
    app_name TEXT,
    app_class TEXT,
    pid INTEGER
);

CREATE INDEX idx_window_start_time ON window_activity(start_time);
CREATE INDEX idx_window_app_class ON window_activity(app_class);
```

### browser_activity

```sql
CREATE TABLE browser_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    domain TEXT
);

CREATE INDEX idx_browser_timestamp ON browser_activity(timestamp);
CREATE INDEX idx_browser_domain ON browser_activity(domain);
```

### terminal_activity

```sql
CREATE TABLE terminal_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    terminal_app TEXT,
    working_directory TEXT
);

CREATE INDEX idx_terminal_start_time ON terminal_activity(start_time);
```

## Materialized Views (Optional)

For performance, create views on Activity Tracker data:

```sql
-- Daily coding time by project
CREATE VIEW daily_coding_time AS
SELECT
    date(start_time) as date,
    working_directory,
    SUM((julianday(end_time) - julianday(start_time)) * 24 * 60) as minutes
FROM terminal_activity
WHERE working_directory IS NOT NULL
GROUP BY date(start_time), working_directory;

-- App usage summary
CREATE VIEW app_usage_summary AS
SELECT
    date(start_time) as date,
    app_class,
    app_name,
    COUNT(*) as sessions,
    SUM((julianday(end_time) - julianday(start_time)) * 24 * 60) as total_minutes
FROM window_activity
WHERE end_time IS NOT NULL
GROUP BY date(start_time), app_class, app_name;

-- Browser time by domain
CREATE VIEW browser_time_by_domain AS
SELECT
    date(timestamp) as date,
    domain,
    COUNT(*) as visits
FROM browser_activity
GROUP BY date(timestamp), domain;
```

## Pydantic Schemas

For API validation and serialization:

```python
# app/schemas.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    estimate_minutes: Optional[int] = Field(default=None, ge=1)
    due_date: Optional[datetime] = None
    energy_level: str = Field(default="medium", pattern="^(low|medium|high)$")
    project_id: Optional[int] = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[str] = Field(
        None,
        pattern="^(pending|scheduled|in_progress|blocked|completed|cancelled)$"
    )
    priority: Optional[str] = None
    estimate_minutes: Optional[int] = None
    due_date: Optional[datetime] = None

class TaskResponse(TaskBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

# Similar schemas for Goal, Project, Session, etc.
```

## Database Migrations

### Creating Migrations

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add session metadata field"

# Create empty migration for manual changes
alembic revision -m "Add custom indexes"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Example Migration

```python
# alembic/versions/001_initial_schema.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        # ... more columns ...
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('idx_tasks_status', 'tasks', ['status'])
    op.create_index('idx_tasks_due_date', 'tasks', ['due_date'])

def downgrade():
    op.drop_index('idx_tasks_due_date')
    op.drop_index('idx_tasks_status')
    op.drop_table('tasks')
```

## Query Examples

### Common Queries

```python
# Get pending tasks due this week
from sqlalchemy import and_, func
from datetime import datetime, timedelta

today = datetime.now()
week_end = today + timedelta(days=7)

tasks = session.query(Task).filter(
    and_(
        Task.status == "pending",
        Task.due_date >= today,
        Task.due_date <= week_end
    )
).order_by(Task.due_date, Task.priority).all()

# Get active projects with recent activity
projects = session.query(Project).filter(
    and_(
        Project.active == True,
        Project.last_activity_at >= datetime.now() - timedelta(days=30)
    )
).order_by(Project.last_activity_at.desc()).all()

# Get daily coding time from Activity Tracker
coding_time = session.execute(
    text("""
        SELECT
            working_directory,
            SUM((julianday(end_time) - julianday(start_time)) * 24 * 60) as minutes
        FROM terminal_activity
        WHERE date(start_time) = date('now')
        AND working_directory IS NOT NULL
        GROUP BY working_directory
    """)
).fetchall()

# Get task completion rate
completion_stats = session.query(
    Task.status,
    func.count(Task.id).label('count')
).group_by(Task.status).all()
```

## Data Integrity

### Constraints

- Foreign keys enforced
- Unique constraints on calendar event IDs
- Check constraints on enum fields
- NOT NULL constraints on required fields

### Triggers (Optional)

```sql
-- Update project last_activity_at on session insert
CREATE TRIGGER update_project_activity
AFTER INSERT ON sessions
BEGIN
    UPDATE projects
    SET last_activity_at = NEW.started_at,
        total_sessions = total_sessions + 1
    WHERE id = NEW.project_id;
END;

-- Update task completed_at on status change
CREATE TRIGGER update_task_completed
AFTER UPDATE OF status ON tasks
WHEN NEW.status = 'completed' AND OLD.status != 'completed'
BEGIN
    UPDATE tasks
    SET completed_at = datetime('now')
    WHERE id = NEW.id;
END;
```

## Backup & Restore

### Backup

```bash
# SQLite backup
sqlite3 data/agent.db ".backup data/backups/agent_$(date +%Y%m%d).db"

# With compression
sqlite3 data/agent.db ".backup /dev/stdout" | gzip > data/backups/agent_$(date +%Y%m%d).db.gz
```

### Restore

```bash
# From backup
cp data/backups/agent_20260217.db data/agent.db

# From compressed backup
gunzip -c data/backups/agent_20260217.db.gz > data/agent.db
```

---

Last updated: 2026-02-17
