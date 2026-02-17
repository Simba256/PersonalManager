"""Session importer — imports Claude Code and OpenCode sessions on demand.

Runs in two modes:
  - Startup scan: imports all historical sessions not yet seen
  - On-demand scan: called by the EOD job or explicitly via API

No continuous file watching — sessions are batch-imported once a day
(end-of-day) or on server startup. Call scan_new() to import manually.

Sources:
  1. ~/.claude/projects/  — Claude Code JSONL transcripts
  2. data/sessions/       — Manual drop folder (JSONL, JSON, txt, md)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from loguru import logger



# ── Claude Code directory decoder ─────────────────────────────────────────────

def decode_claude_project_path(dir_name: str) -> str:
    """Convert Claude Code's encoded directory name back to a filesystem path.

    Claude Code encodes project paths by replacing '/' with '-'.
    e.g. '-media-shared-personalProjects-PersonalManager'
         → '/media/shared/personalProjects/PersonalManager'
    """
    # Leading '-' represents the root '/'
    if dir_name.startswith("-"):
        return dir_name.replace("-", "/", 1).replace("-", "/")
    return dir_name.replace("-", "/")


def get_claude_projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"




# ── Import state persistence ──────────────────────────────────────────────────

_STATE_FILE = Path.home() / ".personal-manager" / "session_import_state.json"


def _load_import_state() -> dict[str, int]:
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_import_state(state: dict[str, int]):
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(state))
    except Exception:
        pass


# ── SessionWatcher ─────────────────────────────────────────────────────────────

class SessionWatcher:
    """Imports Claude Code sessions on startup and on demand.

    No continuous file watching. Sessions are scanned:
      - On server startup (all historical sessions not yet imported)
      - At end of day via the EOD scheduler job
      - On demand via API or CLI
    """

    def __init__(self, drop_dir: Optional[Path] = None):
        from app.config import settings
        self.drop_dir = drop_dir or (settings.data_dir / "sessions")
        self.drop_dir.mkdir(parents=True, exist_ok=True)
        self.claude_dir = get_claude_projects_dir()

    @property
    def available(self) -> bool:
        return True

    def start(self):
        logger.info(f"Session importer ready (Claude Code: {self.claude_dir})")

    def stop(self):
        pass

    def scan_existing(self):
        """Import all Claude Code sessions not yet in the database (startup scan)."""
        count = self._scan_claude_sessions(since=None)
        drop_count = self._scan_drop_folder()
        if count:
            logger.info(f"Startup: imported {count} Claude Code sessions")
        if drop_count:
            logger.info(f"Startup: imported {drop_count} files from drop folder")

    def scan_new(self, since: Optional[datetime] = None) -> dict:
        """Import sessions modified since a given datetime (EOD/on-demand scan).

        Args:
            since: Only import files modified after this time.
                   Defaults to last 24 hours if None.

        Returns:
            Dict with counts of imported sessions
        """
        if since is None:
            since = datetime.now() - timedelta(hours=24)

        count = self._scan_claude_sessions(since=since)
        drop_count = self._scan_drop_folder()

        return {
            "claude_code": count,
            "drop_folder": drop_count,
            "total": count + drop_count,
        }

    def _scan_claude_sessions(self, since: Optional[datetime]) -> int:
        """Scan ~/.claude/projects/ and import new/updated sessions."""
        if not self.claude_dir.exists():
            return 0

        imported = _load_import_state()
        count = 0

        for jsonl_path in sorted(self.claude_dir.rglob("*.jsonl")):
            stat = jsonl_path.stat()
            current_size = stat.st_size
            path_str = str(jsonl_path)

            # Skip tiny files
            if current_size < 1024:
                continue

            # Skip if already imported at this exact size
            if imported.get(path_str) == current_size:
                continue

            # For on-demand scans, skip files not modified in the window
            if since is not None:
                mtime = datetime.fromtimestamp(stat.st_mtime)
                if mtime < since:
                    continue

            try:
                session = parse_claude_code_jsonl(jsonl_path)
                if session:
                    import_session(session)
                    imported[path_str] = current_size
                    count += 1
            except Exception as e:
                logger.warning(f"Could not import {jsonl_path.name}: {e}")

        if count:
            _save_import_state(imported)

        return count

    def _scan_drop_folder(self) -> int:
        """Import files from the manual drop folder."""
        EXTS = {".jsonl", ".json", ".txt", ".md"}
        count = 0
        for path in sorted(self.drop_dir.iterdir()):
            if path.suffix.lower() in EXTS:
                try:
                    session = parse_session_file(path)
                    if session:
                        import_session(session)
                        count += 1
                except Exception as e:
                    logger.warning(f"Could not process drop file {path.name}: {e}")
        return count


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_claude_code_jsonl(path: Path) -> Optional[dict]:
    """Parse a Claude Code JSONL transcript into a session dict.

    Claude Code format: each line is a message object with keys:
      type, message, cwd, timestamp, sessionId, uuid, ...
    """
    records = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        logger.warning(f"Could not read {path.name}: {e}")
        return None

    if not records:
        return None

    # Extract cwd from any record that has it
    cwd = None
    for r in records:
        if r.get("cwd"):
            cwd = r["cwd"]
            break

    # Fall back: decode from directory name
    if not cwd:
        cwd = decode_claude_project_path(path.parent.name)

    # Get timestamps from records with 'timestamp' field
    timestamps = []
    for r in records:
        ts = _parse_datetime_str(r.get("timestamp"))
        if ts:
            timestamps.append(ts)

    started_at = min(timestamps) if timestamps else datetime.fromtimestamp(path.stat().st_mtime)
    ended_at = max(timestamps) if timestamps else started_at

    # Build summary from assistant text content
    assistant_texts = []
    for r in records:
        if r.get("type") != "assistant":
            continue
        msg = r.get("message", {})
        if not isinstance(msg, dict):
            continue
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            assistant_texts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    assistant_texts.append(block["text"])
                    break

    # Also grab user messages to understand what was being worked on
    user_texts = []
    for r in records:
        if r.get("type") != "user":
            continue
        msg = r.get("message", {})
        if not isinstance(msg, dict):
            continue
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            user_texts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    user_texts.append(block["text"])
                    break

    # Summary: first user message + condensed assistant response
    summary_parts = []
    if user_texts:
        summary_parts.append(f"User: {user_texts[0][:120]}")
    if assistant_texts:
        summary_parts.append(f"Assistant: {assistant_texts[0][:120]}")
    summary = " | ".join(summary_parts) if summary_parts else f"Claude Code session ({len(records)} messages)"

    # Extract git hashes from tool use output
    all_text = " ".join(
        str(r.get("message", "")) for r in records
    )
    commit_hashes = list(set(_extract_git_hashes(all_text)))

    # Duration
    duration_minutes = int((ended_at - started_at).total_seconds() / 60) if ended_at > started_at else None

    return {
        "source": "claude_code",
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_minutes": duration_minutes,
        "summary": summary[:500],
        "project_path": cwd,
        "commit_hashes": commit_hashes,
        "message_count": len(records),
        "session_id": records[-1].get("sessionId") if records else None,
    }


def parse_session_file(path: Path) -> Optional[dict]:
    """Parse a manually dropped session file."""
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return parse_claude_code_jsonl(path)
    elif suffix == ".json":
        return _parse_json_session(path)
    elif suffix in (".txt", ".md"):
        return _parse_text_session(path)
    return None


def _parse_json_session(path: Path) -> Optional[dict]:
    """Parse a generic JSON session export (OpenCode or similar)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"Could not read {path.name}: {e}")
        return None

    if not isinstance(data, dict):
        return None

    source = "opencode"
    if "claude" in str(data.get("source", "")).lower():
        source = "claude_code"

    started_at = _parse_datetime_str(
        data.get("started_at") or data.get("created_at") or data.get("start_time")
    )
    ended_at = _parse_datetime_str(
        data.get("ended_at") or data.get("updated_at") or data.get("end_time")
    ) or started_at

    project_path = data.get("project_path") or data.get("working_directory") or data.get("cwd")
    summary = data.get("summary") or data.get("description") or data.get("title") or ""

    if not summary:
        messages = data.get("messages", [])
        texts = []
        for m in messages:
            c = m.get("content", "")
            if isinstance(c, str):
                texts.append(c)
        summary = _truncate(" ".join(texts), 300)

    if not started_at and not summary:
        return None

    return {
        "source": source,
        "started_at": started_at or datetime.now(),
        "ended_at": ended_at or datetime.now(),
        "summary": summary,
        "project_path": project_path,
        "commit_hashes": _extract_git_hashes(json.dumps(data)),
        "message_count": len(data.get("messages", [])),
    }


def _parse_text_session(path: Path) -> Optional[dict]:
    """Parse a plain text or markdown session summary."""
    try:
        content = path.read_text(encoding="utf-8").strip()
    except Exception:
        return None

    if len(content) < 20:
        return None

    started_at = _datetime_from_filename(path.stem)
    return {
        "source": "manual",
        "started_at": started_at or datetime.fromtimestamp(path.stat().st_mtime),
        "ended_at": started_at or datetime.fromtimestamp(path.stat().st_mtime),
        "summary": content[:500],
        "project_path": None,
        "commit_hashes": _extract_git_hashes(content),
        "message_count": 0,
    }


# ── Database import ───────────────────────────────────────────────────────────

def import_session(session: dict) -> bool:
    """Import a parsed session into the project database."""
    try:
        from app.database import SessionLocal
        from app.services.project_service import ProjectService

        db = SessionLocal()
        try:
            service = ProjectService(db)
            projects = service.list()

            project_id = None
            project_path = session.get("project_path")
            if project_path:
                normalized = str(Path(project_path).resolve())
                for p in projects:
                    if p.repo_path and str(Path(p.repo_path).resolve()) == normalized:
                        project_id = p.id
                        break

            service.add_session(
                project_id=project_id,
                source=session.get("source", "manual"),
                started_at=session.get("started_at", datetime.now()),
                ended_at=session.get("ended_at"),
                duration_minutes=session.get("duration_minutes"),
                summary=session.get("summary", "")[:500],
                commit_hashes=session.get("commit_hashes"),
                working_directory=session.get("project_path"),
                transcript_path=session.get("transcript_path"),
            )
            return True
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to import session: {e}")
        return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_datetime_str(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(str(s)[:len(fmt)], fmt)
        except (ValueError, TypeError):
            continue
    return None


def _datetime_from_filename(stem: str) -> Optional[datetime]:
    m = re.search(r"(\d{4}[-_]\d{2}[-_]\d{2})", stem)
    if m:
        try:
            return datetime.strptime(m.group(1).replace("_", "-"), "%Y-%m-%d")
        except ValueError:
            pass
    return None


def _extract_git_hashes(text: str) -> list[str]:
    return list(set(re.findall(r"\b[0-9a-f]{7,40}\b", text)))


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "..."
