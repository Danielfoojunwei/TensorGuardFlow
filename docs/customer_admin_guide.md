# TensorGuardFlow Administrator Guide

**Version:** 2.3.0
**Audience:** System Administrators

---

## Table of Contents

1. [Onboarding](#1-onboarding)
2. [Fleet Management](#2-fleet-management)
3. [Telemetry Ingestion](#3-telemetry-ingestion)
4. [Key Rotation](#4-key-rotation)
5. [Backup and Restore](#5-backup-and-restore)
6. [Monitoring](#6-monitoring)
7. [Security Best Practices](#7-security-best-practices)

---

## 1. Onboarding

### Creating an Organization

**Via UI:**
1. Navigate to `http://localhost:8000`
2. Click "Get Started"
3. Fill in organization details
4. Save your admin credentials securely

**Via API:**
```bash
curl -X POST "http://localhost:8000/api/v1/onboarding/init" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Organization",
    "admin_email": "admin@example.com",
    "admin_pass": "SecurePassword123!"
  }'
```

### Logging In

**Via UI:**
Navigate to `/login` and enter credentials.

**Via API:**
```bash
# Get access token
curl -X POST "http://localhost:8000/api/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin@example.com", "password": "SecurePassword123!"}'

# Response includes access_token for subsequent requests
```

---

## 2. Fleet Management

### What is a Fleet?

A Fleet represents a group of devices that share the same API key for telemetry ingestion. Typical fleet organization:
- By environment (production, staging, dev)
- By geography (us-east, eu-west)
- By use case (robots, sensors, edge devices)

### Creating a Fleet

**Via UI:**
1. Navigate to "Fleets" in the sidebar
2. Click "Create Fleet"
3. Enter a descriptive name
4. Copy the API key (shown only once!)

**Via API:**
```bash
curl -X POST "http://localhost:8000/api/v1/fleets?name=production-fleet" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Response:
# {
#   "id": "fleet-uuid",
#   "name": "production-fleet",
#   "api_key": "tgf_abc123...",  # SAVE THIS!
#   "is_active": true
# }
```

### Listing Fleets

**Via API:**
```bash
# Basic list
curl "http://localhost:8000/api/v1/fleets" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Extended info (includes device counts, trust scores)
curl "http://localhost:8000/api/v1/fleets/extended" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Deactivating a Fleet

Deactivating a fleet immediately revokes its API key.

```bash
curl -X DELETE "http://localhost:8000/api/v1/fleets/FLEET_ID" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## 3. Telemetry Ingestion

### Configuring Devices

Devices use the Fleet API key to send telemetry:

```bash
# Device configuration
FLEET_API_KEY="tgf_your_fleet_api_key"
TENSORGUARD_URL="http://localhost:8000"
```

### Sending Telemetry

```bash
curl -X POST "http://localhost:8000/api/v1/telemetry/ingest" \
  -H "Authorization: Fleet $FLEET_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "batch_id": "unique-batch-id-123",
    "device_info": {
      "device_id": "device-001",
      "agent_version": "1.0.0"
    },
    "messages": [
      {
        "topic": "telemetry.stage",
        "timestamp_ns": 1705000000000000000,
        "payload": {
          "device_id": "device-001",
          "stage": "capture",
          "status": "ok",
          "latency_ms": 25.5
        },
        "priority": 0
      }
    ]
  }'
```

### Supported Topics

| Topic | Description | Required Payload Fields |
|-------|-------------|------------------------|
| `telemetry.stage` | Pipeline stage events | device_id, stage, status |
| `telemetry.system` | System metrics | device_id, cpu_pct, mem_pct |
| `telemetry.error` | Error events | device_id, error_type, message |

### Idempotency

Each batch has a unique `batch_id`. Resubmitting the same batch_id is safe - duplicates are detected and ignored.

---

## 4. Key Rotation

### Why Rotate Keys?

- Compromised key suspected
- Employee offboarding
- Compliance requirements
- Regular security hygiene (recommended: every 90 days)

### Rotating a Fleet Key

**Via UI:**
1. Navigate to Fleets
2. Select the fleet
3. Click "Rotate Key"
4. Confirm the action
5. Copy the new key immediately

**Via API:**
```bash
curl -X POST "http://localhost:8000/api/v1/fleets/FLEET_ID/rotate-key" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Response includes new api_key
```

### Key Rotation Behavior

- Old key is immediately invalidated
- New key is returned in the response
- New key is only shown once
- Devices using old key will receive 401 errors
- Update device configurations promptly

### Rollout Strategy

For zero-downtime rotation:
1. Create a second fleet for migration
2. Update devices gradually to new fleet
3. Monitor for errors on old fleet
4. Deactivate old fleet when empty

---

## 5. Backup and Restore

### SQLite Backup

```bash
# Create backup
cp tg_platform.db tg_platform.db.$(date +%Y%m%d)

# Restore backup
docker compose down
cp tg_platform.db.20240120 tg_platform.db
docker compose up -d
```

### PostgreSQL Backup

```bash
# Create backup
docker compose exec db pg_dump -U tensorguard tensorguard > backup_$(date +%Y%m%d).sql

# Restore backup
docker compose exec -T db psql -U tensorguard tensorguard < backup_20240120.sql
```

### Automated Backups

Add to crontab for daily backups:
```bash
0 2 * * * cd /path/to/tensorguardflow && ./scripts/backup.sh
```

---

## 6. Monitoring

### Health Endpoints

```bash
# Basic health (no auth required)
curl http://localhost:8000/health

# Detailed status (auth required)
curl http://localhost:8000/api/v1/status/health \
  -H "Authorization: Bearer YOUR_TOKEN"

# Metrics
curl http://localhost:8000/api/v1/status/metrics \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Dashboard Metrics

Access the dashboard at `http://localhost:8000` to view:
- System health percentage
- Active fleet count
- Key rotations in last 24h
- Compliance level
- Pipeline visualization

### Logs

```bash
# View all logs
docker compose logs -f

# API logs only
docker compose logs -f api

# Worker logs only
docker compose logs -f worker

# Last 100 lines
docker compose logs --tail=100 api
```

### Alerts to Watch For

| Log Pattern | Meaning | Action |
|-------------|---------|--------|
| `ERROR` | Application error | Investigate |
| `CRITICAL` | Serious failure | Immediate action |
| `401 Unauthorized` | Auth failure | Check API keys |
| `429 Rate Limited` | Too many requests | Scale or throttle |

---

## 7. Security Best Practices

### Environment Security

1. **Set TG_SECRET_KEY**
   ```bash
   # Generate secure key
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Use HTTPS in production**
   - Configure reverse proxy (nginx, traefik)
   - Obtain TLS certificate

3. **Firewall configuration**
   - Only expose port 8000 (or 443 with proxy)
   - Restrict to known IP ranges if possible

### Operational Security

1. **Rotate keys regularly**
   - Recommendation: every 90 days
   - Immediately on compromise suspicion

2. **Monitor for anomalies**
   - Unusual login patterns
   - Spike in 401/403 errors
   - Unknown device IDs

3. **Keep software updated**
   - Check for TensorGuardFlow updates
   - Update Docker regularly
   - Apply OS security patches

### Data Security

1. **Backup encryption**
   ```bash
   # Encrypt backup
   gpg -c backup.sql
   ```

2. **Audit logging**
   - All administrative actions are logged
   - Review audit logs periodically

3. **Access control**
   - Use unique credentials per admin
   - Disable unused accounts
   - Implement MFA (if available)

---

## Quick Reference

### Common Commands

| Task | Command |
|------|---------|
| Start services | `docker compose up -d` |
| Stop services | `docker compose down` |
| View logs | `docker compose logs -f` |
| Check health | `curl localhost:8000/health` |
| Create backup | `cp tg_platform.db backup.db` |
| Collect diagnostics | `./scripts/qa/collect_diagnostics.sh` |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (public) |
| `/api/v1/auth/token` | POST | Login |
| `/api/v1/fleets` | GET/POST | List/create fleets |
| `/api/v1/fleets/{id}/rotate-key` | POST | Rotate key |
| `/api/v1/telemetry/ingest` | POST | Ingest data |
| `/api/v1/dashboard/stats` | GET | Dashboard data |

---

## Support

For issues:
1. Run diagnostics: `./scripts/qa/collect_diagnostics.sh`
2. Check this guide's troubleshooting section
3. Contact support with diagnostics bundle
