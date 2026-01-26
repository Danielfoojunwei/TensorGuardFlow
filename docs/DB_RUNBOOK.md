# Database Operations Runbook

## Overview

TensorGuard uses SQLModel (SQLAlchemy) with Alembic for database migrations.
This runbook covers common database operations, troubleshooting, and disaster recovery.

## Environment Configuration

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | Database connection string | Production | `sqlite:///./tg_platform.db` |
| `TG_DB_POOL_SIZE` | Connection pool size | No | `10` |
| `TG_DB_MAX_OVERFLOW` | Max overflow connections | No | `20` |
| `TG_DB_POOL_TIMEOUT` | Pool checkout timeout (seconds) | No | `30` |
| `TG_DB_POOL_RECYCLE` | Connection recycle interval (seconds) | No | `3600` |
| `TG_AUTO_MIGRATE` | Auto-run migrations on startup | No | `false` |

### Connection String Examples

```bash
# PostgreSQL (recommended for production)
DATABASE_URL=postgresql://user:password@host:5432/tensorguard

# PostgreSQL with SSL
DATABASE_URL=postgresql://user:password@host:5432/tensorguard?sslmode=require

# MySQL
DATABASE_URL=mysql+pymysql://user:password@host:3306/tensorguard

# SQLite (development only)
DATABASE_URL=sqlite:///./tg_platform.db
```

## Migration Commands

### Check Migration Status

```bash
# Using Alembic directly
cd /path/to/tensorguard
alembic current

# Using doctor CLI
python -m tensorguard.platform.doctor --db

# Using db_migration module
python -c "from tensorguard.platform.db_migration import check_migrations; print(check_migrations())"
```

### Apply Migrations (Upgrade)

```bash
# Apply all pending migrations
alembic upgrade head

# Apply specific revision
alembic upgrade <revision_id>

# Apply next migration only
alembic upgrade +1

# Using auto-migrate on startup
TG_AUTO_MIGRATE=true python -m tensorguard.platform.main
```

### Rollback Migrations (Downgrade)

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Rollback all migrations (DANGER: destroys all data)
alembic downgrade base
```

### Create New Migration

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "description of changes"

# Create empty migration for manual edits
alembic revision -m "description of changes"
```

## Current Schema

### Migration History

| Revision | Description |
|----------|-------------|
| `001` | Initial schema (Tenant, User, Fleet, Job, AuditLog) |
| `002` | Telemetry and rollout tracking |
| `003` | FedMoE expert registry |
| `004` | Organization membership and RBAC |

### Core Tables

- `tenant` - Multi-tenant organizations
- `user` - User accounts with password hashes
- `fleet` - Device fleet configurations
- `job` - Background job tracking
- `auditlog` - Audit trail
- `organization_membership` - RBAC memberships

## Health Checks

### Via API

```bash
# Quick health check
curl http://localhost:8000/healthz

# Full readiness check (includes migration status)
curl http://localhost:8000/readyz

# Detailed health with pool status
curl http://localhost:8000/health
```

### Via Doctor CLI

```bash
python -m tensorguard.platform.doctor --db
```

### Expected Healthy Response

```json
{
  "status": "healthy",
  "pool_size": 10,
  "checked_in": 10,
  "checked_out": 0,
  "overflow": 0
}
```

## Backup and Restore

### PostgreSQL

```bash
# Backup
pg_dump -Fc tensorguard > tensorguard_backup_$(date +%Y%m%d_%H%M%S).dump

# Restore
pg_restore -d tensorguard tensorguard_backup.dump

# Backup specific tables
pg_dump -t tenant -t user -t fleet tensorguard > critical_tables.sql
```

### SQLite

```bash
# Backup (simple file copy)
cp tg_platform.db tg_platform_backup_$(date +%Y%m%d_%H%M%S).db

# Or use sqlite3 backup
sqlite3 tg_platform.db ".backup 'backup.db'"
```

### Application-Level Export

```bash
# Export via platform API (if available)
curl -X POST http://localhost:8000/api/v1/admin/export \
  -H "Authorization: Bearer $TOKEN" \
  -o platform_export.json
```

## Disaster Recovery

### Scenario: Database Corruption

1. Stop the application
2. Restore from latest backup
3. Apply any migrations since backup
4. Verify with health check
5. Restart application

```bash
# Stop
docker-compose down api-prod

# Restore (PostgreSQL example)
pg_restore -c -d tensorguard latest_backup.dump

# Check migrations
alembic current
alembic upgrade head

# Verify
python -m tensorguard.platform.doctor --db

# Restart
docker-compose up -d api-prod
```

### Scenario: Migration Failure

1. Check error logs for specific failure
2. If data migration failed, restore backup
3. Fix migration script
4. Re-apply migration

```bash
# Check what went wrong
alembic history --verbose

# Rollback to previous state
alembic downgrade -1

# Fix the migration file, then retry
alembic upgrade head
```

### Scenario: Schema Mismatch

If `/readyz` reports schema behind:

```bash
# Check current state
alembic current
alembic heads

# Apply pending migrations
alembic upgrade head

# Or enable auto-migrate
TG_AUTO_MIGRATE=true
```

## Connection Pool Troubleshooting

### Symptoms of Pool Exhaustion

- Requests timing out
- "QueuePool limit reached" errors
- Slow response times

### Diagnosis

```bash
# Check pool status
curl http://localhost:8000/health | jq '.checks.database'

# Monitor connections (PostgreSQL)
psql -c "SELECT count(*) FROM pg_stat_activity WHERE datname='tensorguard';"
```

### Resolution

1. Increase pool size: `TG_DB_POOL_SIZE=20`
2. Increase overflow: `TG_DB_MAX_OVERFLOW=40`
3. Reduce connection recycle time: `TG_DB_POOL_RECYCLE=1800`
4. Check for connection leaks in application code

## Production Checklist

- [ ] PostgreSQL configured (not SQLite)
- [ ] Connection pooling enabled
- [ ] Migrations are current (`alembic current` matches `alembic heads`)
- [ ] Backup strategy in place
- [ ] Health endpoints responding
- [ ] Pool monitoring configured
- [ ] `TG_AUTO_MIGRATE=false` (migrations should be explicit in production)

## Security Considerations

1. **Never store DATABASE_URL in code** - use environment variables
2. **Use SSL for production databases** - add `?sslmode=require`
3. **Restrict database user permissions** - principle of least privilege
4. **Rotate database credentials** regularly
5. **Encrypt backups** at rest and in transit

## Related Documentation

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [PostgreSQL Administration](https://www.postgresql.org/docs/current/admin.html)
