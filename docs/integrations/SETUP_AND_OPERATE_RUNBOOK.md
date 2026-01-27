# TensorGuardFlow Setup & Operations Runbook

> **Document Version**: 1.0.0
> **Last Updated**: 2026-01-27
> **Status**: Production Reference

## Overview

This runbook provides step-by-step procedures for setting up and operating TensorGuardFlow integrations. It covers the complete lifecycle from initial setup through daily operations, incident response, and compliance reporting.

---

## Table of Contents

1. [Day 0: Initial Setup](#day-0-initial-setup)
2. [Day 1: First Route Creation](#day-1-first-route-creation)
3. [Daily Operations](#daily-operations)
4. [Incident Response](#incident-response)
5. [Compliance & Audit](#compliance--audit)
6. [Portability & Handoff](#portability--handoff)
7. [Maintenance Procedures](#maintenance-procedures)
8. [Troubleshooting Guide](#troubleshooting-guide)

---

## Day 0: Initial Setup

### Prerequisites

Before starting, ensure you have:

- [ ] TensorGuardFlow deployed and accessible
- [ ] Admin credentials for TGF dashboard
- [ ] Cloud provider credentials (AWS/GCP/Azure as needed)
- [ ] KMS keys provisioned in your cloud provider
- [ ] Network access to data sources
- [ ] Container registry access (for training images)

### Step 1: Verify TGF Installation

```bash
# Check TGF service health
curl -s https://your-tgf-instance/api/v1/status/health | jq

# Expected output:
{
  "status": "healthy",
  "version": "1.x.x",
  "components": {
    "database": "ok",
    "cache": "ok",
    "api": "ok"
  }
}
```

### Step 2: Configure Data Source Integration

#### Option A: AWS S3

```bash
# Via CLI
tgf integrations configure \
  --category data \
  --provider aws_s3 \
  --config '{
    "bucket": "my-training-data",
    "prefix": "datasets/",
    "region": "us-west-2"
  }'

# Via API
curl -X POST https://your-tgf-instance/api/v1/integrations/configure \
  -H "Authorization: Bearer $TGF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "data",
    "provider": "aws_s3",
    "config": {
      "bucket": "my-training-data",
      "prefix": "datasets/",
      "region": "us-west-2"
    }
  }'
```

#### Option B: Google Cloud Storage

```bash
tgf integrations configure \
  --category data \
  --provider gcs \
  --config '{
    "bucket": "my-training-data",
    "prefix": "datasets/",
    "project_id": "my-gcp-project"
  }'
```

#### Option C: Local Filesystem

```bash
tgf integrations configure \
  --category data \
  --provider local_fs \
  --config '{
    "base_path": "/data/training",
    "glob_pattern": "**/*.jsonl"
  }'
```

### Step 3: Configure Training Execution

#### Option A: Kubernetes

```bash
tgf integrations configure \
  --category training \
  --provider kubernetes \
  --config '{
    "namespace": "ml-training",
    "image": "your-registry/peft-trainer:latest",
    "gpu_count": 1,
    "cpu_request": "4",
    "memory_request": "16Gi"
  }'
```

#### Option B: Local GPU

```bash
tgf integrations configure \
  --category training \
  --provider cuda_local \
  --config '{
    "device_ids": [0],
    "mixed_precision": true,
    "memory_fraction": 0.9
  }'
```

### Step 4: Configure KMS for Signing

#### AWS KMS

```bash
tgf integrations configure \
  --category trust \
  --provider aws_kms \
  --config '{
    "key_id": "alias/tgf-adapter-signing",
    "region": "us-west-2",
    "signing_algorithm": "RSASSA_PSS_SHA_256"
  }'
```

#### HashiCorp Vault

```bash
tgf integrations configure \
  --category trust \
  --provider vault_transit \
  --config '{
    "vault_addr": "https://vault.example.com:8200",
    "transit_mount": "transit",
    "key_name": "tgf-signing"
  }'
```

### Step 5: Configure Serving Integration (Optional)

#### vLLM

```bash
tgf integrations configure \
  --category serving \
  --provider vllm \
  --config '{
    "base_model": "meta-llama/Llama-3.1-8B",
    "tensor_parallel_size": 1,
    "max_model_len": 4096
  }'
```

### Step 6: Configure Metrics Sink (Optional)

#### MLflow

```bash
tgf integrations configure \
  --category tracking \
  --provider mlflow \
  --config '{
    "tracking_uri": "https://mlflow.example.com",
    "experiment_name": "tgf-adapters"
  }'
```

### Step 7: Run Health Checks

```bash
# Check all integrations
tgf integrations healthcheck --all

# Via API
curl -X POST https://your-tgf-instance/api/v1/integrations/healthcheck \
  -H "Authorization: Bearer $TGF_TOKEN"
```

**Expected Output:**
```json
{
  "integrations": [
    {
      "id": "aws-s3-data",
      "status": "OK",
      "latency_ms": 120,
      "message": "Bucket accessible"
    },
    {
      "id": "k8s-training",
      "status": "OK",
      "latency_ms": 80,
      "message": "Cluster reachable"
    },
    {
      "id": "aws-kms-signing",
      "status": "OK",
      "latency_ms": 100,
      "message": "Key accessible"
    }
  ],
  "overall": "HEALTHY"
}
```

### Step 8: View Integration Topology

```bash
# Via CLI
tgf integrations topology

# Via API
curl https://your-tgf-instance/api/v1/integrations/topology \
  -H "Authorization: Bearer $TGF_TOKEN" | jq
```

### Step 9: Enable N2HE Privacy Mode (Optional)

```bash
tgf integrations configure \
  --category trust \
  --provider n2he \
  --config '{
    "enabled": true,
    "encryption_mode": "FULL",
    "receipt_generation": true,
    "safe_logging": true
  }'
```

---

## Day 1: First Route Creation

### Step 1: Define Route Configuration

```yaml
# route-config.yaml
route_key: customer-support-v1
description: "Customer support assistant fine-tuning"
base_model: meta-llama/Llama-3.1-8B

data_source:
  type: aws_s3
  config:
    bucket: my-training-data
    prefix: customer-support/

training:
  method: lora
  config:
    r: 16
    lora_alpha: 32
    target_modules: ["q_proj", "v_proj"]
    learning_rate: 2e-4
    num_epochs: 3

gates:
  max_forgetting: 0.05
  min_primary_metric: 0.85
  min_eval_samples: 100

channels:
  candidate:
    auto_create: true
  stable:
    require_approval: true
```

### Step 2: Create the Route

```bash
# Via CLI
tgf routes create -f route-config.yaml

# Via API
curl -X POST https://your-tgf-instance/api/v1/routes \
  -H "Authorization: Bearer $TGF_TOKEN" \
  -H "Content-Type: application/json" \
  -d @route-config.json
```

**Expected Response:**
```json
{
  "route_key": "customer-support-v1",
  "status": "created",
  "channels": {
    "candidate": null,
    "stable": null
  },
  "integrations": {
    "data": "aws-s3-data",
    "training": "k8s-training",
    "registry": "tgf-internal",
    "signing": "aws-kms-signing"
  }
}
```

### Step 3: Verify Route Health

```bash
tgf routes health customer-support-v1
```

**Expected Output:**
```
Route: customer-support-v1
Status: READY

Data Source:
  ✓ S3 bucket accessible
  ✓ 1,250 training samples found
  ✓ 200 eval samples found

Training:
  ✓ Kubernetes cluster reachable
  ✓ GPU quota available

Gates:
  ✓ Forgetting threshold: 0.05
  ✓ Primary metric threshold: 0.85

Signing:
  ✓ KMS key accessible
  ✓ Sign/verify operations working
```

### Step 4: Trigger First Training Run

```bash
# Start training
tgf routes run customer-support-v1

# Monitor progress
tgf runs watch customer-support-v1
```

### Step 5: Review Results and Promote

```bash
# View run results
tgf runs show customer-support-v1 --latest

# If gates pass, promote to stable
tgf routes promote customer-support-v1 \
  --from candidate \
  --to stable \
  --reason "Initial production deployment"
```

### Step 6: Generate Serving Pack

```bash
# Generate vLLM config
tgf export customer-support-v1 \
  --target vllm \
  --output ./serving-pack/

# Output files:
# ./serving-pack/vllm-config.yaml
# ./serving-pack/adapter-ref.json
# ./serving-pack/README.md
```

### Step 7: Configure Runtime to Use /resolve

In your vLLM configuration:

```python
# vllm_tgf_integration.py
import httpx

TGF_RESOLVE_URL = "https://your-tgf-instance/tgflow/resolve"

async def get_current_adapter(route_key: str) -> dict:
    """Fetch current adapter from TGF."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TGF_RESOLVE_URL,
            json={
                "route_key": route_key,
                "channel": "stable"
            },
            headers={"Authorization": f"Bearer {TGF_TOKEN}"}
        )
        return response.json()

# Response:
# {
#   "adapter_id": "adpt_abc123",
#   "adapter_uri": "s3://adapters/customer-support/v1.0.0/",
#   "tgsp_manifest_uri": "s3://adapters/customer-support/v1.0.0/manifest.tgsp",
#   "signature_status": "VERIFIED"
# }
```

---

## Daily Operations

### Morning Checklist

1. **Check Integration Health**
   ```bash
   tgf integrations status
   ```
   Look for any WARN or FAIL statuses.

2. **Review Route Health**
   ```bash
   tgf routes list --status
   ```
   Check for any unhealthy routes.

3. **Review Pending Promotions**
   ```bash
   tgf routes pending-promotions
   ```
   Review and approve/reject as needed.

4. **Check Overnight Runs**
   ```bash
   tgf runs list --since yesterday --status failed
   ```
   Investigate any failures.

### Monitoring Route Health

```bash
# Dashboard URL
open https://your-tgf-instance/dashboard

# CLI continuous monitoring
tgf routes watch customer-support-v1

# API polling
while true; do
  curl -s https://your-tgf-instance/api/v1/routes/customer-support-v1/metrics | jq
  sleep 60
done
```

### Approving Promotions

```bash
# View candidate details
tgf routes show customer-support-v1 --channel candidate

# Check gate results
tgf gates show customer-support-v1 --run latest

# Approve promotion
tgf routes promote customer-support-v1 \
  --from candidate \
  --to stable \
  --approver "your-email@example.com" \
  --reason "Gates passed, QA approved"
```

### Scheduled Updates

Set up automated training triggers:

```bash
# Via cron or scheduler
0 2 * * * tgf routes run customer-support-v1 --if-novel

# The --if-novel flag checks for data novelty before running
```

---

## Incident Response

### Scenario 1: Production Regression Detected

**Symptoms**: Users report degraded model quality

**Immediate Actions:**

```bash
# 1. Identify current adapter
tgf routes show customer-support-v1 --channel stable

# 2. Check recent promotions
tgf routes history customer-support-v1 --limit 5

# 3. IMMEDIATE ROLLBACK
tgf routes rollback customer-support-v1 \
  --reason "Production regression - user reports" \
  --notify ops@example.com

# 4. Verify rollback
tgf routes show customer-support-v1 --channel stable
# Should show previous adapter version

# 5. Check runtime picked up change
curl https://your-tgf-instance/tgflow/resolve \
  -d '{"route_key": "customer-support-v1", "channel": "stable"}'
```

**Investigation:**

```bash
# 6. Quarantine problematic adapter
tgf adapters quarantine adpt_problematic123 \
  --reason "Investigation - production regression"

# 7. Export incident evidence
tgf incidents export \
  --route customer-support-v1 \
  --time-range "2026-01-27T00:00:00Z/2026-01-27T12:00:00Z" \
  --output incident-evidence.zip

# 8. Review training run that produced bad adapter
tgf runs show run_abc123 --full
```

### Scenario 2: Integration Failure

**Symptoms**: Health check shows FAIL status

**Immediate Actions:**

```bash
# 1. Identify failed integration
tgf integrations status

# Output:
# aws-s3-data         OK     120ms
# k8s-training        FAIL   timeout
# aws-kms-signing     OK     100ms

# 2. Get detailed error
tgf integrations diagnose k8s-training

# 3. Check if routes are affected
tgf routes affected-by k8s-training

# 4. If critical, switch to alternative
tgf integrations failover k8s-training --to local-gpu
```

**Troubleshooting Steps:**

```bash
# Check Kubernetes connectivity
kubectl cluster-info

# Check TGF service account permissions
kubectl auth can-i create jobs -n ml-training

# Check network policies
kubectl get networkpolicies -n ml-training

# Test API access manually
kubectl run test-api --rm -it --image=curlimages/curl -- \
  curl -v https://kubernetes.default.svc
```

### Scenario 3: Signing Failure

**Symptoms**: Adapters not being signed, signature verification fails

**Immediate Actions:**

```bash
# 1. Check KMS status
tgf integrations diagnose aws-kms-signing

# 2. Test key directly
aws kms describe-key --key-id alias/tgf-adapter-signing

# 3. Test sign operation
echo "test" | base64 | aws kms sign \
  --key-id alias/tgf-adapter-signing \
  --signing-algorithm RSASSA_PSS_SHA_256 \
  --message-type RAW \
  --message fileb:///dev/stdin

# 4. If key issue, check IAM
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789:role/tgf-role \
  --action-names kms:Sign kms:Verify
```

### Scenario 4: N2HE Privacy Mode Issues

**Symptoms**: Privacy receipts not generated, safe logging violations

```bash
# 1. Check N2HE status
tgf integrations diagnose n2he-privacy

# 2. Verify receipt generation
tgf privacy test-receipt --route customer-support-v1

# 3. Check safe logging compliance
tgf privacy audit-logs --since yesterday

# 4. If violations found, enable strict mode
tgf integrations configure \
  --category trust \
  --provider n2he \
  --config '{"strict_mode": true, "block_on_violation": true}'
```

---

## Compliance & Audit

### Generating Audit Bundles

```bash
# Full audit export for a route
tgf audit export \
  --route customer-support-v1 \
  --time-range "2026-01-01/2026-03-31" \
  --framework SOC2 \
  --output audit-q1-2026.zip

# Contents:
# - evidence-chain.json
# - tgsp-manifests/
# - data-lineage.json
# - promotion-logs.json
# - signature-verifications.json
# - integration-topology-snapshots/
# - compliance-checklist.pdf
```

### Verifying Audit Bundle Integrity

```bash
# Verify bundle signature
tgf audit verify audit-q1-2026.zip

# Output:
# Bundle: audit-q1-2026.zip
# Signed: 2026-04-01T10:00:00Z
# Signer: arn:aws:kms:us-west-2:123456789:key/abc123
# Signature: VALID
# Contents: VERIFIED (847 files, no tampering detected)
```

### Compliance Frameworks

#### SOC2

```bash
tgf compliance check --framework soc2 --route customer-support-v1

# Output:
# SOC2 Compliance Check
# =====================
# CC6.1 Logical Access: PASS (RBAC enforced)
# CC6.6 System Operations: PASS (health checks active)
# CC6.7 Change Management: PASS (promotion approval required)
# CC7.2 System Monitoring: PASS (metrics exported)
# CC8.1 Change Management: PASS (evidence chain complete)
```

#### EU AI Act

```bash
tgf compliance check --framework eu-ai-act --route customer-support-v1

# Output:
# EU AI Act Compliance Check
# ==========================
# Art. 9 Risk Management: PASS (gates enforce quality)
# Art. 10 Data Governance: PASS (lineage tracked)
# Art. 11 Technical Documentation: PASS (TGSP manifests)
# Art. 12 Record Keeping: PASS (full audit trail)
# Art. 13 Transparency: PASS (adapter provenance available)
```

### Scheduled Compliance Reports

```bash
# Set up monthly compliance report
tgf compliance schedule \
  --framework SOC2 \
  --routes all \
  --frequency monthly \
  --notify compliance@example.com
```

---

## Portability & Handoff

### Exporting to Customer Stack

#### Kubernetes Deployment

```bash
# Generate complete K8s manifests
tgf export customer-support-v1 \
  --target kubernetes \
  --output ./k8s-deploy/

# Files generated:
# ./k8s-deploy/
#   ├── namespace.yaml
#   ├── configmap.yaml
#   ├── secret-template.yaml
#   ├── deployment.yaml
#   ├── service.yaml
#   ├── hpa.yaml
#   └── README.md

# Apply to cluster
kubectl apply -f ./k8s-deploy/
```

#### SageMaker Deployment

```bash
# Generate SageMaker configs
tgf export customer-support-v1 \
  --target sagemaker \
  --output ./sagemaker-deploy/

# Files generated:
# ./sagemaker-deploy/
#   ├── model-config.json
#   ├── endpoint-config.json
#   ├── create-model.sh
#   ├── create-endpoint.sh
#   └── README.md
```

#### vLLM Deployment

```bash
# Generate vLLM serving pack
tgf export customer-support-v1 \
  --target vllm \
  --output ./vllm-serve/

# Files generated:
# ./vllm-serve/
#   ├── vllm-config.yaml
#   ├── docker-compose.yaml
#   ├── adapter-ref.json
#   ├── resolve-integration.py
#   └── README.md
```

### Runtime /resolve Integration

```python
# resolve_integration.py
"""
TGF Resolve Integration for Runtime
"""
import httpx
import asyncio
from typing import Optional

class TGFResolver:
    def __init__(self, tgf_url: str, api_key: str):
        self.tgf_url = tgf_url.rstrip('/')
        self.api_key = api_key
        self._cache = {}
        self._cache_ttl = 60  # seconds

    async def resolve(
        self,
        route_key: str,
        channel: str = "stable",
        request_context: Optional[dict] = None
    ) -> dict:
        """Resolve current adapter for route."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.tgf_url}/tgflow/resolve",
                json={
                    "route_key": route_key,
                    "channel": channel,
                    "request_context": request_context or {}
                },
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            return response.json()

    async def resolve_cached(self, route_key: str, channel: str = "stable") -> dict:
        """Resolve with caching."""
        cache_key = f"{route_key}:{channel}"
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if (asyncio.get_event_loop().time() - entry['time']) < self._cache_ttl:
                return entry['data']

        result = await self.resolve(route_key, channel)
        self._cache[cache_key] = {
            'data': result,
            'time': asyncio.get_event_loop().time()
        }
        return result


# Usage in vLLM or other runtime
resolver = TGFResolver(
    tgf_url="https://your-tgf-instance",
    api_key=os.environ["TGF_API_KEY"]
)

# On startup or adapter refresh
adapter_info = await resolver.resolve_cached("customer-support-v1")
print(f"Loading adapter: {adapter_info['adapter_uri']}")
print(f"Signature: {adapter_info['signature_status']}")
```

---

## Maintenance Procedures

### Weekly Maintenance

#### Check Adapter Storage Usage

```bash
tgf adapters storage-report

# Output:
# Route                    Adapters  Size     Oldest
# customer-support-v1      12        4.2 GB   30 days
# product-recommendations  8         2.8 GB   45 days
# content-moderation       15        5.1 GB   60 days
# TOTAL                    35        12.1 GB
```

#### Clean Up Deprecated Adapters

```bash
# List deprecated adapters older than 30 days
tgf adapters list --channel deprecated --older-than 30d

# Archive to cold storage
tgf adapters archive --channel deprecated --older-than 30d --to s3://archive-bucket/

# Delete after archival
tgf adapters delete --channel deprecated --older-than 90d --archived-only
```

### Monthly Maintenance

#### Security Posture Assessment

```bash
tgf security assess

# Output:
# Security Assessment Report
# ==========================
#
# Signing:
#   ✓ All production adapters signed
#   ✓ KMS key rotation: 45 days until recommended
#   ✓ No unsigned adapters in stable channels
#
# Access Control:
#   ✓ RBAC policies enforced
#   ✓ No overprivileged service accounts
#   ⚠ 2 API keys older than 90 days (recommend rotation)
#
# Privacy:
#   ✓ N2HE enabled for all routes
#   ✓ Safe logging compliant
#   ✓ No PII detected in logs
#
# Overall Score: 95/100
```

#### Integration Health Trends

```bash
tgf integrations report --period 30d

# Output:
# Integration Health Report (Last 30 Days)
# ========================================
#
# aws-s3-data:
#   Uptime: 99.97%
#   Avg Latency: 115ms
#   Failures: 2 (both network transient)
#
# k8s-training:
#   Uptime: 99.85%
#   Avg Latency: 85ms
#   Failures: 5 (3 quota, 2 timeout)
#
# aws-kms-signing:
#   Uptime: 100%
#   Avg Latency: 98ms
#   Failures: 0
```

### Quarterly Maintenance

#### KMS Key Rotation

```bash
# Check key rotation status
tgf security kms-status

# If rotation needed:
# 1. Create new key
aws kms create-key --description "TGF Signing Key v2"

# 2. Configure TGF to use new key
tgf integrations configure \
  --category trust \
  --provider aws_kms \
  --config '{
    "key_id": "alias/tgf-signing-key-v2",
    "region": "us-west-2"
  }'

# 3. Re-sign critical adapters (optional)
tgf adapters resign --channel stable --all

# 4. Update verification to accept both keys during transition
tgf security key-transition start \
  --old-key alias/tgf-signing-key \
  --new-key alias/tgf-signing-key-v2 \
  --transition-period 30d

# 5. After transition, disable old key
tgf security key-transition complete
```

#### Disaster Recovery Test

```bash
# 1. Export current state
tgf dr export --output dr-backup.tar.gz

# 2. Spin up test environment
docker-compose -f docker-compose.dr-test.yml up -d

# 3. Restore state
tgf dr restore --input dr-backup.tar.gz --target http://localhost:8080

# 4. Verify restoration
tgf routes list --target http://localhost:8080
tgf integrations status --target http://localhost:8080

# 5. Test critical operations
tgf routes run customer-support-v1 --target http://localhost:8080 --dry-run

# 6. Clean up
docker-compose -f docker-compose.dr-test.yml down
```

---

## Troubleshooting Guide

### Common Issues

#### Issue: "Integration health check timeout"

**Cause**: Network connectivity or service unavailable

**Resolution**:
```bash
# 1. Check network connectivity
curl -v https://target-service-endpoint

# 2. Check DNS resolution
nslookup target-service.example.com

# 3. Check firewall rules
# (varies by environment)

# 4. Increase timeout if service is slow
tgf integrations configure \
  --id problematic-integration \
  --timeout-ms 30000
```

#### Issue: "Adapter signature verification failed"

**Cause**: Key mismatch, corrupted adapter, or wrong algorithm

**Resolution**:
```bash
# 1. Check signing key
tgf security key-info aws-kms-signing

# 2. Verify adapter manually
tgf adapters verify adpt_abc123

# 3. Re-sign if necessary
tgf adapters resign adpt_abc123

# 4. Check algorithm compatibility
tgf security signing-algorithms
```

#### Issue: "Training job export failed"

**Cause**: Schema validation error or missing configuration

**Resolution**:
```bash
# 1. Validate configuration
tgf export customer-support-v1 --target kubernetes --validate-only

# 2. Check error details
tgf export customer-support-v1 --target kubernetes --verbose

# 3. Fix configuration
tgf routes update customer-support-v1 -f fixed-config.yaml

# 4. Retry export
tgf export customer-support-v1 --target kubernetes --output ./fixed-export/
```

#### Issue: "Gate evaluation failed unexpectedly"

**Cause**: Eval data issues or threshold misconfiguration

**Resolution**:
```bash
# 1. Check gate configuration
tgf gates show customer-support-v1

# 2. Review eval data
tgf data validate --route customer-support-v1 --split eval

# 3. Check threshold appropriateness
tgf gates history customer-support-v1 --limit 10

# 4. Adjust thresholds if needed
tgf routes update customer-support-v1 \
  --gates '{"max_forgetting": 0.08, "min_primary_metric": 0.82}'
```

#### Issue: "N2HE receipts not generated"

**Cause**: Privacy mode misconfigured or disabled

**Resolution**:
```bash
# 1. Check N2HE status
tgf integrations diagnose n2he-privacy

# 2. Verify configuration
tgf integrations show n2he-privacy

# 3. Enable receipt generation
tgf integrations configure \
  --category trust \
  --provider n2he \
  --config '{"receipt_generation": true}'

# 4. Test receipt generation
tgf privacy test-receipt --route customer-support-v1
```

### Getting Help

```bash
# Built-in help
tgf --help
tgf routes --help
tgf integrations --help

# Diagnostic bundle for support
tgf support bundle --output support-bundle.zip

# Check documentation
open https://docs.tensorguardflow.io

# Community support
open https://github.com/tensorguardflow/tensorguardflow/discussions
```

---

## Quick Reference

### Essential Commands

```bash
# Health checks
tgf integrations status
tgf routes health <route_key>

# Route operations
tgf routes run <route_key>
tgf routes promote <route_key> --from candidate --to stable
tgf routes rollback <route_key>

# Export
tgf export <route_key> --target <platform> --output <dir>

# Audit
tgf audit export --route <route_key> --output <file>

# Troubleshooting
tgf integrations diagnose <integration_id>
tgf runs show <run_id> --full
```

### API Endpoints Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/integrations/topology` | GET | Get integration graph |
| `/api/v1/integrations/status` | GET | Get all integration statuses |
| `/api/v1/integrations/healthcheck` | POST | Trigger health checks |
| `/api/v1/routes` | POST | Create route |
| `/api/v1/routes/{key}/run` | POST | Start training run |
| `/api/v1/routes/{key}/promote` | POST | Promote adapter |
| `/api/v1/routes/{key}/rollback` | POST | Rollback to previous |
| `/tgflow/resolve` | POST | Resolve current adapter |
| `/api/v1/integrations/export` | POST | Generate export artifacts |
| `/api/v1/integrations/audit/export` | POST | Generate audit bundle |

---

## Related Documents

- [VALUE_CHAIN_JTBD.md](../product/VALUE_CHAIN_JTBD.md) - Value chain and JTBD definitions
- [STACK_REFERENCE.md](./STACK_REFERENCE.md) - External system inventory
- [INTEGRATION_TOPOLOGY_MODEL.md](./INTEGRATION_TOPOLOGY_MODEL.md) - Topology JSON schema
