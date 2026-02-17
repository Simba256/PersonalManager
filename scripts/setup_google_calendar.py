#!/usr/bin/env python3
"""
Google Calendar OAuth Setup Script for Personal Manager.

Run this script once to:
1. Authenticate with your Google account
2. Create the 4 dedicated agent calendars
3. Save credentials for future use

Usage:
    python scripts/setup_google_calendar.py
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_credentials():
    """Check for Google credentials file and guide user if missing."""
    from app.config import settings

    creds_path = Path(settings.google_credentials_path).expanduser()

    if creds_path.exists():
        print(f"✓ Credentials file found: {creds_path}")
        return True

    print("\n" + "═" * 60)
    print("  Google Calendar Credentials Not Found")
    print("═" * 60)
    print(f"\nExpected location: {creds_path}")
    print("\nTo set up Google Calendar integration:")
    print()
    print("  1. Go to: https://console.cloud.google.com/")
    print("  2. Create a new project: 'Personal Manager'")
    print("  3. Go to: APIs & Services → Library")
    print("  4. Search and enable: 'Google Calendar API'")
    print("  5. Go to: APIs & Services → OAuth consent screen")
    print("     - User type: External")
    print("     - Add your email as test user")
    print("  6. Go to: APIs & Services → Credentials")
    print("     - Create Credentials → OAuth client ID")
    print("     - Application type: Desktop app")
    print("     - Download the JSON file")
    print(f"  7. Save the downloaded file as:")
    print(f"     {creds_path}")
    print()
    print("  Then run this script again.")
    print()
    return False


def run_oauth_flow():
    """Run the OAuth flow to get user consent."""
    from app.calendar.google import GoogleCalendarClient

    print("\n" + "═" * 60)
    print("  Starting Google OAuth Flow")
    print("═" * 60)
    print("\nA browser window will open for you to grant calendar access.")
    print("Please log in and click 'Allow'.\n")

    client = GoogleCalendarClient()
    if not client.authenticate():
        print("✗ Authentication failed")
        return None

    print("✓ Authentication successful!")
    return client


def create_calendars(client):
    """Create the 4 dedicated agent calendars."""
    print("\n" + "═" * 60)
    print("  Creating Agent Calendars")
    print("═" * 60)

    calendar_ids = client.setup_agent_calendars()

    if not calendar_ids:
        print("✗ Failed to create calendars")
        return False

    print()
    names = {
        "inbox": "Agent Inbox",
        "focus_blocks": "Focus Blocks",
        "checkins": "Check-ins",
        "insights": "Insights",
    }
    for key, cal_id in calendar_ids.items():
        print(f"  ✓ {names.get(key, key)}: {cal_id}")

    return True


def print_usage_guide():
    """Print how to use calendar integration."""
    print("\n" + "═" * 60)
    print("  Calendar Integration Ready!")
    print("═" * 60)
    print()
    print("Your Personal Manager now has 4 dedicated calendars:")
    print()
    print("  📥 Agent Inbox   — Add tasks by creating events here:")
    print('     Title: "Task: Write masters SoP"')
    print('     Title: "Task: Review PR #42, 1h, due friday, P2"')
    print('     Title: "Goal: Get into Masters | target: 2026-12-01"')
    print()
    print("  🟢 Focus Blocks  — Agent schedules your tasks here")
    print("     (read-only, agent manages this)")
    print()
    print("  🔔 Check-ins     — Daily 7 AM planning prompts")
    print("     (edit description to log progress)")
    print()
    print("  📊 Insights      — Weekly productivity summaries")
    print()
    print("Quick Start:")
    print()
    print("  1. Start the server:")
    print("     uvicorn app.main:app --reload")
    print()
    print("  2. Add a task via Google Calendar:")
    print("     Open Agent Inbox calendar → New Event")
    print('     Title: "Task: Your task here"')
    print()
    print("  3. Watch it appear in your tasks:")
    print("     pm task list")
    print()
    print("  4. Or add tasks directly via CLI:")
    print("     pm task add 'Your task' --priority high")
    print()


def main():
    print()
    print("  Personal Manager — Google Calendar Setup")
    print()

    # Step 1: Check credentials
    if not check_credentials():
        sys.exit(1)

    # Step 2: OAuth flow
    client = run_oauth_flow()
    if not client:
        sys.exit(1)

    # Step 3: Create calendars
    if not create_calendars(client):
        sys.exit(1)

    # Step 4: Show usage
    print_usage_guide()
    print("  Setup complete! ✓")
    print()


if __name__ == "__main__":
    main()
