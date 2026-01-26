# TensorGuard Production Runbook

## Overview

This runbook provides operational guidance for running TensorGuard in production.
It covers configuration, deployment, monitoring, troubleshooting, and incident response.

## Table of Contents

1. [Required Environment Variables](#required-environment-variables)
2. [Deployment Topology](#deployment-topology)
3. [Health Checks](#health-checks)
4. [Backup Strategy](#backup-strategy)
5. [Incident Response](#incident-response)
6. [Performance Baseline](#performance-baseline)
7. [Maintenance Operations](#maintenance-operations)

---

## Required Environment Variables

### Critical (Must Be Set)

| Variable | Description | Example |
|----------|-------------|---------|
| `TG_SECRET_KEY` | JWT signing key (32+ chars) | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/tensorguard` |
| `TG_ENVIRONMENT` | Environment identifier | `production` |

### Security (Recommended)

| Variable | Description | Default |
|----------|-------------|---------|
| `TG_VAULT_MASTER_KEY` | Vault encryption key (32+ chars) | Required in production |
| `TG_ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | Empty (deny all) |
| `TG_ENABLE_SECURITY_HEADERS` | Enable OWASP headers | `true` |
| `TG_ENABLE_RATE_LIMIT` | Enable rate limiting | `true` |

### Database

| Variable | Description | Default |
|----------|-------------|---------|
| `TG_DB_POOL_SIZE` | Connection pool size | `10` |
| `TG_DB_MAX_OVERFLOW` | Max overflow connections | `20` |
| `TG_DB_POOL_TIMEOUT` | Pool checkout timeout (sec) | `30` |
| `TG_DB_POOL_RECYCLE` | Connection recycle interval (sec) | `3600` |
| `TG_AUTO_MIGRATE` | Auto-run migrations on startup | `false` |

### Rate Limiting

| Variable | Description | Default |
|----------|-------------|---------|
| `TG_RATE_LIMIT_GENERAL` | Requests/sec for general endpoints | `100` |
| `TG_RATE_LIMIT_AUTH` | Requests/sec for auth endpoints | `10` |
| `TG_RATE_LIMIT_BURST` | Burst capacity multiplier | `3` |

### Observability

| Variable | Description | Default |
|----------|-------------|---------|
| `TG_ENABLE_OTEL` | Enable OpenTelemetry tracing | `false` |
| `TG_OTEL_ENDPOINT` | OTLP collector endpoint | `http://localhost:4317` |
| `TG_OTEL_EXPORTER` | Exporter type (otlp/console) | `console` |
| `TG_ENABLE_PROMETHEUS` | Enable Prometheus metrics | `false` |
| `TG_PROMETHEUS_PORT` | Prometheus metrics port | `9090` |
| `TG_ENABLE_METRICS` | Enable metrics middleware | `true` |

### Demo Mode (Development Only)

| Variable | Description | Default |
|----------|-------------|---------|
| `TG_DEMO_MODE` | Enable demo/test data | `false` |

**WARNING:** Never set `TG_DEMO_MODE=true` in production!

---

## Deployment Topology

### Single Container (Simple)

```yaml
# docker-compose.yml
services:
  api:
    image: tensorguard/platform:latest
    environment:
      - TG_ENVIRONMENT=production
      - TG_SECRET_KEY=${TG_SECRET_KEY}
      - DATABASE_URL=postgresql://...
      - TG_VAULT_MASTER_KEY=${TG_VAULT_MASTER_KEY}
    ports:
      - "8000:8000"
    volumes:
      - ./keys:/app/keys
      - ./frontend/dist:/app/frontend/dist:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Split Services (Recommended for Scale)

```yaml
services:
  api:
    image: tensorguard/platform:latest
    environment:
      - TG_ENVIRONMENT=production
      # ... same as above
    deploy:
      replicas: 3

  worker:
    image: tensorguard/platform:latest
    command: python -m tensorguard.platform.worker
    environment:
      - TG_ENVIRONMENT=production
      # ... same as api

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=tensorguard
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tensorguard-api
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        image: tensorguard/platform:latest
        ports:
        - containerPort: 8000
        readinessProbe:
          httpGet:
            path: /readyz
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 20
```

---

## Health Checks

### Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `GET /healthz` | Liveness probe (process alive) | `200 OK` |
| `GET /readyz` | Readiness probe (all deps healthy) | `200 OK` or `503` |
| `GET /health` | Detailed health with DB pool status | JSON with checks |
| `GET /metrics` | Prometheus metrics | Text/plain |

### Readiness Check Details

`/readyz` verifies:
1. Database connectivity
2. Database schema is current (migrations applied)
3. Vault directory is writable

If any check fails, returns `503 Service Unavailable` with actionable error.

### Doctor CLI

```bash
# Run all checks
python -m tensorguard.platform.doctor --all

# Check specific component
python -m tensorguard.platform.doctor --db
python -m tensorguard.platform.doctor --vault
python -m tensorguard.platform.doctor --config
```

---

## Backup Strategy

### Database Backup

```bash
# PostgreSQL backup
pg_dump -Fc tensorguard > backup_$(date +%Y%m%d_%H%M%S).dump

# Restore
pg_restore -c -d tensorguard backup.dump
```

**Schedule:** Daily full backup, hourly WAL archiving

### Vault Backup

```bash
# Export metadata only (safe)
python -m tensorguard.core.keys export --out vault_metadata.json

# Full export with key material (sensitive!)
python -m tensorguard.core.keys export --out vault_full.json --include-material
chmod 600 vault_full.json  # Protect the file!
```

**Schedule:** After any key rotation or before upgrades

### Backup Retention

- Daily backups: 7 days
- Weekly backups: 4 weeks
- Monthly backups: 12 months

---

## Incident Response

### Authentication Outage

**Symptoms:** Users cannot log in, 401 errors

**Diagnosis:**
```bash
# Check logs for JWT errors
grep -i "jwt\|token\|auth" /var/log/tensorguard/*.log

# Verify secret key
python -m tensorguard.platform.doctor --security
```

**Resolution:**
1. Verify `TG_SECRET_KEY` is set and hasn't changed
2. Check database connectivity for user records
3. Verify JWT expiration settings
4. If key was rotated, users may need to re-authenticate

### Database Down

**Symptoms:** `/readyz` returns 503, "database unavailable"

**Diagnosis:**
```bash
# Check database connectivity
python -m tensorguard.platform.doctor --db

# Check PostgreSQL status
pg_isready -h hostname -p 5432
```

**Resolution:**
1. Check PostgreSQL service status
2. Verify connection string in `DATABASE_URL`
3. Check network connectivity
4. Check connection pool exhaustion (`/health` shows pool status)

### Vault Corruption

**Symptoms:** Key operations fail, encryption errors

**Diagnosis:**
```bash
# Check vault status
python -m tensorguard.core.keys status

# List keys to identify issues
python -m tensorguard.core.keys list
```

**Resolution:**
1. Restore from vault backup
2. Re-import keys: `python -m tensorguard.core.keys import --in backup.json --import-material`
3. Verify `TG_VAULT_MASTER_KEY` hasn't changed

### Rate Limiting Triggered

**Symptoms:** Users getting 429 errors

**Diagnosis:**
```bash
# Check metrics
curl http://localhost:8000/metrics | grep rate
```

**Resolution:**
1. Identify abusive client (check logs for client IP)
2. Temporarily increase limits: `TG_RATE_LIMIT_GENERAL=200`
3. Consider allowlisting trusted IPs

---

## Performance Baseline

### Expected Response Times

| Endpoint | p50 | p95 | p99 |
|----------|-----|-----|-----|
| Health checks | <10ms | <50ms | <100ms |
| API reads | <50ms | <200ms | <500ms |
| API writes | <100ms | <500ms | <1s |
| Auth/login | <200ms | <500ms | <1s |

### Resource Usage

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| CPU | <50% | 70% | 90% |
| Memory | <70% | 85% | 95% |
| DB Connections | <80% pool | 90% pool | Pool exhausted |

### Scaling Triggers

- If p95 latency > 500ms consistently, add replicas
- If DB pool > 80% utilized, increase `TG_DB_POOL_SIZE`
- If rate limits frequently hit, review and adjust limits

---

## Maintenance Operations

### Applying Updates

```bash
# 1. Backup database
pg_dump -Fc tensorguard > pre_upgrade_backup.dump

# 2. Export vault
python -m tensorguard.core.keys export --out vault_backup.json

# 3. Pull new image
docker pull tensorguard/platform:latest

# 4. Run migrations (if needed)
docker run --rm -e DATABASE_URL=$DATABASE_URL tensorguard/platform:latest \
  alembic upgrade head

# 5. Deploy new version
docker-compose up -d

# 6. Verify health
curl http://localhost:8000/readyz
```

### Key Rotation

```bash
# 1. Generate new key
NEW_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# 2. Set as pending (if using dual-key rotation)
export TG_SECRET_KEY_PENDING=$NEW_KEY

# 3. After all tokens expire, promote
export TG_SECRET_KEY=$NEW_KEY
unset TG_SECRET_KEY_PENDING

# 4. Restart services
docker-compose restart api
```

### Database Migration

```bash
# Check current status
python -m tensorguard.platform.doctor --db

# Apply migrations
alembic upgrade head

# Verify
python -m tensorguard.platform.doctor --db
```

---

## Monitoring Checklist

- [ ] `/healthz` returning 200
- [ ] `/readyz` returning 200
- [ ] Database connections healthy
- [ ] No 5xx errors in logs
- [ ] Response latencies within baseline
- [ ] No rate limit violations from legitimate users
- [ ] Vault accessible and encryption working
- [ ] Demo mode is OFF (`TG_DEMO_MODE=false`)

---

## Related Documentation

- [Database Runbook](DB_RUNBOOK.md)
- [Security Documentation](SECURITY.md)
- [GA Go/No-Go Checklist](GA_GONOGO_CHECKLIST.md)
