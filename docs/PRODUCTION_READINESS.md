# Production Readiness Checklist

This document tracks the production-hardening status of TensorGuardFlow.

## Checklist

### Build
- [ ] Reproducible builds with pinned dependencies (lockfile or deterministic install strategy).
- [ ] `make ci` runs lint, type checks (if configured), and tests with deterministic dependency profile.
- [ ] Packaging excludes demo/mock code from production distributions.

### Test
- [ ] Unit tests cover production gates and fail-closed behavior.
- [ ] Integration tests verify critical request flows and storage interactions.
- [ ] CI runs in a reproducible environment with pinned dependencies.

### Docker
- [ ] `docker build -f docker/platform/Dockerfile .` succeeds with pyproject-based install.
- [ ] `docker build -f docker/bench/Dockerfile .` succeeds with pyproject-based install.
- [ ] Docker images validate required secrets/config on startup.

### Security Gates
- [ ] Production startup fails fast if required secrets/config/dependencies are missing.
- [ ] Demo/simulator/stub paths are blocked in production or gated behind explicit research mode.
- [ ] No hardcoded secrets or mock payloads in production code paths.

### Database Migration Strategy
- [ ] Alembic migrations replace ad-hoc scripts.
- [ ] Migrations are versioned, repeatable, and validated in CI.

### Observability
- [ ] Request IDs and structured logs are enabled for API requests.
- [ ] Metrics endpoint is available (Prometheus/OpenTelemetry).
- [ ] Runbooks cover failed submissions, key rotation, and rollback.

## Current Status

- Baseline scan captured in `docs/PROD_GAPS_REPORT.md`.
- Startup validation now enforces production secrets/dependencies on platform and serving entrypoints.
- Additional hardening work is tracked in the PR history and README/HARDENING_REPORT updates.

## Production-Ready Capabilities (Current)

- Core FastAPI platform endpoints with database-backed telemetry ingestion (requires proper secrets/config).
- File-based key provider with enforced master key in production (`TG_KEY_MASTER`).
- HTTP-01 ACME challenge support (manual or file-based).
- TenSEAL inference backend for MOAI model packs.

## Disabled or Gated (Current)

- **Enterprise attestation/certification/recommendation services**: Disabled in this build; raise explicit errors to prevent accidental use. Requires enterprise packages and configuration.
- **TPM simulator**: Blocked in production by default. Can be enabled only with `TG_ALLOW_TPM_SIMULATOR=true`, which forces untrusted attestation claims.
- **PKCS#11 and KMS key providers**: Disabled in this build. Production configuration must use the file provider until supported implementations are shipped.
- **Native MOAI runtime backend**: Disabled in this build; production must use TenSEAL backend or install native runtime.
- **Flower-based aggregation**: Requires `flwr` dependency; production startup fails if aggregation is enabled without `tensorguard[fl]`.

## Enablement Guidance

- **Enterprise services**: Install and configure the enterprise service packages; verify startup gates pass in production.
- **TPM simulator override**: Set `TG_ALLOW_TPM_SIMULATOR=true` only for research use. Claims are marked `attested=false`.
- **PKCS#11/KMS providers**: Deploy supported implementations and update `KeyProviderFactory.SUPPORTED_PROVIDERS` to include validated providers.
- **Native MOAI runtime**: Install the native runtime and update backend selection to use it explicitly.
- **Aggregation**: Install `tensorguard[fl]`, ensure Flower service configuration is present, and validate with production gate tests.
