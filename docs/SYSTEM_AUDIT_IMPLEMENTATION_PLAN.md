# TensorGuardFlow Production Audit & Implementation Plan

## Audit scope

This audit focuses on production-readiness gaps where mock, simulated, placeholder, or stub logic exists in production paths, plus UI flows that surface demo-only behavior. The repository already contains a gap inventory, which is treated as the source of truth for locating mock/simulated references in production code and UI files. The plan below consolidates those findings into execution-ready remediation work. 【F:docs/PROD_GAPS_REPORT.md†L1-L120】

## Production-impacting mock/simulation gaps (key highlights)

### Identity & attestation
- **TPM simulator is wired as the default trust root** in the IdentityManager, which instantiates `TPMSimulator` directly, making software attestation the default path. This must be replaced with a real hardware-backed TPM provider (or remote attestation) for production. 【F:src/tensorguard/agent/identity/manager.py†L18-L36】
- **TPM simulator is explicitly a software-only identity layer** and is currently gated by `TG_ALLOW_TPM_SIMULATOR`, meaning production environments can still opt into simulated attestation. A production-ready implementation must remove the simulator from default dependency injection and enforce hardware-backed keys by default. 【F:src/tensorguard/agent/identity/tpm_simulator.py†L1-L44】
- **Identity renewal challenge handling is simulated**, with `http-01` challenge completion stubbed out and no real ACME/webroot integration. This is a real production workflow gap. 【F:src/tensorguard/agent/identity/work_poller.py†L57-L102】

### Federated ML training & adapter lifecycle
- **Differential privacy (DP) accounting is explicitly simplified**, with placeholders and warnings that RDP accounting and proper DP composition are not implemented. This is a critical production gap that must be replaced with a real DP accountant. 【F:src/tensorguard/agent/ml/worker.py†L87-L173】
- **Global pruning enforcement is simulated when the adapter model is a dict**, with explicit log messages for skipping structured pruning on “mock model dicts.” This indicates missing real model integration. 【F:src/tensorguard/agent/ml/worker.py†L209-L235】
- **MLManager does not load real adapters and has stubbed hot-swap/shadow/rollback logic**, which prevents safe live deployments and rollbacks in production. 【F:src/tensorguard/agent/ml/manager.py†L44-L205】

### External integrations
- **Base integration connector interface is unimplemented** (`validate_credentials` and `health_check` raise `NotImplementedError`), which means any integration without a concrete implementation will fail in production. 【F:src/tensorguard/platform/api/integrations_endpoints.py†L52-L83】
- **Some integration health checks are explicitly placeholders**, such as the ROS2 bridge returning “unavailable” with guidance rather than real discovery. This must be replaced with real connectivity validation or explicit “not supported in production” gating. 【F:src/tensorguard/platform/api/integrations_endpoints.py†L131-L170】

### TGSP marketplace & distribution
- **UI uses mock TGSP package data when the backend fails**, leading to non-production UI behavior. This must be removed in favor of a real empty-state with actionable errors. 【F:frontend/src/components/TGSPMarketplace.vue†L31-L147】
- **Backend TGSP endpoints are real and database-backed**, so the UI should align with these endpoints and not substitute mock data. 【F:src/tensorguard/platform/api/community_tgsp.py†L1-L120】

### FedMoE evaluation UI
- **Eval Arena contains explicit placeholder/"mock sim" UI state** and describes baseline rendering as unavailable. This should be replaced with true evaluation traces or explicit “no data yet” states sourced from the backend. 【F:frontend/src/components/EvalArena.vue†L84-L173】

### Audit trail UI
- **Audit trail UI expects a real backend but only surfaces a general error message**; the design should be tied to actual forensics and audit events, including PQC signatures, rather than empty or mocked placeholder responses. 【F:frontend/src/components/AuditTrail.vue†L1-L79】

## UI realignment matrix (frontend → backend)

| UI Surface | Current UI behavior | Production-aligned backend | Required change |
| --- | --- | --- | --- |
| TGSP Marketplace | Injects mock package list on fetch failure | `/api/v1/tgsp/packages`, `/api/v1/tgsp/upload`, `/api/v1/tgsp/releases` | Remove mock fallback, replace with real empty-state + error UX, keep data model aligned with `TGSPPackage`. 【F:frontend/src/components/TGSPMarketplace.vue†L31-L147】【F:src/tensorguard/platform/api/community_tgsp.py†L1-L120】 |
| FedMoE Eval Arena | Shows “Mock Sim View Active” and no baseline render | `/api/v1/fedmoe/experts`, `/api/v1/fedmoe/experts/{id}/evidence` | Replace simulated visualization with real evaluation traces, or show “no data” when none exists. 【F:frontend/src/components/EvalArena.vue†L84-L173】【F:src/tensorguard/platform/api/fedmoe_endpoints.py†L1-L120】 |
| Integrations Hub | UI assumes connect/disconnect flows; backend has unimplemented base connector behavior | `/api/v1/integrations/status`, `/api/v1/integrations/connect` | Fill in real connector implementations or hard-disable integrations with explicit production gating and remediation. 【F:frontend/src/components/IntegrationsHub.vue†L1-L140】【F:src/tensorguard/platform/api/integrations_endpoints.py†L52-L170】 |
| Audit Trail | Basic fetch + empty state | `/api/v1/audit/logs` + forensics records | Add UI for PQC signatures, integrity status, and actionable remediation when back-end unavailable. 【F:frontend/src/components/AuditTrail.vue†L1-L79】【F:src/tensorguard/platform/services/forensics_service.py†L1-L207】 |

## Implementation plan (production-ready focus)

### Phase 0 — Baseline production gates and data contracts (1–2 weeks)
1. **Define and codify “production mode” invariants**: ensure no mock/simulated logic can execute when `TG_ENVIRONMENT=production` by enforcing gating at startup and in runtime checks. (Use current gap inventory as acceptance criteria.) 【F:docs/PROD_GAPS_REPORT.md†L1-L120】
2. **Finalize backend data contracts for UI** (OpenAPI + typed DTOs): explicitly define UI responses for TGSP packages, audit logs, FedMoE evidence, and integrations. This reduces UI fallback logic and makes missing data explicit instead of simulated.
3. **Remove mock fallback data from UI** and replace with error + empty-state patterns that require real backend data. 【F:frontend/src/components/TGSPMarketplace.vue†L31-L147】

### Phase 1 — Identity & attestation hardening (2–4 weeks)
1. **Replace `TPMSimulator` with a hardware-backed TPM provider** (TPM 2.0 via tpm2-pytss, or cloud-validated remote attestation). Use dependency injection to select the provider, and gate simulator usage only for dev/test. 【F:src/tensorguard/agent/identity/manager.py†L18-L36】【F:src/tensorguard/agent/identity/tpm_simulator.py†L1-L44】
2. **Implement real ACME challenge handling** for `http-01` (or `dns-01`) in `WorkPoller`: write tokens to webroot, update ingress, or call a configured ACME client. Remove the simulated “pass-through” logic. 【F:src/tensorguard/agent/identity/work_poller.py†L57-L121】
3. **Add production-grade certificate deployment** via deployers (nginx/envoy/k8s) in `_handle_deployment` to complete the renewal loop. 【F:src/tensorguard/agent/identity/work_poller.py†L104-L130】

### Phase 2 — Federated ML training integrity (3–6 weeks)
1. **Integrate a real DP accountant** (e.g., Opacus or DP-Accountant) and replace the simplified epsilon logic in `TrainingWorker`. Provide auditable privacy budgets per client. 【F:src/tensorguard/agent/ml/worker.py†L87-L173】
2. **Wire in real model adapters** and remove “mock model dict” pruning paths by ensuring adapters provide actual model objects. Enforce adapter validation during initialization. 【F:src/tensorguard/agent/ml/worker.py†L209-L235】
3. **Implement adapter lifecycle operations**: download, validate, and hot-swap adapters; implement shadow-mode dual inference and rollback on failure. Replace MLManager stubs with real logic. 【F:src/tensorguard/agent/ml/manager.py†L44-L205】

### Phase 3 — Integration connectors (2–4 weeks)
1. **Implement connector-specific validation and health checks** for each supported service (Isaac Lab, ROS2, Formant, Hugging Face). Replace the `NotImplementedError` defaults and define “supported in production” behavior. 【F:src/tensorguard/platform/api/integrations_endpoints.py†L52-L170】
2. **Add backend configuration storage + secrets handling** with explicit error remediation and audit logging for integration changes.

### Phase 4 — TGSP & evidence flows (2–4 weeks)
1. **Align TGSP UI with production endpoints** by removing mock package fallback and adding real-time status polling. 【F:frontend/src/components/TGSPMarketplace.vue†L31-L147】【F:src/tensorguard/platform/api/community_tgsp.py†L1-L120】
2. **Extend evaluation evidence storage** to include trace artifacts and sample outputs required for FedMoE Eval Arena rendering, replacing placeholder UI views. 【F:frontend/src/components/EvalArena.vue†L84-L173】

### Phase 5 — UI/UX production alignment (2–3 weeks)
1. **Audit every UI screen for simulation-specific copy**, replacing with real-state-driven content (e.g., status “unavailable” or “no data yet” instead of mock-sim messaging). 【F:frontend/src/components/EvalArena.vue†L84-L173】
2. **Add explicit error states tied to backend response codes** (e.g., authentication required, missing PQC keys, missing integrations). 【F:frontend/src/components/AuditTrail.vue†L1-L79】
3. **Improve onboarding diagnostics** so operators know which backend services are required before UI functionality is enabled.

## Acceptance criteria
- **No mock or simulated behavior in production code paths** (enforced by production gates and tests). 【F:docs/PROD_GAPS_REPORT.md†L1-L120】
- **Identity renewal and attestation are hardware-backed and auditable**, with no simulator dependency in production. 【F:src/tensorguard/agent/identity/manager.py†L18-L36】【F:src/tensorguard/agent/identity/tpm_simulator.py†L1-L44】
- **Federated training produces DP-compliant updates with audited epsilon consumption**, and adapter swaps/rollbacks are fully implemented. 【F:src/tensorguard/agent/ml/worker.py†L87-L235】【F:src/tensorguard/agent/ml/manager.py†L44-L205】
- **UI presents only real system state and data**, with mock data removed and contracts aligned to backend schemas. 【F:frontend/src/components/TGSPMarketplace.vue†L31-L147】【F:frontend/src/components/EvalArena.vue†L84-L173】
