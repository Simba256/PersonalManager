# Calendar Integration Guide

Complete guide to calendar integration with Personal Manager.

## Overview

Personal Manager uses calendar as the primary interface for task management and scheduling. The system supports:
- **Google Calendar** (primary)
- **CalDAV** (generic standard for NextCloud, Fastmail, etc.)

## Architecture

```
┌─────────────────────────────────────────┐
│   Your Calendar App (Google/CalDAV)     │
│   • Agent Inbox                          │
│   • Focus Blocks                         │
│   • Check-ins                           │
│   • Insights                            │
└────────────────┬────────────────────────┘
                 │ Bidirectional Sync
                 ▼
┌─────────────────────────────────────────┐
│   Personal Manager Sync Engine          │
│   • Incremental sync (every 2 min)      │
│   • Conflict resolution                 │
│   • Metadata preservation               │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│   Local Database                        │
│   • Tasks, Goals, Schedule              │
│   • Sync tokens and state               │
└─────────────────────────────────────────┘
```

## Dedicated Calendars

Personal Manager creates and manages 4 dedicated calendars:

### 1. Agent Inbox
**Purpose**: Input channel for creating tasks and goals

**How to use**:
```
Create calendar event:
Title: "Task: Write masters statement of purpose"
Description: "Priority: High, Duration: 3h, Due: 2026-02-25"
Time: Any (ignored)
```

**Processing**:
1. Agent detects new event (every 5 min)
2. Parses title and description
3. Creates task in database
4. Deletes inbox event
5. Schedules task in Focus Blocks calendar

**Supported formats**:
```
Task: <title>
Task: <title>, <duration>, due <date>, P<1-4>
Task: <title> | priority: high | due: friday | 2h

Goal: <title>
Goal: <title>, target: <date>, category: <category>

Blocker: <description> for task <task_id>
```

### 2. Focus Blocks
**Purpose**: Scheduled work sessions for tasks

**Managed by**: Agent (auto-created, user can reschedule)

**Event format**:
```
Title: "Focus: Write masters SoP"
Description: "Task ID: 123
Priority: High
Estimated: 3h"
Time: 9:00 AM - 12:00 PM
Extended Properties:
  - agent_task_id: 123
  - agent_checksum: abc123
```

**User actions**:
- View scheduled blocks
- Reschedule by dragging in calendar
- Mark complete by editing description: "Status: Done"
- Skip by deleting event

### 3. Check-ins
**Purpose**: Daily reflection and planning prompts

**Managed by**: Agent (auto-created daily at 7 AM)

**Event format**:
```
Title: "Daily Check-in - 2026-02-17"
Description: "
What did you accomplish yesterday?
-

Any blockers or challenges?
-

Top 3 priorities for today:
1.
2.
3.

View full plan: http://localhost:8000/plan/2026-02-17
"
Time: 7:00 AM - 7:15 AM
```

**User interaction**:
1. Edit the description with your responses
2. Agent parses responses on next sync
3. Database updated with completed tasks, blockers
4. Today's schedule adjusted

### 4. Insights
**Purpose**: Weekly productivity summaries

**Managed by**: Agent (auto-created Monday 8 AM)

**Event format**:
```
Title: "Weekly Insights - Week of Feb 17"
Description: "
📊 This Week's Stats
- Deep work: 24h (target: 25h)
- Tasks completed: 18/22 (82%)
- Context switches: 42 (↓ 12% from last week)

🎯 Top Projects
1. PersonalManager (12h)
2. MastersApplication (8h)
3. ResearchPaper (4h)

💡 Key Insights
- Peak productivity: 9-11 AM
- Friday afternoons are low-energy
- Meeting overload on Tuesday

⚡ Recommendations
1. Block Tuesday mornings for deep work
2. Move admin tasks to Friday afternoons
3. Reduce Slack time (2.5h this week)

View detailed report: http://localhost:8000/insights/2026-w07
"
Time: 8:00 AM - 8:30 AM (Monday)
```

## Google Calendar Setup

### Prerequisites

1. Google account
2. Google Cloud Project (free)
3. OAuth 2.0 credentials

### Step-by-Step Setup

#### 1. Create Google Cloud Project

```bash
1. Go to https://console.cloud.google.com/
2. Click "Create Project"
3. Name: "Personal Manager"
4. Click "Create"
```

#### 2. Enable Calendar API

```bash
1. In project, go to "APIs & Services" > "Library"
2. Search for "Google Calendar API"
3. Click "Enable"
```

#### 3. Configure OAuth Consent Screen

```bash
1. Go to "APIs & Services" > "OAuth consent screen"
2. User Type: "External"
3. Fill in:
   - App name: Personal Manager
   - User support email: your email
   - Developer contact: your email
4. Scopes: Add "Google Calendar API" (calendar, calendar.events)
5. Test users: Add your email
6. Save
```

#### 4. Create OAuth Credentials

```bash
1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Application type: "Desktop app"
4. Name: "Personal Manager Desktop"
5. Click "Create"
6. Download JSON file
7. Save as: ~/.personal-manager/credentials/google_credentials.json
```

#### 5. Run Setup Script

```bash
python scripts/setup_google_calendar.py
```

This will:
1. Launch OAuth flow in browser
2. Request calendar access
3. Save refresh token
4. Create 4 dedicated calendars
5. Test API access

### Configuration

```yaml
# config.yaml
calendar:
  google:
    enabled: true
    credentials_path: ~/.personal-manager/credentials/google_credentials.json
    token_path: ~/.personal-manager/tokens/google_token.json
    calendars:
      inbox:
        name: "Agent Inbox"
        color: "9"  # Blue
      focus_blocks:
        name: "Focus Blocks"
        color: "10"  # Green
      checkins:
        name: "Check-ins"
        color: "4"  # Pink
      insights:
        name: "Insights"
        color: "5"  # Yellow
```

## CalDAV Setup

### Supported Providers

- NextCloud
- Fastmail
- iCloud Calendar (limited)
- Radicale
- Any CalDAV-compliant server

### NextCloud Example

```yaml
# config.yaml
calendar:
  caldav:
    enabled: true
    url: https://nextcloud.example.com/remote.php/dav
    username: your_username
    password: ${CALDAV_PASSWORD}  # From environment
    calendars:
      inbox:
        name: "Agent Inbox"
      focus_blocks:
        name: "Focus Blocks"
      checkins:
        name: "Check-ins"
      insights:
        name: "Insights"
```

### Setup

```bash
# Set password in environment
export CALDAV_PASSWORD="your_app_password"

# Run setup
python scripts/setup_caldav.py
```

## Synchronization

### Sync Strategy

**Incremental Sync**:
- Uses sync tokens to fetch only changes
- Reduces API calls and bandwidth
- Faster sync (typically <1 second)

**Full Sync Fallback**:
- If sync token invalid
- On first sync
- On error recovery

### Sync Flow

```
┌─────────────────────────────────────────────┐
│ 1. Check last sync time                     │
│    If < 2 minutes ago, skip                 │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 2. Fetch changes from calendar              │
│    Using sync token (incremental)           │
│    Or full sync if no token                 │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 3. Process each changed event               │
│    • New: Create in DB                      │
│    • Updated: Merge changes                 │
│    • Deleted: Mark deleted in DB            │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 4. Resolve conflicts                        │
│    • Calendar wins for user-created events  │
│    • DB wins for agent-created events       │
│    • Last-modified wins for unclear cases   │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 5. Push local changes to calendar           │
│    • New tasks scheduled → create events    │
│    • Tasks completed → update events        │
│    • Schedule changes → update times        │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│ 6. Update sync token                        │
│    Save for next incremental sync           │
└─────────────────────────────────────────────┘
```

### Metadata Storage

To enable idempotent sync and conflict resolution:

**Google Calendar**:
```json
{
  "extendedProperties": {
    "private": {
      "agent_task_id": "123",
      "agent_type": "focus_block",
      "agent_checksum": "abc123",
      "agent_created_at": "2026-02-17T10:00:00Z"
    }
  }
}
```

**CalDAV** (custom X-properties):
```ics
BEGIN:VEVENT
UID:unique-event-id
SUMMARY:Focus: Write SoP
DTSTART:20260217T090000Z
DTEND:20260217T120000Z
X-AGENT-TASK-ID:123
X-AGENT-TYPE:focus_block
X-AGENT-CHECKSUM:abc123
END:VEVENT
```

### Conflict Resolution

**Scenario 1: User reschedules focus block**
```
DB: Task 123 scheduled 9-11 AM
Calendar: Event moved to 2-4 PM

Resolution: Update DB schedule to 2-4 PM (user intent wins)
```

**Scenario 2: Task completed in DB, calendar event exists**
```
DB: Task 123 status = completed
Calendar: Focus block event still present

Resolution: Update calendar event description to mark completed
```

**Scenario 3: Both modified**
```
DB: Task priority changed to High at 10:05
Calendar: Event time changed at 10:03

Resolution: Apply both changes (priority + time)
```

## Event Parsing

### Rule-Based Parsing

Fast, deterministic parsing for common formats:

```python
# Patterns
patterns = [
    # Task: <title>, <duration>, due <date>, P<priority>
    r"Task:\s*(.+?),\s*(\d+h?),\s*due\s+(\w+),\s*P([1-4])",

    # Task: <title> | priority: <level> | due: <date> | <duration>
    r"Task:\s*(.+?)\s*\|\s*priority:\s*(\w+)\s*\|\s*due:\s*(.+?)\s*\|\s*(\d+h?)",

    # Simple: Task: <title>
    r"Task:\s*(.+)",
]

def parse_event(text):
    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            return extract_task_from_match(match)

    # Fallback to LLM
    return llm_parse(text)
```

### LLM-Based Parsing

For complex or free-form text:

```python
async def llm_parse_event(event_text: str) -> dict:
    prompt = f"""
Parse this calendar event into structured task data:

Event text: "{event_text}"

Extract and return JSON with:
{{
  "type": "task" | "goal" | "blocker",
  "title": "...",
  "priority": "low" | "medium" | "high" | "critical",
  "duration_hours": number or null,
  "due_date": "YYYY-MM-DD" or null,
  "energy_level": "low" | "medium" | "high",
  "category": string or null,
  "description": string or null
}}

If you cannot extract a field, use null.
Be conservative - only extract what is explicitly stated.
"""

    response = await llm_client.generate(
        prompt,
        structured_output=TaskParseSchema
    )

    return response.parsed_data
```

### Supported Date Formats

```
Absolute:
- 2026-02-25
- Feb 25
- February 25, 2026
- 25/02/2026

Relative:
- today
- tomorrow
- next monday
- next week
- in 3 days
- end of month

Week references:
- friday (next Friday)
- this friday
- next friday
```

## API Rate Limits

### Google Calendar API

**Quotas** (free tier):
- 1,000,000 queries per day
- 10 queries per second per user

**Our usage** (estimated):
- Sync every 2 min: 720 queries/day
- Event creation: ~50 queries/day
- Total: ~800 queries/day (0.08% of quota)

**Mitigation**:
- Incremental sync reduces queries by 90%
- Batch operations where possible
- Exponential backoff on errors

### CalDAV

No standard rate limits, depends on server:
- NextCloud: Typically very generous
- Fastmail: 1000 requests/hour
- Self-hosted: Unlimited

## Error Handling

### Network Errors

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(NetworkError)
)
async def sync_calendar():
    # Sync logic
    pass
```

### Invalid Sync Token

```python
try:
    events = await calendar.list_events(sync_token=token)
except InvalidSyncTokenError:
    # Fall back to full sync
    logger.warning("Sync token invalid, performing full sync")
    events = await calendar.list_events(sync_token=None)
    # Save new token
```

### Quota Exceeded

```python
try:
    event = await calendar.create_event(event_data)
except QuotaExceededError as e:
    # Back off and retry
    retry_after = e.retry_after or 60
    logger.error(f"Quota exceeded, retrying after {retry_after}s")
    await asyncio.sleep(retry_after)
    event = await calendar.create_event(event_data)
```

## Advanced Usage

### Custom Event Templates

```yaml
# config.yaml
calendar:
  event_templates:
    deep_work:
      duration: 120  # minutes
      color: "10"  # green
      reminders:
        - method: popup
          minutes: 10

    meeting_prep:
      duration: 15
      color: "4"
      prefix: "Prep:"

    break:
      duration: 15
      color: "8"
```

### Webhook Notifications (Google only)

For instant sync instead of polling:

```python
# Enable webhook
webhook_url = "https://your-domain.com/webhook/calendar"
channel = calendar.watch_events(
    calendar_id="primary",
    webhook_url=webhook_url,
    token="unique-token",
    expiration=7*24*60*60*1000  # 7 days
)

# Renew before expiration
async def renew_webhook():
    # Called daily by scheduler
    calendar.stop_channel(channel.id)
    new_channel = calendar.watch_events(...)
```

### Filtering Events

```python
# Only sync events created by agent
events = calendar.list_events(
    shared_extended_property="agent_created=true"
)

# Only sync specific date range
events = calendar.list_events(
    time_min=datetime.now(),
    time_max=datetime.now() + timedelta(days=30)
)
```

## Troubleshooting

### Sync Issues

**Problem**: Events not syncing

```bash
# Check sync status
curl http://localhost:8000/api/calendar/sync/status

# Manual sync
curl -X POST http://localhost:8000/api/calendar/sync

# View logs
tail -f data/logs/calendar_sync.log
```

**Problem**: Duplicate events

```bash
# Check for duplicate agent IDs
sqlite3 data/agent.db "SELECT calendar_event_id, COUNT(*) FROM schedule GROUP BY calendar_event_id HAVING COUNT(*) > 1"

# Cleanup duplicates
python scripts/cleanup_duplicate_events.py
```

### OAuth Token Expired

```bash
# Refresh token
python scripts/refresh_google_token.py

# Or delete and re-authenticate
rm ~/.personal-manager/tokens/google_token.json
python scripts/setup_google_calendar.py
```

### Calendar Not Found

```bash
# List available calendars
python scripts/list_calendars.py

# Update config with correct calendar IDs
nano config.yaml
```

## Best Practices

1. **Use dedicated calendars**: Don't mix agent events with personal calendar
2. **Descriptive titles**: Include key info in event title for at-a-glance view
3. **Consistent format**: Use template formats for faster parsing
4. **Review focus blocks**: Adjust scheduled blocks to match energy levels
5. **Complete check-ins**: Daily reflection improves scheduling accuracy

## Future Enhancements

- [ ] iCloud Calendar support
- [ ] Outlook Calendar integration
- [ ] Smart notification timing
- [ ] Travel time calculation
- [ ] Meeting notes integration
- [ ] Voice input for inbox events

---

Last updated: 2026-02-17
