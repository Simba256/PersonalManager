"""Parse PROJECT_TRACKER.md files into structured data."""

from __future__ import annotations

import re
from pathlib import Path


SKIP_DIRS = {"node_modules", ".venv", "venv", ".git", "__pycache__", "dist", "build"}


def parse_tracker(content: str) -> dict:
    """Parse a PROJECT_TRACKER.md file into structured data.

    Returns dict with: summary, status, last_updated, in_progress, blockers
    """
    info: dict = {
        "summary": "",
        "status": "Unknown",
        "last_updated": "",
        "in_progress": [],
        "blockers": [],
    }

    match = re.search(r"Last updated:\s*(\d{4}-\d{2}-\d{2})", content)
    if match:
        info["last_updated"] = match.group(1)

    match = re.search(r"## Project Summary\n(.+?)(?=\n##|\Z)", content, re.DOTALL)
    if match:
        info["summary"] = match.group(1).strip().split("\n")[0]

    match = re.search(r"\*\*Status\*\*:\s*(.+)", content)
    if match:
        info["status"] = match.group(1).strip()

    in_progress_match = re.search(
        r"## In Progress\n(.+?)(?=\n## |\Z)", content, re.DOTALL
    )
    if in_progress_match:
        for line in in_progress_match.group(1).strip().split("\n"):
            line = line.strip()
            if line.startswith("- [ ]"):
                info["in_progress"].append(line[6:].strip())

    blockers_match = re.search(r"## Blockers\n(.+?)(?=\n## |\Z)", content, re.DOTALL)
    if blockers_match:
        for line in blockers_match.group(1).strip().split("\n"):
            line = line.strip()
            if line.startswith("- ") and line != "- None":
                info["blockers"].append(line[2:].strip())

    return info


def find_trackers(search_dirs: list[Path]) -> list[dict]:
    """Crawl directories for PROJECT_TRACKER.md files, skip noise dirs.

    Returns list of dicts with parsed tracker data plus path/full_path keys.
    """
    trackers = []
    for search_dir in search_dirs:
        search_dir = Path(search_dir)
        if not search_dir.exists():
            continue
        for tracker_path in search_dir.rglob("PROJECT_TRACKER.md"):
            parts = tracker_path.parts
            if any(p in SKIP_DIRS for p in parts):
                continue
            try:
                content = tracker_path.read_text(errors="replace")
                info = parse_tracker(content)
                info["path"] = str(tracker_path.parent)
                info["full_path"] = str(tracker_path.parent)
                trackers.append(info)
            except (OSError, PermissionError):
                continue

    return trackers
