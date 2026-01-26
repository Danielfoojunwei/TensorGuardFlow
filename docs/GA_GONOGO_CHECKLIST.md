# TensorGuard GA Go/No-Go Checklist

## Pre-Release Verification

This checklist must be completed before any GA (General Availability) release.
All items must pass for a GO decision.

---

## 1. Installation & Build

- [ ] `pip install -e ".[dev]"` completes without errors
- [ ] `python -m compileall -q src` passes (no syntax errors)
- [ ] `cd frontend && npm ci && npm run build` produces `dist/`
- [ ] `docker build -f docker/platform/Dockerfile .` succeeds
- [ ] Version is consistent: `python -m tensorguard.platform.version --check`

**Verification Commands:**
```bash
pip install -e ".[dev]"
python -m compileall -q src
cd frontend && npm ci && npm run build && cd ..
docker build -f docker/platform/Dockerfile .
PYTHONPATH=src python -m tensorguard.platform.version --check
```

---

## 2. Test Suite

- [ ] All unit tests pass: `pytest tests/unit/ -v`
- [ ] All integration tests pass: `pytest tests/integration/ -v`
- [ ] Security gate tests pass: `pytest tests/security/ -v`
- [ ] Coverage >= 70%: `pytest --cov=src/tensorguard --cov-fail-under=70`
- [ ] Frontend tests pass: `cd frontend && npm run test`

**Verification Commands:**
```bash
PYTHONPATH=src pytest tests/ --cov=src/tensorguard --cov-report=term --cov-fail-under=70 -v
cd frontend && npm run test && cd ..
```

---

## 3. Health Endpoints

- [ ] `/healthz` returns 200 (process alive)
- [ ] `/readyz` returns 200 when DB is up and migrations current
- [ ] `/readyz` returns 503 with actionable error when DB is down
- [ ] `/health` returns detailed status with version
- [ ] `/metrics` returns Prometheus-format metrics

**Verification Commands:**
```bash
# Start server in background
PYTHONPATH=src python -m uvicorn tensorguard.platform.main:app --host 0.0.0.0 --port 8000 &
sleep 5

# Test endpoints
curl -s http://localhost:8000/healthz | jq .
curl -s http://localhost:8000/readyz | jq .
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:8000/metrics | head -20

# Cleanup
kill %1
```

---

## 4. Observability

- [ ] Request logging includes request_id
- [ ] Secrets are redacted in logs (test with Authorization header)
- [ ] `/metrics` shows `tensorguard_requests_total`
- [ ] `/metrics` shows `tensorguard_request_latency_seconds`
- [ ] OpenTelemetry traces appear when `TG_ENABLE_OTEL=true`

**Verification Commands:**
```bash
# Check metrics (requires running server)
curl -s http://localhost:8000/metrics | grep tensorguard_

# Test log redaction
curl -s -H "Authorization: Bearer test_secret_token" http://localhost:8000/api/v1/health
# Verify logs show "[REDACTED]" not the actual token
```

---

## 5. Security

- [ ] `TG_SECRET_KEY` is required in production mode
- [ ] `TG_VAULT_MASTER_KEY` is required when vault encryption enabled
- [ ] CORS rejects unknown origins when `TG_ALLOWED_ORIGINS` is empty
- [ ] Rate limiting returns 429 when exceeded
- [ ] Security headers present (X-Frame-Options, CSP, etc.)
- [ ] No secrets in repository: `grep -r "SECRET_KEY" --include="*.py" | grep -v "os.getenv\|environ"`

**Verification Commands:**
```bash
# Verify no hardcoded secrets
grep -r "SECRET_KEY" src/ --include="*.py" | grep -v "os.getenv\|environ\|TG_SECRET_KEY"

# Test production gate
TG_ENVIRONMENT=production python -c "from tensorguard.platform.main import app" 2>&1 || echo "Expected to fail without TG_SECRET_KEY"

# Verify security headers (requires running server)
curl -s -I http://localhost:8000/health | grep -i "x-frame\|x-content-type\|strict-transport"
```

---

## 6. Database

- [ ] `alembic current` shows latest revision
- [ ] `alembic upgrade head` runs without errors
- [ ] Doctor DB check passes: `python -m tensorguard.platform.doctor --db`
- [ ] Connection pool status reported in `/health`

**Verification Commands:**
```bash
alembic current
alembic heads
PYTHONPATH=src python -m tensorguard.platform.doctor --db
```

---

## 7. Vault

- [ ] Vault encryption works: keys saved with `TG_VAULT_MASTER_KEY` are encrypted
- [ ] Vault export works: `python -m tensorguard.core.keys export --out test.json`
- [ ] Vault import works: `python -m tensorguard.core.keys import --in test.json`
- [ ] Doctor vault check passes: `python -m tensorguard.platform.doctor --vault`

**Verification Commands:**
```bash
export TG_VAULT_MASTER_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
PYTHONPATH=src python -m tensorguard.core.keys status
PYTHONPATH=src python -m tensorguard.core.keys export --out /tmp/vault_test.json
rm /tmp/vault_test.json
```

---

## 8. Docker & Deployment

- [ ] `docker-compose up` starts all services
- [ ] Services pass health checks in compose
- [ ] `docker-compose down` shuts down cleanly
- [ ] Production profile works: `docker-compose --profile prod up`

**Verification Commands:**
```bash
docker-compose up -d
sleep 10
docker-compose ps
curl -s http://localhost:8000/healthz
docker-compose down
```

---

## 9. Demo Mode Isolation

- [ ] `TG_DEMO_MODE` defaults to `false`
- [ ] Demo mode is rejected in production: `TG_ENVIRONMENT=production TG_DEMO_MODE=true` fails
- [ ] Demo data does not leak into production mode

**Verification Commands:**
```bash
# Verify default
python -c "import os; print('Demo mode:', os.getenv('TG_DEMO_MODE', 'false'))"

# Verify production rejects demo mode
TG_ENVIRONMENT=production TG_DEMO_MODE=true python -c "
from tensorguard.utils.production_gates import is_demo_mode, is_production
if is_production() and is_demo_mode():
    raise Exception('Demo mode should not be allowed in production')
print('Production gates working correctly')
"
```

---

## 10. Documentation

- [ ] `docs/PRODUCTION_RUNBOOK.md` exists and is current
- [ ] `docs/DB_RUNBOOK.md` exists and is current
- [ ] `docs/SECURITY.md` exists
- [ ] README has quickstart instructions
- [ ] `docs/GA_FIX_LOG.md` has recent changes

**Verification:**
```bash
ls -la docs/PRODUCTION_RUNBOOK.md docs/DB_RUNBOOK.md docs/SECURITY.md
head -20 README.md
```

---

## Final Commands (All Must Pass)

```bash
# 1. Syntax check
python -m compileall -q src

# 2. Install
pip install -e ".[dev]"

# 3. Tests
PYTHONPATH=src pytest -q --cov=src/tensorguard --cov-fail-under=70

# 4. Frontend build
cd frontend && npm ci && npm run build && npm run test && cd ..

# 5. Docker build
docker build -f docker/platform/Dockerfile .

# 6. Start services
docker-compose up -d
sleep 10

# 7. Health checks
curl -f http://localhost:8000/healthz
curl -f http://localhost:8000/readyz

# 8. Metrics
curl -s http://localhost:8000/metrics | head -10

# 9. Cleanup
docker-compose down
```

---

## Decision

| Criteria | Status |
|----------|--------|
| Installation | [ ] GO / [ ] NO-GO |
| Tests | [ ] GO / [ ] NO-GO |
| Health | [ ] GO / [ ] NO-GO |
| Observability | [ ] GO / [ ] NO-GO |
| Security | [ ] GO / [ ] NO-GO |
| Database | [ ] GO / [ ] NO-GO |
| Vault | [ ] GO / [ ] NO-GO |
| Docker | [ ] GO / [ ] NO-GO |
| Demo Isolation | [ ] GO / [ ] NO-GO |
| Documentation | [ ] GO / [ ] NO-GO |

**Final Decision:** [ ] **GO** / [ ] **NO-GO**

**Approver:** ______________________

**Date:** ______________________

---

## Post-Release Verification

After deployment, verify:

- [ ] `/readyz` returns 200 in production
- [ ] No error spikes in monitoring
- [ ] Authentication working for users
- [ ] Key operations successful
- [ ] Demo mode flag is OFF
