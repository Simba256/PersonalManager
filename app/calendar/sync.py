"""Calendar sync engine — bidirectional sync between Google Calendar and local DB."""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
from sqlalchemy.orm import Session

from app.calendar.google import GoogleCalendarClient
from app.calendar.parser import parse_event_to_task
from app.database import SessionLocal
from app.models import SyncState, Task, Goal, Blocker, Meeting, Schedule
from app.services.task_service import TaskService
from app.services.project_service import ProjectService


class CalendarSync:
    """Handles bidirectional sync between Google Calendar and local database."""

    def __init__(self):
        self.client = GoogleCalendarClient()
        self._db: Optional[Session] = None

    def _get_db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def close(self):
        if self._db:
            self._db.close()
            self._db = None

    # ── Main Sync Entry Points ──────────────────────────────────────────────

    def sync_all(self) -> dict:
        """Run a full sync cycle: pull inbox events → create tasks → push focus blocks.

        Returns:
            Summary dict with counts
        """
        if not self.client.available:
            logger.warning("Google Calendar not configured, skipping sync")
            return {"skipped": True}

        try:
            if not self.client.authenticate():
                return {"error": "Authentication failed"}
        except Exception as e:
            logger.error(f"Calendar auth error: {e}")
            return {"error": str(e)}

        summary = {
            "inbox_processed": 0,
            "tasks_created": 0,
            "goals_created": 0,
            "meetings_synced": 0,
            "focus_blocks_created": 0,
        }

        # 1. Process inbox events → create tasks/goals
        inbox_result = self.process_inbox()
        summary["inbox_processed"] = inbox_result.get("processed", 0)
        summary["tasks_created"] = inbox_result.get("tasks", 0)
        summary["goals_created"] = inbox_result.get("goals", 0)

        # 2. Sync meetings from primary calendar
        meetings = self.sync_meetings()
        summary["meetings_synced"] = meetings

        logger.info(f"Sync complete: {summary}")
        return summary

    def process_inbox(self) -> dict:
        """Process Agent Inbox calendar events, converting them to tasks/goals.

        Returns:
            Dict with counts of processed items
        """
        calendar_id = self.client.get_calendar_id("inbox")
        if not calendar_id:
            logger.warning("Inbox calendar not configured")
            return {}

        db = self._get_db()
        task_service = TaskService(db)
        counts = {"processed": 0, "tasks": 0, "goals": 0, "errors": 0}

        # Fetch all upcoming inbox events
        events, _ = self.client.list_events(
            calendar_id,
            time_min=datetime.utcnow() - timedelta(hours=1),
            time_max=datetime.utcnow() + timedelta(days=365)
        )

        for event in events:
            if event.get("status") == "cancelled":
                continue

            summary = event.get("summary", "")
            description = event.get("description", "")
            event_id = event.get("id")

            try:
                parsed = parse_event_to_task(summary, description)
                if not parsed:
                    continue  # Not an agent event

                counts["processed"] += 1
                item_type = parsed.get("type")

                if item_type == "task":
                    task = task_service.create(
                        title=parsed["title"],
                        priority=parsed.get("priority", "medium"),
                        estimate_minutes=parsed.get("duration_minutes"),
                        due_date=parsed.get("due_date"),
                        energy_level=parsed.get("energy_level", "medium"),
                        project_id=parsed.get("project_id"),
                    )
                    counts["tasks"] += 1
                    logger.info(f"Created task from inbox: #{task.id} - {task.title}")

                elif item_type == "goal":
                    goal = Goal(
                        title=parsed["title"],
                        target_date=parsed.get("target_date"),
                        category=parsed.get("category"),
                    )
                    db.add(goal)
                    db.commit()
                    counts["goals"] += 1
                    logger.info(f"Created goal from inbox: #{goal.id} - {goal.title}")

                elif item_type == "blocker":
                    blocker = Blocker(
                        description=parsed["description"],
                        severity=parsed.get("severity", "medium"),
                        task_id=parsed.get("task_id"),
                    )
                    db.add(blocker)
                    db.commit()
                    logger.info(f"Created blocker from inbox: {blocker.description[:50]}")

                # Delete processed inbox event
                self.client.delete_event(calendar_id, event_id)

            except Exception as e:
                logger.error(f"Error processing inbox event '{summary}': {e}")
                counts["errors"] += 1

        return counts

    def sync_meetings(self) -> int:
        """Sync meetings from primary calendar into local DB.

        Returns:
            Number of meetings synced
        """
        db = self._get_db()
        sync_state = self._get_sync_state(db, "google", "primary")

        events, new_token = self.client.list_events(
            "primary",
            time_min=datetime.utcnow(),
            time_max=datetime.utcnow() + timedelta(days=30),
            sync_token=sync_state.sync_token if sync_state else None
        )

        count = 0
        for event in events:
            # Skip all-day events and agent-created events
            if event.get("start", {}).get("date"):  # all-day
                continue
            ext_props = event.get("extendedProperties", {}).get("private", {})
            if ext_props.get("agent_type"):  # Our own event
                continue

            if event.get("status") == "cancelled":
                self._delete_meeting(db, event["id"])
                continue

            self._upsert_meeting(db, event)
            count += 1

        # Save new sync token
        self._save_sync_state(db, "google", "primary", new_token)
        return count

    def create_focus_blocks_for_tasks(self, tasks: list[Task]) -> int:
        """Create calendar focus blocks for a list of tasks.

        Schedules tasks into available time slots in Focus Blocks calendar.

        Returns:
            Number of focus blocks created
        """
        calendar_id = self.client.get_calendar_id("focus_blocks")
        if not calendar_id:
            logger.warning("Focus Blocks calendar not configured")
            return 0

        db = self._get_db()
        created = 0

        for task in tasks:
            # Skip if already has a scheduled block
            existing = db.query(Schedule).filter(
                Schedule.task_id == task.id,
                Schedule.status == "scheduled"
            ).first()
            if existing:
                continue

            duration = task.estimate_minutes or 60
            slot = self._find_next_available_slot(db, duration)
            if not slot:
                continue

            start, end = slot
            event = self.client.create_event(
                calendar_id,
                self.client.build_focus_block(task.title, start, end, task.id)
            )
            if event:
                schedule = Schedule(
                    task_id=task.id,
                    calendar_event_id=event["id"],
                    calendar_id=calendar_id,
                    start_time=start,
                    end_time=end,
                    status="scheduled"
                )
                db.add(schedule)
                task.status = "scheduled"
                created += 1

        db.commit()
        logger.info(f"Created {created} focus blocks")
        return created

    def create_daily_checkin(self, date: Optional[datetime] = None, plan_text: str = "") -> Optional[str]:
        """Create a daily check-in event in the Check-ins calendar.

        Returns:
            Calendar event ID or None
        """
        calendar_id = self.client.get_calendar_id("checkins")
        if not calendar_id:
            return None

        target = date or datetime.now()
        event_data = self.client.build_checkin_event(target, plan_text)
        event = self.client.create_event(calendar_id, event_data)
        if event:
            logger.info(f"Created daily check-in for {target.date()}")
            return event["id"]
        return None

    def create_insights_event(self, week_label: str, insights_text: str) -> Optional[str]:
        """Create a weekly insights event in the Insights calendar."""
        calendar_id = self.client.get_calendar_id("insights")
        if not calendar_id:
            return None

        event_data = self.client.build_insights_event(week_label, insights_text)
        event = self.client.create_event(calendar_id, event_data)
        if event:
            logger.info(f"Created insights event for {week_label}")
            return event["id"]
        return None

    # ── Helpers ────────────────────────────────────────────────────────────

    def _find_next_available_slot(
        self,
        db: Session,
        duration_minutes: int
    ) -> Optional[tuple[datetime, datetime]]:
        """Find the next available time slot for a focus block.

        Simple heuristic: fill from 9 AM, skip meetings and existing blocks.
        """
        from datetime import time as dtime

        working_start = dtime(9, 0)
        working_end = dtime(18, 0)
        now = datetime.now()

        # Try next 7 days
        for day_offset in range(7):
            day = now + timedelta(days=day_offset)
            if day.weekday() >= 5:  # Skip weekends
                continue

            day_start = day.replace(
                hour=working_start.hour,
                minute=working_start.minute,
                second=0, microsecond=0
            )
            day_end = day.replace(
                hour=working_end.hour,
                minute=working_end.minute,
                second=0, microsecond=0
            )

            # If today, start from current time (next hour)
            if day_offset == 0 and now > day_start:
                day_start = now.replace(
                    minute=0, second=0, microsecond=0
                ) + timedelta(hours=1)

            # Get existing blocks for this day
            existing = db.query(Schedule).filter(
                Schedule.start_time >= day_start,
                Schedule.start_time < day_end,
                Schedule.status != "cancelled"
            ).order_by(Schedule.start_time).all()

            meetings = db.query(Meeting).filter(
                Meeting.start_time >= day_start,
                Meeting.start_time < day_end
            ).order_by(Meeting.start_time).all()

            # Build list of busy slots
            busy = sorted(
                [(s.start_time, s.end_time) for s in existing] +
                [(m.start_time, m.end_time) for m in meetings],
                key=lambda x: x[0]
            )

            # Find first free slot
            cursor = day_start
            for busy_start, busy_end in busy:
                if cursor + timedelta(minutes=duration_minutes) <= busy_start:
                    return cursor, cursor + timedelta(minutes=duration_minutes)
                cursor = max(cursor, busy_end)

            # Try after last busy slot
            if cursor + timedelta(minutes=duration_minutes) <= day_end:
                return cursor, cursor + timedelta(minutes=duration_minutes)

        return None

    def _upsert_meeting(self, db: Session, event: dict) -> None:
        """Insert or update a meeting from a calendar event."""
        event_id = event["id"]
        existing = db.query(Meeting).filter(
            Meeting.calendar_event_id == event_id
        ).first()

        start_str = event.get("start", {}).get("dateTime", "")
        end_str = event.get("end", {}).get("dateTime", "")

        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00")).replace(tzinfo=None)
            end = datetime.fromisoformat(end_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return

        attendees_raw = event.get("attendees", [])
        attendees = ",".join(a.get("email", "") for a in attendees_raw)

        if existing:
            existing.title = event.get("summary", "(No title)")
            existing.start_time = start
            existing.end_time = end
            existing.attendees = attendees
        else:
            meeting = Meeting(
                calendar_event_id=event_id,
                calendar_id="primary",
                source="google",
                title=event.get("summary", "(No title)"),
                description=event.get("description"),
                start_time=start,
                end_time=end,
                attendees=attendees,
                organizer=event.get("organizer", {}).get("email"),
                location=event.get("location"),
                meeting_url=event.get("hangoutLink") or event.get("location"),
            )
            db.add(meeting)

        db.commit()

    def _delete_meeting(self, db: Session, calendar_event_id: str) -> None:
        db.query(Meeting).filter(
            Meeting.calendar_event_id == calendar_event_id
        ).delete()
        db.commit()

    def _get_sync_state(self, db: Session, provider: str, calendar_id: str) -> Optional[SyncState]:
        return db.query(SyncState).filter(
            SyncState.provider == provider,
            SyncState.calendar_id == calendar_id
        ).first()

    def _save_sync_state(
        self,
        db: Session,
        provider: str,
        calendar_id: str,
        sync_token: Optional[str]
    ) -> None:
        state = self._get_sync_state(db, provider, calendar_id)
        if state:
            state.sync_token = sync_token
            state.last_sync_at = datetime.utcnow()
            state.last_sync_status = "success"
        else:
            state = SyncState(
                provider=provider,
                calendar_id=calendar_id,
                calendar_name=calendar_id,
                sync_token=sync_token,
                last_sync_at=datetime.utcnow(),
                last_sync_status="success"
            )
            db.add(state)
        db.commit()
