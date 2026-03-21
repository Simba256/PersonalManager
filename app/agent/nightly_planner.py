"""Nightly planning agent — generates a time-slotted daily schedule at 2 AM."""

from __future__ import annotations

import json
import subprocess
from datetime import date, datetime, timedelta
from typing import Optional
from loguru import logger

from app.config import settings
from app.llm.router import get_llm


SYSTEM_PROMPT = """You are a daily planning assistant. Given pending tasks, meetings, and a previous-day
summary, produce a realistic time-blocked schedule for the working day.

Rules:
- Working hours: 09:00–18:00
- Include a 15-min break every 90 min of focused work
- Honour task priority: critical > high > medium > low
- Use task estimate_minutes as block duration; default 60 min if unknown
- Leave meetings in their fixed time slots; schedule tasks around them
- Return ONLY a JSON array of slot objects, no other text:
  [{"id":"s1","start":"09:00","duration_minutes":90,
    "title":"...","type":"task","task_id":5,"notes":"..."},...]

Slot types: "task" | "break" | "meeting" | "admin"
"""


class NightlyPlanner:
    """Generates and manages interactive daily plans."""

    PLAN_DIR = settings.data_dir / "plans"

    def run(self, target_date: date) -> dict:
        """Full pipeline: gather context → LLM → save → notify."""
        context = self._gather_context(target_date)
        slots = self._call_llm(context, target_date)
        plan = {
            "date": str(target_date),
            "generated_at": datetime.now().isoformat(),
            "status": "draft",
            "summary": context.get("summary", f"{len(slots)} slots planned"),
            "slots": slots,
            "calendar_event_ids": [],
        }
        self.save(target_date, plan)
        self.send_notification(
            f"Daily plan ready for {target_date} — {len(slots)} slots"
        )
        logger.info(f"Nightly plan generated for {target_date}: {len(slots)} slots")
        return plan

    def _gather_context(self, target_date: date) -> dict:
        """Load EOD summary and task/meeting data for context."""
        context: dict = {}

        # Load EOD JSON for the previous day
        yesterday = target_date - timedelta(days=1)
        eod_path = settings.data_dir / "eod" / f"{yesterday}.json"
        if eod_path.exists():
            try:
                eod = json.loads(eod_path.read_text())
                context["eod_summary"] = eod.get("summary", "")
                context["eod_date"] = str(yesterday)
            except Exception as e:
                logger.warning(f"Could not load EOD for {yesterday}: {e}")

        # Gather tasks and meetings from DailyPlanner
        try:
            from app.agent.planner import DailyPlanner
            from app.database import SessionLocal

            db = SessionLocal()
            try:
                planner = DailyPlanner(db)
                plan_data = planner.generate_plan(
                    date=datetime.combine(target_date, datetime.min.time())
                )
                context["pending_tasks"] = self._extract_task_list(db)
                context["meetings"] = plan_data.get("plan_text", "")
                context["summary"] = (
                    f"Focus day: {plan_data['pending_count']} tasks, "
                    f"{plan_data['overdue_count']} overdue"
                )
                planner.close()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not gather planner context: {e}")
            context["pending_tasks"] = []
            context["summary"] = "Plan generated"

        # Load cross-project snapshot
        try:
            from app.integrations.project_scanner import ProjectScanner
            snapshot = ProjectScanner().load_snapshot()
            if snapshot:
                context["project_snapshot"] = snapshot
        except Exception as e:
            logger.debug(f"Could not load project snapshot: {e}")

        return context

    def _extract_task_list(self, db) -> list[dict]:
        """Extract pending tasks with id, title, priority, estimate_minutes."""
        try:
            from app.services.task_service import TaskService

            service = TaskService(db)
            pending = service.get_pending_for_schedule()
            return [
                {
                    "id": t.id,
                    "title": t.title,
                    "priority": t.priority or "medium",
                    "estimate_minutes": t.estimate_minutes or 60,
                    "energy_level": t.energy_level,
                }
                for t in pending[:15]
            ]
        except Exception as e:
            logger.warning(f"Could not extract task list: {e}")
            return []

    def _call_llm(self, context: dict, target_date: date) -> list[dict]:
        """Ask LLM to produce a JSON array of time slots."""
        llm = get_llm()
        if not llm.available:
            logger.info("LLM unavailable — using rule-based planner")
            return self._rule_based_slots(context, target_date)

        tasks = context.get("pending_tasks", [])
        eod = context.get("eod_summary", "")

        task_lines = "\n".join(
            f"  - [{t['priority'].upper()}] {t['title']} "
            f"({t['estimate_minutes']}min, energy={t.get('energy_level','?')})"
            for t in tasks
        ) or "  No pending tasks."

        user_prompt = (
            f"Date: {target_date.strftime('%A, %B %d, %Y')}\n\n"
            f"Pending tasks:\n{task_lines}\n\n"
        )
        if eod:
            user_prompt += f"Yesterday's EOD summary:\n{eod}\n\n"

        meetings_text = context.get("meetings", "")
        if meetings_text:
            user_prompt += f"Context / meetings:\n{meetings_text}\n\n"

        # Append active project context from snapshot
        snapshot = context.get("project_snapshot")
        if snapshot and snapshot.get("projects"):
            active_lines = []
            for p in snapshot["projects"]:
                tracker = p.get("tracker")
                if not tracker:
                    continue
                wip = tracker.get("in_progress", [])
                if not wip and tracker.get("status") != "Active":
                    continue
                line = f"  - {p['name']}"
                if wip:
                    line += f": {wip[0][:60]}"
                active_lines.append(line)
            if active_lines:
                user_prompt += "Active projects with in-progress work:\n" + "\n".join(active_lines) + "\n\n"

        user_prompt += (
            "Produce a full day schedule as a JSON array of slot objects. "
            "Return ONLY the JSON array, no other text."
        )

        try:
            result = llm.complete_json(
                prompt=user_prompt,
                system=SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=2000,
            )
            if isinstance(result, list):
                return self._validate_slots(result)
            # Some LLMs may return {"slots": [...]}
            if isinstance(result, dict) and "slots" in result:
                return self._validate_slots(result["slots"])
        except Exception as e:
            logger.warning(f"LLM slot generation failed: {e}")

        return self._rule_based_slots(context, target_date)

    def _validate_slots(self, slots: list) -> list[dict]:
        """Ensure each slot has required fields; drop invalid ones."""
        valid = []
        for i, s in enumerate(slots, 1):
            if not isinstance(s, dict):
                continue
            slot = {
                "id": s.get("id") or f"s{i}",
                "start": s.get("start", "09:00"),
                "duration_minutes": int(s.get("duration_minutes", 60)),
                "title": s.get("title", "Untitled"),
                "type": s.get("type", "task"),
                "task_id": s.get("task_id"),
                "notes": s.get("notes", ""),
            }
            valid.append(slot)
        return valid

    def _rule_based_slots(self, context: dict, target_date: date) -> list[dict]:
        """Fallback: pack tasks into 09:00–18:00 with 15-min breaks."""
        tasks = context.get("pending_tasks", [])

        PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_tasks = sorted(
            tasks, key=lambda t: PRIORITY_ORDER.get(t.get("priority", "medium"), 2)
        )

        slots: list[dict] = []
        # Current time cursor in minutes from midnight
        cursor = 9 * 60  # 09:00
        end_of_day = 18 * 60  # 18:00
        work_since_break = 0
        slot_index = 1

        def mins_to_hhmm(m: int) -> str:
            return f"{m // 60:02d}:{m % 60:02d}"

        for task in sorted_tasks:
            if cursor >= end_of_day:
                break

            # Insert break every 90 min of focused work
            if work_since_break >= 90:
                break_end = cursor + 15
                if break_end <= end_of_day:
                    slots.append({
                        "id": f"s{slot_index}",
                        "start": mins_to_hhmm(cursor),
                        "duration_minutes": 15,
                        "title": "Break",
                        "type": "break",
                        "task_id": None,
                        "notes": "",
                    })
                    slot_index += 1
                    cursor = break_end
                    work_since_break = 0

            duration = min(task.get("estimate_minutes", 60), end_of_day - cursor)
            if duration <= 0:
                break

            slots.append({
                "id": f"s{slot_index}",
                "start": mins_to_hhmm(cursor),
                "duration_minutes": duration,
                "title": task["title"],
                "type": "task",
                "task_id": task.get("id"),
                "notes": f"Priority: {task.get('priority', 'medium')}",
            })
            slot_index += 1
            cursor += duration
            work_since_break += duration

        if not slots:
            slots.append({
                "id": "s1",
                "start": "09:00",
                "duration_minutes": 60,
                "title": "Planning & Admin",
                "type": "admin",
                "task_id": None,
                "notes": "No tasks scheduled — review goals",
            })

        return slots

    def send_notification(self, message: str) -> None:
        """Send a desktop notification via notify-send."""
        try:
            subprocess.run(
                ["notify-send", "-u", "normal", "-t", "10000", "Personal Manager", message],
                check=False,
                timeout=5,
            )
        except Exception as e:
            logger.debug(f"notify-send unavailable: {e}")

    def save(self, target_date: date, plan: dict) -> None:
        """Persist plan JSON to data/plans/YYYY-MM-DD.json."""
        self.PLAN_DIR.mkdir(parents=True, exist_ok=True)
        path = self.PLAN_DIR / f"{target_date}.json"
        path.write_text(json.dumps(plan, indent=2))

    def load(self, target_date: date) -> Optional[dict]:
        """Load plan JSON for given date, or None if not found."""
        path = self.PLAN_DIR / f"{target_date}.json"
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception as e:
                logger.warning(f"Could not load plan for {target_date}: {e}")
        return None

    def finalize(self, target_date: date, slots: list[dict]) -> list[str]:
        """Post slots to Google Calendar and mark plan as finalized.

        Returns list of created Google Calendar event IDs.
        """
        from app.calendar.google import GoogleCalendarClient

        client = GoogleCalendarClient()
        if not client.available or not client.authenticate():
            logger.warning("Google Calendar not available for finalize")
            return []

        event_ids: list[str] = []
        date_str = str(target_date)

        for slot in slots:
            if slot.get("type") == "break":
                continue  # Don't post breaks to calendar

            start_time = slot.get("start", "09:00")
            duration = int(slot.get("duration_minutes", 60))

            # Build start/end datetime strings
            start_h, start_m = map(int, start_time.split(":"))
            start_total = start_h * 60 + start_m
            end_total = start_total + duration
            end_h, end_m = end_total // 60, end_total % 60

            start_dt = f"{date_str}T{start_h:02d}:{start_m:02d}:00"
            end_dt = f"{date_str}T{end_h:02d}:{end_m:02d}:00"

            event_data = {
                "summary": slot.get("title", "Untitled"),
                "description": slot.get("notes", ""),
                "start": {"dateTime": start_dt, "timeZone": settings.timezone},
                "end": {"dateTime": end_dt, "timeZone": settings.timezone},
            }

            try:
                event = client.create_event("primary", event_data)
                if event and event.get("id"):
                    event_ids.append(event["id"])
            except Exception as e:
                logger.error(f"Failed to create calendar event for slot {slot.get('id')}: {e}")

        # Update plan file
        plan = self.load(target_date)
        if plan:
            plan["status"] = "finalized"
            plan["calendar_event_ids"] = event_ids
            plan["slots"] = slots
            self.save(target_date, plan)

        return event_ids
