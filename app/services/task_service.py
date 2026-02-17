"""Task management service."""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models import Task, Blocker


class TaskService:
    """Service for task CRUD operations and business logic."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, title: str, **kwargs) -> Task:
        """Create a new task."""
        task = Task(title=title, **kwargs)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get(self, task_id: int) -> Optional[Task]:
        """Get task by ID."""
        return self.db.query(Task).filter(Task.id == task_id).first()

    def list(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        project_id: Optional[int] = None,
        due_before: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[list[Task], int]:
        """List tasks with optional filters.

        Returns:
            Tuple of (tasks list, total count)
        """
        query = self.db.query(Task)

        if status:
            query = query.filter(Task.status == status)
        if priority:
            query = query.filter(Task.priority == priority)
        if project_id:
            query = query.filter(Task.project_id == project_id)
        if due_before:
            query = query.filter(Task.due_date <= due_before)

        total = query.count()
        tasks = query.order_by(Task.due_date.asc().nullslast(), Task.priority.desc())\
                     .limit(limit).offset(offset).all()

        return tasks, total

    def update(self, task_id: int, **kwargs) -> Optional[Task]:
        """Update a task."""
        task = self.get(task_id)
        if not task:
            return None

        for key, value in kwargs.items():
            if hasattr(task, key) and value is not None:
                setattr(task, key, value)

        task.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(task)
        return task

    def set_status(self, task_id: int, status: str) -> Optional[Task]:
        """Update task status with side effects."""
        task = self.get(task_id)
        if not task:
            return None

        task.status = status
        if status == "completed":
            task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(task)
        return task

    def delete(self, task_id: int) -> bool:
        """Delete a task."""
        task = self.get(task_id)
        if not task:
            return False

        self.db.delete(task)
        self.db.commit()
        return True

    def add_blocker(self, task_id: int, description: str, severity: str = "medium") -> Optional[Blocker]:
        """Add a blocker to a task."""
        task = self.get(task_id)
        if not task:
            return None

        blocker = Blocker(
            description=description,
            severity=severity,
            task_id=task_id
        )
        self.db.add(blocker)

        task.status = "blocked"
        task.blocker_id = blocker.id
        task.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(blocker)
        return blocker

    def get_pending_for_schedule(self) -> list[Task]:
        """Get tasks that need to be scheduled."""
        return self.db.query(Task).filter(
            Task.status.in_(["pending", "scheduled"])
        ).order_by(Task.due_date.asc().nullslast(), Task.priority.desc()).all()

    def get_due_soon(self, days: int = 7) -> list[Task]:
        """Get tasks due within N days."""
        from datetime import timedelta
        cutoff = datetime.utcnow() + timedelta(days=days)
        return self.db.query(Task).filter(
            and_(
                Task.due_date <= cutoff,
                Task.due_date >= datetime.utcnow(),
                Task.status.notin_(["completed", "cancelled"])
            )
        ).order_by(Task.due_date.asc()).all()

    def get_overdue(self) -> list[Task]:
        """Get tasks that are past their due date and not completed/cancelled."""
        return self.db.query(Task).filter(
            and_(
                Task.due_date < datetime.utcnow(),
                Task.due_date.isnot(None),
                Task.status.notin_(["completed", "cancelled"])
            )
        ).order_by(Task.due_date.asc()).all()
