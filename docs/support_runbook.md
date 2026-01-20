# TensorGuardFlow Support Runbook

**Version:** 2.3.0
**Audience:** Support Engineers, DevOps, On-Call Staff

---

## Table of Contents

1. [Log Locations](#1-log-locations)
2. [Diagnostics Collection](#2-diagnostics-collection)
3. [Common Issues & Resolutions](#3-common-issues--resolutions)
4. [System Reset Procedures](#4-system-reset-procedures)
5. [Escalation Paths](#5-escalation-paths)

---

## 1. Log Locations

### Docker Deployment (Default)

| Component | Log Access | Description |
|-----------|------------|-------------|
| API Server | `docker compose logs api` | FastAPI backend logs |
| Worker | `docker compose logs worker` | Background job processor |
| Database | `docker compose logs db` | PostgreSQL logs (if using) |
| All Services | `docker compose logs -f` | Combined real-time logs |

### Log Filtering

```bash
# Last 100 lines from API
docker compose logs --tail=100 api

# Errors only
docker compose logs api 2>&1 | grep -i error

# Time-filtered (last hour)
docker compose logs --since=1h api

# Follow logs in real-time
docker compose logs -f --tail=50
```

### File-based Logs (if configured)

| Path | Content |
|------|---------|
| `./logs/api.log` | API server logs |
| `./logs/worker.log` | Worker process logs |
| `./artifacts/` | Test and QA artifacts |
| `/tmp/tensorguard/` | Temporary debug logs |

### Log Levels

Application logs use standard levels:
- `DEBUG` - Verbose debugging (development only)
- `INFO` - Normal operations
- `WARNING` - Non-critical issues
- `ERROR` - Errors requiring attention
- `CRITICAL` - System-critical failures

Set log level via environment:
```bash
TG_LOG_LEVEL=DEBUG docker compose up
```

---

## 2. Diagnostics Collection

### Automated Diagnostics Bundle

Run the diagnostics collection script to gather all relevant information:

```bash
./scripts/qa/collect_diagnostics.sh
```

This creates a timestamped bundle in `artifacts/diagnostics/` containing:
- System information (OS, Python, Docker versions)
- Configuration files (sanitized, no secrets)
- Docker container logs
- Application logs
- Database health check
- API health check results
- Recent error summary

### Manual Diagnostics

#### System Information
```bash
# OS and environment
uname -a
python3 --version
docker --version
docker compose version

# Disk space
df -h

# Memory
free -h
```

#### Container Status
```bash
# Running containers
docker ps -a --filter "name=tensor"

# Container resource usage
docker stats --no-stream

# Container details
docker inspect tensorguardflow-api-1
```

#### API Health
```bash
# Basic health (no auth)
curl -v http://localhost:8000/health

# Detailed health (requires auth)
curl http://localhost:8000/api/v1/status/health \
  -H "Authorization: Bearer YOUR_TOKEN"

# Metrics endpoint
curl http://localhost:8000/api/v1/status/metrics \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Database Health
```bash
# SQLite database size and status
ls -la tg_platform.db
sqlite3 tg_platform.db "PRAGMA integrity_check;"

# PostgreSQL (if using)
docker compose exec db psql -U tensorguard -c "SELECT version();"
docker compose exec db psql -U tensorguard -c "SELECT count(*) FROM fleets;"
```

### What to Include in Support Tickets

1. **Diagnostics bundle** (from collect_diagnostics.sh)
2. **Steps to reproduce** the issue
3. **Expected vs actual behavior**
4. **Timestamp** when issue occurred
5. **Environment details** (platform, Docker version)

---

## 3. Common Issues & Resolutions

### 3.1 API Not Starting

**Symptoms:**
- `curl localhost:8000/health` fails
- Container exits immediately

**Diagnosis:**
```bash
docker compose logs api --tail=50
docker compose ps
```

**Common Causes & Fixes:**

| Cause | Fix |
|-------|-----|
| Port 8000 in use | `lsof -i :8000` then stop conflicting service |
| Missing env vars | Check `.env` file exists and has required vars |
| Database connection | Verify `DATABASE_URL` or SQLite file permissions |
| Python import error | Check `docker compose build --no-cache` |

### 3.2 Authentication Failures

**Symptoms:**
- 401 Unauthorized responses
- "Invalid token" errors

**Diagnosis:**
```bash
# Check recent auth errors
docker compose logs api 2>&1 | grep -i "401\|auth\|token"
```

**Common Causes & Fixes:**

| Cause | Fix |
|-------|-----|
| Expired token | Re-authenticate via `/api/v1/auth/token` |
| Wrong auth header | Use `Bearer TOKEN` for users, `Fleet API_KEY` for devices |
| Rotated API key | Obtain new key from fleet management |
| Clock skew | Sync system time (`timedatectl set-ntp true`) |

### 3.3 Telemetry Ingestion Failures

**Symptoms:**
- Devices report 401/403 errors
- Events not appearing in dashboard

**Diagnosis:**
```bash
# Test ingestion manually
curl -X POST "http://localhost:8000/api/v1/telemetry/ingest" \
  -H "Authorization: Fleet YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"batch_id":"test","device_info":{"device_id":"test"},"messages":[]}'
```

**Common Causes & Fixes:**

| Cause | Fix |
|-------|-----|
| Invalid API key | Verify key with fleet list endpoint |
| Fleet deactivated | Re-activate or create new fleet |
| Malformed payload | Validate JSON against schema |
| Rate limiting | Reduce request frequency |

### 3.4 Database Issues

**Symptoms:**
- "Database locked" errors
- Slow queries
- Data not persisting

**Diagnosis:**
```bash
# SQLite
sqlite3 tg_platform.db "PRAGMA integrity_check;"
ls -la tg_platform.db*

# PostgreSQL
docker compose exec db psql -U tensorguard -c "\dt"
```

**Common Causes & Fixes:**

| Cause | Fix |
|-------|-----|
| SQLite locked | Stop concurrent writers, check file permissions |
| Disk full | Free space, check `df -h` |
| Corrupted DB | Restore from backup (see Section 4) |
| Missing migrations | Run `alembic upgrade head` |

### 3.5 Worker Not Processing

**Symptoms:**
- Jobs queued but not completing
- Worker container restarting

**Diagnosis:**
```bash
docker compose logs worker --tail=100
docker compose ps worker
```

**Common Causes & Fixes:**

| Cause | Fix |
|-------|-----|
| Worker crashed | `docker compose restart worker` |
| Queue full | Check Redis/memory limits |
| Deadlock | Restart worker with `docker compose restart worker` |

### 3.6 High Memory/CPU Usage

**Symptoms:**
- System slowdown
- OOM kills

**Diagnosis:**
```bash
docker stats --no-stream
docker compose top
```

**Fixes:**
```bash
# Limit container resources in docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
```

---

## 4. System Reset Procedures

### 4.1 Soft Reset (Restart Services)

Preserves all data, just restarts services:

```bash
docker compose restart
```

Or restart specific service:
```bash
docker compose restart api
docker compose restart worker
```

### 4.2 Clean Restart (Recreate Containers)

Recreates containers but preserves volumes/data:

```bash
docker compose down
docker compose up -d
```

### 4.3 Database Reset (Data Loss!)

**WARNING: This destroys all data!**

```bash
# Stop services
docker compose down

# Backup first (important!)
cp tg_platform.db tg_platform.db.backup.$(date +%Y%m%d)

# Remove database
rm tg_platform.db

# Restart (creates fresh database)
docker compose up -d
```

### 4.4 Full Reset (Complete Reinstall)

**WARNING: Removes all data and images!**

```bash
# Stop and remove everything
docker compose down -v --rmi all

# Remove local database
rm -f tg_platform.db

# Remove artifacts
rm -rf artifacts/

# Fresh install
docker compose up -d --build
```

### 4.5 Restore from Backup

#### SQLite Restore
```bash
docker compose down
cp backup/tg_platform.db.20240115 tg_platform.db
docker compose up -d
```

#### PostgreSQL Restore
```bash
docker compose down
docker compose up -d db  # Start only DB
docker compose exec -T db psql -U tensorguard tensorguard < backup.sql
docker compose up -d     # Start all services
```

### 4.6 Emergency Recovery

If system is unresponsive:

```bash
# Force stop all containers
docker compose kill

# Remove potentially corrupted state
docker compose rm -f

# Clean Docker system
docker system prune -f

# Fresh start
docker compose up -d --build
```

---

## 5. Escalation Paths

### Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| P1 - Critical | System down, data loss risk | Immediate | API unreachable, database corruption |
| P2 - High | Major feature broken | 4 hours | Auth failing, ingest broken |
| P3 - Medium | Feature degraded | 24 hours | Slow performance, UI bugs |
| P4 - Low | Minor issues | 72 hours | Cosmetic issues, docs |

### Escalation Checklist

Before escalating:
1. [ ] Collect diagnostics bundle
2. [ ] Document steps to reproduce
3. [ ] Check this runbook for known issues
4. [ ] Attempt basic troubleshooting
5. [ ] Note timestamp and affected users

### Support Contacts

| Issue Type | Contact |
|------------|---------|
| Technical Support | support@tensorguard.example |
| Security Issues | security@tensorguard.example |
| Sales/Licensing | sales@tensorguard.example |

### Information to Provide

```
Subject: [P1/P2/P3/P4] Brief description

Environment:
- TensorGuardFlow Version: X.X.X
- Platform: Windows/macOS/Linux
- Docker Version: X.X.X

Issue:
[Detailed description]

Steps to Reproduce:
1. ...
2. ...

Expected Behavior:
[What should happen]

Actual Behavior:
[What actually happens]

Attachments:
- diagnostics_bundle.zip
- screenshots (if applicable)
```

---

## Quick Reference

### Essential Commands

```bash
# Start
docker compose up -d

# Stop
docker compose down

# Logs
docker compose logs -f

# Status
docker compose ps

# Restart
docker compose restart

# Health check
curl localhost:8000/health

# Collect diagnostics
./scripts/qa/collect_diagnostics.sh
```

### Key Paths

| Path | Purpose |
|------|---------|
| `./tg_platform.db` | SQLite database |
| `./logs/` | Application logs |
| `./artifacts/` | QA and diagnostic outputs |
| `./.env` | Environment configuration |
| `./docker-compose.yml` | Service definitions |

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `TG_SECRET_KEY` | JWT signing key | (required in production) |
| `TG_ENVIRONMENT` | Environment mode | development |
| `TG_LOG_LEVEL` | Logging verbosity | INFO |
| `DATABASE_URL` | Database connection | SQLite |

---

*Last Updated: 2024-01*
