# Production Audit & Implementation Plan

**Audit Date:** 2026-01-18
**Version:** 2.3.0
**Auditor:** System Audit

---

## Executive Summary

This document provides a comprehensive audit of TensorGuardFlow identifying **ALL** mock implementations, simulations, stubs, and placeholder data that must be replaced or gated for production deployment. It also identifies frontend UI components that display hardcoded or simulated data instead of connecting to real backend APIs.

### Audit Scope
- **Backend Python codebase** (`src/tensorguard/`)
- **Frontend Vue.js components** (`frontend/src/`)
- **API endpoint analysis** (`platform/api/`)
- **Integration points and external services**

### Key Findings Summary

| Category | Count | Critical | Gated |
|----------|-------|----------|-------|
| Backend Mocks/Simulations | 18 | 8 | 10 |
| Frontend Hardcoded Data | 13 | 6 | 0 |
| API Endpoints with Mock Data | 5 | 2 | 3 |
| Integration Stubs | 6 | 4 | 2 |

---

## Part 1: Backend Mocks and Simulations

### 1.1 CRITICAL - Hardware/Security Simulations

#### 1.1.1 TPM Simulator (Hardware Root of Trust)
**File:** `src/tensorguard/agent/identity/tpm_simulator.py`
**Lines:** 1-152
**Status:** Gated with `TG_ALLOW_TPM_SIMULATOR` environment variable

**Current Implementation:**
- Simulates TPM 2.0 with software-only Platform Configuration Registers (PCRs)
- Generates fake Attestation Identity Key (AIK) with ephemeral RSA-2048 keys
- Hardcoded PCR values: `BIOS_V2`, `UBUNTU hardened config`, `SECURE_BOOT`
- Quote generation returns `{"attested": False, "simulator": True}`
- No actual hardware root of trust

**Production Gate:**
```python
if is_production() and not os.getenv("TG_ALLOW_TPM_SIMULATOR"):
    raise ProductionGateError("TPM simulator blocked in production")
```

**Required Implementation:**
- [ ] Integrate with real TPM 2.0 hardware via `tpm2-tss` library
- [ ] Support cloud attestation services (Azure Attestation, AWS Nitro, GCP Confidential)
- [ ] Implement PKCS#11 interface for HSM-backed attestation
- [ ] Add AMD SEV-SNP / Intel TDX attestation support

---

#### 1.1.2 Identity ACME Challenge Simulation
**File:** `src/tensorguard/agent/identity/work_poller.py`
**Lines:** 63-145
**Status:** Partially implemented (HTTP-01 is no-op)

**Current Implementation:**
- HTTP-01 challenge handling is a placeholder (logs but doesn't create challenge files)
- Certificate deployment is acknowledged but not executed
- No actual certificate installation to endpoints

**Required Implementation:**
- [ ] Write HTTP-01 challenge tokens to webroot/ingress path
- [ ] Implement DNS-01 challenge handling for wildcard certificates
- [ ] Add certificate deployment to target endpoints (nginx reload, HAProxy, etc.)
- [ ] Implement OCSP stapling refresh

---

#### 1.1.3 Private CA SPIRE Issuance Stub
**File:** `src/tensorguard/identity/ca/private_ca.py`
**Lines:** 170-216
**Status:** Blocked in production when public trust disabled

**Current Implementation:**
- Private CA issuance raises `NotImplementedError` for SPIRE backend
- Scheduler blocks private CA flows in production

**Required Implementation:**
- [ ] Integrate SPIRE workload API for mTLS certificate issuance
- [ ] Add HashiCorp Vault PKI secrets engine support
- [ ] Implement step-ca integration for private CA workflows
- [ ] Add certificate chain validation

---

### 1.2 CRITICAL - ML/Training Simulations

#### 1.2.1 PEFT DemoTrainer
**File:** `src/tensorguard/integrations/peft_hub/connectors/training_hf.py`
**Lines:** 280-361
**Status:** Gated with `ProductionGateError`

**Current Implementation:**
```python
class DemoTrainer:
    # Creates placeholder files: adapter_model.demo.bin
    # Returns fake metrics: {"status": "demo_success", "warning": "This was a demo run"}
    # No actual training performed
```

**Production Gate:**
- Blocked by `ProductionGateError` when PyTorch/Transformers unavailable

**Required Implementation:**
- [ ] Ensure production dependencies installed (PyTorch, Transformers, PEFT)
- [ ] Remove DemoTrainer class entirely from production builds
- [ ] Add pre-flight dependency check before training workflow
- [ ] Implement artifact validation for adapter weights

---

#### 1.2.2 ML Manager Adapter Loading Stubs
**File:** `src/tensorguard/agent/ml/manager.py`
**Lines:** 42-229
**Status:** Stub implementation

**Current Implementation:**
- `load_adapter()` is a stub that doesn't actually load model weights
- `hot_swap()` logs but doesn't perform atomic model replacement
- `rollback()` is a no-op placeholder
- No compatibility validation between adapters

**Required Implementation:**
- [ ] Implement real adapter registry with version tracking
- [ ] Add model weight download from artifact store (S3, GCS, Azure Blob)
- [ ] Implement atomic model swap with rollback capability
- [ ] Add adapter compatibility validation (architecture, dtype, dimensions)
- [ ] Implement health check after adapter load

---

#### 1.2.3 Training Worker DP Accounting Placeholder
**File:** `src/tensorguard/agent/ml/worker.py`
**Lines:** 115-238
**Status:** Simplified placeholder

**Current Implementation:**
```python
# "Simplified DP accounting - production should use RDP accountant"
epsilon_consumed = noise_multiplier * 0.1  # Placeholder calculation
```
- Simulated pruning that logs "skipped on mock models"
- No per-sample gradient clipping
- Inaccurate privacy budget tracking

**Required Implementation:**
- [ ] Integrate production RDP (Renyi Differential Privacy) accountant
- [ ] Implement per-sample gradient clipping (Opacus-style)
- [ ] Add accurate epsilon/delta tracking per training round
- [ ] Enforce privacy budget exhaustion (halt training when exceeded)
- [ ] Replace simulated pruning with real layer-wise pruning hooks

---

### 1.3 CRITICAL - Integration Simulations

#### 1.3.1 RMF Adapter Mock Payload
**File:** `src/tensorguard/integrations/rmf/adapter.py`
**Lines:** 18-69
**Status:** Not gated

**Current Implementation:**
- Builds fake encrypted payload instead of encrypting real robot telemetry
- Uses mock ciphertext and mock keys
- Prevents end-to-end MOAI inference verification

**Required Implementation:**
- [ ] Build real RMF payload adapter using robot telemetry/task state
- [ ] Use actual N2HE/CKKS encryption from MOAI context
- [ ] Wire to real MOAI key vault (no placeholder eval keys)
- [ ] Add payload schema validation before encryption
- [ ] Implement request signing and envelope generation

---

#### 1.3.2 MOAI Placeholder Evaluation Keys
**File:** `src/tensorguard/moai/keys.py`
**Lines:** 85-118
**Status:** Fallback to placeholder

**Current Implementation:**
- Returns placeholder evaluation keys if `.eval` artifacts are missing
- Silently bypasses required key material validation

**Required Implementation:**
- [ ] Fail-closed when eval keys are missing in production
- [ ] Require explicit key provisioning from MOAI key vault
- [ ] Add key validation (format, expiry, permissions)
- [ ] Implement key rotation with zero-downtime

---

#### 1.3.3 FastUMI Robotic Data Simulator
**File:** `src/tensorguard/utils/fastumi_adapter.py`
**Lines:** 57-88
**Status:** Fallback when HDF5 unavailable

**Current Implementation:**
```python
class FastUMISimulator:
    def _generate_synthetic():
        # Random video frames (224x224x3)
        # Random joint positions (qpos: shape 7)
        # Metadata: {"sim": True, "provider": "MockFastUMI"}
```

**Required Implementation:**
- [ ] Fail when real HDF5 episodes are unavailable in production
- [ ] Add data validation for episode format and completeness
- [ ] Implement episode caching and prefetch
- [ ] Add provenance tracking for training data

---

### 1.4 MODERATE - Observability and Logging

#### 1.4.1 No-Op OpenTelemetry Tracer
**File:** `src/tensorguard/observability/otel.py`
**Lines:** 180-249
**Status:** Silent fallback

**Current Implementation:**
- Uses no-op tracer stub when OTEL exporter unavailable
- Traces silently dropped without warning
- No production-grade export path

**Required Implementation:**
- [ ] Require OTLP exporter configuration in production
- [ ] Emit explicit startup warnings when observability disabled
- [ ] Add metrics fallback to Prometheus push gateway
- [ ] Implement trace sampling configuration

---

### 1.5 MOCK API ENDPOINTS

#### 1.5.1 Attestation Verify Endpoint
**File:** `src/tensorguard/platform/api/endpoints.py`
**Route:** `POST /api/v1/attestation/verify`
**Status:** Hardcoded "allow"

**Current Implementation:**
- Always returns `{"result": "allow", "confidence": 1.0}`
- No actual attestation verification

**Required Implementation:**
- [ ] Integrate with TPM/attestation service for real verification
- [ ] Add quote signature validation
- [ ] Implement attestation policy evaluation
- [ ] Add audit logging for attestation decisions

---

#### 1.5.2 TGSP Key Release Endpoint
**File:** `src/tensorguard/platform/api/endpoints.py`
**Route:** `POST /api/v1/tgsp/key-release`
**Status:** Random token generation

**Current Implementation:**
- Generates random tokens instead of real key unwrapping
- No actual KMS integration

**Required Implementation:**
- [ ] Integrate with configured KMS backend (AWS KMS, Azure Key Vault, GCP KMS)
- [ ] Implement proper key envelope decryption
- [ ] Add key usage policy enforcement
- [ ] Audit log all key release events

---

#### 1.5.3 Lineage Endpoints (Mock Registry)
**File:** `src/tensorguard/platform/api/lineage_endpoints.py`
**Routes:** `GET /api/v1/lineage/versions`, `GET /api/v1/lineage/versions/{tag}`
**Status:** Hardcoded MODEL_REGISTRY

**Current Implementation:**
- Returns from in-memory `MODEL_REGISTRY` dictionary
- Not persisted to database
- Sync endpoint is placeholder

**Required Implementation:**
- [ ] Persist model versions to database (ModelVersion table)
- [ ] Implement real HuggingFace Hub sync
- [ ] Add model artifact storage integration
- [ ] Track deployment lineage in audit log

---

#### 1.5.4 Demo Fleet Data Endpoint
**File:** `src/tensorguard/platform/api/endpoints.py`
**Route:** `GET /api/v1/fleets` (fallback)
**Status:** Gated with `is_demo_mode()`

**Current Implementation:**
```python
if not result and is_demo_mode():
    result = [
        {"id": "demo-f1", "name": "US-East-1 Cluster", ...},
        {"id": "demo-f2", "name": "Berlin Gigafactory", ...}
    ]
```

**Required Implementation:**
- [ ] Remove demo data fallback entirely
- [ ] Return empty list with proper HTTP status when no fleets
- [ ] Add fleet creation onboarding flow

---

### 1.6 INTENTIONAL IMPLEMENTATIONS (NOT MOCKS)

The following are **intentional security features**, not mocks to be replaced:

| Component | File | Purpose |
|-----------|------|---------|
| WTF-PAD Dummy Packets | `agent/network/defense/wtf_pad.py` | Traffic analysis defense |
| FRONT Dummy Injection | `agent/network/defense/front.py` | Robotics traffic masking |

---

## Part 2: Frontend UI Misalignments

### 2.1 CRITICAL - Completely Hardcoded Components

#### 2.1.1 Dashboard.vue - Static Statistics
**File:** `frontend/src/components/Dashboard.vue`
**Status:** No API calls

**Current Implementation:**
```javascript
const stats = [
  { label: 'System Health', value: '99.9%', ... },
  { label: 'Active Fleets', value: '12', ... },
  { label: 'Keys Rotated', value: '24h', ... },
  { label: 'Compliance', value: 'Level 4', ... }
]
```

**Required Implementation:**
- [ ] Create `/api/v1/dashboard/stats` endpoint
- [ ] Fetch real system health from service health checks
- [ ] Aggregate fleet count from Fleet table
- [ ] Track key rotation from KMSRotationLog
- [ ] Calculate compliance score from compliance checks

---

#### 2.1.2 CommandCenter.vue - Hardcoded Metrics
**File:** `frontend/src/components/CommandCenter.vue`
**Status:** All metrics hardcoded

**Hardcoded Values:**
- System health: `{ overall: 'healthy', services: {...} }`
- Metrics: `{ activeFleets: 12, connectedDevices: 847, ... }`
- Secondary stats: `99.9%` uptime, `48.2ms` latency, `7,844x` BW reduction

**Required Implementation:**
- [ ] Create `/api/v1/status/health` for service health
- [ ] Create `/api/v1/metrics/summary` for aggregated metrics
- [ ] Connect to real telemetry pipeline data
- [ ] Implement WebSocket for real-time updates

---

#### 2.1.3 TrainingMonitor.vue - Simulated Metrics
**File:** `frontend/src/components/TrainingMonitor.vue`
**Lines:** 79-107
**Status:** Uses `Math.random()` for all metrics

**Current Implementation:**
```javascript
// Simulate metrics update (in production, this would come from backend)
const newLoss = Math.max(0.01, ... - Math.random() * 0.02)
const newAcc = Math.min(0.99, ... + Math.random() * 0.01)
expertWeights.value = {
  'visual_primary': 0.35 + Math.random() * 0.05,
  // ... all randomly generated
}
```

**Required Implementation:**
- [ ] Connect to `/api/v1/training/metrics` endpoint
- [ ] Implement SSE or WebSocket for streaming metrics
- [ ] Fetch expert weights from aggregator state
- [ ] Show real active client counts from telemetry

---

### 2.2 CRITICAL - Fallback Mock Data

#### 2.2.1 OperationsCenter.vue
**File:** `frontend/src/components/OperationsCenter.vue`
**Lines:** 59-106

**Mock Fallbacks:**
1. Fleet data fallback (lines 59-64): Hardcoded US-East, EU, APAC fleets
2. TGSP packages fallback (lines 75-78): Hardcoded package list
3. Integration statuses (lines 44-49): Static connection states
4. Training metrics (lines 88-105): `Math.random()` simulation

**Required Implementation:**
- [ ] Remove all catch block mock data
- [ ] Show proper error states when APIs fail
- [ ] Connect to real `/api/v1/integrations/status` endpoint
- [ ] Stream training metrics from telemetry service

---

#### 2.2.2 SecurityCenter.vue
**File:** `frontend/src/components/SecurityCenter.vue`
**Lines:** 30-94

**Hardcoded Values:**
- Security score: `ref(92)`
- Compliance score: `ref(95)`
- Alerts: Static warning/info alerts
- Certificates fallback: Hardcoded cert list
- Keys fallback: Hardcoded key list
- Audit logs fallback: Hardcoded log entries
- Policies fallback: Hardcoded policy list

**Required Implementation:**
- [ ] Create `/api/v1/security/score` endpoint
- [ ] Connect to `/api/v1/identity/inventory` for real certificates
- [ ] Connect to `/api/v1/kms/keys` for real keys
- [ ] Connect to `/api/v1/identity/audit` for real audit logs
- [ ] Calculate scores from real security posture data

---

#### 2.2.3 IdentityManager.vue
**File:** `frontend/src/components/IdentityManager.vue`
**Status:** Falls back to mock inventory, policies, renewals

**Required Implementation:**
- [ ] Remove mock inventory fallback
- [ ] Map certificate fields to real API contract
- [ ] Connect to `/api/v1/identity/policies` without fallback
- [ ] Connect to `/api/v1/identity/renewals` without fallback

---

### 2.3 MODERATE - Partial API Integration

#### 2.3.1 TGSPMarketplace.vue
**File:** `frontend/src/components/TGSPMarketplace.vue`
**Status:** Falls back to mock on API failure

**Required Implementation:**
- [ ] Remove mock package fallback
- [ ] Show explicit error states on API failure
- [ ] Surface real package status transitions
- [ ] Allow retry via backend events

---

#### 2.3.2 NodePalette.vue (Flow Editor)
**File:** `frontend/src/components/flow/NodePalette.vue`
**Status:** Static node catalog

**Required Implementation:**
- [ ] Create `/api/v1/flow/nodes` endpoint for dynamic capabilities
- [ ] Fetch supported triggers/actions from backend
- [ ] Add capability discovery for installed integrations

---

### 2.4 API Endpoint Mapping

| Frontend Component | Required Backend Endpoints | Status |
|--------------------|---------------------------|--------|
| Dashboard.vue | `/api/v1/dashboard/stats` | NOT EXISTS |
| CommandCenter.vue | `/api/v1/status/health`, `/api/v1/metrics/summary` | PARTIAL |
| TrainingMonitor.vue | `/api/v1/training/metrics` (streaming) | NOT EXISTS |
| OperationsCenter.vue | `/api/v1/integrations/status` | EXISTS |
| SecurityCenter.vue | `/api/v1/security/score` | NOT EXISTS |
| IdentityManager.vue | `/api/v1/identity/*` | EXISTS |
| TGSPMarketplace.vue | `/api/v1/tgsp/packages` | EXISTS |
| NodePalette.vue | `/api/v1/flow/nodes` | NOT EXISTS |

---

## Part 3: Implementation Phases

### Phase 1: Security-Critical Replacements (Week 1-2)

**Objective:** Replace all security-critical mocks that affect trust and attestation.

| Task | File(s) | Priority | Complexity |
|------|---------|----------|------------|
| 1.1 Real TPM/HSM attestation | `tpm_simulator.py`, `manager.py` | P0 | High |
| 1.2 ACME challenge handling | `work_poller.py` | P0 | Medium |
| 1.3 Private CA integration | `private_ca.py`, `scheduler.py` | P0 | High |
| 1.4 Attestation verify endpoint | `endpoints.py` | P0 | Medium |
| 1.5 TGSP key release endpoint | `endpoints.py` | P0 | Medium |

**Deliverables:**
- Hardware-backed attestation support
- Real certificate issuance workflow
- Production KMS integration

---

### Phase 2: ML/Training Pipeline (Week 2-3)

**Objective:** Replace training simulations with production implementations.

| Task | File(s) | Priority | Complexity |
|------|---------|----------|------------|
| 2.1 Remove DemoTrainer | `training_hf.py` | P0 | Low |
| 2.2 ML adapter lifecycle | `manager.py` | P0 | High |
| 2.3 Production RDP accountant | `worker.py` | P0 | High |
| 2.4 Real pruning hooks | `worker.py` | P1 | Medium |
| 2.5 FastUMI production gate | `fastumi_adapter.py` | P1 | Low |

**Deliverables:**
- End-to-end PEFT training with real artifacts
- Accurate privacy budget tracking
- Model adapter management with rollback

---

### Phase 3: Integration Layer (Week 3-4)

**Objective:** Replace integration stubs with real implementations.

| Task | File(s) | Priority | Complexity |
|------|---------|----------|------------|
| 3.1 RMF real payload adapter | `adapter.py` | P0 | High |
| 3.2 MOAI eval key enforcement | `keys.py` | P0 | Medium |
| 3.3 Lineage database persistence | `lineage_endpoints.py` | P1 | Medium |
| 3.4 HuggingFace Hub sync | `lineage_endpoints.py` | P2 | Medium |

**Deliverables:**
- Real MOAI inference pipeline
- Database-backed model registry
- External integration sync

---

### Phase 4: Frontend Realignment (Week 4-5)

**Objective:** Connect all frontend components to real backend APIs.

| Task | File(s) | Priority | Complexity |
|------|---------|----------|------------|
| 4.1 Dashboard stats endpoint | Backend + `Dashboard.vue` | P0 | Medium |
| 4.2 Command center health/metrics | Backend + `CommandCenter.vue` | P0 | Medium |
| 4.3 Training metrics streaming | Backend + `TrainingMonitor.vue` | P0 | High |
| 4.4 Remove OperationsCenter mocks | `OperationsCenter.vue` | P1 | Low |
| 4.5 Remove SecurityCenter mocks | `SecurityCenter.vue` | P1 | Low |
| 4.6 Flow nodes catalog | Backend + `NodePalette.vue` | P2 | Medium |

**New API Endpoints Required:**
```
POST /api/v1/dashboard/stats
GET  /api/v1/status/health
GET  /api/v1/metrics/summary
GET  /api/v1/training/metrics (SSE/WebSocket)
GET  /api/v1/security/score
GET  /api/v1/flow/nodes
```

**Deliverables:**
- Real-time dashboard with live data
- Streaming training metrics
- Dynamic flow editor capabilities

---

### Phase 5: Observability & Hardening (Week 5-6)

**Objective:** Enforce production observability and remove all remaining stubs.

| Task | File(s) | Priority | Complexity |
|------|---------|----------|------------|
| 5.1 Require OTLP exporter | `otel.py` | P1 | Low |
| 5.2 Remove demo fleet fallback | `endpoints.py` | P1 | Low |
| 5.3 Production readiness check | New startup validator | P1 | Medium |
| 5.4 Integration base class cleanup | `integrations_endpoints.py` | P2 | Low |

**Deliverables:**
- Enforced observability in production
- Startup validation for all dependencies
- Clean error states for missing features

---

## Part 4: Success Criteria

### Production Readiness Checklist

- [ ] **Zero mock data in production UI** - All components fetch from real APIs
- [ ] **All API endpoints return real data** - No hardcoded responses in production
- [ ] **Hardware attestation validated** - Real TPM/HSM integration tested
- [ ] **PEFT training end-to-end** - Real model artifacts produced and stored
- [ ] **Privacy budget accurate** - RDP accountant tracks real epsilon consumption
- [ ] **KMS integration complete** - Real key operations with audit trail
- [ ] **Observability enforced** - OTLP traces exported, no silent drops
- [ ] **Startup validation passes** - All production gates checked

### Validation Tests

```bash
# Run production gate tests
pytest tests/security/test_production_gates.py -v

# Verify no mock data in production mode
TG_ENVIRONMENT=production pytest tests/integration/test_no_mocks.py -v

# End-to-end training validation
pytest tests/e2e/test_peft_training.py -v

# Frontend API integration tests
cd frontend && npm run test:integration
```

---

## Part 5: Detailed Task Breakdown

### Backend Implementation Tasks

```
PHASE 1: Security-Critical
├── 1.1 TPM/HSM Attestation
│   ├── Add tpm2-tss bindings
│   ├── Implement PKCS#11 interface
│   ├── Add cloud attestation adapters
│   └── Update production gate checks
├── 1.2 ACME Challenge Handler
│   ├── Implement HTTP-01 file writer
│   ├── Add DNS-01 TXT record handler
│   ├── Certificate deployment hooks
│   └── OCSP stapling refresh
├── 1.3 Private CA Integration
│   ├── SPIRE workload API client
│   ├── Vault PKI integration
│   ├── step-ca adapter
│   └── Certificate chain validation
├── 1.4 Attestation Verify Endpoint
│   ├── Quote signature validation
│   ├── Policy evaluation logic
│   ├── Attestation audit logging
│   └── Integration with identity service
└── 1.5 TGSP Key Release
    ├── AWS KMS unwrap integration
    ├── Azure Key Vault integration
    ├── GCP Cloud KMS integration
    └── Key usage policy enforcement

PHASE 2: ML/Training Pipeline
├── 2.1 Remove DemoTrainer
│   ├── Delete DemoTrainer class
│   ├── Add dependency pre-check
│   └── Update error messages
├── 2.2 ML Adapter Lifecycle
│   ├── Adapter registry with versions
│   ├── S3/GCS/Azure download
│   ├── Atomic model swap
│   ├── Compatibility validation
│   └── Post-load health check
├── 2.3 RDP Accountant
│   ├── Integrate RDP library
│   ├── Per-sample gradient clipping
│   ├── Per-round epsilon tracking
│   ├── Budget exhaustion enforcement
│   └── Privacy ledger updates
├── 2.4 Real Pruning Hooks
│   ├── Layer-wise pruning implementation
│   ├── Model availability guard
│   └── Pruning metrics collection
└── 2.5 FastUMI Gate
    ├── Production mode check
    ├── HDF5 validation
    └── Episode provenance tracking

PHASE 3: Integration Layer
├── 3.1 RMF Payload Adapter
│   ├── Robot telemetry ingestion
│   ├── N2HE/CKKS encryption
│   ├── MOAI key vault wiring
│   ├── Payload schema validation
│   └── Request signing
├── 3.2 MOAI Eval Keys
│   ├── Fail-closed on missing keys
│   ├── Key validation checks
│   └── Key rotation support
├── 3.3 Lineage Database
│   ├── ModelVersion table schema
│   ├── CRUD endpoints
│   └── Deployment tracking
└── 3.4 HuggingFace Sync
    ├── Hub API integration
    ├── Model download/upload
    └── Version sync logic
```

### Frontend Implementation Tasks

```
PHASE 4: Frontend Realignment
├── 4.1 Dashboard Stats
│   ├── Create stats endpoint
│   ├── Service health aggregation
│   ├── Fleet count query
│   ├── Key rotation tracking
│   ├── Compliance calculation
│   └── Update Dashboard.vue
├── 4.2 Command Center
│   ├── Create health endpoint
│   ├── Create metrics endpoint
│   ├── Update CommandCenter.vue
│   └── Add loading/error states
├── 4.3 Training Metrics
│   ├── Create streaming endpoint
│   ├── SSE/WebSocket setup
│   ├── Update TrainingMonitor.vue
│   └── Real-time chart updates
├── 4.4 Operations Center
│   ├── Remove mock fallbacks
│   ├── Add error states
│   └── Connect to real APIs
├── 4.5 Security Center
│   ├── Create score endpoint
│   ├── Remove mock fallbacks
│   ├── Connect to identity APIs
│   └── Add error states
└── 4.6 Flow Nodes
    ├── Create nodes endpoint
    ├── Dynamic capability discovery
    └── Update NodePalette.vue
```

---

## Appendix A: Environment Variables

### Production Required Variables

```bash
# Core Production Settings
TG_ENVIRONMENT=production
TG_JWT_SECRET=<secure-random-256-bit>
TG_KEY_MASTER=<encryption-master-key>

# Database
TG_DATABASE_URL=postgresql://...

# KMS Configuration (one required)
TG_KMS_PROVIDER=aws|azure|gcp|hsm
TG_AWS_KMS_KEY_ARN=arn:aws:kms:...
TG_AZURE_VAULT_URL=https://...vault.azure.net
TG_GCP_KMS_KEY_NAME=projects/.../cryptoKeys/...

# Observability (required in production)
TG_OTEL_ENDPOINT=https://otel-collector:4317
TG_OTEL_SERVICE_NAME=tensorguard

# Identity (optional overrides)
TG_ACME_DIRECTORY_URL=https://acme-v02.api.letsencrypt.org/directory
TG_PRIVATE_CA_BACKEND=vault|spire|step-ca
```

### Development/Testing Overrides

```bash
# Allow simulators (research only)
TG_ALLOW_TPM_SIMULATOR=true
TG_DEMO_MODE=true

# Disable production gates
TG_ENVIRONMENT=development
```

---

## Appendix B: Database Migrations Required

```python
# New tables needed for lineage persistence
class ModelVersion(SQLModel, table=True):
    id: str = Field(primary_key=True)
    tag: str = Field(index=True)
    base_model: str
    peft_method: str
    architecture: dict
    metrics: dict
    created_at: datetime
    deployed_at: Optional[datetime]

# Security score tracking
class SecurityPosture(SQLModel, table=True):
    id: str = Field(primary_key=True)
    timestamp: datetime
    overall_score: int
    certificate_score: int
    key_score: int
    compliance_score: int
    details: dict
```

---

## Appendix C: API Contracts for New Endpoints

### GET /api/v1/dashboard/stats
```json
{
  "system_health": {
    "status": "healthy|degraded|unhealthy",
    "uptime_percent": 99.9,
    "last_incident": "2026-01-15T10:00:00Z"
  },
  "fleet_count": 12,
  "device_count": 847,
  "key_rotations_24h": 24,
  "compliance_level": 4,
  "privacy_budget_remaining": 4.2
}
```

### GET /api/v1/status/health
```json
{
  "overall": "healthy",
  "services": {
    "aggregator": {"status": "healthy", "latency_ms": 12},
    "identity": {"status": "healthy", "latency_ms": 8},
    "kms": {"status": "healthy", "latency_ms": 5},
    "storage": {"status": "healthy", "latency_ms": 15}
  },
  "timestamp": "2026-01-18T12:00:00Z"
}
```

### GET /api/v1/training/metrics (SSE Stream)
```
event: metrics
data: {"round": 42, "loss": 0.0234, "accuracy": 0.968, "active_clients": 45, "expert_weights": {...}}

event: metrics
data: {"round": 43, "loss": 0.0221, "accuracy": 0.971, "active_clients": 47, "expert_weights": {...}}
```

### GET /api/v1/security/score
```json
{
  "overall": 92,
  "categories": {
    "certificates": 95,
    "keys": 90,
    "compliance": 95,
    "attestation": 88
  },
  "alerts": [
    {"type": "warning", "title": "Certificates Expiring", "count": 5}
  ],
  "last_audit": "2026-01-18T10:00:00Z"
}
```

### GET /api/v1/flow/nodes
```json
{
  "triggers": [
    {"id": "training_complete", "name": "Training Complete", "icon": "CheckCircle"},
    {"id": "model_deployed", "name": "Model Deployed", "icon": "Rocket"}
  ],
  "actions": [
    {"id": "send_notification", "name": "Send Notification", "icon": "Bell"},
    {"id": "rotate_keys", "name": "Rotate Keys", "icon": "RefreshCw"}
  ]
}
```

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-18 | 2.0 | Complete system audit with comprehensive mock inventory |
| 2026-01-18 | 2.1 | Added frontend UI misalignment analysis |
| 2026-01-18 | 2.2 | Added implementation phases and task breakdown |
