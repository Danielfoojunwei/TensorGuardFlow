# Production Gaps Report (Repo-Wide Scan)

This report lists every occurrence of `mock`, `simulate`, `simulator`, `stub`, `placeholder`, `NotImplementedError`, hardcoded secrets, or demo telemetry patterns found in the repo, plus known hotspots called out in the requirements. Each entry includes file path, function/class (or section), why it breaks production, and the remediation plan.

## API / Platform

### examples/vercel_mock/api/index.py
- **Location:** `handler.do_GET`
- **Finding:** Vercel mock endpoint returning simulated telemetry.
- **Why it breaks production:** Returns fake status, not tied to real EdgeClient state.
- **Fix plan:** Kept in `examples/` only; do not ship in production builds. Replace with real platform status endpoint in production.

### src/tensorguard/platform/auth.py
- **Location:** module-level `SECRET_KEY` fallback; `get_current_user` demo bypass.
- **Finding:** Generates a secret key at runtime and allows demo auth bypass.
- **Why it breaks production:** Secrets must be stable and enforced; demo bypass undermines auth.
- **Fix plan:** Fail-closed in production when `TG_SECRET_KEY` missing; disable demo bypass in production and gate with explicit dev flag.

### src/tensorguard/platform/services/jobs.py
- **Location:** `target_url` constant.
- **Finding:** Placeholder URL.
- **Why it breaks production:** Jobs will dispatch to localhost instead of configured endpoint.
- **Fix plan:** Require configured URL via settings; fail startup when missing in production.

### src/tensorguard/platform/api/integrations_endpoints.py
- **Location:** `get_integrations_status`.
- **Finding:** Returns mock integration status.
- **Why it breaks production:** Misleads operators and hides integration failures.
- **Fix plan:** Wire to real integration health checks or hard-disable endpoint in production.

### src/tensorguard/platform/api/edge_gating_endpoints.py
- **Location:** module in-memory state and simulated telemetry.
- **Finding:** Mock in-memory gating state and simulated telemetry.
- **Why it breaks production:** Telemetry is not real-time and is not persisted.
- **Fix plan:** Back with persistent store and real telemetry; gate with explicit dev-only mode.

### src/tensorguard/platform/api/config_endpoints.py
- **Location:** policy retrieval.
- **Finding:** Default/stub policy return.
- **Why it breaks production:** Security policy should be configured and enforced, not defaulted silently.
- **Fix plan:** Load policy from configured source; fail startup if missing in production.

### src/tensorguard/platform/api/peft_endpoints.py
- **Location:** response payload.
- **Finding:** `"config_hash": "stub-hash-123"`.
- **Why it breaks production:** Hash should represent actual configuration state.
- **Fix plan:** Compute config hash from persisted config and return real hash.

## Server / Aggregation / Core

### src/tensorguard/server/aggregator.py
- **Location:** module-level `try/except ImportError` with fake `fl` class.
- **Finding:** Flower stub for missing dependency; simulated evaluation metrics in aggregation.
- **Why it breaks production:** Silent stub usage hides dependency issues; simulated evaluation undermines gating.
- **Fix plan:** Remove stubs; require `flwr` when aggregation enabled; fail-closed if missing in production. Replace simulated evaluation with real metrics.

### src/tensorguard/core/client.py
- **Location:** `EdgeClient.process_round`.
- **Finding:** Returns mock payload `b"TENSORGUARD_ENCRYPTED_UPDATE_V2"`.
- **Why it breaks production:** Edge client produces fake updates; no real training or encryption occurs.
- **Fix plan:** Implement real pipeline, remove mock payload, add contract tests, and ensure determinism.

### src/tensorguard/core/adapters.py
- **Location:** adapter loading logic.
- **Finding:** Mock loading comment implies placeholder behavior.
- **Why it breaks production:** Model loading must be real for export/adapter operations.
- **Fix plan:** Implement real loading mechanism and remove mock path.

### src/tensorguard/serving/backend.py
- **Location:** `NativeBackend` methods.
- **Finding:** `NotImplementedError` for native runtime.
- **Why it breaks production:** Backend can be configured but will crash at runtime.
- **Fix plan:** Implement native backend or hard-disable with startup validation in production.

### src/tensorguard/integrations/rmf/adapter.py
- **Location:** `get_status`.
- **Finding:** Mock encrypted payload and key returned.
- **Why it breaks production:** Integration payloads must be real for RMF workflows.
- **Fix plan:** Connect to real RMF encryption/transport pipeline; fail-closed if not configured.

### src/tensorguard/edge_agent/spooler.py
- **Location:** SQL delete logic (`placeholders` variable).
- **Finding:** SQL placeholder string usage flagged by scan keyword.
- **Why it breaks production:** This is a benign use of SQL placeholders, not a stub; no production gap.
- **Fix plan:** None required for functionality; keep for parameterized SQL safety.

## Attestation / Certification / Recommendations

### src/tensorguard/attestation_service/__init__.py
- **Location:** `attest_node`.
- **Finding:** Stub response (`"unattested"`).
- **Why it breaks production:** Attestation is a core security function.
- **Fix plan:** Implement real service or fail-closed when enabled.

### src/tensorguard/certification/__init__.py
- **Location:** `certify_artifact`.
- **Finding:** Stub response (`"certified": False`).
- **Why it breaks production:** Certification must be real or disabled.
- **Fix plan:** Implement real certification engine or gate off in production.

### src/tensorguard/recommend/__init__.py
- **Location:** `get_recommendations`.
- **Finding:** Stub empty list.
- **Why it breaks production:** Recommendation engine returns no data.
- **Fix plan:** Implement real recommendations or disable feature behind gate.

### src/tensorguard/agent/identity/attestation.py
- **Location:** `TPMSimulator` class.
- **Finding:** Software TPM simulator used for attestation.
- **Why it breaks production:** Simulated attestation claims are not hardware-backed.
- **Fix plan:** Rename to simulator module, gate behind explicit research/dev flag, and disable attested claims in production.

### src/tensorguard/identity/acme/challenges.py
- **Location:** DNS providers and `NotImplementedError` paths.
- **Finding:** DNS-01 handlers are stubbed or raise `NotImplementedError`.
- **Why it breaks production:** ACME DNS validation cannot complete.
- **Fix plan:** Implement providers or fail startup when DNS-01 is configured but unsupported.

### src/tensorguard/identity/ca/private_ca.py
- **Location:** stub comment for CA flow.
- **Finding:** Simplified stub in CA implementation.
- **Why it breaks production:** CA operations must be fully compliant and audited.
- **Fix plan:** Replace stub with real CA flow or gate feature in production.

### src/tensorguard/identity/scheduler.py
- **Location:** placeholder comment for Private CA flow.
- **Finding:** Placeholder flow logic.
- **Why it breaks production:** CA scheduling may omit required steps.
- **Fix plan:** Implement actual CA scheduling and validations.

## Crypto / PQC

### src/tensorguard/crypto/pqc/dilithium.py
- **Location:** module init and fallback code.
- **Finding:** Simulator fallback when liboqs missing.
- **Why it breaks production:** PQC security guarantees are void without real liboqs.
- **Fix plan:** Require liboqs in production when PQC enabled; fail-closed otherwise.

### src/tensorguard/crypto/pqc/kyber.py
- **Location:** module init and fallback code.
- **Finding:** Simulator fallback when liboqs missing.
- **Why it breaks production:** PQC security guarantees are void without real liboqs.
- **Fix plan:** Require liboqs in production when PQC enabled; fail-closed otherwise.

### src/tensorguard/crypto/pqc/__init__.py
- **Location:** module-level warning.
- **Finding:** Simulator mode warning and message.
- **Why it breaks production:** Simulator mode must be gated and disabled in production.
- **Fix plan:** Enforce production guardrails in startup validation.

## Benchmarks / Demo / Example Code in Production Paths

### benchmarks/production_benchmark.py
- **Location:** benchmark class methods.
- **Finding:** Mock demonstrations, simulated network latency, simulated aggregation.
- **Why it breaks production:** Benchmark code should not be in production runtime paths.
- **Fix plan:** Ensure benchmarks are excluded from production builds or moved to `benchmarks/` only.

### src/tensorguard/bench/cli.py
- **Location:** pipeline comment.
- **Finding:** UpdatePkg stub.
- **Why it breaks production:** Bench pipeline references stubbed behavior.
- **Fix plan:** Implement real pipeline or keep benchmarks out of production builds.

### src/tensorguard/bench/privacy/inversion.py
- **Location:** `_simulate_reconstruction` and usages.
- **Finding:** Simulated leakage and mock PSNR metrics.
- **Why it breaks production:** Privacy metrics are not real.
- **Fix plan:** Replace with real inversion analysis or keep in benchmark-only scope.

### src/tensorguard/bench/reporting.py
- **Location:** report template field `simulated_attack_psnr`.
- **Finding:** Simulated metric usage.
- **Why it breaks production:** Reporting should use real metrics.
- **Fix plan:** Replace with real metrics or isolate to benchmark-only builds.

### src/tensorguard/bench/compliance/evidence.py
- **Location:** evidence pack template.
- **Finding:** `sha256:mock...` placeholder hash.
- **Why it breaks production:** Evidence pack should contain real integrity hashes.
- **Fix plan:** Replace placeholder with computed hashes.

### src/tensorguard/bench/comprehensive_vla_bench.py
- **Location:** `_simulate_learning_dynamics`.
- **Finding:** Simulated learning dynamics.
- **Why it breaks production:** Benchmark-only logic in runtime.
- **Fix plan:** Keep benchmarks out of production builds.

### src/tensorguard/bench/continual_learning_experiment.py
- **Location:** `_simulate_task_performance` and jitter simulation.
- **Finding:** Simulated performance metrics.
- **Why it breaks production:** Simulations are not production metrics.
- **Fix plan:** Keep benchmark-only or replace with real evaluation.

### src/tensorguard/bench/production_demo.py
- **Location:** `FastUMISimulator` usage.
- **Finding:** Simulator-driven demos in production namespace.
- **Why it breaks production:** Demo simulator should not be in production paths.
- **Fix plan:** Move to `examples/` or gate behind demo-only feature flag.

### scripts/demo_moai_flow.py
- **Location:** export call and comments.
- **Finding:** Mock model path and mock weights.
- **Why it breaks production:** Demo scripts must not be shipped in production builds.
- **Fix plan:** Keep under `scripts/` or move to `examples/` and exclude from distribution.

### scripts/verify_hardened_pipeline.py
- **Location:** mock pipeline stage functions.
- **Finding:** Mock capture/embed/gate/peft/shield functions.
- **Why it breaks production:** Verification should use real pipeline components.
- **Fix plan:** Keep in test/dev scope or replace with real pipeline validation.

### src/tensorguard/moai/exporter.py
- **Location:** `export`.
- **Finding:** Generates mock weights.
- **Why it breaks production:** Exporter should read real model weights.
- **Fix plan:** Implement real export logic or gate under demo mode.

### src/tensorguard/moai/keys.py
- **Location:** `load_public_context` docstring.
- **Finding:** Placeholder eval keys note.
- **Why it breaks production:** Placeholder keys are insecure.
- **Fix plan:** Load real keys from vault/secret store.

### src/tensorguard/agent/ml/worker.py
- **Location:** pruning logic.
- **Finding:** Logs when skipping operations on mock model dict.
- **Why it breaks production:** Indicates dependency on mock model dicts.
- **Fix plan:** Require real model objects in production flow.

### src/tensorguard/agent/ml/manager.py
- **Location:** adapter selection.
- **Finding:** Stub note in comment.
- **Why it breaks production:** Adapter selection should be deterministic and implemented.
- **Fix plan:** Implement real adapter registry and selection.

### src/tensorguard/agent/identity/work_poller.py
- **Location:** work poll loop.
- **Finding:** Simulates success for MVP.
- **Why it breaks production:** Poller should reflect real work completion.
- **Fix plan:** Implement real platform communication and acknowledgements.

### src/tensorguard/agent/network/defense/front.py
- **Location:** comment referencing mock systems.
- **Finding:** Behavior tied to benchmarks.
- **Why it breaks production:** Production logic should not be benchmark-specific.
- **Fix plan:** Separate benchmark logic from production defense module.

### src/tensorguard/tgsp/cli.py
- **Location:** key generation comments.
- **Finding:** Simulator key generation messaging.
- **Why it breaks production:** Suggests simulator workflows in core CLI.
- **Fix plan:** Gate simulator behavior to dev/test, require real keys in prod.

### src/tensorguard/tgsp/format.py
- **Location:** secret key derivation comment.
- **Finding:** Simulator key behavior note.
- **Why it breaks production:** Indicates simulator-based key derivation.
- **Fix plan:** Ensure production keys are derived securely and simulator mode is gated.

### src/tensorguard/enablement/robotics/ros2/time_sync.py
- **Location:** `TimeSync` stub.
- **Finding:** Stub yields empty bundles.
- **Why it breaks production:** Time sync data missing.
- **Fix plan:** Implement real ROS2 time sync or gate off in production.

### src/tensorguard/enablement/integrations/adapters.py
- **Location:** adapter base.
- **Finding:** `NotImplementedError` in provider.
- **Why it breaks production:** Base adapter can be configured but fails at runtime.
- **Fix plan:** Implement adapters or enforce provider registry that fails early.

### examples/demo_n2he_tgsp_federation.py
- **Location:** aggregation step.
- **Finding:** Placeholder update aggregation.
- **Why it breaks production:** Example-only behavior.
- **Fix plan:** Keep in examples and exclude from production builds.

### examples/demo_moai_tgsp_integration.py
- **Location:** mock weights and keys.
- **Finding:** Demo-only mock weights and keys.
- **Why it breaks production:** Example-only behavior.
- **Fix plan:** Keep in examples and exclude from production builds.

### src/artifacts_storage/*/report.json
- **Location:** JSON report metrics.
- **Finding:** `simulated_attack_psnr` values in stored artifacts.
- **Why it breaks production:** Demo artifact data should not be shipped as production artifacts.
- **Fix plan:** Remove demo artifacts from production build and enforce artifact retention policies.

## Frontend / UI (Mock Data + Placeholders)

### frontend/src/components/AuditTrail.vue
- **Location:** comment.
- **Finding:** Fallback to mock data when backend not available.
- **Why it breaks production:** UI may show stale or fake audit data.
- **Fix plan:** Require backend connectivity or disable view in production without data.

### frontend/src/stores/peft.js
- **Location:** `simulateTraining` and usages.
- **Finding:** Simulated training flow.
- **Why it breaks production:** UI should reflect real training jobs.
- **Fix plan:** Integrate with `/api/v1/peft/runs` or disable feature in production.

### frontend/src/components/EvalArena.vue
- **Location:** UI placeholder text.
- **Finding:** Input placeholder strings.
- **Why it breaks production:** UI placeholders are acceptable but should reflect real examples.
- **Fix plan:** Update placeholder content to production-ready guidance if needed.

### frontend/src/components/flow/NodePalette.vue
- **Location:** search input placeholder.
- **Finding:** Placeholder text.
- **Why it breaks production:** Cosmetic; not a blocker but should be vetted for UX.
- **Fix plan:** Review placeholder content during UI hardening.

## Tests / QA / Docs (Mock Usage)

### tests/peft/test_run_simulated.py
- **Location:** simulated run tests.
- **Finding:** Tests explicitly validate simulated workflows.
- **Why it breaks production:** Tests codify simulator expectations.
- **Fix plan:** Replace with real workflow tests or mark as dev-only.

### tests/peft/test_catalog.py
- **Location:** connector simulated status test.
- **Finding:** Tests simulate connector status.
- **Why it breaks production:** Encourages simulated connectors in production.
- **Fix plan:** Update tests to require real integration health checks.

### tests/unit/test_identity.py
- **Location:** mocking in tests.
- **Finding:** Use of `unittest.mock`.
- **Why it breaks production:** Acceptable in tests but note usage for scan completeness.
- **Fix plan:** Keep tests; ensure production paths are not mocked.

### tests/unit/test_tgsp_core.py
- **Location:** comment referencing mocking verification.
- **Finding:** Mocking in tests.
- **Why it breaks production:** Acceptable in tests; indicates areas to harden with integration tests.
- **Fix plan:** Add integration tests with real signatures.

### tests/unit/test_tgsp_full.py
- **Location:** `unittest.mock` usage.
- **Finding:** Mocking in tests.
- **Why it breaks production:** Acceptable in tests; should be complemented with integration tests.
- **Fix plan:** Add integration coverage.

### tests/unit/test_utils_standardization.py
- **Location:** `unittest.mock` usage.
- **Finding:** Mocked HTTP client.
- **Why it breaks production:** Acceptable in tests; no production impact.
- **Fix plan:** Add integration test for real HTTP client if needed.

### tests/unit/test_rtpl.py
- **Location:** skipped test.
- **Finding:** simulate_defense test skipped.
- **Why it breaks production:** Gaps in test coverage for defense logic.
- **Fix plan:** Replace with real defense test or re-enable with proper dependencies.

### tests/security/test_security_hardening.py
- **Location:** mock container reader.
- **Finding:** Uses mock for security test.
- **Why it breaks production:** Acceptable in tests; ensure runtime enforcement exists.
- **Fix plan:** Add runtime startup validation tests.

### tests/security/test_platform_security.py
- **Location:** mock TGSP read.
- **Finding:** Mocked TGSP header reading.
- **Why it breaks production:** Acceptable for unit tests; add integration tests.
- **Fix plan:** Add real TGSP verification test.

### tests/test_edge_resilience.py
- **Location:** mock server usage.
- **Finding:** Mock HTTP responses.
- **Why it breaks production:** Acceptable in tests; integration coverage needed.
- **Fix plan:** Add integration test against real server.

### tests/integration/test_fedmoe_system.py
- **Location:** mock key usage.
- **Finding:** In-memory mock key use.
- **Why it breaks production:** Integration tests should use realistic key handling.
- **Fix plan:** Use test fixtures with real keys.

### tests/integration/test_tgsp_platform.py
- **Location:** mock fleet and signatures.
- **Finding:** Mocked auth and signature.
- **Why it breaks production:** Integration tests should validate actual auth flow.
- **Fix plan:** Add real auth fixture and signature validation.

### tests/integration/test_bench_evidence.py
- **Location:** `MagicMock` usage.
- **Finding:** Mocked evidence dependencies.
- **Why it breaks production:** Benchmark tests are fine but should not gate production readiness.
- **Fix plan:** Keep in bench scope or replace with real evidence generation test.

### tests/integration/test_platform_api.py
- **Location:** mock TGSP read.
- **Finding:** Mocked read of TGSP header.
- **Why it breaks production:** Integration tests should validate actual TGSP parsing.
- **Fix plan:** Add real parsing integration test.

### tests/integration/test_fastumi_fedmoe.py
- **Location:** simulator usage.
- **Finding:** `FastUMISimulator` in integration test.
- **Why it breaks production:** Simulators in integration tests mask real behavior.
- **Fix plan:** Replace with real environment or gate to dev-only.

### qa_simulation_600.py
- **Location:** simulation user data.
- **Finding:** mock user password.
- **Why it breaks production:** QA simulation data should not ship in production.
- **Fix plan:** Move to QA-only scope or delete from production build.

### docs/PEFT_STUDIO.md
- **Location:** simulation mode docs.
- **Finding:** documentation references simulation mode.
- **Why it breaks production:** OK for docs, but must be gated in code.
- **Fix plan:** Update to clarify dev-only scope.

### docs/SYSTEM_AUDIT_PRD.md
- **Location:** multiple issues listing mock components.
- **Finding:** notes about mock data and simulated checks.
- **Why it breaks production:** Documents known gaps; must be addressed in code.
- **Fix plan:** Track and close listed issues.

### DEPLOYMENT_V2.md
- **Location:** environment variable examples.
- **Finding:** `TG_SECRET_KEY` mention (documentation).
- **Why it breaks production:** Documentation-only; not a code gap, but must align with fail-closed enforcement.
- **Fix plan:** Ensure docs match production startup validation behavior.

### README.md
- **Location:** feature policy table.
- **Finding:** Mentions simulator blocking in production.
- **Why it breaks production:** Documentation-only; must be enforced in code.
- **Fix plan:** Implement and validate simulator blocking in production.

## Docker / Build

### docker/platform/Dockerfile
- **Location:** build steps.
- **Finding:** Previously referenced missing `requirements.txt`.
- **Why it breaks production:** Docker build fails or uses undeclared deps.
- **Fix plan:** Resolved by switching to pinned lockfiles (`requirements.lock`) and pyproject install.

### docker/bench/Dockerfile
- **Location:** build steps.
- **Finding:** Previously referenced missing `requirements.txt`.
- **Why it breaks production:** Docker build fails or uses undeclared deps.
- **Fix plan:** Resolved by switching to pinned lockfiles (`requirements-bench.lock`) and pyproject install.

### Dockerfile.moai-serve
- **Location:** `ENV MOAI_BACKEND=mock`.
- **Finding:** Explicit mock backend setting.
- **Why it breaks production:** Forces mock backend in runtime.
- **Fix plan:** Remove mock backend or gate behind dev-only config.

## Known Hotspots (explicitly required)

- `examples/vercel_mock/api/index.py` (Vercel mock) — see API section above.
- `src/tensorguard/server/aggregator.py` (Flower stub) — see Aggregation section above.
- `src/tensorguard/attestation_service/__init__.py` (stub) — see Attestation section above.
- `src/tensorguard/certification/__init__.py` (stub) — see Attestation section above.
- `src/tensorguard/recommend/__init__.py` (stub) — see Attestation section above.
- `src/tensorguard/agent/identity/attestation.py` (TPM simulator) — see Attestation section above.
- `src/tensorguard/serving/backend.py` (NativeBackend NotImplemented) — see Server section above.
- `src/tensorguard/platform/auth.py` (SECRET_KEY fallback) — see API section above.
- `migrate_db.py` (ad-hoc migration) — see DB section below.
- `docker/*/Dockerfile` referencing missing requirements.txt — see Docker section above.
- `src/tensorguard/core/client.py` (mock payload + ShieldConfig import) — see Core section above.

## Database

### migrate_db.py
- **Location:** module script.
- **Finding:** Ad-hoc migration with inline SQL.
- **Why it breaks production:** Migrations are not versioned or repeatable.
- **Fix plan:** Replace with Alembic migrations and CI validation.
