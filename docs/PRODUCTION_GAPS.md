# TensorGuard Production Gaps Analysis

> **Document Version**: 1.0
> **Generated**: 2024-01
> **Status**: Active remediation in progress

This document provides a comprehensive "truth map" of the TensorGuard system, identifying production gaps and tracking remediation status.

---

## 1. Services Architecture

### 1.1 Service Inventory

| Service | Location | Port | Description | Status |
|---------|----------|------|-------------|--------|
| **Platform API** | `src/tensorguard/platform/main.py` | 8000 | Central management platform (FastAPI) | Production |
| **Edge Agent** | `src/tensorguard/agent/daemon.py` | 8080 | On-device daemon for telemetry/inference | Production |
| **Identity Agent** | `src/tensorguard/identity/agent/` | N/A | Certificate lifecycle management | Production |
| **Enablement Sidecar** | `api/enablement_service.py` | 8001 | Job submission service (legacy location) | **NEEDS MIGRATION** |

### 1.2 Entry Points

```yaml
# CLI Entry Points (pyproject.toml)
tensorguard: src/tensorguard/cli.py:main
tg-agent: src/tensorguard/agent/daemon.py:main

# FastAPI Applications
platform: src/tensorguard/platform/main.py:app
enablement: api/enablement_service.py:app  # LEGACY - needs migration
```

### 1.3 Legacy Code Locations (TO BE REMOVED)

| Path | Issue | Remediation |
|------|-------|-------------|
| `backend/auth.py` | **HARDCODED SECRET KEY**, duplicate of platform auth | DELETE |
| `backend/notifications.py` | Simulation code, duplicate functionality | DELETE |
| `api/enablement_service.py` | Outside src/ boundary | MIGRATE to services/ or platform |

---

## 2. Environment Variable Contract

### 2.1 Required Variables (Production)

| Variable | Purpose | Default | Notes |
|----------|---------|---------|-------|
| `TG_SECRET_KEY` | JWT signing key | *generated* | **REQUIRED** in production, min 32 chars |
| `DATABASE_URL` | Database connection | sqlite (dev only) | **REQUIRED** PostgreSQL in production |
| `TG_ENVIRONMENT` | Runtime mode | `development` | Set to `production` for enforcement |

### 2.2 Security Variables

| Variable | Purpose | Default | Notes |
|----------|---------|---------|-------|
| `TG_SECRET_KEY` | Primary JWT signing | - | **REQUIRED** |
| `TG_SECRET_KEY_CURRENT` | Current rotation key | - | For key rotation |
| `TG_SECRET_KEY_PREVIOUS` | Previous rotation key | - | Grace period for old tokens |
| `TG_VAULT_MASTER_KEY` | Vault encryption key | - | For encrypted key storage |
| `TG_DEMO_MODE` | Enable demo fixtures | `false` | **NEVER** true in production |
| `TG_PQC_STRICT` | Require real PQC libs | `true` | Auto-enforced in production |

### 2.3 Database Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | Connection string | `sqlite:///./tg_platform.db` |
| `TG_DB_POOL_SIZE` | Connection pool size | `10` |
| `TG_DB_MAX_OVERFLOW` | Pool overflow | `20` |
| `TG_DB_POOL_TIMEOUT` | Connection timeout (s) | `30` |
| `TG_DB_POOL_RECYCLE` | Connection recycle (s) | `3600` |

### 2.4 Authentication Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `TG_TOKEN_EXPIRE_MINUTES` | Access token TTL | `30` |
| `TG_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL | `7` |
| `TG_MIN_PASSWORD_LENGTH` | Password requirement | `12` |
| `TG_REQUIRE_PASSWORD_COMPLEXITY` | Enforce complexity | `true` |
| `TG_JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `TG_TOKEN_ISSUER` | JWT issuer claim | `tensorguard-platform` |
| `TG_TOKEN_AUDIENCE` | JWT audience claim | `tensorguard-api` |

### 2.5 Networking Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `TG_ALLOWED_ORIGINS` | CORS origins (comma-sep) | localhost:3000,5173 (dev) |
| `TG_ALLOW_CREDENTIALS` | CORS credentials | `false` |
| `TG_ENABLE_SECURITY_HEADERS` | Add OWASP headers | `true` |
| `TG_CONTROL_PLANE_URL` | Platform URL | `http://localhost:8000` |

### 2.6 Observability Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `TG_LOG_LEVEL` | Logging level | `INFO` |
| `TG_ENABLE_OTEL` | OpenTelemetry tracing | `false` |
| `TG_OTEL_ENDPOINT` | OTLP collector | `http://localhost:4317` |
| `TG_ENABLE_PROMETHEUS` | Prometheus metrics | `false` |

---

## 3. Runtime Dependencies

### 3.1 Required Infrastructure

| Dependency | Dev Default | Production Requirement |
|------------|-------------|----------------------|
| **Database** | SQLite (file) | PostgreSQL 13+ |
| **Filesystem** | Local `./keys/` | Encrypted volume or HSM |
| **Network** | localhost | TLS termination required |

### 3.2 Optional Infrastructure

| Dependency | Purpose | Environment Variable |
|------------|---------|---------------------|
| Redis | Rate limiting, caching | `REDIS_URL` |
| OTLP Collector | Distributed tracing | `TG_OTEL_ENDPOINT` |
| HSM | Hardware key storage | `TG_HSM_*` |
| ACME Server | Certificate automation | `TG_ACME_*` |

### 3.3 Database Schema

Managed via Alembic migrations in `alembic/versions/`:

```
001_initial_schema.py           - Core tables (users, fleets, tenants)
002_telemetry_and_rollout.py    - Telemetry + deployment tables
003_fedmoe_experts.py           - FedMoE expert system
004_organization_membership.py   - Multi-tenant RBAC
```

---

## 4. Production Gaps Summary

### 4.1 Critical (P0) - Security

| Gap | Location | Risk | Remediation |
|-----|----------|------|-------------|
| Hardcoded secret | `backend/auth.py:9` | **CRITICAL** | Delete file |
| Keys stored unencrypted | `src/tensorguard/core/keys.py` | HIGH | Implement vault encryption |
| Bare except in job handler | `api/enablement_service.py:76` | MEDIUM | Add specific exceptions |

### 4.2 High (P1) - Structure

| Gap | Location | Risk | Remediation |
|-----|----------|------|-------------|
| Code outside src/ | `backend/`, `api/` | HIGH | Delete or migrate |
| Duplicate auth module | `backend/auth.py` | MEDIUM | Delete (use platform/auth.py) |
| Simulation code in prod paths | `backend/notifications.py` | MEDIUM | Delete |

### 4.3 Medium (P2) - Operations

| Gap | Location | Risk | Remediation |
|-----|----------|------|-------------|
| No migration enforcement | startup | MEDIUM | Add Alembic check on boot |
| Version scattered | multiple files | LOW | Centralize in pyproject.toml |
| requirements.txt broken | root | LOW | Fix encoding, mark legacy |

### 4.4 Low (P3) - Quality

| Gap | Location | Risk | Remediation |
|-----|----------|------|-------------|
| Missing test categories | pytest.ini | LOW | Add markers |
| No coverage threshold | CI | LOW | Add 70% minimum |

---

## 5. Deployment Topology

### 5.1 Recommended Production Setup

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer (TLS)                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Platform    │  │  Platform    │  │  Platform    │
│  (Replica 1) │  │  (Replica 2) │  │  (Replica N) │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
       ┌──────────┐          ┌──────────┐
       │PostgreSQL│          │  Redis   │
       │ (Primary)│          │ (Cache)  │
       └──────────┘          └──────────┘
```

### 5.2 Edge Deployment

```
┌─────────────────────────────────────────┐
│             Edge Device                  │
│  ┌─────────────────────────────────┐    │
│  │         TG Edge Agent            │    │
│  │  - Telemetry collection          │    │
│  │  - Model inference               │    │
│  │  - Certificate management        │    │
│  └─────────────────────────────────┘    │
│                    │                     │
│                    ▼                     │
│  ┌─────────────────────────────────┐    │
│  │    Local Key Vault (encrypted)   │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
              │
              │ HTTPS/mTLS
              ▼
       ┌──────────────┐
       │   Platform   │
       └──────────────┘
```

---

## 6. Health Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `GET /health` | Full health check | `{"status": "healthy", "checks": {...}}` |
| `GET /ready` | Kubernetes readiness | `{"ready": true}` or 503 |
| `GET /live` | Kubernetes liveness | `{"alive": true}` |
| `GET /metrics` | Prometheus metrics | Prometheus text format |

---

## 7. Remediation Tracking

### Phase 0: Truth Map (This Document)
- [x] Document services and entrypoints
- [x] Document env var contract
- [x] Identify production gaps
- [ ] Create repo_audit.py scanner

### Phase 1: Repo Structure
- [ ] Delete `backend/` directory
- [ ] Migrate or delete `api/` directory
- [ ] Verify all code under `src/` or `services/`

### Phase 2: Dependencies
- [ ] Fix requirements.txt encoding
- [ ] Verify `pip install -e ".[all]"` works
- [ ] Add dependency lock file

### Phase 3: Security
- [ ] Implement encrypted key vault
- [ ] Add JWT key rotation
- [ ] Remove all bare except blocks
- [ ] Add secret scanning to CI

### Phase 4: Database
- [ ] Add migration enforcement on startup
- [ ] Create db doctor command
- [ ] Add migration test

### Phase 5: Demo Mode
- [ ] Gate all simulation code
- [ ] Add TG_DEMO_MODE visibility

### Phase 6: Observability
- [ ] Add OpenTelemetry tracing
- [ ] Implement structured logging
- [ ] Add production metrics

### Phase 7: Testing
- [ ] Add test categories
- [ ] Add coverage threshold
- [ ] Add lint/type enforcement

### Phase 8: Release
- [ ] Single version source
- [ ] Reproducible Docker builds
- [ ] SBOM generation

---

## Appendix A: Quick Reference

### Start Development Server
```bash
# Install dependencies
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start server
uvicorn tensorguard.platform.main:app --reload
```

### Environment Setup
```bash
# Copy and edit environment
cp .env.example .env

# Generate secret key
export TG_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

### Run Audit
```bash
python scripts/repo_audit.py
```
