"""Google Calendar API client."""

from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from loguru import logger

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings

# Scopes required for calendar read/write
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]

# Calendar colors (Google Calendar color IDs)
CALENDAR_COLORS = {
    "inbox": "9",        # Blue
    "focus_blocks": "10", # Green (Sage)
    "checkins": "4",      # Pink (Flamingo)
    "insights": "5",      # Yellow (Banana)
}

# Names for dedicated calendars
CALENDAR_NAMES = {
    "inbox": "Agent Inbox",
    "focus_blocks": "Focus Blocks",
    "checkins": "Check-ins",
    "insights": "Insights",
}


class GoogleCalendarClient:
    """Client for Google Calendar API operations."""

    def __init__(self):
        self._service = None
        self._credentials_path = Path(settings.google_credentials_path).expanduser()
        self._token_path = Path(settings.google_token_path).expanduser()
        self._calendar_ids: dict[str, str] = {}

    @property
    def available(self) -> bool:
        """Check if credentials file exists."""
        return self._credentials_path.exists()

    def authenticate(self) -> bool:
        """Authenticate with Google Calendar API.

        Returns:
            True if authentication succeeded
        """
        creds = None

        # Load existing token
        if self._token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(self._token_path), SCOPES
                )
            except Exception as e:
                logger.warning(f"Could not load existing token: {e}")

        # Refresh or get new token
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Google token refreshed")
                except Exception as e:
                    logger.warning(f"Token refresh failed: {e}")
                    creds = None

            if not creds:
                if not self._credentials_path.exists():
                    logger.error(
                        f"Credentials file not found: {self._credentials_path}\n"
                        "Run: python scripts/setup_google_calendar.py"
                    )
                    return False

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self._credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save token
            self._token_path.parent.mkdir(parents=True, exist_ok=True)
            self._token_path.write_text(creds.to_json())
            logger.info(f"Token saved to {self._token_path}")

        self._service = build("calendar", "v3", credentials=creds)
        logger.info("Google Calendar authenticated")
        return True

    def _get_service(self):
        """Get authenticated service, authenticating if needed."""
        if self._service is None:
            if not self.authenticate():
                raise RuntimeError("Google Calendar not authenticated")
        return self._service

    # ── Calendar Management ────────────────────────────────────────────────

    def list_calendars(self) -> list[dict]:
        """List all calendars."""
        try:
            service = self._get_service()
            result = service.calendarList().list().execute()
            return result.get("items", [])
        except HttpError as e:
            logger.error(f"Error listing calendars: {e}")
            return []

    def get_or_create_calendar(self, name: str, color_id: Optional[str] = None) -> Optional[str]:
        """Get existing calendar by name or create it.

        Args:
            name: Calendar name
            color_id: Google color ID (1-11)

        Returns:
            Calendar ID or None on failure
        """
        # Check if already exists
        for cal in self.list_calendars():
            if cal.get("summary") == name:
                logger.info(f"Found existing calendar: {name} ({cal['id']})")
                return cal["id"]

        # Create new calendar
        try:
            service = self._get_service()
            body = {"summary": name}
            if color_id:
                body["colorId"] = color_id

            result = service.calendars().insert(body=body).execute()
            cal_id = result["id"]
            logger.info(f"Created calendar: {name} ({cal_id})")
            return cal_id
        except HttpError as e:
            logger.error(f"Error creating calendar {name}: {e}")
            return None

    def setup_agent_calendars(self) -> dict[str, str]:
        """Create all 4 dedicated agent calendars.

        Returns:
            Dict mapping calendar type to calendar ID
        """
        calendar_ids = {}
        for key, name in CALENDAR_NAMES.items():
            cal_id = self.get_or_create_calendar(name, CALENDAR_COLORS.get(key))
            if cal_id:
                calendar_ids[key] = cal_id

        self._calendar_ids = calendar_ids
        # Persist calendar IDs
        id_file = self._token_path.parent / "calendar_ids.json"
        id_file.write_text(json.dumps(calendar_ids, indent=2))
        logger.info(f"Calendar IDs saved to {id_file}")
        return calendar_ids

    def load_calendar_ids(self) -> dict[str, str]:
        """Load saved calendar IDs."""
        id_file = self._token_path.parent / "calendar_ids.json"
        if id_file.exists():
            self._calendar_ids = json.loads(id_file.read_text())
        return self._calendar_ids

    def get_calendar_id(self, key: str) -> Optional[str]:
        """Get calendar ID by key (inbox, focus_blocks, checkins, insights)."""
        if not self._calendar_ids:
            self.load_calendar_ids()
        return self._calendar_ids.get(key)

    # ── Event Operations ───────────────────────────────────────────────────

    def list_events(
        self,
        calendar_id: str,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        sync_token: Optional[str] = None,
        max_results: int = 250
    ) -> tuple[list[dict], Optional[str]]:
        """List events from a calendar, supporting incremental sync.

        Args:
            calendar_id: Calendar ID
            time_min: Earliest event time (ignored with sync_token)
            time_max: Latest event time (ignored with sync_token)
            sync_token: Token from previous sync for incremental sync
            max_results: Maximum events to return

        Returns:
            Tuple of (events list, next_sync_token)
        """
        service = self._get_service()
        events = []
        next_sync_token = None

        try:
            kwargs: dict = {
                "calendarId": calendar_id,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
            }

            if sync_token:
                # Incremental sync — ignore time filters
                kwargs["syncToken"] = sync_token
            else:
                # Full sync
                if time_min:
                    kwargs["timeMin"] = time_min.isoformat() + "Z"
                if time_max:
                    kwargs["timeMax"] = time_max.isoformat() + "Z"
                else:
                    from datetime import timedelta
                    kwargs["timeMax"] = (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"

            # Paginate through results
            page_token = None
            while True:
                if page_token:
                    kwargs["pageToken"] = page_token

                result = service.events().list(**kwargs).execute()
                events.extend(result.get("items", []))

                page_token = result.get("nextPageToken")
                if not page_token:
                    next_sync_token = result.get("nextSyncToken")
                    break

        except HttpError as e:
            if e.resp.status == 410:  # Sync token invalid (GONE)
                logger.warning("Sync token expired, performing full sync")
                return self.list_events(calendar_id, time_min, time_max, sync_token=None)
            logger.error(f"Error listing events: {e}")

        return events, next_sync_token

    def create_event(self, calendar_id: str, event_data: dict) -> Optional[dict]:
        """Create a calendar event.

        Args:
            calendar_id: Target calendar ID
            event_data: Event body dict

        Returns:
            Created event dict or None on failure
        """
        try:
            service = self._get_service()
            result = service.events().insert(
                calendarId=calendar_id,
                body=event_data
            ).execute()
            logger.debug(f"Created event: {result.get('summary')} ({result.get('id')})")
            return result
        except HttpError as e:
            logger.error(f"Error creating event: {e}")
            return None

    def update_event(self, calendar_id: str, event_id: str, event_data: dict) -> Optional[dict]:
        """Update an existing calendar event."""
        try:
            service = self._get_service()
            result = service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event_data
            ).execute()
            logger.debug(f"Updated event: {result.get('summary')}")
            return result
        except HttpError as e:
            logger.error(f"Error updating event {event_id}: {e}")
            return None

    def delete_event(self, calendar_id: str, event_id: str) -> bool:
        """Delete a calendar event."""
        try:
            service = self._get_service()
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            logger.debug(f"Deleted event {event_id}")
            return True
        except HttpError as e:
            logger.error(f"Error deleting event {event_id}: {e}")
            return False

    def get_event(self, calendar_id: str, event_id: str) -> Optional[dict]:
        """Get a single event by ID."""
        try:
            service = self._get_service()
            return service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
        except HttpError as e:
            logger.error(f"Error getting event {event_id}: {e}")
            return None

    # ── Event Builders ─────────────────────────────────────────────────────

    def build_focus_block(
        self,
        title: str,
        start: datetime,
        end: datetime,
        task_id: int,
        description: str = ""
    ) -> dict:
        """Build a focus block event dict.

        Args:
            title: Task title
            start: Start datetime (local time)
            end: End datetime (local time)
            task_id: Database task ID
            description: Optional extra description

        Returns:
            Event body dict ready for create_event()
        """
        return {
            "summary": f"Focus: {title}",
            "description": description or f"Scheduled focus block\nTask ID: {task_id}",
            "start": {"dateTime": start.isoformat(), "timeZone": _local_tz()},
            "end": {"dateTime": end.isoformat(), "timeZone": _local_tz()},
            "colorId": "10",  # Green
            "extendedProperties": {
                "private": {
                    "agent_task_id": str(task_id),
                    "agent_type": "focus_block",
                    "agent_version": "1",
                }
            },
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": 5}]
            }
        }

    def build_checkin_event(
        self,
        date: datetime,
        plan_text: str,
        local_url: str = "http://localhost:8000"
    ) -> dict:
        """Build a daily check-in event."""
        date_str = date.strftime("%A, %B %d")
        return {
            "summary": f"Daily Check-in — {date_str}",
            "description": (
                f"Good morning! Here's your plan for today:\n\n"
                f"{plan_text}\n\n"
                "---\n"
                "📋 What did you accomplish yesterday?\n-\n\n"
                "⚠️  Any blockers or challenges?\n-\n\n"
                "🎯 How did today go?\n-\n\n"
                f"View full dashboard: {local_url}"
            ),
            "start": {
                "dateTime": date.replace(hour=7, minute=0, second=0).isoformat(),
                "timeZone": _local_tz()
            },
            "end": {
                "dateTime": date.replace(hour=7, minute=15, second=0).isoformat(),
                "timeZone": _local_tz()
            },
            "colorId": "4",  # Pink
            "extendedProperties": {
                "private": {
                    "agent_type": "checkin",
                    "agent_date": date.date().isoformat(),
                }
            },
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": 0}]
            }
        }

    def build_insights_event(
        self,
        week_label: str,
        insights_text: str,
        local_url: str = "http://localhost:8000"
    ) -> dict:
        """Build a weekly insights event."""
        from datetime import timedelta
        monday = _this_monday()
        return {
            "summary": f"Weekly Insights — {week_label}",
            "description": f"{insights_text}\n\nFull report: {local_url}/insights",
            "start": {
                "dateTime": monday.replace(hour=8, minute=0, second=0).isoformat(),
                "timeZone": _local_tz()
            },
            "end": {
                "dateTime": monday.replace(hour=8, minute=30, second=0).isoformat(),
                "timeZone": _local_tz()
            },
            "colorId": "5",  # Yellow
            "extendedProperties": {
                "private": {
                    "agent_type": "insights",
                    "agent_week": week_label,
                }
            }
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _local_tz() -> str:
    """Get configured timezone name (from settings.TIMEZONE)."""
    from app.config import settings
    return settings.timezone


def _this_monday() -> datetime:
    """Get this Monday at midnight."""
    today = datetime.now()
    days_since_monday = today.weekday()
    monday = today - __import__("datetime").timedelta(days=days_since_monday)
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)
