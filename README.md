# Personal Manager - AI-Powered Personal Assistant

A local-first, privacy-preserving AI agent that manages your tasks, projects, and productivity through calendar integration and intelligent scheduling.

## Overview

Personal Manager is a Python-based AI assistant that:
- Tracks all your coding projects and current work
- Monitors development sessions (Claude Code, OpenCode, git activity)
- Manages tasks, goals, and blockers with local memory
- Integrates with your Activity Tracker for productivity insights
- Uses both OpenAI and Anthropic APIs for intelligent processing
- Schedules your day optimally via calendar integration
- Provides daily check-ins and weekly reviews

## Key Features

### 📅 Calendar-First Interface
- Add tasks by creating calendar events
- Receive scheduled focus blocks automatically
- Daily check-ins and weekly reviews as calendar events
- Native calendar notifications (no external messaging apps needed)

### 🧠 Intelligent Scheduling
- Constraint-based optimization for task scheduling
- Respects deadlines, priorities, and working hours
- Minimizes context switching
- Protected deep work blocks

### 📊 Productivity Insights
- Analyzes your Activity Tracker data
- Identifies focus patterns and distractions
- Tracks project progress automatically
- Weekly productivity summaries

### 🔒 Privacy-First
- All data stored locally in SQLite
- No cloud dependencies except LLM API calls
- Self-hosted web interface
- Open source and auditable

## Architecture

```
┌─────────────────────────────────────────────────┐
│   Google Calendar / CalDAV (Interface)          │
│   • Agent Inbox (task input)                    │
│   • Focus Blocks (scheduled work)               │
│   • Check-ins (daily reflections)               │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│   Python Service (FastAPI + Background Jobs)    │
│   • FastAPI web UI                              │
│   • APScheduler background jobs                 │
│   • LangGraph agent workflows                   │
│   • Multi-LLM support (OpenAI + Anthropic)      │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│   Data Layer (SQLite)                           │
│   • Main DB: tasks, goals, projects, sessions   │
│   • Attached: Activity Tracker (read-only)      │
└─────────────────────────────────────────────────┘
```

## Technology Stack

- **Runtime**: Python 3.11+
- **Web Framework**: FastAPI + Uvicorn
- **Background Jobs**: APScheduler
- **Database**: SQLite + SQLAlchemy
- **AI/Agent**: LangGraph, OpenAI SDK, Anthropic SDK
- **Calendar**: Google Calendar API, CalDAV
- **Scheduling**: OR-Tools (constraint solver)
- **Analytics**: Polars / Pandas
- **CLI**: Typer
- **UI**: Jinja2 + HTMX + Tailwind CSS

## Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd PersonalManager
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp config.example.yaml config.yaml
# Edit config.yaml with your settings

# Setup Google Calendar OAuth
python scripts/setup_calendars.py

# Run
python -m app.main

# Access web UI
open http://localhost:8000
```

## Documentation

- [Architecture Documentation](docs/ARCHITECTURE.md) - Detailed system design
- [Implementation Plan](docs/IMPLEMENTATION.md) - Development roadmap
- [API Reference](docs/API.md) - REST API documentation
- [Calendar Integration](docs/CALENDAR.md) - Calendar setup and usage
- [Data Models](docs/MODELS.md) - Database schema
- [Development Guide](docs/DEVELOPMENT.md) - Contributing guidelines
- [Deployment Guide](docs/DEPLOYMENT.md) - Production setup

## Project Structure

```
PersonalManager/
├── app/                    # Main application code
│   ├── main.py            # FastAPI application
│   ├── scheduler.py       # APScheduler setup
│   ├── models.py          # SQLAlchemy models
│   ├── calendar/          # Calendar integrations
│   ├── agent/             # LangGraph workflows
│   ├── integrations/      # Activity Tracker, Git, etc.
│   ├── web/               # Web UI routes and templates
│   └── cli.py             # CLI interface
├── data/                  # SQLite databases and session exports
├── docs/                  # Documentation
├── scripts/               # Setup and utility scripts
├── tests/                 # Test suite
├── config.yaml            # User configuration
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Use Cases

### Adding a Task via Calendar
```
Create event in "Agent Inbox" calendar:
Title: "Task: Write masters statement of purpose"
Description: "Priority: High, Duration: 3h, Due: 2026-02-25"
```

### Daily Check-in
```
7 AM: Agent creates calendar event
"What did you accomplish yesterday? Any blockers?"

Edit the description with your response
Agent updates memory and adjusts schedule
```

### Viewing Productivity Insights
```bash
# Via CLI
python -m app.cli insights --week

# Via Web UI
http://localhost:8000/insights
```

## Requirements

- Python 3.11 or higher
- Linux operating system
- Google account (for Google Calendar) or CalDAV server
- OpenAI API key (for GPT models)
- Anthropic API key (for Claude models)
- Existing Activity Tracker installation

## License

[Choose appropriate license]

## Support

For issues, questions, or contributions, please see [CONTRIBUTING.md](CONTRIBUTING.md)

## Roadmap

- [x] Project planning and documentation
- [ ] Core database and models
- [ ] Calendar integration (Google + CalDAV)
- [ ] Task management and scheduling
- [ ] Activity Tracker integration
- [ ] LangGraph agent implementation
- [ ] Web UI and dashboard
- [ ] CLI interface
- [ ] Session monitoring (Git, Claude Code, OpenCode)
- [ ] Smart scheduling algorithm
- [ ] Insights and analytics
- [ ] Testing and deployment

---

Built with ❤️ for personal productivity and privacy
