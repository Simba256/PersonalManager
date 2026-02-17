"""Project management service."""

from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from app.models import Project, Session as SessionModel


class ProjectService:
    """Service for project management and git repository discovery."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, name: str, **kwargs) -> Project:
        """Create a new project."""
        project = Project(name=name, **kwargs)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get(self, project_id: int) -> Optional[Project]:
        """Get project by ID."""
        return self.db.query(Project).filter(Project.id == project_id).first()

    def get_by_path(self, repo_path: str) -> Optional[Project]:
        """Get project by repository path."""
        return self.db.query(Project).filter(Project.repo_path == repo_path).first()

    def list(self, active_only: bool = True) -> list[Project]:
        """List all projects."""
        query = self.db.query(Project)
        if active_only:
            query = query.filter(Project.active == True)  # noqa: E712
        return query.order_by(Project.last_activity_at.desc().nullslast()).all()

    def update_activity(self, project_id: int) -> Optional[Project]:
        """Update project's last activity timestamp."""
        project = self.get(project_id)
        if not project:
            return None
        project.last_activity_at = datetime.utcnow()
        self.db.commit()
        return project

    def discover_from_filesystem(self, search_paths: list[str]) -> list[Project]:
        """Discover git repositories and create/update projects.

        Args:
            search_paths: List of directory paths to search for git repos

        Returns:
            List of discovered/updated projects
        """
        discovered = []

        for search_path in search_paths:
            path = Path(search_path).expanduser()
            if not path.exists():
                continue

            # Find .git directories (max depth 3 to avoid going too deep)
            for git_dir in path.rglob(".git"):
                if git_dir.is_dir():
                    repo_path = str(git_dir.parent)

                    # Skip hidden dirs and venvs
                    parts = git_dir.parts
                    if any(p.startswith('.') or p in ('venv', 'node_modules', '__pycache__')
                           for p in parts[len(path.parts):-1]):
                        continue

                    # Check if already tracked
                    existing = self.get_by_path(repo_path)
                    if existing:
                        discovered.append(existing)
                        continue

                    # Detect language and name
                    name = git_dir.parent.name
                    language = self._detect_language(git_dir.parent)

                    project = self.create(
                        name=name,
                        repo_path=repo_path,
                        primary_language=language
                    )
                    discovered.append(project)

        return discovered

    def _detect_language(self, repo_path: Path) -> Optional[str]:
        """Detect primary language of a repository."""
        indicators = {
            "Python": ["*.py", "requirements.txt", "pyproject.toml", "setup.py"],
            "JavaScript": ["*.js", "package.json"],
            "TypeScript": ["*.ts", "tsconfig.json"],
            "Rust": ["Cargo.toml"],
            "Go": ["go.mod"],
            "Java": ["pom.xml", "*.java"],
        }

        for language, patterns in indicators.items():
            for pattern in patterns:
                if list(repo_path.glob(pattern)):
                    return language
        return None

    def add_session(self, project_id: Optional[int], source: str, started_at: datetime,
                    ended_at: Optional[datetime] = None, summary: Optional[str] = None,
                    commit_hashes: Optional[list] = None,
                    duration_minutes: Optional[int] = None,
                    working_directory: Optional[str] = None,
                    transcript_path: Optional[str] = None) -> Optional[SessionModel]:
        """Record a work session, optionally linked to a project."""
        project = self.get(project_id) if project_id else None

        duration = duration_minutes
        if duration is None and ended_at and started_at:
            duration = int((ended_at - started_at).total_seconds() / 60)

        session = SessionModel(
            project_id=project_id if project else None,
            source=source,
            started_at=started_at,
            ended_at=ended_at,
            duration_minutes=duration,
            summary=summary,
            working_directory=working_directory,
            transcript_path=transcript_path,
            commit_hashes=json.dumps(commit_hashes) if commit_hashes else None
        )
        self.db.add(session)

        if project:
            project.last_activity_at = started_at
            project.total_sessions += 1

        self.db.commit()
        self.db.refresh(session)
        return session
