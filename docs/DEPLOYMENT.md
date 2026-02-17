# Deployment Guide

Guide for deploying Personal Manager in production.

## Deployment Options

### Option 1: Systemd Service (Recommended)
Run as a system service on Linux

### Option 2: Docker
Containerized deployment

### Option 3: Manual
Direct execution for development/testing

## Prerequisites

- Linux system (Ubuntu 20.04+ or similar)
- Python 3.11+
- SQLite 3.35+
- Google Calendar API credentials
- OpenAI and/or Anthropic API keys
- Existing Activity Tracker installation

## Option 1: Systemd Service Deployment

### Step 1: Prepare Application

```bash
# Create application directory
sudo mkdir -p /opt/personal-manager
sudo chown $USER:$USER /opt/personal-manager

# Clone or copy application
cd /opt/personal-manager
git clone <repository-url> .

# Create virtual environment
python3.11 -m venv venv

# Install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2: Configure Application

```bash
# Create config directory
mkdir -p ~/.personal-manager/{credentials,tokens,logs}

# Copy and edit configuration
cp config.example.yaml config.yaml
nano config.yaml

# Setup environment variables
cp .env.example .env
nano .env  # Add API keys
```

**config.yaml**:
```yaml
app:
  host: "127.0.0.1"  # Only local access
  port: 8000
  debug: false
  log_level: "INFO"

database:
  url: "sqlite:////opt/personal-manager/data/agent.db"
  echo: false

activity_tracker:
  db_path: "/media/shared/personalProjects/ActivityTracker/activity.db"

calendar:
  google:
    enabled: true
    credentials_path: "~/.personal-manager/credentials/google_credentials.json"
    token_path: "~/.personal-manager/tokens/google_token.json"

llm:
  default_provider: "anthropic"  # or "openai"
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4-turbo"
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-3-5-sonnet-20250129"

scheduler:
  timezone: "America/New_York"  # Your timezone
  jobs:
    calendar_sync:
      interval_minutes: 2
    daily_plan:
      hour: 7
      minute: 0
    eod_summary:
      hour: 18
      minute: 0
```

**.env**:
```bash
# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional
CALDAV_PASSWORD=your-password
```

### Step 3: Initialize Database

```bash
cd /opt/personal-manager
source venv/bin/activate

# Run migrations
alembic upgrade head

# Setup Google Calendar
python scripts/setup_google_calendar.py
```

### Step 4: Create Systemd Service

```bash
sudo nano /etc/systemd/system/personal-manager.service
```

**personal-manager.service**:
```ini
[Unit]
Description=Personal Manager AI Assistant
After=network.target

[Service]
Type=simple
User=your-username
Group=your-username
WorkingDirectory=/opt/personal-manager
Environment="PATH=/opt/personal-manager/venv/bin"
EnvironmentFile=/opt/personal-manager/.env

ExecStart=/opt/personal-manager/venv/bin/uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --log-config /opt/personal-manager/logging.conf

# Restart on failure
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=personal-manager

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### Step 5: Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable personal-manager

# Start service
sudo systemctl start personal-manager

# Check status
sudo systemctl status personal-manager

# View logs
sudo journalctl -u personal-manager -f

# Stop service
sudo systemctl stop personal-manager

# Restart service
sudo systemctl restart personal-manager
```

### Step 6: Setup Log Rotation

```bash
sudo nano /etc/logrotate.d/personal-manager
```

**personal-manager logrotate config**:
```
/opt/personal-manager/data/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 your-username your-username
    sharedscripts
    postrotate
        systemctl reload personal-manager > /dev/null 2>&1 || true
    endscript
}
```

### Step 7: Setup Automated Backups

```bash
# Create backup script
nano /opt/personal-manager/scripts/backup.sh
```

**backup.sh**:
```bash
#!/bin/bash

BACKUP_DIR="/opt/personal-manager/data/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_PATH="/opt/personal-manager/data/agent.db"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup database
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/agent_$DATE.db'"

# Compress
gzip "$BACKUP_DIR/agent_$DATE.db"

# Keep only last 30 days
find "$BACKUP_DIR" -name "agent_*.db.gz" -mtime +30 -delete

echo "Backup completed: agent_$DATE.db.gz"
```

```bash
# Make executable
chmod +x /opt/personal-manager/scripts/backup.sh

# Add to crontab
crontab -e

# Add line (daily backup at 2 AM)
0 2 * * * /opt/personal-manager/scripts/backup.sh >> /opt/personal-manager/data/logs/backup.log 2>&1
```

## Option 2: Docker Deployment

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directories
RUN mkdir -p /app/data/{logs,sessions,backups}

# Run migrations
RUN alembic upgrade head

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health')"

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  personal-manager:
    build: .
    container_name: personal-manager
    restart: unless-stopped
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      # Persistent data
      - ./data:/app/data
      # Config
      - ./config.yaml:/app/config.yaml:ro
      - ./env:/app/.env:ro
      # Google credentials
      - ~/.personal-manager/credentials:/root/.personal-manager/credentials:ro
      - ~/.personal-manager/tokens:/root/.personal-manager/tokens
      # Activity Tracker (read-only)
      - /media/shared/personalProjects/ActivityTracker/activity.db:/data/activity_tracker.db:ro
    environment:
      - TZ=America/New_York
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### Deploy with Docker Compose

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Restart
docker-compose restart

# Update
git pull
docker-compose build
docker-compose up -d
```

## Security Considerations

### API Key Protection

```bash
# Use restrictive permissions
chmod 600 .env
chmod 600 ~/.personal-manager/credentials/*
chmod 600 ~/.personal-manager/tokens/*

# Never commit secrets
echo ".env" >> .gitignore
echo "config.yaml" >> .gitignore
```

### Firewall Configuration

```bash
# Only allow local access
sudo ufw allow from 127.0.0.1 to any port 8000

# If remote access needed (not recommended for personal use)
sudo ufw allow from 192.168.1.0/24 to any port 8000
```

### Database Security

```bash
# Restrict database file permissions
chmod 640 data/agent.db
chmod 640 /media/shared/personalProjects/ActivityTracker/activity.db

# Optional: Enable SQLite encryption
# Requires sqlcipher
sudo apt install sqlcipher
```

## Monitoring

### Application Monitoring

```bash
# Create monitoring script
nano /opt/personal-manager/scripts/monitor.sh
```

**monitor.sh**:
```bash
#!/bin/bash

# Check if service is running
if ! systemctl is-active --quiet personal-manager; then
    echo "ERROR: Service is not running"
    systemctl restart personal-manager
    exit 1
fi

# Check API health
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health)
if [ "$RESPONSE" != "200" ]; then
    echo "ERROR: Health check failed (HTTP $RESPONSE)"
    systemctl restart personal-manager
    exit 1
fi

# Check database size
DB_SIZE=$(du -m /opt/personal-manager/data/agent.db | cut -f1)
if [ "$DB_SIZE" -gt 1000 ]; then
    echo "WARNING: Database size is ${DB_SIZE}MB"
fi

# Check disk space
DISK_USAGE=$(df -h /opt/personal-manager | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 90 ]; then
    echo "WARNING: Disk usage is ${DISK_USAGE}%"
fi

echo "OK: All checks passed"
```

```bash
chmod +x /opt/personal-manager/scripts/monitor.sh

# Add to crontab (check every 5 minutes)
*/5 * * * * /opt/personal-manager/scripts/monitor.sh >> /opt/personal-manager/data/logs/monitor.log 2>&1
```

### Log Monitoring

```bash
# Watch logs in real-time
sudo journalctl -u personal-manager -f

# View errors only
sudo journalctl -u personal-manager -p err -n 50

# View logs for specific date
sudo journalctl -u personal-manager --since "2026-02-17" --until "2026-02-18"

# Export logs
sudo journalctl -u personal-manager --since today > today.log
```

## Performance Tuning

### SQLite Optimization

```python
# app/database.py
from sqlalchemy import event, create_engine

engine = create_engine(
    "sqlite:///data/agent.db",
    connect_args={
        "check_same_thread": False,
        "timeout": 30
    },
    pool_pre_ping=True,
    echo=False
)

# Enable WAL mode and optimize
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()
```

### Application Performance

```yaml
# config.yaml
app:
  workers: 1  # Single process for SQLite
  reload: false  # Disable in production
  log_level: "WARNING"  # Reduce logging

scheduler:
  max_instances: 1
  coalesce: true
  misfire_grace_time: 60
```

## Backup and Restore

### Manual Backup

```bash
# Stop service
sudo systemctl stop personal-manager

# Backup database
sqlite3 /opt/personal-manager/data/agent.db ".backup /opt/personal-manager/data/backups/agent_manual.db"

# Backup configuration
tar -czf /opt/personal-manager/data/backups/config_$(date +%Y%m%d).tar.gz \
    config.yaml .env ~/.personal-manager/

# Start service
sudo systemctl start personal-manager
```

### Restore from Backup

```bash
# Stop service
sudo systemctl stop personal-manager

# Restore database
cp /opt/personal-manager/data/backups/agent_20260217.db /opt/personal-manager/data/agent.db

# Verify database
sqlite3 /opt/personal-manager/data/agent.db "PRAGMA integrity_check"

# Start service
sudo systemctl start personal-manager
```

### Remote Backup

```bash
# Backup to remote server via rsync
rsync -avz --delete /opt/personal-manager/data/backups/ \
    user@backup-server:/backups/personal-manager/
```

## Updates and Maintenance

### Updating Application

```bash
# Stop service
sudo systemctl stop personal-manager

# Backup first
/opt/personal-manager/scripts/backup.sh

# Pull updates
cd /opt/personal-manager
git pull

# Update dependencies
source venv/bin/activate
pip install --upgrade -r requirements.txt

# Run migrations
alembic upgrade head

# Restart service
sudo systemctl start personal-manager

# Check status
sudo systemctl status personal-manager
```

### Database Maintenance

```bash
# Vacuum database (reclaim space)
sqlite3 /opt/personal-manager/data/agent.db "VACUUM;"

# Analyze database (update statistics)
sqlite3 /opt/personal-manager/data/agent.db "ANALYZE;"

# Check integrity
sqlite3 /opt/personal-manager/data/agent.db "PRAGMA integrity_check;"
```

## Troubleshooting Production Issues

### Service Won't Start

```bash
# Check service status
sudo systemctl status personal-manager

# View detailed logs
sudo journalctl -u personal-manager -n 100 --no-pager

# Check permissions
ls -la /opt/personal-manager/data/

# Test manually
cd /opt/personal-manager
source venv/bin/activate
python -m app.main  # Check for errors
```

### High Memory Usage

```bash
# Check memory usage
ps aux | grep uvicorn

# Restart service
sudo systemctl restart personal-manager

# Consider limiting memory in systemd
# Add to service file:
# MemoryMax=512M
```

### Database Locked

```bash
# Check for other connections
lsof /opt/personal-manager/data/agent.db

# Kill processes if safe
sudo systemctl stop personal-manager

# Enable WAL mode (if not already)
sqlite3 /opt/personal-manager/data/agent.db "PRAGMA journal_mode=WAL;"
```

### Calendar Sync Issues

```bash
# Refresh OAuth token
cd /opt/personal-manager
source venv/bin/activate
python scripts/refresh_google_token.py

# Test calendar access
python scripts/test_calendar.py

# View sync logs
tail -f data/logs/calendar_sync.log
```

## Migration from Development

### Export Development Data

```bash
# On development machine
sqlite3 data/agent.db .dump > agent_export.sql

# Transfer to production
scp agent_export.sql user@production-server:/tmp/
```

### Import to Production

```bash
# On production server
sudo systemctl stop personal-manager

# Backup existing
cp /opt/personal-manager/data/agent.db /opt/personal-manager/data/backups/agent_before_import.db

# Import
sqlite3 /opt/personal-manager/data/agent.db < /tmp/agent_export.sql

# Run migrations
cd /opt/personal-manager
source venv/bin/activate
alembic upgrade head

# Start service
sudo systemctl start personal-manager
```

## Uninstallation

```bash
# Stop and disable service
sudo systemctl stop personal-manager
sudo systemctl disable personal-manager

# Remove service file
sudo rm /etc/systemd/system/personal-manager.service
sudo systemctl daemon-reload

# Backup data (optional)
cp -r /opt/personal-manager/data ~/personal-manager-backup

# Remove application
sudo rm -rf /opt/personal-manager

# Remove config (optional)
rm -rf ~/.personal-manager

# Remove cron jobs
crontab -e  # Remove backup and monitor entries
```

---

Last updated: 2026-02-17
