# TensorGuardFlow Subsystem Map for Benchmarking

**Purpose:** This document maps all critical subsystems and code paths for performance benchmarking.

---

## 1. Control Plane (FastAPI Backend)

**Entry Point:** `src/tensorguard/platform/main.py`

### Key API Endpoints for Load Testing

| Endpoint | Method | Purpose | Auth | Target SLA |
|----------|--------|---------|------|------------|
| `/api/v1/auth/token` | POST | Authentication | Public | < 50ms |
| `/api/v1/fleets` | GET | List fleets | User JWT | < 100ms |
| `/api/v1/telemetry/ingest` | POST | Batch ingestion | Fleet HMAC | < 500ms/1000 msgs |
| `/api/v1/telemetry/pipeline` | GET | Aggregated metrics | User JWT | < 1s |
| `/api/v1/dashboard/stats` | GET | Real-time stats | User JWT | < 500ms |
| `/api/v1/identity/renewals/run` | POST | Start renewal job | User JWT | < 100ms |
| `/api/v1/status/health` | GET | Health check | Public | < 100ms |

### Critical Code Paths

| File | Function | Measurement |
|------|----------|-------------|
| `platform/auth.py` | `get_current_user()` | Auth overhead per request |
| `platform/database.py` | `SessionLocal()` | Connection acquisition |
| `api/telemetry_endpoints.py` | `ingest_telemetry()` | Batch processing latency |
| `api/endpoints.py` | `login_for_access_token()` | Token generation |

---

## 2. Database Layer

**Configuration:** `src/tensorguard/platform/database.py`

### Connection Pool Settings

| Parameter | Default | Env Var |
|-----------|---------|---------|
| Pool Size | 10 | `TG_DB_POOL_SIZE` |
| Max Overflow | 20 | `TG_DB_MAX_OVERFLOW` |
| Pool Timeout | 30s | `TG_DB_POOL_TIMEOUT` |
| Pool Recycle | 3600s | `TG_DB_POOL_RECYCLE` |

### Core Tables for Query Performance

| Table | Model | Heavy Queries |
|-------|-------|---------------|
| `fleet` | Fleet | List with filters |
| `telemetrystageevent` | TelemetryStageEvent | Time-range aggregations |
| `telemetrysystemevent` | TelemetrySystemEvent | Device metrics |
| `identityrenewalfjob` | IdentityRenewalJob | Status filtering |
| `fleetdevice` | FleetDevice | Upsert on ingest |

---

## 3. Telemetry Ingest Pipeline

**Path:** Edge Device → POST /telemetry/ingest → Database

### Pipeline Stages

```
1. HMAC Authentication (Fleet API key validation)
2. Batch ID Deduplication (LRU cache: 10K entries, 1hr TTL)
3. Payload Deserialization (Max: 1000 msgs, 10MB)
4. Device Upsert (FleetDevice table)
5. Event Storage (TelemetryStageEvent/SystemEvent)
6. Response Generation
```

### Performance Metrics

| Metric | Target | Measurement Point |
|--------|--------|-------------------|
| Ingest Latency | < 500ms | POST response time |
| Throughput | > 10K events/sec | Events processed per second |
| Dedup Hit Rate | > 95% | Cache statistics |
| Device Upsert | < 50ms | Database operation |

---

## 4. Identity & Renewal Subsystem

**Scheduler:** `src/tensorguard/identity/scheduler.py`

### State Machine

```
PENDING → CSR_REQUESTED → CSR_RECEIVED → CHALLENGE_PENDING
→ CHALLENGE_COMPLETE → ISSUING → ISSUED → DEPLOYING
→ VALIDATING → SUCCEEDED/FAILED/ROLLED_BACK
```

### Performance Metrics

| Metric | Target | Measurement Point |
|--------|--------|-------------------|
| Job Creation | < 100ms | POST /renewals/run |
| State Transition | < 200ms | Worker advancement |
| CSR Generation | < 500ms | Agent crypto ops |
| Certificate Deploy | < 2s | K8s/Nginx update |

---

## 5. Platform Worker (Background Jobs)

**Entry Point:** `src/tensorguard/platform/worker.py`

### Worker Loop (10s interval)

```python
1. process_identity_renewals()  # Advance renewal jobs
2. process_telemetry_aggregation()  # Future: rollups
3. cleanup_stale_jobs()  # Mark stuck jobs failed
```

### Performance Metrics

| Metric | Target | Measurement Point |
|--------|--------|-------------------|
| Loop Iteration | < 5s | Full processor cycle |
| Jobs per Loop | ≥ 100 | Renewals advanced |
| Cleanup Efficiency | < 1s | Stale job detection |

---

## 6. Unified Agent

**Entry Point:** `src/tensorguard/agent/daemon.py`

### Subsystems

| Component | File | Purpose |
|-----------|------|---------|
| IdentityManager | `agent/identity/manager.py` | Certificate lifecycle |
| NetworkGuardian | `agent/network/guardian.py` | RTPL defense |
| MLManager | `agent/ml/manager.py` | Federated learning |
| TelemetryEmitter | `agent/telemetry/emitter.py` | Event batching |

### Performance Metrics

| Metric | Target | Measurement Point |
|--------|--------|-------------------|
| Config Sync | < 100ms | Fetch + apply |
| Endpoint Scan | < 5s | Large K8s cluster |
| Telemetry Emit | < 100ms | Batch send |

---

## 7. Edge Agent (Telemetry Uploader)

**Entry Point:** `src/tensorguard/edge_agent/main.py`

### Architecture

```
Spooler (SQLite) → Uploader → POST /telemetry/ingest
```

### Performance Metrics

| Metric | Target | Measurement Point |
|--------|--------|-------------------|
| Spool Write | < 10ms | SQLite insert |
| Batch Upload | < 1s | HTTP POST |
| Backlog Growth | Monitor | Queue depth |

---

## 8. Load Testing Priority Order

### Phase 1: Foundation
1. Authentication throughput (POST /auth/token)
2. Database connection pool saturation
3. Fleet CRUD operations

### Phase 2: Telemetry
4. Telemetry ingestion (target: 100K events/sec)
5. Dashboard query performance

### Phase 3: Identity
6. Renewal job scheduling
7. Worker job processing

### Phase 4: Distributed
8. Multi-agent simulation (1000+ agents)
9. Failover and recovery

---

## Key Files Quick Reference

| Purpose | File | Description |
|---------|------|-------------|
| Main App | `platform/main.py` | FastAPI application |
| Database | `platform/database.py` | Connection pooling |
| Telemetry API | `api/telemetry_endpoints.py` | Ingest pipeline |
| Identity API | `api/identity_endpoints.py` | Renewal management |
| Worker | `platform/worker.py` | Background jobs |
| Agent | `agent/daemon.py` | Unified agent |
| Edge | `edge_agent/main.py` | Telemetry uploader |

---

**Generated:** 2026-01-20
**For:** Performance Benchmarking Initiative
