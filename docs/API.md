# API Reference

REST API documentation for Personal Manager.

## Base URL

```
http://localhost:8000/api
```

## Authentication

Currently: No authentication (local-only access)

Future: Optional basic auth or API key for remote access

## Response Format

All responses follow this structure:

### Success Response
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation successful"
}
```

### Error Response
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": { ... }
  }
}
```

## Tasks API

### List Tasks

```http
GET /api/tasks
```

**Query Parameters**:
- `status` (optional): Filter by status (pending, scheduled, in_progress, completed, blocked, cancelled)
- `priority` (optional): Filter by priority (low, medium, high, critical)
- `project_id` (optional): Filter by project
- `due_before` (optional): ISO 8601 date
- `due_after` (optional): ISO 8601 date
- `limit` (optional): Default 100, max 1000
- `offset` (optional): For pagination

**Response**:
```json
{
  "success": true,
  "data": {
    "tasks": [
      {
        "id": 1,
        "title": "Write masters statement of purpose",
        "description": "Draft SoP for university applications",
        "status": "in_progress",
        "priority": "high",
        "estimate_minutes": 180,
        "actual_minutes": 120,
        "due_date": "2026-02-25T00:00:00Z",
        "energy_level": "high",
        "context_tags": ["writing", "academic"],
        "project_id": 5,
        "blocker_id": null,
        "created_at": "2026-02-17T10:00:00Z",
        "updated_at": "2026-02-17T14:30:00Z",
        "completed_at": null
      }
    ],
    "total": 42,
    "limit": 100,
    "offset": 0
  }
}
```

### Get Task

```http
GET /api/tasks/{task_id}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "id": 1,
    "title": "Write masters statement of purpose",
    // ... (full task object)
    "project": {
      "id": 5,
      "name": "Masters Application"
    },
    "schedule_entries": [
      {
        "id": 10,
        "start_time": "2026-02-18T09:00:00Z",
        "end_time": "2026-02-18T11:00:00Z",
        "status": "scheduled",
        "calendar_event_id": "evt_abc123"
      }
    ]
  }
}
```

### Create Task

```http
POST /api/tasks
Content-Type: application/json
```

**Request Body**:
```json
{
  "title": "Review pull request",
  "description": "Review PR #42 for authentication feature",
  "priority": "high",
  "estimate_minutes": 60,
  "due_date": "2026-02-18T17:00:00Z",
  "energy_level": "medium",
  "project_id": 3,
  "context_tags": ["code-review", "security"]
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "id": 123,
    "title": "Review pull request",
    // ... (full created task)
  },
  "message": "Task created successfully"
}
```

### Update Task

```http
PUT /api/tasks/{task_id}
Content-Type: application/json
```

**Request Body** (all fields optional):
```json
{
  "title": "Updated title",
  "status": "in_progress",
  "priority": "critical",
  "actual_minutes": 45
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    // ... (updated task)
  },
  "message": "Task updated successfully"
}
```

### Update Task Status

```http
PATCH /api/tasks/{task_id}/status
Content-Type: application/json
```

**Request Body**:
```json
{
  "status": "completed"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    // ... (updated task with completed_at set)
  },
  "message": "Task marked as completed"
}
```

### Delete Task

```http
DELETE /api/tasks/{task_id}
```

**Response**:
```json
{
  "success": true,
  "message": "Task deleted successfully"
}
```

## Goals API

### List Goals

```http
GET /api/goals
```

**Query Parameters**:
- `status` (optional): active, paused, completed, abandoned
- `category` (optional): career, education, health, etc.
- `parent_id` (optional): Get sub-goals of a parent

**Response**:
```json
{
  "success": true,
  "data": {
    "goals": [
      {
        "id": 1,
        "title": "Get into Masters Program",
        "description": "Apply to top CS programs",
        "status": "active",
        "parent_goal_id": null,
        "level": 0,
        "target_date": "2026-12-01T00:00:00Z",
        "progress_percent": 35,
        "category": "education",
        "created_at": "2026-01-01T00:00:00Z",
        "sub_goals": [
          {
            "id": 2,
            "title": "Complete applications",
            "level": 1,
            "progress_percent": 60
          }
        ]
      }
    ]
  }
}
```

### Create Goal

```http
POST /api/goals
Content-Type: application/json
```

**Request Body**:
```json
{
  "title": "Learn machine learning",
  "description": "Complete ML specialization and build projects",
  "parent_goal_id": 1,
  "target_date": "2026-06-30T00:00:00Z",
  "category": "education"
}
```

### Update Goal Progress

```http
PATCH /api/goals/{goal_id}/progress
Content-Type: application/json
```

**Request Body**:
```json
{
  "progress_percent": 75
}
```

## Projects API

### List Projects

```http
GET /api/projects
```

**Query Parameters**:
- `active` (optional): true/false
- `language` (optional): Filter by primary language
- `search` (optional): Search in name and description

**Response**:
```json
{
  "success": true,
  "data": {
    "projects": [
      {
        "id": 1,
        "name": "PersonalManager",
        "description": "AI-powered personal assistant",
        "repo_path": "/home/user/projects/PersonalManager",
        "repo_url": "https://github.com/user/PersonalManager",
        "active": true,
        "tags": ["python", "ai", "productivity"],
        "primary_language": "Python",
        "frameworks": ["FastAPI", "SQLAlchemy", "LangGraph"],
        "last_activity_at": "2026-02-17T15:30:00Z",
        "total_commits": 157,
        "total_sessions": 42,
        "created_at": "2026-01-15T00:00:00Z"
      }
    ]
  }
}
```

### Get Project Details

```http
GET /api/projects/{project_id}
```

**Response** includes recent sessions and tasks:
```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "PersonalManager",
    // ... (project fields)
    "recent_sessions": [
      {
        "id": 50,
        "source": "git",
        "started_at": "2026-02-17T14:00:00Z",
        "duration_minutes": 90,
        "summary": "Implemented calendar sync"
      }
    ],
    "active_tasks": [
      {
        "id": 10,
        "title": "Add insights dashboard",
        "status": "in_progress"
      }
    ],
    "stats": {
      "commits_this_week": 12,
      "sessions_this_week": 5,
      "total_time_this_week": 480
    }
  }
}
```

## Sessions API

### List Sessions

```http
GET /api/sessions
```

**Query Parameters**:
- `project_id` (optional)
- `source` (optional): git, claude_code, opencode, manual
- `start_date` (optional): ISO 8601
- `end_date` (optional): ISO 8601

**Response**:
```json
{
  "success": true,
  "data": {
    "sessions": [
      {
        "id": 1,
        "source": "claude_code",
        "started_at": "2026-02-17T09:00:00Z",
        "ended_at": "2026-02-17T11:30:00Z",
        "duration_minutes": 150,
        "summary": "Built calendar integration module",
        "topics": ["calendar", "oauth", "sync"],
        "transcript_path": "/data/sessions/2026-02-17-claude.md",
        "project_id": 1,
        "project_name": "PersonalManager"
      }
    ]
  }
}
```

### Create Session (Manual)

```http
POST /api/sessions
Content-Type: application/json
```

**Request Body**:
```json
{
  "source": "manual",
  "project_id": 1,
  "started_at": "2026-02-17T14:00:00Z",
  "ended_at": "2026-02-17T16:00:00Z",
  "summary": "Reviewed documentation and fixed typos",
  "topics": ["docs", "review"]
}
```

## Calendar API

### Get Calendars

```http
GET /api/calendar/calendars
```

**Response**:
```json
{
  "success": true,
  "data": {
    "calendars": [
      {
        "id": "primary",
        "name": "Primary Calendar",
        "provider": "google",
        "synced": true,
        "last_sync_at": "2026-02-17T16:00:00Z"
      },
      {
        "id": "agent_inbox",
        "name": "Agent Inbox",
        "provider": "google",
        "synced": true,
        "type": "inbox"
      }
    ]
  }
}
```

### Sync Calendar

```http
POST /api/calendar/sync
Content-Type: application/json
```

**Request Body** (optional):
```json
{
  "calendar_id": "agent_inbox",
  "force_full_sync": false
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "events_added": 2,
    "events_updated": 5,
    "events_deleted": 1,
    "sync_duration_ms": 345,
    "next_sync_token": "abc123xyz"
  },
  "message": "Calendar synced successfully"
}
```

### Get Sync Status

```http
GET /api/calendar/sync/status
```

**Response**:
```json
{
  "success": true,
  "data": {
    "last_sync_at": "2026-02-17T16:00:00Z",
    "next_sync_in_seconds": 45,
    "sync_enabled": true,
    "calendars": [
      {
        "calendar_id": "agent_inbox",
        "last_sync_at": "2026-02-17T16:00:00Z",
        "status": "success",
        "events_count": 3
      }
    ]
  }
}
```

## Schedule API

### Get Today's Schedule

```http
GET /api/schedule/today
```

**Response**:
```json
{
  "success": true,
  "data": {
    "date": "2026-02-17",
    "schedule": [
      {
        "type": "focus_block",
        "task_id": 10,
        "task_title": "Write SoP",
        "start_time": "2026-02-17T09:00:00Z",
        "end_time": "2026-02-17T11:00:00Z",
        "status": "scheduled",
        "calendar_event_id": "evt_123"
      },
      {
        "type": "meeting",
        "title": "Team standup",
        "start_time": "2026-02-17T14:00:00Z",
        "end_time": "2026-02-17T14:30:00Z"
      }
    ],
    "stats": {
      "total_focus_time": 240,
      "total_meeting_time": 30,
      "free_time": 210
    }
  }
}
```

### Generate Schedule

```http
POST /api/schedule/generate
Content-Type: application/json
```

**Request Body**:
```json
{
  "date": "2026-02-18",
  "tasks": [10, 11, 12],  // Optional: specific tasks, or all pending
  "constraints": {
    "working_hours": {
      "start": "09:00",
      "end": "18:00"
    },
    "deep_work_blocks": [
      {"start": "09:00", "end": "11:00"},
      {"start": "14:00", "end": "16:00"}
    ],
    "max_hours_per_day": 6
  }
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "schedule": [
      // ... (generated schedule)
    ],
    "conflicts": [],
    "unscheduled_tasks": []
  },
  "message": "Schedule generated and saved to calendar"
}
```

## Insights API

### Get Daily Insights

```http
GET /api/insights/daily?date=2026-02-17
```

**Response**:
```json
{
  "success": true,
  "data": {
    "date": "2026-02-17",
    "metrics": {
      "deep_work_hours": 5.5,
      "context_switches": 8,
      "tasks_completed": 4,
      "tasks_planned": 6,
      "completion_rate": 0.67,
      "top_projects": [
        {"name": "PersonalManager", "time_minutes": 240},
        {"name": "MastersApp", "time_minutes": 90}
      ],
      "distractions": [
        {"app": "Slack", "time_minutes": 35},
        {"domain": "reddit.com", "time_minutes": 12}
      ]
    },
    "insights": {
      "summary": "Productive day with good focus in morning hours",
      "highlights": [
        "Completed calendar integration ahead of schedule",
        "Maintained focus during morning deep work block"
      ],
      "improvements": [
        "Reduce Slack time in afternoon",
        "Take more breaks between tasks"
      ]
    }
  }
}
```

### Get Weekly Insights

```http
GET /api/insights/weekly?week=2026-W07
```

**Response**:
```json
{
  "success": true,
  "data": {
    "week": "2026-W07",
    "start_date": "2026-02-17",
    "end_date": "2026-02-23",
    "metrics": {
      "total_deep_work_hours": 24,
      "avg_daily_deep_work": 4.8,
      "tasks_completed": 18,
      "tasks_planned": 22,
      "completion_rate": 0.82,
      "context_switches_per_day": 12,
      "peak_hours": ["09:00-11:00", "14:00-16:00"],
      "low_energy_times": ["15:00-16:00", "Friday afternoon"]
    },
    "trends": {
      "deep_work_hours_change": "+2h vs last week",
      "completion_rate_change": "-5% vs last week",
      "distraction_time_change": "-18% vs last week"
    },
    "insights": {
      "summary": "Strong week with improved focus...",
      "key_insights": [
        "Morning hours most productive",
        "Friday afternoons consistently low energy",
        "Tuesday overloaded with meetings"
      ],
      "recommendations": [
        "Block Tuesday mornings for deep work",
        "Schedule admin tasks for Friday afternoons",
        "Maintain current morning routine"
      ]
    }
  }
}
```

## Blockers API

### List Blockers

```http
GET /api/blockers
```

**Query Parameters**:
- `status` (optional): open, in_progress, resolved
- `severity` (optional): low, medium, high, critical

**Response**:
```json
{
  "success": true,
  "data": {
    "blockers": [
      {
        "id": 1,
        "description": "Waiting for API access from third-party service",
        "severity": "high",
        "status": "open",
        "task_id": 15,
        "task_title": "Integrate payment system",
        "created_at": "2026-02-15T10:00:00Z",
        "age_days": 2
      }
    ]
  }
}
```

### Create Blocker

```http
POST /api/blockers
Content-Type: application/json
```

**Request Body**:
```json
{
  "description": "Need design mockups from designer",
  "severity": "medium",
  "task_id": 20
}
```

### Resolve Blocker

```http
PATCH /api/blockers/{blocker_id}/resolve
Content-Type: application/json
```

**Request Body**:
```json
{
  "resolution_notes": "Received API credentials via email"
}
```

## Activity API

### Get Activity Summary

```http
GET /api/activity/summary
```

**Query Parameters**:
- `start_date` (required): ISO 8601
- `end_date` (required): ISO 8601
- `granularity` (optional): hour, day, week (default: day)

**Response**:
```json
{
  "success": true,
  "data": {
    "period": {
      "start": "2026-02-10T00:00:00Z",
      "end": "2026-02-17T00:00:00Z"
    },
    "coding_time": [
      {
        "date": "2026-02-17",
        "projects": [
          {
            "path": "/home/user/projects/PersonalManager",
            "minutes": 240
          }
        ],
        "total_minutes": 240
      }
    ],
    "app_usage": [
      {
        "date": "2026-02-17",
        "apps": [
          {"name": "Visual Studio Code", "minutes": 280},
          {"name": "Google Chrome", "minutes": 120},
          {"name": "Terminal", "minutes": 90}
        ]
      }
    ],
    "browser_activity": [
      {
        "date": "2026-02-17",
        "domains": [
          {"domain": "github.com", "visits": 45},
          {"domain": "stackoverflow.com", "visits": 12},
          {"domain": "docs.python.org", "visits": 8}
        ]
      }
    ]
  }
}
```

## Health & Status API

### Health Check

```http
GET /api/health
```

**Response**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-02-17T16:30:00Z",
  "checks": {
    "database": "ok",
    "calendar_sync": "ok",
    "activity_tracker": "ok"
  }
}
```

### System Status

```http
GET /api/status
```

**Response**:
```json
{
  "success": true,
  "data": {
    "uptime_seconds": 86400,
    "database": {
      "size_mb": 12.5,
      "tasks_count": 157,
      "projects_count": 8,
      "sessions_count": 423
    },
    "background_jobs": {
      "calendar_sync": {
        "next_run": "2026-02-17T16:32:00Z",
        "last_run": "2026-02-17T16:30:00Z",
        "status": "success"
      },
      "daily_plan": {
        "next_run": "2026-02-18T07:00:00Z",
        "last_run": "2026-02-17T07:00:00Z",
        "status": "success"
      }
    },
    "calendar": {
      "synced_calendars": 4,
      "last_sync": "2026-02-17T16:30:00Z",
      "pending_events": 2
    }
  }
}
```

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request body or parameters |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource conflict (e.g., duplicate) |
| `CALENDAR_SYNC_ERROR` | 500 | Calendar sync failed |
| `DATABASE_ERROR` | 500 | Database operation failed |
| `LLM_ERROR` | 500 | LLM API call failed |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

## Rate Limiting

Current: No rate limiting (local-only)

Future: When remote access enabled:
- 100 requests/minute per IP
- 1000 requests/hour per IP

## Pagination

For endpoints that return lists:

**Query Parameters**:
- `limit`: Number of items (default: 100, max: 1000)
- `offset`: Skip N items (default: 0)

**Response includes**:
```json
{
  "data": {
    "items": [...],
    "total": 500,
    "limit": 100,
    "offset": 200,
    "has_more": true
  }
}
```

## Webhooks (Future)

Support for outgoing webhooks when events occur:

```yaml
# config.yaml
webhooks:
  - event: task.completed
    url: https://example.com/webhook
    headers:
      Authorization: "Bearer token"

  - event: blocker.created
    url: https://example.com/webhook
```

---

Last updated: 2026-02-17
