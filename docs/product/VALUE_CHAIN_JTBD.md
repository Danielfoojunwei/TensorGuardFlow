# TensorGuardFlow Value Chain & Jobs-to-be-Done (JTBD)

> **Document Version**: 1.0.0
> **Last Updated**: 2026-01-27
> **Status**: Production Reference

## Executive Summary

TensorGuardFlow (TGF) is a **Continuous PEFT Control Plane + Trust Layer** that enables AI Engineers to safely manage adapter lifecycles in production. TGF does NOT replace training platforms, serving infrastructure, or full observability stacks—instead, it **integrates with them** through exporters, contracts, and governance policies.

This document maps the complete value chain for AI Engineers working with fine-tuned LLMs, defines the Jobs-to-be-Done (JTBD) that TGF enables, and specifies operating processes for day-to-day operations.

---

## 1. Value Chain Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AI ENGINEER VALUE CHAIN                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐             │
│   │     C     │    │     D     │    │     E     │    │     F     │             │
│   │   DATA    │───▶│  TRAINING │───▶│   EVAL    │───▶│  SERVING  │             │
│   │  SOURCE   │    │ EXECUTION │    │ & RELEASE │    │ INFERENCE │             │
│   └───────────┘    └───────────┘    └───────────┘    └───────────┘             │
│        │                │                │                │                     │
│        │                │                │                │                     │
│        └────────────────┴────────────────┴────────────────┘                     │
│                                    │                                            │
│                                    ▼                                            │
│                         ┌─────────────────────┐                                 │
│                         │         G           │                                 │
│                         │  TRUST & PRIVACY    │                                 │
│                         │      OVERLAY        │                                 │
│                         └─────────────────────┘                                 │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### What TGF Owns vs. Integrates

| Stage | TGF Ownership | TGF Integration Style |
|-------|---------------|----------------------|
| **C - Data Sources** | Records dataset hashes, lineage refs | Read-only access, no ETL |
| **D - Training Execution** | Governs results, exports job specs | Exports YAML/JSON, NO cluster scheduling |
| **E - Eval & Release** | **PRIMARY OWNER**: Gates, registry, channels, promotion | Internal registry + optional sinks (MLflow/W&B) |
| **F - Serving/Inference** | Produces serving packs, provides resolve endpoint | Exports templates, NO hosting |
| **G - Trust & Privacy** | **PRIMARY OWNER**: Signing, verification, privacy mode | BYOKMS integration, N2HE provider |

---

## 2. Value Chain Details

### 2.1 Category C: Data & Governance

**What happens here**: Data is collected, cleaned, labeled, and versioned for training.

**TGF's Role**: TGF does NOT perform data engineering. Instead, it:
- Records dataset hashes for reproducibility
- Stores lineage references (pointers to source systems)
- Validates dataset fingerprints before training runs
- Enables audit trails linking adapters to training data

**Supported Sources**:
| Source | Integration Style | What TGF Records |
|--------|------------------|------------------|
| AWS S3 | Read (s3:GetObject) | bucket, key, etag, size, hash |
| Google Cloud Storage | Read (storage.objects.get) | bucket, object, generation, hash |
| Azure Blob Storage | Read (blob.download) | container, blob, etag, hash |
| Local Filesystem/NFS | Read (os.stat, hash) | path, mtime, size, hash |
| HuggingFace Datasets | Reference (metadata) | dataset_id, revision, config, hash |

**Data Governance Guarantees**:
- Immutable dataset references after training run starts
- Hash verification before training ingestion
- Lineage chain from adapter → training run → dataset hash
- Support for data retention policies (TTL on references)

---

### 2.2 Category D: Training Execution

**What happens here**: ML training jobs run on compute infrastructure.

**TGF's Role**: TGF does NOT schedule or manage compute clusters. Instead, it:
- Exports job specifications in platform-native formats
- Records training run metadata and hyperparameters
- Collects training metrics and artifacts
- Governs which training results can proceed to evaluation

**Supported Execution Environments**:
| Environment | Integration Style | Artifacts Exported |
|-------------|------------------|-------------------|
| Local GPU (NVIDIA CUDA) | Direct execution via PyTorch | N/A (runs locally) |
| Kubernetes Job | Export YAML manifests | `training-job.yaml`, `configmap.yaml` |
| AWS SageMaker | Export JSON/YAML job definition | `sagemaker-training-job.json` |
| Google Vertex AI | Export JSON job spec | `vertex-custom-job.json` |
| Azure ML | Export JSON workspace job | `azureml-job.json` |
| Databricks | Export notebook/job config | `databricks-job.json` |

**Training Governance**:
- Hyperparameter validation before export
- Resource quota enforcement (optional)
- Training timeout policies
- Artifact collection and verification

**Important**: By default, TGF only exports job specifications. Remote job submission is disabled unless `TG_ENABLE_REMOTE_SUBMIT=true` is set. This ensures TGF remains a control plane, not an orchestrator.

---

### 2.3 Category E: Eval & Release

**What happens here**: Trained adapters are evaluated, packaged, and promoted through release channels.

**TGF's Role**: This is TGF's **primary domain**. TGF owns:
- Evaluation gates (forgetting metrics, regression detection, primary metrics)
- Adapter packaging (TGSP format)
- Evidence chain generation and signing
- Adapter registry with channels (candidate, stable, deprecated)
- Promotion and rollback workflows

**Internal Systems (TGF Owned)**:
| Component | Function |
|-----------|----------|
| Adapter Registry | Source of truth for all adapters |
| TGSP Packager | Creates signed, versioned adapter packages |
| Gate Evaluator | Runs forgetting/regression/metric checks |
| Evidence Generator | Creates provenance chains |
| Channel Manager | Handles candidate → stable promotion |

**External Integrations (Optional Sinks)**:
| System | Integration Style | What TGF Sends |
|--------|------------------|----------------|
| MLflow | Metrics export | Run metrics, parameters, artifacts |
| Weights & Biases | Metrics export | Run metrics, media, tables |

**Release Channels**:
```
candidate ──[gates pass]──▶ stable ──[deprecate]──▶ deprecated
     ▲                          │
     │                          │
     └────────[rollback]────────┘
```

---

### 2.4 Category F: Serving / Inference

**What happens here**: Adapters are loaded by inference runtimes to serve requests.

**TGF's Role**: TGF does NOT host inference endpoints. Instead, it:
- Produces "serving pack" templates for major runtimes
- Provides a `/resolve` endpoint for runtimes to query "which adapter?"
- Tracks which adapters are actively deployed
- Enables policy-based adapter routing

**Supported Runtimes**:
| Runtime | Integration Style | Artifacts Produced |
|---------|------------------|-------------------|
| vLLM | Serving pack export + resolve | `vllm-config.yaml`, adapter path |
| Text Generation Inference (TGI) | Serving pack export + resolve | `tgi-config.json`, adapter path |
| NVIDIA Triton | Serving pack export + resolve | `triton-model-config.pbtxt` |
| SageMaker Endpoint | Template export (no hosting) | `sagemaker-endpoint.json` |
| Custom Runtime | Resolve API | JSON response with adapter URI |

**Resolve Contract**:
```json
POST /tgflow/resolve
{
  "route_key": "customer-support-v2",
  "channel": "stable",
  "request_context": { ... }
}

Response:
{
  "adapter_id": "adpt_abc123",
  "adapter_uri": "s3://adapters/customer-support/v2.1.0/",
  "tgsp_manifest_uri": "s3://adapters/customer-support/v2.1.0/manifest.tgsp",
  "signature_status": "VERIFIED",
  "privacy_receipt": { ... }  // If N2HE enabled
}
```

---

### 2.5 Category G: Trust & Privacy Overlay

**What happens here**: Cryptographic guarantees and privacy protections are applied.

**TGF's Role**: This is TGF's **trust boundary**. TGF owns:
- BYOKMS integration for signing and verification
- Privacy mode via N2HE (encrypted routing, receipts, safe logging)
- Optional Nitro Enclave support for key custody
- Audit evidence generation

**BYOKMS (Bring Your Own KMS)**:
| Provider | Integration Style | Operations |
|----------|------------------|------------|
| AWS KMS | API calls (kms:Sign, kms:Verify) | Adapter signing, manifest verification |
| HashiCorp Vault | Transit API | Sign, verify, encrypt |
| Local (Dev Only) | File-based keys | Development signing only |

**Privacy Mode (N2HE)**:
- Encrypted routing decisions
- Privacy receipts for audit compliance
- Safe logging (no PII in logs)
- Homomorphic operations on sensitive metadata

**Nitro Enclaves (Optional)**:
- Isolated key custody
- Provenance signing within enclave boundary
- Attestation documents for compliance

---

## 3. Jobs-to-be-Done (JTBD)

### JTBD Framework

Each JTBD follows this structure:
- **Trigger**: What event initiates this job?
- **Inputs**: What data/context is needed?
- **Steps**: What actions occur?
- **Expected Outputs**: What should result from success?
- **Failure Modes**: What can go wrong, and what does TGF show?

---

### JTBD-01: Start a New Continuous Tuning Route for a Team

**Trigger**: Team lead decides to enable continuous fine-tuning for a new use case.

**Inputs**:
- Route name and description
- Base model reference (e.g., `meta-llama/Llama-3.1-8B`)
- Data source configuration (S3 bucket, dataset ID)
- Training configuration (PEFT method, hyperparameters)
- Evaluation gate thresholds (max forgetting, min accuracy)
- Serving target (vLLM, TGI, etc.)

**Steps**:
1. Validate base model availability
2. Validate data source connectivity and permissions
3. Create route configuration in TGF registry
4. Initialize adapter channel structure (candidate, stable)
5. Configure integration topology (data → train → eval → serve)
6. Run initial health checks on all integrations
7. Generate initial serving pack template

**Expected Outputs**:
- Route created with unique `route_key`
- Integration topology validated and stored
- Health check report for all connected systems
- Serving pack template ready for runtime configuration

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| Data source unreachable | Show connectivity error, suggest credential check |
| Base model not found | Show model resolution error, suggest alternatives |
| Invalid gate thresholds | Validation error with acceptable ranges |
| KMS key not configured | Warn that signing disabled, require key for production |

---

### JTBD-02: Decide Whether to Update Based on Novelty

**Trigger**: New data arrives or scheduled check detects potential drift.

**Inputs**:
- Route key
- Current stable adapter reference
- New data fingerprint
- Novelty detection configuration

**Steps**:
1. Compute data fingerprint for new samples
2. Compare against training data of current stable adapter
3. Calculate novelty score (distribution shift, new patterns)
4. Apply novelty threshold policy
5. Emit decision: UPDATE_RECOMMENDED or SKIP

**Expected Outputs**:
- Novelty analysis report
- Decision with confidence score
- If UPDATE_RECOMMENDED: trigger training preparation
- Metrics logged to tracking system

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| Data fingerprint computation fails | Show data access error, retry with backoff |
| Novelty threshold not configured | Use default conservative threshold, warn operator |
| Analysis timeout | Partial result with timeout indicator |

---

### JTBD-03: Run a Controlled Update and Measure Forgetting

**Trigger**: Novelty detection recommends update, or operator manually triggers.

**Inputs**:
- Route key
- Training configuration
- Evaluation dataset (holdout for forgetting measurement)
- Gate thresholds

**Steps**:
1. Snapshot current stable adapter performance on eval set
2. Export training job specification
3. Execute training (local or export for remote)
4. Collect trained adapter artifacts
5. Run forgetting evaluation (compare new vs. baseline on eval set)
6. Run primary metric evaluation
7. Package results in TGSP format
8. Create candidate adapter entry

**Expected Outputs**:
- Training run logged with metrics
- Forgetting score computed and compared to threshold
- Primary metrics computed
- TGSP package created and signed
- Candidate adapter available for promotion decision

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| Training fails | Log error, mark run failed, preserve artifacts for debugging |
| Forgetting exceeds threshold | Block promotion, show forgetting analysis, suggest remediation |
| Primary metric regresses | Block promotion, show regression details |
| Signing fails | Mark package unsigned, block production deployment |

---

### JTBD-04: Promote Candidate Safely

**Trigger**: Candidate adapter passes all gates, operator approves promotion.

**Inputs**:
- Route key
- Candidate adapter ID
- Promotion approval (operator confirmation)

**Steps**:
1. Verify all gates passed
2. Verify signature integrity
3. Archive current stable adapter
4. Promote candidate to stable channel
5. Update serving pack with new adapter reference
6. Notify connected runtimes (if webhooks configured)
7. Log promotion event in audit trail

**Expected Outputs**:
- Stable channel points to new adapter
- Previous stable archived with timestamp
- Serving pack updated
- Audit log entry created
- Promotion notification sent

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| Gates not passed | Block promotion, show which gates failed |
| Signature invalid | Block promotion, show signature verification error |
| Concurrent promotion | Prevent race, show conflict error |
| Notification fails | Complete promotion, log notification failure |

---

### JTBD-05: Rollback Instantly After Regression

**Trigger**: Production issue detected, operator initiates emergency rollback.

**Inputs**:
- Route key
- Target rollback version (optional, defaults to previous stable)

**Steps**:
1. Identify rollback target (previous stable or specified version)
2. Verify rollback target exists and is valid
3. Update stable channel to rollback target
4. Update serving pack immediately
5. Invalidate caches (if applicable)
6. Log rollback event with reason
7. Notify connected systems

**Expected Outputs**:
- Stable channel reverted to previous adapter
- Serving pack updated within seconds
- Rollback audit log entry
- Notification to monitoring systems

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| No previous version available | Error: cannot rollback, show adapter history |
| Rollback target corrupted | Error: target validation failed, suggest alternative |
| Serving pack update fails | Retry with exponential backoff, alert operator |

---

### JTBD-06: Route Requests to the Right Adapter Per Policy

**Trigger**: Runtime calls `/resolve` endpoint for adapter selection.

**Inputs**:
- Route key
- Channel preference (stable, candidate)
- Request context (optional: user segment, feature flags)

**Steps**:
1. Validate route key exists
2. Apply routing policy (channel, A/B test, canary)
3. Retrieve adapter reference from registry
4. Verify adapter signature (if enforcement enabled)
5. Generate privacy receipt (if N2HE enabled)
6. Return adapter resolution response

**Expected Outputs**:
- Adapter ID and URI
- TGSP manifest URI
- Signature verification status
- Privacy receipt (if applicable)
- Response latency < 50ms p99

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| Route not found | 404 with helpful message |
| No stable adapter | 503 with "route not ready" status |
| Signature verification fails | Return adapter with `signature_status: FAILED`, let runtime decide |
| N2HE privacy error | Return without receipt, log error |

---

### JTBD-07: Export to Customer's Stack Without Rewrites

**Trigger**: Customer needs to deploy TGF-managed adapters in their infrastructure.

**Inputs**:
- Route key
- Target platform (k8s, sagemaker, vertex, azureml, databricks, vllm, tgi, triton)
- Configuration overrides (optional)

**Steps**:
1. Retrieve route configuration and current stable adapter
2. Generate platform-specific export artifacts
3. Validate artifacts against platform schema
4. Package with deployment instructions
5. Sign export bundle (if signing enabled)

**Expected Outputs**:
- Platform-native configuration files
- Adapter reference with checksum
- Deployment instructions
- Schema validation report
- Signed bundle checksum

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| Unsupported target platform | Error with list of supported platforms |
| Schema validation fails | Show validation errors, suggest fixes |
| Adapter not found | Error: route has no stable adapter |

---

### JTBD-08: Prove Provenance and Integrity for Audits

**Trigger**: Compliance team requests proof of adapter provenance.

**Inputs**:
- Route key or adapter ID
- Time range (optional)
- Audit scope (training, promotion, deployment)

**Steps**:
1. Gather evidence chain for specified scope
2. Collect TGSP manifests with signatures
3. Collect training run metadata and data lineage
4. Collect promotion and deployment logs
5. Generate integration topology snapshot
6. Package into audit bundle
7. Sign audit bundle

**Expected Outputs**:
- Complete evidence chain in structured format
- TGSP packages with verification status
- Data lineage references
- Integration topology at time of events
- Signed audit bundle with timestamp

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| Evidence incomplete | Partial bundle with missing items flagged |
| Signature verification fails | Include in bundle with verification failure noted |
| Time range has no data | Empty bundle with explanation |

---

### JTBD-09: Enable Privacy Mode and Validate Receipts

**Trigger**: Organization requires privacy-preserving adapter management.

**Inputs**:
- Tenant configuration
- N2HE provider settings
- Privacy policy (what to encrypt, receipt requirements)

**Steps**:
1. Configure N2HE provider connection
2. Enable privacy mode for tenant
3. Configure receipt generation policy
4. Validate privacy mode operation with test request
5. Verify receipts are generated correctly
6. Enable safe logging mode

**Expected Outputs**:
- Privacy mode enabled for tenant
- Receipt validation passing
- Safe logging configured (no PII in logs)
- Privacy mode health check passing

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| N2HE provider unreachable | Error: cannot enable privacy mode without provider |
| Receipt validation fails | Show receipt verification error, suggest configuration |
| Safe logging validation fails | Show logging configuration that needs changes |

---

### JTBD-10: Integrate with Existing MLflow/W&B Without Replacing Them

**Trigger**: Team already uses MLflow or W&B for experiment tracking.

**Inputs**:
- Tracking system type (mlflow, wandb)
- Connection configuration (URI, API key, project)
- Sync policy (what metrics to export)

**Steps**:
1. Validate tracking system connectivity
2. Configure metric export policy
3. Test metric export with sample data
4. Enable ongoing sync for new training runs
5. Verify historical runs accessible (if backfill requested)

**Expected Outputs**:
- Tracking integration connected and healthy
- Metrics flowing to external system
- TGF remains source of truth for adapter registry
- External system used as optional visibility sink

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| Connection fails | Show connectivity error, preserve metrics locally |
| API rate limited | Queue metrics, retry with backoff |
| Schema mismatch | Transform metrics to compatible format, warn on data loss |

---

### JTBD-11: Operate Multi-Cloud/Hybrid and Keep Portability

**Trigger**: Organization uses multiple cloud providers or hybrid infrastructure.

**Inputs**:
- Cloud provider configurations (AWS, GCP, Azure)
- On-premises infrastructure details
- Data residency requirements
- KMS configuration per region

**Steps**:
1. Configure cloud-specific connectors
2. Set up region-aware routing policies
3. Configure cross-cloud artifact replication (if needed)
4. Set up KMS keys per region/cloud
5. Validate end-to-end operation across environments

**Expected Outputs**:
- Multi-cloud topology configured
- Adapters deployable to any configured environment
- Portable export artifacts work across clouds
- KMS signing works with region-appropriate keys

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| Cloud connectivity fails | Show which cloud, preserve operation in others |
| Cross-region replication fails | Queue replication, continue serving from source |
| KMS key not available in region | Warn, allow unsigned operation or block per policy |

---

### JTBD-12: Debug a Failed Update Quickly from a Single Dashboard

**Trigger**: Training run or promotion fails, engineer needs to diagnose.

**Inputs**:
- Route key
- Failed run ID or promotion ID
- Access to dashboard

**Steps**:
1. Navigate to route in dashboard
2. View run history with status indicators
3. Click failed run to see details
4. View logs, metrics, and error messages
5. View integration topology at time of failure
6. View gate evaluation results
7. Access suggested remediation steps

**Expected Outputs**:
- Clear failure reason displayed
- Logs accessible without leaving dashboard
- Integration status at failure time visible
- Gate results showing what failed
- Actionable next steps suggested

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| Logs not available | Show log retrieval error, suggest checking log storage |
| Run not found | Show run ID not found, suggest checking route |
| Dashboard timeout | Paginate data, show partial results |

---

### JTBD-13: Validate Adapter Security Before Production Deployment

**Trigger**: Security team requires validation before production promotion.

**Inputs**:
- Adapter ID
- Security policy requirements
- Compliance framework (SOC2, HIPAA, etc.)

**Steps**:
1. Verify adapter signature with production KMS
2. Check data lineage for approved sources only
3. Verify training configuration meets security policy
4. Check for known vulnerabilities in dependencies
5. Generate security assessment report
6. Apply security approval status

**Expected Outputs**:
- Security assessment report
- Approval status (approved, pending, rejected)
- Compliance checklist completion status
- Remediation items if rejected

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| Signature from non-production key | Reject: require re-signing with production key |
| Unapproved data source | Reject: show unapproved sources, require remediation |
| Policy violation | Reject: show specific violations |

---

### JTBD-14: Set Up Canary Deployment for Safe Rollout

**Trigger**: Team wants gradual rollout of new adapter version.

**Inputs**:
- Route key
- Candidate adapter ID
- Canary configuration (percentage, duration, metrics)

**Steps**:
1. Configure canary policy on route
2. Enable traffic splitting in resolve endpoint
3. Monitor canary metrics vs. stable metrics
4. Auto-promote or auto-rollback based on thresholds
5. Log canary experiment results

**Expected Outputs**:
- Canary deployment active
- Traffic split according to configuration
- Metrics comparison dashboard available
- Auto-decision logged with reasoning

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| Canary metrics degraded | Auto-rollback, log reason |
| Metrics collection fails | Pause canary, alert operator |
| Percentage configuration invalid | Validation error |

---

### JTBD-15: Generate Compliance Report for Regulatory Audit

**Trigger**: Regulatory audit requires documentation of AI model management.

**Inputs**:
- Time range for audit
- Compliance framework (EU AI Act, SOC2, etc.)
- Specific routes or all routes

**Steps**:
1. Gather all adapter changes in time range
2. Collect evidence chains for each change
3. Generate human-readable compliance report
4. Include integration topology and security posture
5. Sign report with audit timestamp

**Expected Outputs**:
- Compliance report in PDF and JSON formats
- Complete evidence chain
- Security posture assessment
- Integration status at audit time
- Signed report bundle

**Failure Modes**:
| Failure | TGF Response |
|---------|-------------|
| Incomplete evidence | Flag gaps, include what's available |
| Report generation timeout | Generate incrementally, allow resume |
| Signing fails | Generate unsigned, flag in report |

---

## 4. Operating Processes

### 4.1 Onboarding (Day 0)

**Objective**: Configure TGF integrations and create first route.

**Prerequisites**:
- TGF deployed and accessible
- Cloud credentials available (AWS, GCP, Azure as needed)
- KMS keys provisioned
- Data sources accessible

**Steps**:

1. **Configure Data Source Integration**
   ```bash
   # Via API or dashboard
   POST /api/v1/integrations/configure
   {
     "category": "data",
     "provider": "s3",
     "config": {
       "bucket": "my-training-data",
       "region": "us-west-2",
       "role_arn": "arn:aws:iam::123456789:role/tgf-data-reader"
     }
   }
   ```

2. **Configure KMS Integration**
   ```bash
   POST /api/v1/integrations/configure
   {
     "category": "trust",
     "provider": "aws_kms",
     "config": {
       "key_id": "alias/tgf-signing-key",
       "region": "us-west-2"
     }
   }
   ```

3. **Run Health Checks**
   ```bash
   POST /api/v1/integrations/healthcheck
   # Verify all integrations show "OK" status
   ```

4. **Create First Route**
   ```bash
   POST /api/v1/routes
   {
     "route_key": "customer-support-v1",
     "base_model": "meta-llama/Llama-3.1-8B",
     "data_source": { "type": "s3", "ref": "configured-s3-source" },
     "gates": {
       "max_forgetting": 0.05,
       "min_primary_metric": 0.85
     }
   }
   ```

5. **Verify Route Health**
   ```bash
   GET /api/v1/routes/customer-support-v1/health
   ```

---

### 4.2 Daily Operations

**Objective**: Monitor route health, review metrics, approve promotions.

**Morning Checklist**:
1. Check dashboard for any failed runs overnight
2. Review forgetting metrics trends
3. Check integration health status
4. Review pending promotion approvals

**Responding to Promotion Requests**:
1. Review candidate adapter gate results
2. Verify forgetting score acceptable
3. Verify primary metrics meet threshold
4. Check signature verification status
5. Approve or reject with reason

**Monitoring Route Health**:
- Set up alerts for:
  - Forgetting score approaching threshold
  - Training run failures
  - Integration health degradation
  - Resolve endpoint latency increase

---

### 4.3 Incident Response

**Objective**: Quickly recover from production issues.

**Scenario: Adapter Causing Production Issues**

1. **Immediate Rollback**
   ```bash
   POST /api/v1/routes/customer-support-v1/rollback
   {
     "reason": "Production degradation detected",
     "target_version": "previous"  # or specific version
   }
   ```

2. **Verify Rollback**
   ```bash
   GET /api/v1/routes/customer-support-v1/status
   # Confirm stable channel points to previous adapter
   ```

3. **Quarantine Problematic Adapter**
   ```bash
   POST /api/v1/adapters/{adapter_id}/quarantine
   {
     "reason": "Production incident investigation"
   }
   ```

4. **Generate Incident Report**
   ```bash
   POST /api/v1/routes/customer-support-v1/incident-report
   {
     "incident_id": "INC-2024-001",
     "time_range": {
       "start": "2024-01-15T10:00:00Z",
       "end": "2024-01-15T12:00:00Z"
     }
   }
   ```

**Scenario: Integration Failure**

1. **Identify Failed Integration**
   ```bash
   GET /api/v1/integrations/status
   # Look for FAIL status
   ```

2. **Run Targeted Health Check**
   ```bash
   POST /api/v1/integrations/{provider}/health
   ```

3. **Review Error Details**
   - Check credentials validity
   - Check network connectivity
   - Check provider service status

4. **Reconfigure if Needed**
   ```bash
   PUT /api/v1/integrations/{provider}/config
   ```

---

### 4.4 Compliance Audit Export

**Objective**: Generate evidence bundles for auditors.

**Steps**:

1. **Define Audit Scope**
   ```bash
   POST /api/v1/integrations/audit/export
   {
     "route_key": "customer-support-v1",  # or "all"
     "time_range": {
       "start": "2024-01-01T00:00:00Z",
       "end": "2024-03-31T23:59:59Z"
     },
     "compliance_framework": "SOC2"
   }
   ```

2. **Download Audit Bundle**
   - Evidence chain for all adapter changes
   - TGSP manifests with signatures
   - Data lineage references
   - Integration topology snapshots
   - Security posture assessments

3. **Verify Bundle Integrity**
   ```bash
   POST /api/v1/audit/verify
   {
     "bundle_path": "/path/to/audit-bundle.zip",
     "expected_signature": "..."
   }
   ```

---

### 4.5 Periodic Maintenance

**Objective**: Keep the system healthy and optimized.

**Weekly Tasks**:
- Review adapter storage usage
- Check for deprecated adapters to clean up
- Verify KMS key rotation status
- Review integration health trends

**Monthly Tasks**:
- Adapter consolidation review (merge similar adapters)
- Security posture assessment
- Compliance checklist review
- Performance optimization review

**Quarterly Tasks**:
- KMS key rotation (if policy requires)
- Full integration topology audit
- Disaster recovery test
- Compliance report generation

**Adapter Consolidation Process**:
1. Identify adapters with similar performance profiles
2. Compare forgetting scores across consolidation candidates
3. Select best-performing adapter as consolidation target
4. Update routes to use consolidated adapter
5. Deprecate redundant adapters
6. Archive deprecated adapters after retention period

**KMS Key Rotation Process**:
1. Generate new KMS key
2. Configure TGF to use new key for signing
3. Re-sign critical adapters with new key (optional)
4. Update verification to accept both keys during transition
5. After transition period, disable old key

---

## 5. Success Metrics

### Operational Metrics
| Metric | Target | Description |
|--------|--------|-------------|
| Route Health | > 99% | Routes with passing health checks |
| Promotion Success Rate | > 95% | Promotions that don't require rollback |
| Rollback Time | < 60s | Time from rollback trigger to serving new adapter |
| Resolve Latency p99 | < 50ms | Adapter resolution endpoint latency |

### Integration Metrics
| Metric | Target | Description |
|--------|--------|-------------|
| Integration Uptime | > 99.5% | Connected integrations healthy |
| Export Success Rate | > 99% | Export operations that produce valid artifacts |
| Health Check Latency | < 5s | Time to complete all integration health checks |

### Compliance Metrics
| Metric | Target | Description |
|--------|--------|-------------|
| Evidence Completeness | 100% | Adapter changes with full evidence chain |
| Signature Coverage | 100% | Production adapters with valid signatures |
| Audit Bundle Generation | < 5min | Time to generate compliance audit bundle |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Adapter** | A PEFT (Parameter-Efficient Fine-Tuning) module that modifies base model behavior |
| **Route** | A continuous tuning configuration linking data, training, eval, and serving |
| **Channel** | A deployment stage (candidate, stable, deprecated) |
| **TGSP** | TensorGuard Signed Package - versioned, signed adapter artifact |
| **Gate** | An evaluation check that must pass for promotion |
| **Forgetting** | Performance degradation on previously-learned tasks |
| **N2HE** | Privacy mode providing encrypted operations and receipts |
| **BYOKMS** | Bring Your Own Key Management Service |

---

## Appendix B: Related Documents

- [STACK_REFERENCE.md](../integrations/STACK_REFERENCE.md) - External system inventory
- [INTEGRATION_TOPOLOGY_MODEL.md](../integrations/INTEGRATION_TOPOLOGY_MODEL.md) - Topology JSON schema
- [SETUP_AND_OPERATE_RUNBOOK.md](../integrations/SETUP_AND_OPERATE_RUNBOOK.md) - Detailed operational procedures
- [TGSP_SPEC.md](../TGSP_SPEC.md) - TGSP package format specification
