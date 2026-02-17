# Implementation Plan

This document outlines the step-by-step implementation plan for Personal Manager.

## Project Phases

### Phase 1: Foundation (Week 1-2)
Core infrastructure and data models

### Phase 2: Integration (Week 3-4)
Calendar, Activity Tracker, and Git integration

### Phase 3: Intelligence (Week 5-6)
LangGraph agents and smart scheduling

### Phase 4: Polish (Week 7-8)
UI improvements, testing, and deployment

---

## Phase 1: Foundation (Week 1-2)

### Week 1: Project Setup & Data Layer

#### Day 1: Project Scaffolding
- [x] Create documentation
- [ ] Initialize git repository
- [ ] Setup project structure
- [ ] Create virtual environment
- [ ] Install base dependencies

**Tasks**:
```bash
# Project structure
mkdir -p app/{calendar,agent,integrations,web/templates,web/static}
mkdir -p data/{sessions,logs}
mkdir -p scripts tests docs

# Git initialization
git init
git add .
git commit -m "Initial project structure"

# Virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Base dependencies
pip install fastapi uvicorn sqlalchemy alembic pydantic python-dotenv
```

**Deliverables**:
- [x] Complete documentation set
- [ ] Working git repository
- [ ] Project structure created
- [ ] Base dependencies installed

#### Day 2: Database Models
- [ ] Define SQLAlchemy models
- [ ] Create Alembic migrations
- [ ] Setup database initialization
- [ ] Write model tests

**Tasks**:
```bash
# Initialize Alembic
alembic init alembic

# Create models in app/models.py
# Create first migration
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

**Models to implement**:
- Task
- Goal
- Blocker
- Project
- Session
- Meeting
- Schedule
- SyncState

**Deliverables**:
- [ ] `app/models.py` with all models
- [ ] Database migrations
- [ ] Unit tests for models
- [ ] Database initialization script

#### Day 3: Configuration System
- [ ] Create config schema
- [ ] Setup environment variables
- [ ] Implement config validation
- [ ] Create example configs

**Tasks**:
```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///data/agent.db"
    activity_tracker_db: str
    google_credentials_path: str
    openai_api_key: str
    anthropic_api_key: str
    # ... more settings

    class Config:
        env_file = ".env"
```

**Deliverables**:
- [ ] `app/config.py` with Settings class
- [ ] `.env.example` template
- [ ] `config.yaml.example` for complex settings
- [ ] Configuration documentation

#### Day 4-5: Basic FastAPI Application
- [ ] Setup FastAPI app structure
- [ ] Create health check endpoint
- [ ] Setup logging
- [ ] Create basic web UI skeleton
- [ ] Setup CORS and middleware

**Tasks**:
```python
# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Personal Manager")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Mount static files and templates
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
templates = Jinja2Templates(directory="app/web/templates")
```

**Deliverables**:
- [ ] Working FastAPI application
- [ ] Basic web UI with homepage
- [ ] Health check endpoint
- [ ] Structured logging setup
- [ ] Development server running

#### Day 6-7: Task Management CRUD
- [ ] Create task API endpoints
- [ ] Implement task service layer
- [ ] Create task web UI pages
- [ ] Write integration tests

**Endpoints**:
```
POST   /api/tasks          - Create task
GET    /api/tasks          - List tasks
GET    /api/tasks/{id}     - Get task details
PUT    /api/tasks/{id}     - Update task
DELETE /api/tasks/{id}     - Delete task
PATCH  /api/tasks/{id}/status - Update task status
```

**UI Pages**:
- `/tasks` - Task list
- `/tasks/new` - Create task form
- `/tasks/{id}` - Task detail/edit

**Deliverables**:
- [ ] Task API endpoints
- [ ] Task service layer
- [ ] Task web UI
- [ ] API tests
- [ ] Basic task management working

### Week 2: Calendar Integration

#### Day 8-9: Google Calendar OAuth Setup
- [ ] Setup Google Cloud Project
- [ ] Configure OAuth consent screen
- [ ] Implement OAuth flow
- [ ] Token storage and refresh
- [ ] Create setup script

**Tasks**:
```bash
# Install dependencies
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

# Create setup script
python scripts/setup_google_oauth.py
```

**Script flow**:
1. Check for existing credentials
2. Launch OAuth flow in browser
3. Save tokens to `~/.personal-manager/tokens/google_token.json`
4. Test API access
5. Create dedicated calendars

**Deliverables**:
- [ ] Google Cloud Project configured
- [ ] OAuth flow working
- [ ] Token storage implemented
- [ ] Setup script completed
- [ ] Documentation for OAuth setup

#### Day 10-11: Calendar Sync Engine
- [ ] Implement calendar read/write
- [ ] Create sync token management
- [ ] Implement incremental sync
- [ ] Handle conflicts
- [ ] Write sync tests

**Components**:
```python
# app/calendar/google.py
class GoogleCalendarClient:
    async def list_events(self, calendar_id, sync_token=None)
    async def create_event(self, calendar_id, event_data)
    async def update_event(self, calendar_id, event_id, event_data)
    async def delete_event(self, calendar_id, event_id)
    async def watch_events(self, calendar_id, webhook_url)

# app/calendar/sync.py
class CalendarSync:
    async def sync_calendar(self, calendar_id)
    async def push_local_changes(self)
    async def resolve_conflicts(self)
```

**Deliverables**:
- [ ] Google Calendar client
- [ ] Sync engine with incremental sync
- [ ] Conflict resolution logic
- [ ] Sync state persistence
- [ ] Integration tests

#### Day 12-13: Calendar Event Parser
- [ ] Implement natural language parsing
- [ ] Create event templates
- [ ] Test various input formats
- [ ] LLM-based fallback parser

**Parser flow**:
```python
# Rule-based parsing for common formats
"Task: Write SoP, 3h, due Friday, P1"
  → Task(title="Write SoP", duration=3h, due="2026-02-21", priority="high")

# LLM fallback for complex formats
"I need to finish the masters application by end of month, probably take 5-6 hours"
  → LLM extracts structured data
```

**Deliverables**:
- [ ] Event parser with rule-based extraction
- [ ] LLM fallback parser
- [ ] Parser tests with diverse inputs
- [ ] Supported format documentation

#### Day 14: APScheduler Setup
- [ ] Configure APScheduler
- [ ] Create job definitions
- [ ] Implement job persistence
- [ ] Setup job monitoring

**Jobs to create**:
```python
# app/scheduler.py
scheduler = AsyncIOScheduler(
    jobstores={'default': SQLAlchemyJobStore(url='sqlite:///data/jobs.db')},
    timezone='UTC'
)

# Periodic jobs
scheduler.add_job(calendar_sync, 'interval', minutes=2, id='calendar_sync')
scheduler.add_job(inbox_triage, 'interval', minutes=5, id='inbox_triage')
scheduler.add_job(git_monitor, 'interval', minutes=10, id='git_monitor')

# Scheduled jobs
scheduler.add_job(daily_plan, 'cron', hour=7, minute=0, id='daily_plan')
scheduler.add_job(eod_summary, 'cron', hour=18, minute=0, id='eod_summary')
scheduler.add_job(weekly_review, 'cron', day_of_week='mon', hour=8, id='weekly_review')
```

**Deliverables**:
- [ ] APScheduler configured
- [ ] All background jobs defined
- [ ] Job persistence working
- [ ] Manual job trigger endpoints

---

## Phase 2: Integration (Week 3-4)

### Week 3: Activity Tracker & Git Integration

#### Day 15-16: Activity Tracker Integration
- [ ] Attach Activity Tracker database
- [ ] Create query layer
- [ ] Implement metrics calculation
- [ ] Test activity queries

**Tasks**:
```python
# app/integrations/activity_tracker.py
class ActivityTracker:
    def __init__(self, db_path):
        # ATTACH database as read-only
        self.conn = sqlite3.connect(db_path, uri=True)

    def get_coding_time(self, start_date, end_date, project_path=None):
        # Query terminal_activity
        pass

    def get_app_usage(self, start_date, end_date):
        # Query window_activity
        pass

    def get_browser_activity(self, start_date, end_date):
        # Query browser_activity
        pass

    def calculate_focus_metrics(self, date):
        # Calculate deep work, context switches, etc.
        pass
```

**Deliverables**:
- [ ] Activity Tracker database attached
- [ ] Query methods implemented
- [ ] Metrics calculation functions
- [ ] Integration tests
- [ ] Sample metrics displayed in UI

#### Day 17-18: Git Repository Monitoring
- [ ] Discover git repositories
- [ ] Monitor commits
- [ ] Extract commit metadata
- [ ] Link commits to projects

**Tasks**:
```python
# app/integrations/git_monitor.py
class GitMonitor:
    def discover_repos(self, search_paths):
        # Find all .git directories
        pass

    def get_recent_commits(self, repo_path, since):
        # Use GitPython to get commits
        pass

    def parse_commit(self, commit):
        # Extract: hash, message, author, timestamp, files
        pass

    def create_session_from_commits(self, commits):
        # Group commits into sessions
        pass
```

**Deliverables**:
- [ ] Git repository discovery
- [ ] Commit monitoring
- [ ] Commit-to-session correlation
- [ ] Project activity tracking
- [ ] Git integration tests

#### Day 19-20: Session File Watcher
- [ ] Setup file system watcher
- [ ] Parse session exports (MD/JSON)
- [ ] Extract session metadata
- [ ] Store in database

**Tasks**:
```python
# app/integrations/session_watcher.py
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class SessionFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        # New file in data/sessions/
        if event.src_path.endswith(('.md', '.json')):
            self.parse_and_import(event.src_path)

    def parse_and_import(self, file_path):
        # Parse Claude Code / OpenCode export
        # Extract: project, duration, topics, code snippets
        # Store in sessions table
        pass
```

**Deliverables**:
- [ ] File system watcher running
- [ ] MD/JSON parsers
- [ ] Session import working
- [ ] Manual import endpoint
- [ ] Parser tests

#### Day 21: Basic CLI Interface
- [ ] Setup Typer CLI
- [ ] Implement task commands
- [ ] Implement sync commands
- [ ] Create help documentation

**Commands**:
```bash
# Task management
personal-manager task add "Write documentation" --due tomorrow --priority high
personal-manager task list
personal-manager task done <task-id>

# Sync operations
personal-manager sync calendar
personal-manager sync git

# Information
personal-manager status
personal-manager insights --week
```

**Deliverables**:
- [ ] CLI framework setup
- [ ] Core commands implemented
- [ ] Help text and examples
- [ ] CLI tests

### Week 4: Scheduling & Insights

#### Day 22-23: Smart Scheduler Implementation
- [ ] Implement constraint-based scheduler
- [ ] Create scheduling heuristics
- [ ] Test with various scenarios
- [ ] Optimize performance

**Algorithm** (choose one to implement first):

**Option A: Heuristic Scheduler** (simpler, faster)
```python
def heuristic_schedule(tasks, busy_times, working_hours):
    # 1. Sort tasks by (deadline * priority)
    sorted_tasks = sort_by_urgency_and_priority(tasks)

    # 2. Get available time slots
    slots = find_available_slots(busy_times, working_hours)

    # 3. Assign tasks to slots
    schedule = []
    for task in sorted_tasks:
        best_slot = find_best_slot(task, slots)
        if best_slot:
            schedule.append(create_focus_block(task, best_slot))
            slots.remove(best_slot)

    return schedule
```

**Option B: OR-Tools CP-SAT** (more powerful)
```python
from ortools.sat.python import cp_model

def ortools_schedule(tasks, busy_times, working_hours):
    model = cp_model.CpModel()

    # Create variables
    task_vars = {}
    for task in tasks:
        start_var = model.NewIntVar(0, MAX_TIME, f"start_{task.id}")
        end_var = model.NewIntVar(0, MAX_TIME, f"end_{task.id}")
        task_vars[task.id] = (start_var, end_var)

    # Add constraints
    # ... (no overlap, working hours, dependencies, etc.)

    # Objective: minimize (context_switches + deadline_violations)
    model.Minimize(objective)

    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    return extract_schedule(solver, task_vars)
```

**Deliverables**:
- [ ] Scheduler implementation (heuristic or OR-Tools)
- [ ] Slot finding logic
- [ ] Focus block generation
- [ ] Scheduler tests with edge cases
- [ ] Performance benchmarks

#### Day 24-25: Insights Pipeline
- [ ] Implement metrics calculation
- [ ] Create aggregation queries
- [ ] Setup daily/weekly jobs
- [ ] Generate insights with LLM

**Metrics**:
```python
# app/integrations/insights.py
class InsightsEngine:
    def calculate_daily_metrics(self, date):
        return {
            'deep_work_hours': ...,
            'context_switches': ...,
            'tasks_completed': ...,
            'top_projects': ...,
            'distractions': ...,
        }

    def calculate_weekly_metrics(self, week):
        return {
            'total_focus_time': ...,
            'completion_rate': ...,
            'blocker_count': ...,
            'energy_pattern': ...,  # best hours
            'recommendations': ...,
        }

    async def generate_insights(self, metrics):
        # Use LLM to create narrative summary
        prompt = create_insights_prompt(metrics)
        insights = await llm_client.generate(prompt)
        return insights
```

**Deliverables**:
- [ ] Metrics calculation functions
- [ ] Aggregation queries optimized
- [ ] Daily/weekly insight jobs
- [ ] LLM summarization
- [ ] Insights displayed in UI

#### Day 26-27: LLM Integration
- [ ] Setup OpenAI client
- [ ] Setup Anthropic client
- [ ] Implement LiteLLM router (optional)
- [ ] Create prompt templates
- [ ] Implement structured output parsing

**LLM Clients**:
```python
# app/llm/client.py
class LLMClient:
    def __init__(self, provider="openai"):
        self.provider = provider
        if provider == "openai":
            self.client = OpenAI(api_key=settings.openai_api_key)
        elif provider == "anthropic":
            self.client = Anthropic(api_key=settings.anthropic_api_key)

    async def generate(self, prompt, model=None, structured_output=None):
        # Call appropriate API
        # Parse response
        # Return structured data if schema provided
        pass

    async def parse_event(self, event_text):
        # Parse calendar event to task/goal
        pass

    async def summarize_insights(self, metrics):
        # Generate weekly summary
        pass
```

**Deliverables**:
- [ ] OpenAI integration
- [ ] Anthropic integration
- [ ] Prompt template system
- [ ] Structured output parsing
- [ ] LLM provider tests

#### Day 28: Integration Testing
- [ ] End-to-end workflow tests
- [ ] Calendar sync tests
- [ ] Scheduling tests
- [ ] Error handling tests

**Test scenarios**:
1. User creates inbox event → task created → scheduled → appears in calendar
2. Daily plan runs → focus blocks created → check-in event created
3. Git commit made → session created → project updated
4. Activity tracked → insights generated → calendar event created

**Deliverables**:
- [ ] Integration test suite
- [ ] End-to-end scenarios covered
- [ ] Error cases tested
- [ ] Test documentation

---

## Phase 3: Intelligence (Week 5-6)

### Week 5: LangGraph Agents

#### Day 29-30: LangGraph Setup
- [ ] Install LangGraph
- [ ] Define agent tools
- [ ] Create state schemas
- [ ] Setup checkpointing

**Tools**:
```python
# app/agent/tools.py
from langchain.tools import tool

@tool
def calendar_read(calendar_id: str, date_range: str):
    """Read events from calendar."""
    pass

@tool
def calendar_write(calendar_id: str, event: dict):
    """Create calendar event."""
    pass

@tool
def db_query(query: str):
    """Query database."""
    pass

@tool
def schedule_compute(tasks: list, constraints: dict):
    """Compute optimal schedule."""
    pass

@tool
def activity_analyze(date_range: str):
    """Analyze activity data."""
    pass
```

**Deliverables**:
- [ ] LangGraph installed and configured
- [ ] All agent tools defined
- [ ] State schemas created
- [ ] Checkpointing enabled

#### Day 31-32: Inbox Triage Workflow
- [ ] Implement inbox triage graph
- [ ] Event parsing logic
- [ ] Database creation nodes
- [ ] Error handling

**Graph**:
```python
# app/agent/graphs.py
from langgraph.graph import StateGraph, END

def create_inbox_triage_graph():
    workflow = StateGraph(InboxState)

    workflow.add_node("fetch_events", fetch_inbox_events)
    workflow.add_node("parse_event", parse_event_with_llm)
    workflow.add_node("create_task", create_task_in_db)
    workflow.add_node("create_goal", create_goal_in_db)
    workflow.add_node("delete_event", delete_inbox_event)

    workflow.set_entry_point("fetch_events")
    workflow.add_edge("fetch_events", "parse_event")
    workflow.add_conditional_edges(
        "parse_event",
        determine_type,
        {"task": "create_task", "goal": "create_goal"}
    )
    workflow.add_edge("create_task", "delete_event")
    workflow.add_edge("create_goal", "delete_event")
    workflow.add_edge("delete_event", END)

    return workflow.compile()
```

**Deliverables**:
- [ ] Inbox triage graph implemented
- [ ] Parsing with LLM working
- [ ] Task/goal creation working
- [ ] Inbox cleanup working

#### Day 33-34: Daily Planner Workflow
- [ ] Implement daily planner graph
- [ ] Schedule computation node
- [ ] Calendar write-back
- [ ] Check-in creation

**Graph**:
```python
def create_daily_planner_graph():
    workflow = StateGraph(PlannerState)

    workflow.add_node("fetch_tasks", fetch_pending_tasks)
    workflow.add_node("fetch_calendar", fetch_calendar_busy_times)
    workflow.add_node("compute_schedule", run_smart_scheduler)
    workflow.add_node("create_focus_blocks", create_calendar_focus_blocks)
    workflow.add_node("generate_plan_text", generate_daily_plan_summary)
    workflow.add_node("create_checkin", create_checkin_event)

    # ... add edges ...

    return workflow.compile()
```

**Deliverables**:
- [ ] Daily planner graph implemented
- [ ] Schedule computation integrated
- [ ] Focus blocks created in calendar
- [ ] Check-in events created

#### Day 35: Insights Generator Workflow
- [ ] Implement insights graph
- [ ] Metrics collection
- [ ] LLM summarization
- [ ] Calendar event creation

**Deliverables**:
- [ ] Insights graph implemented
- [ ] Metrics aggregation working
- [ ] LLM summaries generated
- [ ] Insights posted to calendar

### Week 6: UI Polish & Testing

#### Day 36-37: Web Dashboard
- [ ] Create dashboard layout
- [ ] Today's plan view
- [ ] Task list with filters
- [ ] Insights display
- [ ] Activity charts

**Pages**:
- `/` - Dashboard (today's plan, quick stats)
- `/tasks` - Task management
- `/projects` - Project list and activity
- `/insights` - Analytics and reports
- `/settings` - Configuration

**Deliverables**:
- [ ] Dashboard UI complete
- [ ] All pages functional
- [ ] Responsive design
- [ ] Charts and visualizations

#### Day 38-39: Real-time Updates
- [ ] Add WebSocket support
- [ ] Live task updates
- [ ] Real-time schedule changes
- [ ] Notification system

**Deliverables**:
- [ ] WebSocket endpoint
- [ ] Real-time UI updates
- [ ] Browser notifications
- [ ] Activity feed

#### Day 40-41: CalDAV Support (Optional)
- [ ] Implement CalDAV client
- [ ] Unified calendar interface
- [ ] Test with various providers
- [ ] Documentation

**Deliverables**:
- [ ] CalDAV client working
- [ ] Tested with NextCloud/other providers
- [ ] Unified with Google Calendar interface
- [ ] Setup documentation

#### Day 42: Comprehensive Testing
- [ ] Complete test coverage
- [ ] Performance testing
- [ ] Load testing
- [ ] Bug fixes

**Deliverables**:
- [ ] 80%+ test coverage
- [ ] Performance benchmarks
- [ ] Known issues documented
- [ ] Critical bugs fixed

---

## Phase 4: Polish (Week 7-8)

### Week 7: Refinement

#### Day 43-44: Error Handling & Resilience
- [ ] Add comprehensive error handling
- [ ] Implement retry logic
- [ ] Graceful degradation
- [ ] Error reporting

#### Day 45-46: Documentation
- [ ] User guide
- [ ] API documentation
- [ ] Setup tutorials
- [ ] Troubleshooting guide

#### Day 47-48: Optimization
- [ ] Database query optimization
- [ ] Caching implementation
- [ ] Reduce LLM API calls
- [ ] Performance tuning

#### Day 49: Security Audit
- [ ] Review authentication
- [ ] Check for vulnerabilities
- [ ] Secure API keys
- [ ] Privacy review

### Week 8: Deployment & Launch

#### Day 50-52: Deployment Setup
- [ ] Create systemd service
- [ ] Setup logging rotation
- [ ] Backup scripts
- [ ] Monitoring setup

#### Day 53-54: User Testing
- [ ] Deploy on your system
- [ ] Real-world usage testing
- [ ] Collect feedback
- [ ] Fix issues

#### Day 55-56: Final Polish
- [ ] Final bug fixes
- [ ] Performance tuning
- [ ] Documentation updates
- [ ] Release preparation

---

## Success Criteria

### Must Have (MVP)
- [x] Complete documentation
- [ ] Task CRUD via web UI and CLI
- [ ] Google Calendar integration working
- [ ] Daily planning with focus blocks
- [ ] Activity Tracker integration
- [ ] Basic insights generation
- [ ] Git monitoring
- [ ] Runs as systemd service

### Should Have
- [ ] LangGraph agent workflows
- [ ] Smart scheduling algorithm
- [ ] CalDAV support
- [ ] Real-time UI updates
- [ ] Comprehensive testing
- [ ] User documentation

### Nice to Have
- [ ] OR-Tools optimization
- [ ] Advanced analytics
- [ ] Mobile-responsive UI
- [ ] Export/import functionality
- [ ] Plugin system foundations

---

## Risk Mitigation

### Technical Risks

**Risk**: Calendar API rate limits
**Mitigation**: Implement incremental sync, cache aggressively

**Risk**: LLM parsing errors
**Mitigation**: Rule-based fallbacks, validation, user confirmation

**Risk**: Activity Tracker database locked
**Mitigation**: Read-only ATTACH, retry logic, graceful degradation

**Risk**: Scheduling complexity too high
**Mitigation**: Start with heuristic, upgrade to OR-Tools later if needed

### Project Risks

**Risk**: Scope creep
**Mitigation**: Stick to MVP, defer nice-to-haves to Phase 2

**Risk**: Integration challenges
**Mitigation**: Build incrementally, test early and often

**Risk**: Time estimates too optimistic
**Mitigation**: Focus on must-haves first, flexible timeline

---

## Development Workflow

### Daily Routine
1. Review tasks for the day
2. Write failing tests first (TDD)
3. Implement feature
4. Write documentation
5. Commit with clear messages
6. Update this plan with progress

### Code Review Checklist
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] Error handling implemented
- [ ] Logging added for debugging
- [ ] Performance acceptable
- [ ] Security reviewed

### Git Workflow
```bash
# Feature branches
git checkout -b feature/calendar-sync
# ... develop ...
git commit -m "feat: implement Google Calendar sync"
git checkout main
git merge feature/calendar-sync

# Commit message format
feat: new feature
fix: bug fix
docs: documentation
test: testing
refactor: code refactoring
```

---

## Next Steps

1. Review this implementation plan
2. Setup development environment (Day 1 tasks)
3. Begin Phase 1, Week 1 implementation
4. Track progress in this document
5. Adjust timeline as needed based on learnings

---

Last updated: 2026-02-17
Status: Planning Complete, Ready for Implementation
