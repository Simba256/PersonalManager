"""Git repository monitoring - watches for commits and activity."""

from __future__ import annotations
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from loguru import logger

try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    logger.warning("gitpython not installed, git monitoring disabled")


class GitMonitor:
    """Monitor git repositories for commits and activity."""

    def __init__(self, search_paths: Optional[list[str]] = None):
        self.search_paths = [
            Path(p).expanduser()
            for p in (search_paths or ["/media/shared/personalProjects", "~/projects"])
        ]

    def discover_repos(self) -> list[Path]:
        """Find all git repositories in search paths."""
        repos = []
        for search_path in self.search_paths:
            if not search_path.exists():
                continue
            for git_dir in search_path.rglob(".git"):
                if git_dir.is_dir():
                    # Skip hidden dirs, venvs, node_modules
                    parts = git_dir.relative_to(search_path).parts
                    if any(p.startswith('.') or p in ('venv', 'node_modules', '__pycache__')
                           for p in parts[:-1]):
                        continue
                    repos.append(git_dir.parent)
        return repos

    def get_recent_commits(self, repo_path: Path, since: Optional[datetime] = None) -> list[dict]:
        """Get recent commits from a repository.

        Args:
            repo_path: Path to git repository
            since: Get commits since this datetime (default: last 24 hours)

        Returns:
            List of commit dicts
        """
        if not GIT_AVAILABLE:
            return []

        since = since or (datetime.now() - timedelta(hours=24))

        try:
            repo = git.Repo(repo_path)
            commits = []

            for commit in repo.iter_commits(since=since.isoformat()):
                commits.append({
                    "hash": commit.hexsha[:8],
                    "message": commit.message.strip(),
                    "author": commit.author.name,
                    "timestamp": datetime.fromtimestamp(commit.committed_date),
                    "files_changed": len(commit.stats.files),
                    "repo_path": str(repo_path),
                    "branch": self._get_current_branch(repo)
                })

            return commits

        except (git.InvalidGitRepositoryError, git.GitCommandError) as e:
            logger.debug(f"Could not read commits from {repo_path}: {e}")
            return []
        except Exception as e:
            logger.warning(f"Unexpected error reading commits from {repo_path}: {e}")
            return []

    def get_all_recent_commits(self, since: Optional[datetime] = None) -> list[dict]:
        """Get recent commits across all discovered repositories."""
        all_commits = []
        repos = self.discover_repos()

        for repo_path in repos:
            commits = self.get_recent_commits(repo_path, since)
            all_commits.extend(commits)

        # Sort by timestamp
        all_commits.sort(key=lambda c: c["timestamp"], reverse=True)
        return all_commits

    def get_repo_status(self, repo_path: Path) -> dict:
        """Get current status of a repository."""
        if not GIT_AVAILABLE:
            return {}

        try:
            repo = git.Repo(repo_path)
            return {
                "path": str(repo_path),
                "branch": self._get_current_branch(repo),
                "dirty": repo.is_dirty(),
                "untracked": len(repo.untracked_files),
                "remote_url": self._get_remote_url(repo),
                "last_commit": self._get_last_commit(repo)
            }
        except Exception as e:
            logger.debug(f"Could not get status for {repo_path}: {e}")
            return {"path": str(repo_path), "error": str(e)}

    def _get_current_branch(self, repo: "git.Repo") -> str:
        try:
            return repo.active_branch.name
        except Exception:
            return "HEAD (detached)"

    def _get_remote_url(self, repo: "git.Repo") -> Optional[str]:
        try:
            return repo.remotes.origin.url
        except Exception:
            return None

    def _get_last_commit(self, repo: "git.Repo") -> Optional[dict]:
        try:
            commit = repo.head.commit
            return {
                "hash": commit.hexsha[:8],
                "message": commit.message.strip().split("\n")[0],
                "timestamp": datetime.fromtimestamp(commit.committed_date).isoformat()
            }
        except Exception:
            return None
