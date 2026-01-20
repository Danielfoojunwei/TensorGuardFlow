# Changelog

All notable changes to TensorGuardFlow will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.0] - 2024-01-20

### Added
- **QA Infrastructure**: Comprehensive test harness for release certification
  - Automated regression testing with JUnit XML output
  - Security scanning (pip-audit, npm audit, gitleaks, trivy)
  - Performance smoke tests for telemetry ingest throughput
  - Worker stability verification
  - Installation smoke tests for Docker lifecycle
  - E2E stability runs to detect flaky tests
- **Customer Documentation**: Release-ready documentation suite
  - Installation guide for Docker Desktop deployment
  - Administrator guide for fleet management and operations
  - Support runbook for troubleshooting and diagnostics
  - 45-item manual QA checklist
- **Frontend Testing**: Complete frontend test infrastructure
  - Vitest unit tests for API services and components
  - Playwright E2E tests for onboarding, fleet management, and telemetry
  - ESLint configuration for code quality
- **Diagnostics Collection**: Automated diagnostic bundle generation
  - System information collection
  - Log aggregation and error extraction
  - Health check results
  - Sanitized configuration export

### Changed
- Improved test isolation with in-memory SQLite for integration tests
- Enhanced audit logging with comprehensive test coverage
- Updated Docker Compose configuration for better health checks

### Security
- Added security assertion tests for endpoint protection
- Implemented gitleaks secret scanning in CI
- Container image scanning with trivy
- Dependency vulnerability scanning for Python and Node.js

### Documentation
- Added `/docs/customer_install.md` - Customer installation guide
- Added `/docs/customer_admin_guide.md` - Administrator operations guide
- Added `/docs/support_runbook.md` - Support engineer runbook
- Added `/docs/qa_manual_checklist.md` - Manual QA verification checklist

## [2.2.0] - 2024-01-15

### Added
- Post-quantum cryptography (PQC) support with liboqs integration
- TGSP secure package format for model distribution
- Agent and edge device diagnose mode
- Feature flags system for controlled rollout
- CI gates with E2E integration tests

### Changed
- Stabilized background worker for improved reliability
- Enhanced telemetry ingestion pipeline

### Fixed
- Worker crash recovery and automatic restart
- Memory leak in long-running telemetry processing

## [2.1.0] - 2024-01-10

### Added
- Fleet management with API key rotation
- Dashboard with real-time statistics
- Telemetry ingestion REST API
- User authentication with JWT tokens

### Changed
- Migrated from Flask to FastAPI for improved performance
- Updated Vue.js to 3.4.x

## [2.0.0] - 2024-01-01

### Added
- Initial release of TensorGuardFlow platform
- Single-tenant self-hosted deployment
- Docker Compose packaging
- Basic fleet device management
- Telemetry collection and visualization

---

For upgrade instructions, see the [Installation Guide](docs/customer_install.md).
For known issues and workarounds, see the [Release Notes](docs/release_notes.md).
