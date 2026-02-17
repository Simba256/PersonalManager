# Architecture Documentation

## System Overview

Personal Manager is a single-process Python application with three main layers:
1. **Interface Layer**: Calendar + Web UI + CLI
2. **Application Layer**: FastAPI + APScheduler + LangGraph
3. **Data Layer**: SQLite databases

## Design Principles

### 1. Local-First Architecture
- All data persisted locally in SQLite
- No cloud storage dependencies
- LLM API calls are the only external dependencies
- Can operate offline for core functions

### 2. Calendar as Primary Interface
- Calendar events are the source of truth for scheduling
- Native calendar notifications replace messaging apps
- Bidirectional sync with metadata preservation
- Multiple dedicated calendars for different purposes

### 3. Single-Process Design
- All components run in one Python process
- FastAPI handles HTTP requests
- APScheduler manages background jobs in the same process
- Simplified deployment and debugging

### 4. Privacy by Design
- Sensitive data never leaves local machine
- LLM prompts sanitized of PII
- Activity Tracker data queried read-only
- Optional local LLM support (future)

## Component Architecture

```
┌───────────────────────────────────────────────────────────┐
│                    Interface Layer                         │
│  ┌─────────────┬──────────────┬──────────────────────┐   │
│  │  Calendar   │   Web UI     │        CLI          │   │
│  │  (Google/   │ (localhost:  │   (Typer CLI)       │   │
│  │   CalDAV)   │    8000)     │                      │   │
│  └─────────────┴──────────────┴──────────────────────┘   │
└───────────────────────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────┐
│                   Application Layer                        │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐│
│  │              FastAPI Web Server                       ││
│  │  • REST API endpoints                                 ││
│  │  • HTML template rendering (Jinja2)                   ││
│  │  • WebSocket for real-time updates (optional)         ││
│  └──────────────────────────────────────────────────────┘│
│                                                            │
│  ┌──────────────────────────────────────────────────────┐│
│  │              APScheduler (AsyncIO)                    ││
│  │  ┌─────────────────────────────────────────────────┐ ││
│  │  │ Periodic Jobs:                                   │ ││
│  │  │ • calendar_sync (every 2 min)                    │ ││
│  │  │ • inbox_triage (every 5 min)                     │ ││
│  │  │ • git_monitor (every 10 min)                     │ ││
│  │  │                                                  │ ││
│  │  │ Scheduled Jobs:                                  │ ││
│  │  │ • daily_plan (7:00 AM)                           │ ││
│  │  │ • eod_summary (6:00 PM)                          │ ││
│  │  │ • weekly_review (Mon 8:00 AM)                    │ ││
│  │  └─────────────────────────────────────────────────┘ ││
│  └──────────────────────────────────────────────────────┘│
│                                                            │
│  ┌──────────────────────────────────────────────────────┐│
│  │              LangGraph Agent System                   ││
│  │  ┌─────────────────────────────────────────────────┐││
│  │  │ Workflows:                                       │││
│  │  │ • inbox_triage: Parse events → tasks             │││
│  │  │ • daily_planner: Tasks → schedule → calendar     │││
│  │  │ • insights_generator: Activity → summaries       │││
│  │  │ • session_analyzer: Code sessions → projects     │││
│  │  └─────────────────────────────────────────────────┘││
│  │                                                       ││
│  │  ┌─────────────────────────────────────────────────┐││
│  │  │ Tools:                                           │││
│  │  │ • calendar_read / calendar_write                 │││
│  │  │ • db_read / db_write                             │││
│  │  │ • schedule_compute                               │││
│  │  │ • insights_compute                               │││
│  │  │ • activity_query                                 │││
│  │  └─────────────────────────────────────────────────┘││
│  └──────────────────────────────────────────────────────┘│
│                                                            │
│  ┌──────────────────────────────────────────────────────┐│
│  │              LLM Router                               ││
│  │  • LiteLLM for unified interface                      ││
│  │  • Provider selection: OpenAI vs Anthropic            ││
│  │  • Structured output parsing                          ││
│  │  • Rate limiting and retries                          ││
│  └──────────────────────────────────────────────────────┘│
│                                                            │
│  ┌──────────────────────────────────────────────────────┐│
│  │           Integration Modules                         ││
│  │  • Calendar (Google + CalDAV)                         ││
│  │  • Activity Tracker (SQLite queries)                  ││
│  │  • Git Monitor (GitPython)                            ││
│  │  • Session Watcher (Watchdog)                         ││
│  │  • Smart Scheduler (OR-Tools / Heuristic)             ││
│  └──────────────────────────────────────────────────────┘│
└───────────────────────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────┐
│                      Data Layer                            │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐│
│  │         Main Database (agent.db - SQLite)             ││
│  │  Tables:                                              ││
│  │  • tasks, goals, blockers                             ││
│  │  • projects, sessions                                 ││
│  │  • meetings, schedule                                 ││
│  │  • sync_state, job_store                              ││
│  └──────────────────────────────────────────────────────┘│
│                                                            │
│  ┌──────────────────────────────────────────────────────┐│
│  │    Activity Tracker DB (activity.db - Attached)       ││
│  │  Tables (read-only):                                  ││
│  │  • window_activity                                    ││
│  │  • browser_activity                                   ││
│  │  • terminal_activity                                  ││
│  └──────────────────────────────────────────────────────┘│
│                                                            │
│  ┌──────────────────────────────────────────────────────┐│
│  │         File System Storage                           ││
│  │  • Session exports (MD/JSON)                          ││
│  │  • Configuration files                                ││
│  │  • OAuth tokens                                       ││
│  │  • Log files                                          ││
│  └──────────────────────────────────────────────────────┘│
└───────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Calendar Integration Layer

**Purpose**: Bidirectional sync with calendar providers

**Components**:
- `GoogleCalendar`: Google Calendar API client with OAuth2
- `CalDAVClient`: Generic CalDAV protocol client
- `CalendarParser`: Natural language event parsing
- `CalendarSync`: Sync engine with conflict resolution

**Key Features**:
- Incremental sync using sync tokens
- Metadata storage in event properties
- Idempotent writes using checksums
- Multiple calendar support

**Flow**:
```
1. Poll calendar for changes (every 2 min)
2. Download new/modified events
3. Parse event text into structured data
4. Update local database
5. Trigger dependent jobs (inbox triage)
6. Push local changes back to calendar
7. Update sync tokens
```

### 2. Task Management System

**Purpose**: Core task, goal, and blocker tracking

**Components**:
- `TaskManager`: CRUD operations for tasks
- `GoalTracker`: Hierarchical goal management
- `BlockerDetector`: Identifies and tracks blockers
- `PriorityEngine`: Dynamic priority calculation

**State Machine**:
```
Task States: pending → scheduled → in_progress → completed
                                    ↓
                                 blocked
                                    ↓
                              pending (after resolution)
```

### 3. Smart Scheduler

**Purpose**: Optimal task scheduling with constraints

**Algorithm**:
```python
Input:
- tasks: List[Task] with (duration, deadline, priority, energy_level)
- calendar_busy: List[TimeBlock] from meetings
- working_hours: TimeRange per weekday
- constraints: max_wip, context_switch_penalty, deep_work_windows

Process:
1. Filter tasks ready to schedule (not blocked)
2. Calculate available time slots
3. For each task:
   a. Compute urgency score (deadline proximity)
   b. Compute value score (priority * impact)
   c. Compute cost (context switches if scheduled now)
4. Use constraint solver (OR-Tools CP-SAT) or heuristic:
   - Maximize: (urgency + value - cost)
   - Constraints:
     * No overlap with meetings
     * Respect working hours
     * Max hours per day
     * Group similar tasks (reduce context switches)
     * Protect deep work windows
5. Generate focus block events
6. Write to calendar

Output:
- schedule: List[FocusBlock] with (task_id, start, end, calendar_event_id)
```

**Heuristic Alternative** (if OR-Tools too complex):
```python
1. Sort tasks by: (deadline urgency * priority)
2. Iterate through available time slots
3. Fill slots with highest-priority tasks
4. Apply rules:
   - Morning: High cognitive load tasks
   - After lunch: Medium load tasks
   - Late day: Low load tasks (email, admin)
   - Minimum 25 min blocks (Pomodoro)
   - Maximum 2 hours continuous (break needed)
```

### 4. Session Monitoring

**Purpose**: Track development activity across tools

**Sources**:
1. **Git Activity**:
   - Monitor repos in ~/projects or configured paths
   - Track commits, branches, PR references
   - Map to projects in database

2. **Claude Code / OpenCode**:
   - File watcher on export directory
   - Parse MD/JSON transcripts
   - Extract: project, duration, topics, outcomes

3. **Activity Tracker**:
   - Query window_activity for editor focus
   - Query terminal_activity for working directories
   - Correlate with git repos

**Correlation Logic**:
```python
def correlate_session(terminal_activity, git_commit):
    # Match by working directory and timestamp
    if terminal_activity.working_directory == git_commit.repo_path:
        if abs(terminal_activity.end_time - git_commit.time) < 10min:
            return Session(
                project=git_commit.project,
                start=terminal_activity.start_time,
                end=terminal_activity.end_time,
                commits=[git_commit],
                focus_time=terminal_activity.duration
            )
```

### 5. Insights Engine

**Purpose**: Generate productivity insights from activity data

**Data Pipeline**:
```
Activity Tracker (raw events)
    ↓
Aggregation (Polars/Pandas)
    ↓
Metrics Calculation
    ↓
LLM Summarization
    ↓
Calendar Event / Web Dashboard
```

**Metrics**:
- **Focus Metrics**:
  - Deep work hours per day
  - Context switches per hour
  - Average focus block duration
  - Distraction rate (non-work apps)

- **Project Metrics**:
  - Active projects
  - Time per project
  - Commit frequency
  - Session duration trends

- **Task Metrics**:
  - Completion rate
  - Average task duration vs estimate
  - Blocker dwell time
  - Priority distribution

- **Energy Metrics**:
  - Peak productivity hours
  - Decline patterns
  - Break frequency
  - Weekend recovery

**LLM Summarization**:
```python
prompt = f"""
Analyze this week's productivity data:
- Deep work: {deep_work_hours}h
- Context switches: {switches}
- Top projects: {top_projects}
- Completion rate: {completion_rate}%
- Blockers: {blockers}

Generate:
1. 3 key insights
2. 2 recommendations for next week
3. 1 warning if any negative trend
"""
```

### 6. LangGraph Agent Workflows

**Inbox Triage Workflow**:
```python
@graph
def inbox_triage():
    # 1. Get new events from "Agent Inbox" calendar
    events = get_new_inbox_events()

    # 2. Parse each event with LLM
    for event in events:
        structured = llm_parse(event.description)
        # Extracts: type (task/goal/blocker), title, due, priority, duration

    # 3. Create database entries
    if structured.type == "task":
        create_task(structured)
    elif structured.type == "goal":
        create_goal(structured)

    # 4. Delete processed inbox event
    delete_calendar_event(event.id)

    # 5. Trigger replanning
    trigger_job("daily_plan")
```

**Daily Planner Workflow**:
```python
@graph
def daily_planner():
    # 1. Get all pending/scheduled tasks
    tasks = get_tasks(status=["pending", "scheduled"])

    # 2. Get calendar busy times
    busy = get_calendar_events(exclude=["Focus Blocks"])

    # 3. Run scheduler
    schedule = smart_schedule(tasks, busy)

    # 4. Generate human-readable plan
    plan_text = format_daily_plan(schedule)

    # 5. Create calendar events
    for block in schedule:
        create_focus_block(block)

    # 6. Create check-in event with plan
    create_checkin_event(plan_text)
```

**Insights Generator Workflow**:
```python
@graph
def insights_generator(period="week"):
    # 1. Query Activity Tracker
    activity = query_activity_tracker(period)

    # 2. Query sessions and tasks
    sessions = get_sessions(period)
    tasks = get_tasks_completed(period)

    # 3. Calculate metrics
    metrics = calculate_metrics(activity, sessions, tasks)

    # 4. LLM summarization
    insights = llm_summarize(metrics)

    # 5. Create insights calendar event
    create_insights_event(insights)

    # 6. Update web dashboard
    update_dashboard(metrics, insights)
```

## Data Flow

### Task Creation Flow
```
User creates calendar event
    ↓
Calendar sync detects new event (APScheduler job)
    ↓
Inbox triage workflow triggered
    ↓
LLM parses event text → structured task
    ↓
Task created in database
    ↓
Daily planner triggered
    ↓
Scheduler computes optimal time slot
    ↓
Focus block event created in calendar
    ↓
User sees scheduled block in calendar
```

### Daily Check-in Flow
```
7:00 AM: APScheduler triggers daily_plan job
    ↓
Daily planner workflow executes
    ↓
Generates today's plan with tasks and timing
    ↓
Creates "Daily Check-in" calendar event with questions
    ↓
User edits event description with answers
    ↓
Calendar sync detects change
    ↓
LLM parses responses
    ↓
Database updated with completed tasks, new blockers
    ↓
Schedule adjusted if needed
```

### Session Tracking Flow
```
User codes in project directory
    ↓
Activity Tracker logs window/terminal activity
    ↓
User makes git commit
    ↓
Git monitor (APScheduler) detects commit
    ↓
Correlation engine matches activity + commit
    ↓
Session created in database
    ↓
Project "last_activity_at" updated
    ↓
Insights job uses session for metrics
```

## Security & Privacy

### Authentication
- **Google Calendar**: OAuth 2.0 with token storage in `~/.personal-manager/tokens/`
- **CalDAV**: Username/password stored in system keyring
- **Web UI**: Optional basic auth for localhost access

### Data Protection
- **Encryption at rest**: Optional SQLite encryption via SQLCipher
- **API key storage**: Environment variables or encrypted config
- **LLM prompt sanitization**: PII detection and masking before API calls

### Privacy Measures
- **Activity data**: Never sent to LLM providers
- **Calendar data**: Minimal metadata in cloud (only IDs, not content)
- **Local processing**: All analysis done locally
- **Audit logs**: Track all external API calls

## Performance Considerations

### Database
- SQLite with WAL mode for concurrent reads
- Indexes on frequently queried columns
- ATTACH for Activity Tracker (read-only)
- Regular VACUUM for optimization

### Caching
- Calendar events cached with sync tokens
- LLM responses cached for repeated queries
- Activity metrics cached (invalidate daily)

### Rate Limiting
- LLM API: Max 60 requests/minute
- Calendar API: Respect quota limits
- Background jobs: Debounced to prevent thrashing

### Scalability
- Single-process design sufficient for personal use
- Can handle 1000s of tasks, 100s of projects
- Activity Tracker integration optimized with views
- Future: Optional PostgreSQL migration path

## Error Handling

### Retry Strategy
```python
- LLM API failures: Exponential backoff, 3 retries
- Calendar API failures: Retry with jitter, 5 attempts
- Network errors: Queue for later retry
- Parse errors: Log and skip, notify user
```

### Graceful Degradation
- Calendar offline: Continue with local data
- LLM API down: Fall back to rule-based parsing
- Activity Tracker unavailable: Skip insights update

### Monitoring
- Structured logging with loguru
- Error aggregation in database
- Health check endpoint: `/health`
- Metrics endpoint: `/metrics` (Prometheus format)

## Future Enhancements

### Phase 2
- [ ] Local LLM support (Ollama integration)
- [ ] Voice interface (whisper + TTS)
- [ ] Mobile app (calendar-based, read-only)
- [ ] Advanced analytics dashboard
- [ ] Multi-user support (team features)

### Phase 3
- [ ] Plugin system for custom integrations
- [ ] API for third-party apps
- [ ] Machine learning for schedule optimization
- [ ] Predictive task duration estimation
- [ ] Smart notification timing

## Testing Strategy

See [DEVELOPMENT.md](DEVELOPMENT.md#testing) for detailed testing approach.

## Deployment Options

See [DEPLOYMENT.md](DEPLOYMENT.md) for deployment instructions.

---

Last updated: 2026-02-17
