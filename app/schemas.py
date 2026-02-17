"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# Task Schemas
class TaskBase(BaseModel):
    """Base task schema."""

    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    estimate_minutes: Optional[int] = Field(default=None, ge=1)
    due_date: Optional[datetime] = None
    energy_level: str = Field(default="medium", pattern="^(low|medium|high)$")
    context_tags: Optional[str] = None
    project_id: Optional[int] = None


class TaskCreate(TaskBase):
    """Schema for creating a task."""
    pass


class TaskUpdate(BaseModel):
    """Schema for updating a task."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[str] = Field(
        None,
        pattern="^(pending|scheduled|in_progress|blocked|completed|cancelled)$"
    )
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|critical)$")
    estimate_minutes: Optional[int] = Field(None, ge=1)
    actual_minutes: Optional[int] = Field(None, ge=0)
    due_date: Optional[datetime] = None
    energy_level: Optional[str] = Field(None, pattern="^(low|medium|high)$")


class TaskResponse(TaskBase):
    """Schema for task response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    actual_minutes: Optional[int]
    blocker_id: Optional[int]
    parent_task_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


# Goal Schemas
class GoalBase(BaseModel):
    """Base goal schema."""

    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    target_date: Optional[datetime] = None
    parent_goal_id: Optional[int] = None


class GoalCreate(GoalBase):
    """Schema for creating a goal."""
    pass


class GoalUpdate(BaseModel):
    """Schema for updating a goal."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[str] = Field(
        None,
        pattern="^(active|paused|completed|abandoned)$"
    )
    target_date: Optional[datetime] = None
    progress_percent: Optional[int] = Field(None, ge=0, le=100)


class GoalResponse(GoalBase):
    """Schema for goal response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    level: int
    progress_percent: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


# Project Schemas
class ProjectBase(BaseModel):
    """Base project schema."""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    repo_path: Optional[str] = None
    repo_url: Optional[str] = None
    tags: Optional[str] = None


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""
    pass


class ProjectResponse(ProjectBase):
    """Schema for project response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    active: bool
    primary_language: Optional[str]
    frameworks: Optional[str]
    last_activity_at: Optional[datetime]
    total_commits: int
    total_sessions: int
    created_at: datetime
    updated_at: datetime


# Session Schemas
class SessionBase(BaseModel):
    """Base session schema."""

    source: str = Field(..., max_length=50)
    started_at: datetime
    ended_at: Optional[datetime] = None
    summary: Optional[str] = None
    topics: Optional[str] = None
    project_id: Optional[int] = None


class SessionCreate(SessionBase):
    """Schema for creating a session."""
    pass


class SessionResponse(SessionBase):
    """Schema for session response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    duration_minutes: Optional[int]
    transcript_path: Optional[str]
    commit_hashes: Optional[str]
    created_at: datetime


# API Response Wrapper
class APIResponse(BaseModel):
    """Standard API response wrapper."""

    success: bool
    data: Optional[dict | list] = None
    message: Optional[str] = None
    error: Optional[dict] = None


# Health Check
class HealthCheck(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: datetime
    checks: dict
