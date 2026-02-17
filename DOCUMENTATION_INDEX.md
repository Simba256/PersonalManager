# Documentation Index

Complete documentation for Personal Manager - AI-Powered Personal Assistant

## Quick Navigation

### Getting Started
- [README.md](README.md) - Project overview and quick start
- [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) - Step-by-step implementation plan (8-week roadmap)

### Core Documentation
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture and design
- [docs/MODELS.md](docs/MODELS.md) - Database schema and data models
- [docs/API.md](docs/API.md) - REST API reference
- [docs/CALENDAR.md](docs/CALENDAR.md) - Calendar integration guide

### Development & Deployment
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) - Development environment setup and guidelines
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - Production deployment instructions
- [CONTRIBUTING.md](CONTRIBUTING.md) - How to contribute to the project

### Configuration
- [config.example.yaml](config.example.yaml) - Example configuration file
- [.env.example](.env.example) - Environment variables template
- [requirements.txt](requirements.txt) - Python dependencies
- [requirements-dev.txt](requirements-dev.txt) - Development dependencies

## Documentation by Role

### For End Users
1. **Getting Started**
   - [README.md](README.md) - What is Personal Manager?
   - [docs/CALENDAR.md](docs/CALENDAR.md) - How to use calendar integration
   - Setup Guide (TBD) - First-time setup walkthrough

2. **Using the System**
   - Calendar Integration Guide
   - Task Management Guide (TBD)
   - Understanding Insights (TBD)

### For Developers
1. **Understanding the System**
   - [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - How it works
   - [docs/MODELS.md](docs/MODELS.md) - Data structures
   - [docs/API.md](docs/API.md) - API endpoints

2. **Building & Development**
   - [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) - Dev environment setup
   - [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) - Implementation roadmap
   - [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines

3. **Reference**
   - [requirements.txt](requirements.txt) - Dependencies
   - [config.example.yaml](config.example.yaml) - Configuration options

### For System Administrators
1. **Deployment**
   - [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - Production deployment
   - [docs/DEPLOYMENT.md#systemd-service-deployment](docs/DEPLOYMENT.md#option-1-systemd-service-deployment) - Systemd setup
   - [docs/DEPLOYMENT.md#docker-deployment](docs/DEPLOYMENT.md#option-2-docker-deployment) - Docker setup

2. **Maintenance**
   - [docs/DEPLOYMENT.md#backup-and-restore](docs/DEPLOYMENT.md#backup-and-restore) - Backup procedures
   - [docs/DEPLOYMENT.md#monitoring](docs/DEPLOYMENT.md#monitoring) - Monitoring setup
   - [docs/DEPLOYMENT.md#troubleshooting-production-issues](docs/DEPLOYMENT.md#troubleshooting-production-issues) - Common issues

## Documentation by Topic

### Architecture & Design
- [System Overview](docs/ARCHITECTURE.md#system-overview)
- [Component Architecture](docs/ARCHITECTURE.md#component-architecture)
- [Data Flow](docs/ARCHITECTURE.md#data-flow)
- [Security & Privacy](docs/ARCHITECTURE.md#security--privacy)

### Calendar Integration
- [Calendar Setup](docs/CALENDAR.md#google-calendar-setup)
- [Dedicated Calendars](docs/CALENDAR.md#dedicated-calendars)
- [Event Parsing](docs/CALENDAR.md#event-parsing)
- [Synchronization](docs/CALENDAR.md#synchronization)
- [Troubleshooting](docs/CALENDAR.md#troubleshooting)

### Database
- [Database Schema](docs/MODELS.md#core-models)
- [Relationships](docs/MODELS.md#schema-diagram)
- [Migrations](docs/MODELS.md#database-migrations)
- [Query Examples](docs/MODELS.md#query-examples)

### API
- [Tasks API](docs/API.md#tasks-api)
- [Goals API](docs/API.md#goals-api)
- [Projects API](docs/API.md#projects-api)
- [Sessions API](docs/API.md#sessions-api)
- [Calendar API](docs/API.md#calendar-api)
- [Schedule API](docs/API.md#schedule-api)
- [Insights API](docs/API.md#insights-api)

### Development
- [Setup](docs/DEVELOPMENT.md#development-environment-setup)
- [Code Style](docs/DEVELOPMENT.md#code-style)
- [Testing](docs/DEVELOPMENT.md#testing)
- [Debugging](docs/DEVELOPMENT.md#debugging)
- [Contributing](CONTRIBUTING.md)

### Implementation
- [Phase 1: Foundation](docs/IMPLEMENTATION.md#phase-1-foundation-week-1-2)
- [Phase 2: Integration](docs/IMPLEMENTATION.md#phase-2-integration-week-3-4)
- [Phase 3: Intelligence](docs/IMPLEMENTATION.md#phase-3-intelligence-week-5-6)
- [Phase 4: Polish](docs/IMPLEMENTATION.md#phase-4-polish-week-7-8)

### Deployment
- [Systemd Service](docs/DEPLOYMENT.md#option-1-systemd-service-deployment)
- [Docker](docs/DEPLOYMENT.md#option-2-docker-deployment)
- [Security](docs/DEPLOYMENT.md#security-considerations)
- [Monitoring](docs/DEPLOYMENT.md#monitoring)
- [Backup & Restore](docs/DEPLOYMENT.md#backup-and-restore)

## Implementation Progress

Track implementation progress against the plan:

### Phase 1: Foundation (Week 1-2)
- [x] Complete documentation
- [ ] Project scaffolding
- [ ] Database models
- [ ] Configuration system
- [ ] Basic FastAPI application
- [ ] Task management CRUD
- [ ] Calendar integration setup

### Phase 2: Integration (Week 3-4)
- [ ] Activity Tracker integration
- [ ] Git repository monitoring
- [ ] Session file watcher
- [ ] Basic CLI interface
- [ ] Smart scheduler
- [ ] Insights pipeline
- [ ] LLM integration

### Phase 3: Intelligence (Week 5-6)
- [ ] LangGraph setup
- [ ] Inbox triage workflow
- [ ] Daily planner workflow
- [ ] Insights generator workflow
- [ ] Web dashboard
- [ ] Real-time updates

### Phase 4: Polish (Week 7-8)
- [ ] Error handling & resilience
- [ ] Documentation updates
- [ ] Optimization
- [ ] Security audit
- [ ] Deployment setup
- [ ] User testing

## Quick Reference

### Key Commands
```bash
# Setup
python scripts/setup_google_calendar.py

# Development
uvicorn app.main:app --reload

# Testing
pytest
pytest --cov=app

# Database
alembic upgrade head
alembic revision --autogenerate -m "description"

# Deployment
sudo systemctl start personal-manager
sudo systemctl status personal-manager
sudo journalctl -u personal-manager -f

# Backup
python scripts/backup_database.py

# CLI
personal-manager task add "Task title"
personal-manager sync calendar
personal-manager insights --week
```

### Important Files
- `config.yaml` - Main configuration
- `.env` - Environment variables and API keys
- `data/agent.db` - Main SQLite database
- `data/logs/` - Application logs
- `~/.personal-manager/credentials/` - OAuth credentials
- `~/.personal-manager/tokens/` - OAuth tokens

### Important URLs
- Web UI: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/health
- Status: http://localhost:8000/api/status

## Getting Help

1. Check relevant documentation section
2. Search existing issues
3. Review troubleshooting guides:
   - [Calendar Troubleshooting](docs/CALENDAR.md#troubleshooting)
   - [Development Troubleshooting](docs/DEVELOPMENT.md#troubleshooting)
   - [Production Troubleshooting](docs/DEPLOYMENT.md#troubleshooting-production-issues)
4. Create a new issue if needed

## Documentation Standards

All documentation follows these standards:
- Markdown format
- Clear, concise language
- Code examples included
- Updated with changes
- Last updated date at bottom

## Contributing to Documentation

See [CONTRIBUTING.md](CONTRIBUTING.md#documentation) for guidelines on:
- Writing documentation
- Documentation style
- Examples and code blocks
- Keeping docs up to date

---

**Total Documentation**: 11 files, ~15,000 lines

Last updated: 2026-02-17
Status: Initial documentation complete, ready for implementation
