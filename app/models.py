"""SQLAlchemy models for Personal Manager."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Task(Base):
    """Task model for actionable items."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Core fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        index=True
    )  # pending, scheduled, in_progress, blocked, completed, cancelled

    # Scheduling
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    estimate_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    actual_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)

    # Energy/context
    energy_level: Mapped[str] = mapped_column(String(10), default="medium")
    context_tags: Mapped[Optional[str]] = mapped_column(String(200))

    # Relationships
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("projects.id"))
    blocker_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("blockers.id"))
    parent_task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id"))

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    project: Mapped[Optional["Project"]] = relationship(back_populates="tasks")
    blocker: Mapped[Optional["Blocker"]] = relationship(
        foreign_keys=[blocker_id]
    )
    parent_task: Mapped[Optional["Task"]] = relationship(
        remote_side=[id],
        foreign_keys=[parent_task_id]
    )
    schedule_entries: Mapped[List["Schedule"]] = relationship(back_populates="task")

    def __repr__(self):
        return f"<Task(id={self.id}, title='{self.title}', status='{self.status}')>"


class Goal(Base):
    """Goal model for long-term objectives."""

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")

    # Hierarchy
    parent_goal_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("goals.id"))
    level: Mapped[int] = mapped_column(Integer, default=0)

    # Tracking
    target_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[Optional[str]] = mapped_column(String(50))

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

    def __repr__(self):
        return f"<Goal(id={self.id}, title='{self.title}', progress={self.progress_percent}%)>"


class Blocker(Base):
    """Blocker model for obstacles preventing task completion."""

    __tablename__ = "blockers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="open")

    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id"))

    def __repr__(self):
        return f"<Blocker(id={self.id}, status='{self.status}', severity='{self.severity}')>"


class Project(Base):
    """Project model for code projects being tracked."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    repo_path: Mapped[Optional[str]] = mapped_column(String(500))
    repo_url: Mapped[Optional[str]] = mapped_column(String(500))

    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    tags: Mapped[Optional[str]] = mapped_column(String(200))

    primary_language: Mapped[Optional[str]] = mapped_column(String(50))
    frameworks: Mapped[Optional[str]] = mapped_column(String(200))

    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    total_commits: Mapped[int] = mapped_column(Integer, default=0)
    total_sessions: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    tasks: Mapped[List["Task"]] = relationship(back_populates="project")
    sessions: Mapped[List["Session"]] = relationship(back_populates="project")

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', active={self.active})>"


class Session(Base):
    """Session model for coding/work sessions."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source: Mapped[str] = mapped_column(String(50), nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)

    summary: Mapped[Optional[str]] = mapped_column(Text)
    topics: Mapped[Optional[str]] = mapped_column(String(500))
    transcript_path: Mapped[Optional[str]] = mapped_column(String(500))
    working_directory: Mapped[Optional[str]] = mapped_column(String(500))
    commit_hashes: Mapped[Optional[str]] = mapped_column(String(500))

    metadata_json: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("projects.id"))
    project: Mapped[Optional["Project"]] = relationship(back_populates="sessions")

    def __repr__(self):
        return f"<Session(id={self.id}, source='{self.source}', project_id={self.project_id})>"


class Schedule(Base):
    """Schedule model for scheduled focus blocks."""

    __tablename__ = "schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), nullable=False)
    calendar_event_id: Mapped[str] = mapped_column(String(200), unique=True)
    calendar_id: Mapped[str] = mapped_column(String(200))

    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="scheduled")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    task: Mapped["Task"] = relationship(back_populates="schedule_entries")

    def __repr__(self):
        return f"<Schedule(id={self.id}, task_id={self.task_id}, status='{self.status}')>"


class Meeting(Base):
    """Meeting model for calendar meetings."""

    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    calendar_event_id: Mapped[str] = mapped_column(String(200), unique=True)
    calendar_id: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(50))

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)

    attendees: Mapped[Optional[str]] = mapped_column(Text)
    organizer: Mapped[Optional[str]] = mapped_column(String(200))

    location: Mapped[Optional[str]] = mapped_column(String(500))
    meeting_url: Mapped[Optional[str]] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<Meeting(id={self.id}, title='{self.title}')>"


class SyncState(Base):
    """SyncState model for tracking calendar synchronization."""

    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    calendar_id: Mapped[str] = mapped_column(String(200), nullable=False)
    calendar_name: Mapped[str] = mapped_column(String(200))

    sync_token: Mapped[Optional[str]] = mapped_column(String(500))
    page_token: Mapped[Optional[str]] = mapped_column(String(500))
    etag: Mapped[Optional[str]] = mapped_column(String(200))

    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_sync_status: Mapped[str] = mapped_column(String(20), default="success")
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    events_synced: Mapped[int] = mapped_column(Integer, default=0)
    last_event_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint('provider', 'calendar_id', name='uix_provider_calendar'),
    )

    def __repr__(self):
        return f"<SyncState(provider='{self.provider}', calendar='{self.calendar_name}')>"
