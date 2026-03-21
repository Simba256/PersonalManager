"""Cross-project scanner — combines git status + tracker parsing into a single snapshot."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from app.config import settings
from app.utils.tracker_parser import parse_tracker

try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


class ProjectScanner:
    """Discovers repos, collects git status + tracker data, writes JSON snapshot."""

    SNAPSHOT_PATH = settings.data_dir / "snapshots" / "project-snapshot.json"
    SEARCH_DIRS = [
        Path("/media/shared/personalProjects"),
        Path("/media/shared/bld.ai"),
        Path("/media/shared/Chameleon-Ideas"),
        Path("/media/shared/Masters"),
    ]
    SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", "dist", "build"}

    def scan(self) -> dict:
        """Discover repos, collect git status + tracker data, write JSON snapshot."""
        if not GIT_AVAILABLE:
            logger.warning("gitpython not installed, project scan skipped")
            return {"generated_at": datetime.now().isoformat(), "project_count": 0, "projects": []}

        repos = self._discover_repos()
        projects = []
        for repo_path in repos:
            try:
                project = self._scan_repo(repo_path)
                if project:
                    projects.append(project)
            except Exception as e:
                logger.debug(f"Could not scan {repo_path}: {e}")

        snapshot = {
            "generated_at": datetime.now().isoformat(),
            "project_count": len(projects),
            "projects": projects,
        }

        self.SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2, default=str))
        logger.info(f"Project snapshot saved: {len(projects)} projects")
        return snapshot

    def load_snapshot(self) -> Optional[dict]:
        """Read saved snapshot from disk."""
        if not self.SNAPSHOT_PATH.exists():
            return None
        try:
            return json.loads(self.SNAPSHOT_PATH.read_text())
        except Exception:
            return None

    def _discover_repos(self) -> list[Path]:
        """Find all git repos in search dirs."""
        repos = []
        for search_dir in self.SEARCH_DIRS:
            if not search_dir.exists():
                continue
            for git_dir in search_dir.rglob(".git"):
                if not git_dir.is_dir():
                    continue
                parts = git_dir.relative_to(search_dir).parts
                if any(p.startswith(".") or p in self.SKIP_DIRS for p in parts[:-1]):
                    continue
                repos.append(git_dir.parent)
        return repos

    def _scan_repo(self, repo_path: Path) -> Optional[dict]:
        """Scan a single repo for branch, dirty state, staged/unstaged files, commits, tracker."""
        try:
            repo = git.Repo(repo_path)
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            return None

        try:
            branch = repo.active_branch.name
        except Exception:
            branch = "HEAD (detached)"

        dirty = repo.is_dirty()

        # Staged files
        try:
            staged_raw = repo.git.diff("--cached", "--name-only").strip()
            staged_files = staged_raw.split("\n")[:10] if staged_raw else []
        except Exception:
            staged_files = []

        # Unstaged files
        try:
            unstaged_raw = repo.git.diff("--name-only").strip()
            unstaged_files = unstaged_raw.split("\n")[:10] if unstaged_raw else []
        except Exception:
            unstaged_files = []

        # Untracked count
        untracked_count = len(repo.untracked_files)

        # Last commit
        last_commit = None
        try:
            head = repo.head.commit
            last_commit = {
                "hash": head.hexsha[:8],
                "message": head.message.strip().split("\n")[0][:120],
                "timestamp": datetime.fromtimestamp(head.committed_date).isoformat(),
            }
        except Exception:
            pass

        # Recent commits (last 24h, cap 5)
        recent_commits_24h = []
        try:
            since = datetime.now() - timedelta(hours=24)
            for commit in repo.iter_commits(since=since.isoformat()):
                recent_commits_24h.append({
                    "hash": commit.hexsha[:8],
                    "message": commit.message.strip().split("\n")[0][:120],
                    "timestamp": datetime.fromtimestamp(commit.committed_date).isoformat(),
                    "files_changed": len(commit.stats.files),
                })
                if len(recent_commits_24h) >= 5:
                    break
        except Exception:
            pass

        # Tracker
        tracker = self._find_tracker(repo_path)

        return {
            "name": repo_path.name,
            "path": str(repo_path),
            "branch": branch,
            "dirty": dirty,
            "staged_files": staged_files,
            "unstaged_files": unstaged_files,
            "untracked_count": untracked_count,
            "last_commit": last_commit,
            "recent_commits_24h": recent_commits_24h,
            "tracker": tracker,
        }

    def _find_tracker(self, repo_path: Path) -> Optional[dict]:
        """Check for PROJECT_TRACKER.md in repo root, parse if exists."""
        tracker_path = repo_path / "PROJECT_TRACKER.md"
        if not tracker_path.exists():
            return None
        try:
            content = tracker_path.read_text(errors="replace")
            return parse_tracker(content)
        except (OSError, PermissionError):
            return None
