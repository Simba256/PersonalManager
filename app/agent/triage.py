"""Inbox triage agent — parses and classifies calendar inbox events using LLM fallback."""

from __future__ import annotations

from typing import Optional
from loguru import logger

from app.calendar.parser import parse_event_to_task
from app.llm.router import get_llm
from app.llm.prompts import SYSTEM_TRIAGE


class InboxTriage:
    """Hybrid event parser: rule-based first, LLM fallback for ambiguous inputs.

    The rule-based parser handles structured formats like:
      "Task: Title, 2h, due Friday, P1"

    The LLM handles freeform inputs like:
      "Need to finish the API docs before the team review on Thursday"
    """

    def __init__(self):
        self._llm = get_llm()

    def parse(self, event_summary: str, event_description: str = "") -> Optional[dict]:
        """Parse a calendar event into a structured task/goal/blocker.

        Tries rule-based parser first, falls back to LLM for unrecognized formats.

        Returns:
            Dict with type, title, priority, etc. or None if not an agent event
        """
        # Fast path: rule-based parser
        result = parse_event_to_task(event_summary, event_description)
        if result:
            return result

        # Slow path: LLM for freeform natural language (only if available)
        if not self._llm.available:
            return None

        return self._llm_parse(event_summary, event_description)

    def _llm_parse(self, summary: str, description: str) -> Optional[dict]:
        """Use LLM to parse an ambiguous event into a structured item."""
        prompt_parts = [f"Event title: {summary}"]
        if description:
            prompt_parts.append(f"Event description: {description}")
        prompt = "\n".join(prompt_parts)

        parsed = self._llm.complete_json(
            prompt=prompt,
            system=SYSTEM_TRIAGE,
            temperature=0.1,
            max_tokens=256,
        )

        if not parsed:
            return None

        item_type = parsed.get("type")
        if not item_type:
            return None

        # Normalize and validate
        result = {"type": item_type}

        if item_type == "task":
            title = parsed.get("title", "").strip()
            if not title:
                return None
            result.update({
                "title": title,
                "priority": _normalize_priority(parsed.get("priority", "medium")),
                "estimate_minutes": _parse_int(parsed.get("estimate_minutes")),
                "due_date": parsed.get("due_date"),
                "energy_level": parsed.get("energy_level", "medium"),
            })

        elif item_type == "goal":
            title = parsed.get("title", "").strip()
            if not title:
                return None
            result.update({
                "title": title,
                "target_date": parsed.get("target_date"),
                "category": parsed.get("category"),
            })

        elif item_type == "blocker":
            desc = parsed.get("description", "").strip()
            if not desc:
                return None
            result.update({
                "description": desc,
                "severity": parsed.get("severity", "medium"),
                "task_id": parsed.get("task_id"),
            })

        else:
            return None

        logger.info(f"LLM triage parsed '{summary}' → {item_type}: {result.get('title', result.get('description', ''))[:60]}")
        return result

    def batch_parse(self, events: list[dict]) -> list[dict]:
        """Parse a list of calendar events, returning only successfully parsed items.

        Each input dict should have 'id', 'summary', 'description' keys.
        Returns list of dicts with original event data merged with parsed fields.
        """
        results = []
        for event in events:
            summary = event.get("summary", "")
            description = event.get("description", "") or ""

            parsed = self.parse(summary, description)
            if parsed:
                results.append({**event, **parsed})

        return results


def _normalize_priority(value: str) -> str:
    mapping = {"p1": "critical", "p2": "high", "p3": "medium", "p4": "low"}
    v = str(value).lower().strip()
    return mapping.get(v, v if v in ("low", "medium", "high", "critical") else "medium")


def _parse_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
