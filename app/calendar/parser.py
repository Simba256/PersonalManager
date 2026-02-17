"""Calendar event parser — turns natural language event text into structured tasks."""

from __future__ import annotations
import re
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger


# ── Regex patterns ─────────────────────────────────────────────────────────────

# Priority shorthand: P1=critical, P2=high, P3=medium, P4=low
_PRIORITY_MAP = {
    "p1": "critical", "p2": "high", "p3": "medium", "p4": "low",
    "critical": "critical", "high": "high", "medium": "medium", "low": "low",
    "urgent": "critical", "important": "high",
}

_DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*h(?:ours?)?|(\d+)\s*min(?:utes?)?", re.I)
_PRIORITY_RE = re.compile(r"\bP([1-4])\b|priority[:\s]+(\w+)", re.I)
_DUE_RE      = re.compile(
    r"due[:\s]+(.+?)(?:,|$)"
    r"|by\s+(.+?)(?:,|$)"
    r"|deadline[:\s]+(.+?)(?:,|$)",
    re.I
)


# ── Date parsing ───────────────────────────────────────────────────────────────

def parse_relative_date(text: str) -> Optional[datetime]:
    """Parse relative date expressions into datetime objects.

    Handles: today, tomorrow, next <weekday>, friday, in N days,
    YYYY-MM-DD, DD/MM/YYYY
    """
    text = text.strip().lower()
    now = datetime.now()

    if text in ("today",):
        return now.replace(hour=23, minute=59, second=0)
    if text in ("tomorrow",):
        return (now + timedelta(days=1)).replace(hour=23, minute=59, second=0)
    if text in ("next week", "end of week"):
        return (now + timedelta(days=7)).replace(hour=23, minute=59, second=0)
    if text in ("end of month",):
        next_month = now.replace(day=28) + timedelta(days=4)
        return next_month.replace(day=1, hour=23, minute=59, second=0) - timedelta(days=1)

    # Day of week
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, day in enumerate(weekdays):
        if day in text:
            days_ahead = i - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            if "next" in text and days_ahead < 7:
                days_ahead += 7
            return (now + timedelta(days=days_ahead)).replace(hour=23, minute=59, second=0)

    # "in N days"
    m = re.search(r"in\s+(\d+)\s+days?", text)
    if m:
        return (now + timedelta(days=int(m.group(1)))).replace(hour=23, minute=59, second=0)

    # ISO and common formats
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d %b %Y", "%d %B %Y",
                "%b %d", "%B %d", "%b %d %Y", "%B %d %Y"):
        try:
            dt = datetime.strptime(text, fmt)
            # If no year in format, assume current or next year
            if dt.year == 1900:
                dt = dt.replace(year=now.year)
                if dt < now:
                    dt = dt.replace(year=now.year + 1)
            return dt.replace(hour=23, minute=59, second=0)
        except ValueError:
            continue

    return None


# ── Event text parser ─────────────────────────────────────────────────────────

def parse_event_to_task(event_summary: str, event_description: str = "") -> Optional[dict]:
    """Parse a calendar event into a structured task dict.

    Supports multiple formats:
        "Task: Write SoP, 3h, due Friday, P1"
        "Task: Write SoP | priority: high | due: 2026-02-25 | 120min"
        "Goal: Get into Masters | target: 2026-12-01 | category: education"
        "Blocker: Waiting for API access"

    Args:
        event_summary: Calendar event title
        event_description: Calendar event description (optional extra info)

    Returns:
        Parsed dict or None if not an agent inbox event
    """
    full_text = event_summary.strip()
    if event_description:
        full_text += "\n" + event_description.strip()

    # Detect type
    summary_lower = event_summary.lower()
    if summary_lower.startswith("task:"):
        return _parse_task(event_summary[5:].strip(), event_description)
    elif summary_lower.startswith("goal:"):
        return _parse_goal(event_summary[5:].strip(), event_description)
    elif summary_lower.startswith("blocker:"):
        return _parse_blocker(event_summary[8:].strip())
    else:
        return None  # Not an agent inbox event


def _parse_task(text: str, description: str = "") -> dict:
    """Parse task fields from text."""
    result: dict = {"type": "task"}

    # Pipe-separated key:value format: "title | priority: high | due: friday | 2h"
    if "|" in text:
        parts = [p.strip() for p in text.split("|")]
        result["title"] = parts[0]
        for part in parts[1:]:
            _extract_kv(part, result)
    else:
        # Comma-separated: "title, 3h, due friday, P1"
        parts = [p.strip() for p in text.split(",")]
        result["title"] = parts[0]
        for part in parts[1:]:
            _extract_kv(part, result)

    # Fallback: scan full text for patterns
    combined = text + ("\n" + description if description else "")

    if "duration_minutes" not in result:
        m = _DURATION_RE.search(combined)
        if m:
            if m.group(1):  # hours
                result["duration_minutes"] = int(float(m.group(1)) * 60)
            else:  # minutes
                result["duration_minutes"] = int(m.group(2))

    if "priority" not in result:
        m = _PRIORITY_RE.search(combined)
        if m:
            key = f"p{m.group(1)}" if m.group(1) else m.group(2).lower()
            result["priority"] = _PRIORITY_MAP.get(key, "medium")

    if "due_date" not in result:
        m = _DUE_RE.search(combined)
        if m:
            due_text = (m.group(1) or m.group(2) or m.group(3) or "").strip()
            dt = parse_relative_date(due_text)
            if dt:
                result["due_date"] = dt

    result.setdefault("priority", "medium")
    result.setdefault("energy_level", "medium")

    logger.debug(f"Parsed task: {result}")
    return result


def _parse_goal(text: str, description: str = "") -> dict:
    """Parse goal fields from text."""
    result: dict = {"type": "goal"}
    combined = text + ("\n" + description if description else "")

    if "|" in text:
        parts = [p.strip() for p in text.split("|")]
        result["title"] = parts[0]
        for part in parts[1:]:
            _extract_kv(part, result)
    else:
        result["title"] = text.split(",")[0].strip()

    # Extract target date
    m = re.search(r"target[:\s]+(.+?)(?:\n|$)", combined, re.I)
    if m:
        dt = parse_relative_date(m.group(1).strip())
        if dt:
            result["target_date"] = dt

    # Extract category
    m = re.search(r"category[:\s]+(\w+)", combined, re.I)
    if m:
        result["category"] = m.group(1).lower()

    result.setdefault("category", "general")
    return result


def _parse_blocker(text: str) -> dict:
    """Parse blocker fields from text."""
    result: dict = {"type": "blocker", "description": text.strip()}

    m = re.search(r"severity[:\s]+(\w+)", text, re.I)
    if m:
        sev = m.group(1).lower()
        result["severity"] = sev if sev in ("low", "medium", "high", "critical") else "medium"
    else:
        result.setdefault("severity", "medium")

    m = re.search(r"task[:\s#]+(\d+)", text, re.I)
    if m:
        result["task_id"] = int(m.group(1))

    return result


def _extract_kv(part: str, result: dict) -> None:
    """Extract a key:value pair from a text fragment and merge into result."""
    part = part.strip().rstrip(",")

    # "priority: high" or "priority high"
    m = re.match(r"priority[:\s]+(\w+)", part, re.I)
    if m:
        result["priority"] = _PRIORITY_MAP.get(m.group(1).lower(), "medium")
        return

    # "due: friday" or "due friday"
    m = re.match(r"(?:due|deadline|by)[:\s]+(.+)", part, re.I)
    if m:
        dt = parse_relative_date(m.group(1).strip())
        if dt:
            result["due_date"] = dt
        return

    # Duration: "3h", "90min", "90 minutes"
    m = _DURATION_RE.fullmatch(part)
    if m:
        if m.group(1):
            result["duration_minutes"] = int(float(m.group(1)) * 60)
        else:
            result["duration_minutes"] = int(m.group(2))
        return

    # Priority shorthand: P1, P2, P3, P4
    m = re.fullmatch(r"P([1-4])", part, re.I)
    if m:
        result["priority"] = _PRIORITY_MAP[f"p{m.group(1)}"]
        return

    # Energy level
    m = re.match(r"energy[:\s]+(\w+)", part, re.I)
    if m:
        result["energy_level"] = m.group(1).lower()
        return

    # Project ID
    m = re.match(r"project[:\s#]+(\d+)", part, re.I)
    if m:
        result["project_id"] = int(m.group(1))
        return
