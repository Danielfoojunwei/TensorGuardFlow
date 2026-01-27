# TensorGuardFlow Stack Reference

> **Document Version**: 1.0.0
> **Last Updated**: 2026-01-27
> **Status**: Production Reference

## Overview

This document inventories all external systems that TensorGuardFlow (TGF) integrates with, organized by category. For each system, we specify:

- **What TGF needs from it** (inputs)
- **What TGF gives it** (outputs)
- **Contract endpoint or artifact**
- **How to test without cloud**

---

## Integration Philosophy

TGF follows these principles for external integrations:

1. **Exporters over Orchestration**: Generate artifacts and specifications rather than directly managing resources
2. **Read-Only Data Access**: Never modify source data; only read and record references
3. **Optional Sinks**: External tracking systems are optional destinations, not dependencies
4. **BYOKMS**: Customers bring their own key management; TGF doesn't custody keys
5. **Graceful Degradation**: If an integration fails, core functionality continues

### Remote Submit Policy

By default, TGF only exports job specifications. Remote job submission is **disabled** unless:
```bash
export TG_ENABLE_REMOTE_SUBMIT=true
```

This ensures TGF remains a control plane, not a training orchestrator.

---

## Category C: Data Sources

Data sources provide training data and evaluation datasets. TGF reads from these sources and records metadata for lineage tracking.

### C.1 AWS S3

| Attribute | Value |
|-----------|-------|
| **Provider** | Amazon Web Services |
| **Integration Style** | Read-only API |
| **What TGF Needs** | Object read access, list bucket contents |
| **What TGF Gives** | Dataset references, hash verification results |
| **Contract** | S3 API (GetObject, HeadObject, ListObjectsV2) |
| **Test Without Cloud** | LocalStack, MinIO, or mock S3 responses |

**Required Permissions**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:HeadObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket",
        "arn:aws:s3:::your-bucket/*"
      ]
    }
  ]
}
```

**Configuration Schema**:
```python
class S3DataSourceConfig(BaseModel):
    bucket: str
    prefix: str = ""
    region: str = "us-east-1"
    role_arn: Optional[str] = None  # For cross-account access
    endpoint_url: Optional[str] = None  # For S3-compatible stores
```

**Health Check**:
```python
def health_check(config: S3DataSourceConfig) -> HealthResult:
    """Verify S3 bucket is accessible and permissions are valid."""
    # 1. List bucket (verifies ListBucket permission)
    # 2. Head object on known key (verifies GetObject permission)
    # 3. Return latency and status
```

---

### C.2 Google Cloud Storage (GCS)

| Attribute | Value |
|-----------|-------|
| **Provider** | Google Cloud Platform |
| **Integration Style** | Read-only API |
| **What TGF Needs** | Object read access |
| **What TGF Gives** | Dataset references, hash verification results |
| **Contract** | GCS JSON API (storage.objects.get, storage.objects.list) |
| **Test Without Cloud** | fake-gcs-server, mock responses |

**Required Permissions**:
```yaml
roles/storage.objectViewer:
  - storage.objects.get
  - storage.objects.list
```

**Configuration Schema**:
```python
class GCSDataSourceConfig(BaseModel):
    bucket: str
    prefix: str = ""
    project_id: str
    credentials_path: Optional[str] = None  # Path to service account JSON
```

---

### C.3 Azure Blob Storage

| Attribute | Value |
|-----------|-------|
| **Provider** | Microsoft Azure |
| **Integration Style** | Read-only API |
| **What TGF Needs** | Blob read access |
| **What TGF Gives** | Dataset references, hash verification results |
| **Contract** | Azure Blob REST API |
| **Test Without Cloud** | Azurite emulator, mock responses |

**Required Permissions**:
```
Storage Blob Data Reader (built-in role)
```

**Configuration Schema**:
```python
class AzureBlobDataSourceConfig(BaseModel):
    storage_account: str
    container: str
    prefix: str = ""
    connection_string: Optional[str] = None
    sas_token: Optional[str] = None
```

---

### C.4 Local Filesystem / NFS

| Attribute | Value |
|-----------|-------|
| **Provider** | Local / Network Storage |
| **Integration Style** | Direct file access |
| **What TGF Needs** | Read permissions on paths |
| **What TGF Gives** | Dataset references, hash verification results |
| **Contract** | POSIX filesystem API |
| **Test Without Cloud** | Always available locally |

**Configuration Schema**:
```python
class LocalDataSourceConfig(BaseModel):
    base_path: str
    glob_pattern: str = "**/*"
    follow_symlinks: bool = False
```

---

### C.5 HuggingFace Datasets

| Attribute | Value |
|-----------|-------|
| **Provider** | Hugging Face |
| **Integration Style** | Reference / Metadata |
| **What TGF Needs** | Dataset availability check |
| **What TGF Gives** | Dataset references, version tracking |
| **Contract** | HuggingFace Hub API |
| **Test Without Cloud** | Mock API responses, offline cache |

**Configuration Schema**:
```python
class HFDatasetConfig(BaseModel):
    dataset_id: str  # e.g., "squad", "glue"
    config_name: Optional[str] = None
    revision: str = "main"
    split: str = "train"
    token: Optional[str] = None  # For private datasets
```

---

## Category D: Training Execution

Training execution environments run ML training jobs. TGF exports job specifications and collects results.

### D.1 Local GPU (NVIDIA CUDA)

| Attribute | Value |
|-----------|-------|
| **Provider** | NVIDIA |
| **Integration Style** | Direct execution via PyTorch |
| **What TGF Needs** | CUDA availability, GPU memory |
| **What TGF Gives** | Training execution, metrics collection |
| **Contract** | PyTorch CUDA API |
| **Test Without Cloud** | CPU fallback, CUDA mock |

**Requirements**:
- CUDA toolkit installed
- PyTorch with CUDA support
- Sufficient GPU memory for model + adapter

**Configuration Schema**:
```python
class LocalGPUConfig(BaseModel):
    device_ids: List[int] = [0]
    mixed_precision: bool = True
    memory_fraction: float = 0.9
```

**Capabilities Detection**:
```python
def detect_capabilities() -> dict:
    return {
        "cuda_available": torch.cuda.is_available(),
        "device_count": torch.cuda.device_count(),
        "devices": [
            {
                "id": i,
                "name": torch.cuda.get_device_name(i),
                "memory_gb": torch.cuda.get_device_properties(i).total_memory / 1e9
            }
            for i in range(torch.cuda.device_count())
        ]
    }
```

---

### D.2 Kubernetes Job

| Attribute | Value |
|-----------|-------|
| **Provider** | CNCF Kubernetes |
| **Integration Style** | Export YAML manifests |
| **What TGF Needs** | Cluster context (optional, for validation) |
| **What TGF Gives** | Job YAML, ConfigMap YAML, PVC specs |
| **Contract** | Kubernetes Job API v1 |
| **Test Without Cloud** | Schema validation, dry-run |

**Exported Artifacts**:
```yaml
# training-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: tgf-training-{{ route_key }}-{{ run_id }}
  labels:
    app.kubernetes.io/managed-by: tensorguardflow
    tgf.io/route-key: {{ route_key }}
spec:
  template:
    spec:
      containers:
      - name: trainer
        image: {{ training_image }}
        resources:
          limits:
            nvidia.com/gpu: {{ gpu_count }}
        env:
        - name: TGF_RUN_ID
          value: "{{ run_id }}"
        - name: TGF_ROUTE_KEY
          value: "{{ route_key }}"
        volumeMounts:
        - name: data
          mountPath: /data
        - name: output
          mountPath: /output
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: {{ data_pvc }}
      - name: output
        persistentVolumeClaim:
          claimName: {{ output_pvc }}
      restartPolicy: Never
  backoffLimit: 3
```

**Configuration Schema**:
```python
class K8sJobConfig(BaseModel):
    namespace: str = "default"
    image: str
    gpu_count: int = 1
    cpu_request: str = "4"
    memory_request: str = "16Gi"
    data_pvc: str
    output_pvc: str
    service_account: Optional[str] = None
    node_selector: Dict[str, str] = {}
    tolerations: List[dict] = []
```

---

### D.3 AWS SageMaker Training Job

| Attribute | Value |
|-----------|-------|
| **Provider** | Amazon Web Services |
| **Integration Style** | Export JSON job definition |
| **What TGF Needs** | None (export only) |
| **What TGF Gives** | CreateTrainingJob JSON |
| **Contract** | SageMaker CreateTrainingJob API |
| **Test Without Cloud** | Schema validation |

**Exported Artifacts**:
```json
{
  "TrainingJobName": "tgf-{{ route_key }}-{{ run_id }}",
  "AlgorithmSpecification": {
    "TrainingImage": "{{ training_image }}",
    "TrainingInputMode": "File"
  },
  "RoleArn": "{{ role_arn }}",
  "InputDataConfig": [
    {
      "ChannelName": "training",
      "DataSource": {
        "S3DataSource": {
          "S3DataType": "S3Prefix",
          "S3Uri": "{{ data_s3_uri }}",
          "S3DataDistributionType": "FullyReplicated"
        }
      }
    }
  ],
  "OutputDataConfig": {
    "S3OutputPath": "{{ output_s3_uri }}"
  },
  "ResourceConfig": {
    "InstanceType": "{{ instance_type }}",
    "InstanceCount": 1,
    "VolumeSizeInGB": 100
  },
  "StoppingCondition": {
    "MaxRuntimeInSeconds": 86400
  },
  "HyperParameters": {
    "tgf_route_key": "{{ route_key }}",
    "tgf_run_id": "{{ run_id }}"
  },
  "Tags": [
    {"Key": "tgf:managed", "Value": "true"},
    {"Key": "tgf:route-key", "Value": "{{ route_key }}"}
  ]
}
```

**Configuration Schema**:
```python
class SageMakerJobConfig(BaseModel):
    role_arn: str
    instance_type: str = "ml.g5.xlarge"
    volume_size_gb: int = 100
    max_runtime_seconds: int = 86400
    training_image: str
    data_s3_uri: str
    output_s3_uri: str
    vpc_config: Optional[dict] = None
    enable_network_isolation: bool = False
```

---

### D.4 Google Vertex AI Custom Job

| Attribute | Value |
|-----------|-------|
| **Provider** | Google Cloud Platform |
| **Integration Style** | Export JSON job spec |
| **What TGF Needs** | None (export only) |
| **What TGF Gives** | CustomJob JSON |
| **Contract** | Vertex AI CustomJob API |
| **Test Without Cloud** | Schema validation |

**Exported Artifacts**:
```json
{
  "displayName": "tgf-{{ route_key }}-{{ run_id }}",
  "jobSpec": {
    "workerPoolSpecs": [
      {
        "machineSpec": {
          "machineType": "{{ machine_type }}",
          "acceleratorType": "{{ accelerator_type }}",
          "acceleratorCount": {{ accelerator_count }}
        },
        "replicaCount": 1,
        "containerSpec": {
          "imageUri": "{{ training_image }}",
          "env": [
            {"name": "TGF_RUN_ID", "value": "{{ run_id }}"},
            {"name": "TGF_ROUTE_KEY", "value": "{{ route_key }}"}
          ]
        }
      }
    ]
  },
  "labels": {
    "tgf-managed": "true",
    "tgf-route-key": "{{ route_key }}"
  }
}
```

**Configuration Schema**:
```python
class VertexAIJobConfig(BaseModel):
    project_id: str
    location: str = "us-central1"
    machine_type: str = "n1-standard-8"
    accelerator_type: str = "NVIDIA_TESLA_V100"
    accelerator_count: int = 1
    training_image: str
    staging_bucket: str
```

---

### D.5 Azure ML Job

| Attribute | Value |
|-----------|-------|
| **Provider** | Microsoft Azure |
| **Integration Style** | Export JSON job spec |
| **What TGF Needs** | None (export only) |
| **What TGF Gives** | Job YAML/JSON |
| **Contract** | Azure ML Job API |
| **Test Without Cloud** | Schema validation |

**Configuration Schema**:
```python
class AzureMLJobConfig(BaseModel):
    workspace_name: str
    resource_group: str
    subscription_id: str
    compute_target: str
    environment_name: str
    training_script: str
    data_uri: str
    output_uri: str
```

---

### D.6 Databricks Job

| Attribute | Value |
|-----------|-------|
| **Provider** | Databricks |
| **Integration Style** | Export JSON job spec |
| **What TGF Needs** | None (export only) |
| **What TGF Gives** | Jobs API JSON |
| **Contract** | Databricks Jobs API 2.1 |
| **Test Without Cloud** | Schema validation |

**Configuration Schema**:
```python
class DatabricksJobConfig(BaseModel):
    workspace_url: str
    cluster_id: Optional[str] = None
    new_cluster: Optional[dict] = None
    notebook_path: Optional[str] = None
    python_file: Optional[str] = None
    parameters: Dict[str, str] = {}
```

---

## Category E: Eval / Tracking / Registry

### E.1 TensorGuardFlow Internal Registry (Source of Truth)

| Attribute | Value |
|-----------|-------|
| **Provider** | TensorGuardFlow |
| **Integration Style** | Internal (always available) |
| **What TGF Needs** | Database access |
| **What TGF Gives** | Adapter registry, channels, evidence |
| **Contract** | Internal API |
| **Test Without Cloud** | Always available |

**Capabilities**:
- Adapter versioning and channels (candidate, stable, deprecated)
- TGSP package storage and signing
- Evidence chain management
- Promotion and rollback workflows
- Gate evaluation and enforcement

---

### E.2 MLflow (Optional Metrics Sink)

| Attribute | Value |
|-----------|-------|
| **Provider** | MLflow (Databricks / Self-hosted) |
| **Integration Style** | Metrics export (write-only) |
| **What TGF Needs** | Tracking server URI, optional auth |
| **What TGF Gives** | Run metrics, parameters, artifacts |
| **Contract** | MLflow Tracking API |
| **Test Without Cloud** | Local MLflow server, mock |

**Configuration Schema**:
```python
class MLflowConfig(BaseModel):
    tracking_uri: str  # e.g., "http://mlflow:5000" or "databricks"
    experiment_name: str
    artifact_location: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
```

**Exported Data**:
```python
# Metrics exported to MLflow
{
    "run_name": f"tgf-{route_key}-{run_id}",
    "tags": {
        "tgf.route_key": route_key,
        "tgf.run_id": run_id,
        "tgf.adapter_id": adapter_id
    },
    "params": training_config.dict(),
    "metrics": {
        "forgetting_score": 0.023,
        "primary_metric": 0.876,
        "training_loss_final": 0.142
    },
    "artifacts": ["adapter_weights.safetensors", "tgsp_manifest.json"]
}
```

---

### E.3 Weights & Biases (Optional Metrics Sink)

| Attribute | Value |
|-----------|-------|
| **Provider** | Weights & Biases |
| **Integration Style** | Metrics export (write-only) |
| **What TGF Needs** | API key, project/entity |
| **What TGF Gives** | Run metrics, media, tables |
| **Contract** | W&B SDK API |
| **Test Without Cloud** | wandb offline mode, mock |

**Configuration Schema**:
```python
class WandBConfig(BaseModel):
    api_key: str
    project: str
    entity: Optional[str] = None
    tags: List[str] = []
```

---

## Category F: Serving / Inference

### F.1 vLLM

| Attribute | Value |
|-----------|-------|
| **Provider** | vLLM Project |
| **Integration Style** | Serving pack export + resolve |
| **What TGF Needs** | None (export only) |
| **What TGF Gives** | Config YAML, adapter path, resolve endpoint |
| **Contract** | vLLM config + TGF /resolve |
| **Test Without Cloud** | Schema validation |

**Exported Artifacts**:
```yaml
# vllm-config.yaml
model: {{ base_model }}
lora_modules:
  - name: {{ adapter_name }}
    path: {{ adapter_path }}
    # Resolved from TGF:
    tgf_adapter_id: {{ adapter_id }}
    tgf_resolve_endpoint: {{ resolve_endpoint }}
tensor_parallel_size: {{ tp_size }}
max_model_len: {{ max_model_len }}
```

**Configuration Schema**:
```python
class VLLMServingConfig(BaseModel):
    base_model: str
    tensor_parallel_size: int = 1
    max_model_len: int = 4096
    gpu_memory_utilization: float = 0.9
    adapter_path: str
    resolve_endpoint: str  # TGF /resolve URL
```

**Runtime Integration**:
```python
# vLLM runtime calls TGF /resolve to get current adapter
async def resolve_adapter(route_key: str) -> dict:
    response = await http_client.post(
        f"{TGF_URL}/tgflow/resolve",
        json={"route_key": route_key, "channel": "stable"}
    )
    return response.json()
    # Returns: adapter_id, adapter_uri, tgsp_manifest_uri, signature_status
```

---

### F.2 Text Generation Inference (TGI)

| Attribute | Value |
|-----------|-------|
| **Provider** | Hugging Face |
| **Integration Style** | Serving pack export + resolve |
| **What TGF Needs** | None (export only) |
| **What TGF Gives** | Config JSON, adapter path, resolve endpoint |
| **Contract** | TGI config + TGF /resolve |
| **Test Without Cloud** | Schema validation |

**Exported Artifacts**:
```json
{
  "model_id": "{{ base_model }}",
  "lora_adapters": "{{ adapter_path }}",
  "max_input_length": {{ max_input_length }},
  "max_total_tokens": {{ max_total_tokens }},
  "tgf_integration": {
    "resolve_endpoint": "{{ resolve_endpoint }}",
    "route_key": "{{ route_key }}"
  }
}
```

**Configuration Schema**:
```python
class TGIServingConfig(BaseModel):
    base_model: str
    max_input_length: int = 1024
    max_total_tokens: int = 2048
    quantize: Optional[str] = None  # "bitsandbytes", "gptq"
    adapter_path: str
    resolve_endpoint: str
```

---

### F.3 NVIDIA Triton Inference Server

| Attribute | Value |
|-----------|-------|
| **Provider** | NVIDIA |
| **Integration Style** | Serving pack export + resolve |
| **What TGF Needs** | None (export only) |
| **What TGF Gives** | Model config.pbtxt, adapter path |
| **Contract** | Triton model config + TGF /resolve |
| **Test Without Cloud** | Schema validation |

**Exported Artifacts**:
```protobuf
# config.pbtxt
name: "{{ model_name }}"
platform: "pytorch_libtorch"
max_batch_size: {{ max_batch_size }}
input [
  {
    name: "input_ids"
    data_type: TYPE_INT64
    dims: [ -1 ]
  }
]
output [
  {
    name: "logits"
    data_type: TYPE_FP32
    dims: [ -1, -1 ]
  }
]
parameters: {
  key: "tgf_resolve_endpoint"
  value: { string_value: "{{ resolve_endpoint }}" }
}
parameters: {
  key: "tgf_route_key"
  value: { string_value: "{{ route_key }}" }
}
```

**Configuration Schema**:
```python
class TritonServingConfig(BaseModel):
    model_name: str
    max_batch_size: int = 8
    instance_count: int = 1
    adapter_path: str
    resolve_endpoint: str
```

---

### F.4 SageMaker Endpoint (Template Export)

| Attribute | Value |
|-----------|-------|
| **Provider** | Amazon Web Services |
| **Integration Style** | Template export (no hosting) |
| **What TGF Needs** | None |
| **What TGF Gives** | Endpoint config JSON |
| **Contract** | SageMaker CreateEndpoint API |
| **Test Without Cloud** | Schema validation |

**Configuration Schema**:
```python
class SageMakerEndpointConfig(BaseModel):
    role_arn: str
    instance_type: str = "ml.g5.xlarge"
    initial_instance_count: int = 1
    model_data_url: str  # S3 path to adapter
    inference_image: str
```

---

### F.5 Bedrock Import Path (Documentation Only)

| Attribute | Value |
|-----------|-------|
| **Provider** | Amazon Web Services |
| **Integration Style** | Documentation guidance |
| **What TGF Needs** | N/A |
| **What TGF Gives** | Packaging compatibility validation |
| **Contract** | Bedrock custom model import spec |
| **Test Without Cloud** | Schema validation of package format |

**Note**: TGF does not directly integrate with Bedrock. This entry documents how to package TGF-managed adapters for Bedrock import if the customer chooses that path.

---

## Category G: Trust & Privacy

### G.1 AWS KMS

| Attribute | Value |
|-----------|-------|
| **Provider** | Amazon Web Services |
| **Integration Style** | Sign/Verify API |
| **What TGF Needs** | KMS key access for Sign and Verify |
| **What TGF Gives** | Signed adapters, verification results |
| **Contract** | KMS Sign/Verify/GetPublicKey APIs |
| **Test Without Cloud** | LocalStack, mock responses |

**Required Permissions**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "kms:Sign",
        "kms:Verify",
        "kms:GetPublicKey",
        "kms:DescribeKey"
      ],
      "Resource": "arn:aws:kms:*:*:key/your-key-id"
    }
  ]
}
```

**Configuration Schema**:
```python
class AWSKMSConfig(BaseModel):
    key_id: str  # Key ID, ARN, or alias
    region: str = "us-east-1"
    signing_algorithm: str = "RSASSA_PSS_SHA_256"
    role_arn: Optional[str] = None  # For cross-account
```

**Operations**:
```python
async def sign_adapter(adapter_hash: bytes, config: AWSKMSConfig) -> bytes:
    """Sign adapter hash using KMS key."""
    response = await kms_client.sign(
        KeyId=config.key_id,
        Message=adapter_hash,
        MessageType="DIGEST",
        SigningAlgorithm=config.signing_algorithm
    )
    return response["Signature"]

async def verify_signature(adapter_hash: bytes, signature: bytes, config: AWSKMSConfig) -> bool:
    """Verify adapter signature using KMS key."""
    response = await kms_client.verify(
        KeyId=config.key_id,
        Message=adapter_hash,
        MessageType="DIGEST",
        Signature=signature,
        SigningAlgorithm=config.signing_algorithm
    )
    return response["SignatureValid"]
```

---

### G.2 HashiCorp Vault Transit

| Attribute | Value |
|-----------|-------|
| **Provider** | HashiCorp |
| **Integration Style** | Transit API |
| **What TGF Needs** | Vault address, token, transit path |
| **What TGF Gives** | Signed adapters, verification results |
| **Contract** | Vault Transit secrets engine API |
| **Test Without Cloud** | Vault dev server |

**Configuration Schema**:
```python
class VaultTransitConfig(BaseModel):
    vault_addr: str  # e.g., "https://vault.example.com:8200"
    token: Optional[str] = None  # Or use other auth methods
    transit_mount: str = "transit"
    key_name: str
    auth_method: str = "token"  # token, kubernetes, aws
    auth_config: Dict[str, str] = {}
```

---

### G.3 AWS Nitro Enclaves (Optional)

| Attribute | Value |
|-----------|-------|
| **Provider** | Amazon Web Services |
| **Integration Style** | Enclave attestation + key custody |
| **What TGF Needs** | Enclave endpoint, attestation document |
| **What TGF Gives** | Enclave-signed artifacts, attestation verification |
| **Contract** | Nitro Enclaves SDK |
| **Test Without Cloud** | Mock attestation, schema validation |

**Configuration Schema**:
```python
class NitroEnclaveConfig(BaseModel):
    enclave_cid: int  # Enclave CID
    vsock_port: int = 5000
    pcr_values: Dict[int, str]  # Expected PCR values for attestation
    kms_key_id: str  # KMS key provisioned to enclave
```

---

### G.4 N2HE Privacy Mode

| Attribute | Value |
|-----------|-------|
| **Provider** | TensorGuardFlow Internal |
| **Integration Style** | Privacy mode provider |
| **What TGF Needs** | N2HE configuration |
| **What TGF Gives** | Encrypted routing, receipts, safe logging |
| **Contract** | Internal N2HE API |
| **Test Without Cloud** | Always available |

**Configuration Schema**:
```python
class N2HEConfig(BaseModel):
    enabled: bool = False
    encryption_mode: str = "FULL"  # FULL, METADATA_ONLY
    receipt_generation: bool = True
    safe_logging: bool = True  # No PII in logs
    receipt_retention_days: int = 90
```

**Capabilities**:
- Encrypted adapter resolution decisions
- Privacy receipts for audit compliance
- Safe logging (sensitive data redacted)
- Homomorphic operations on metadata

---

## DevOps / Engineering Systems

### Continuous Integration

#### GitHub Actions

| Attribute | Value |
|-----------|-------|
| **Integration Style** | Workflow triggers, status checks |
| **What TGF Needs** | Webhook configuration (optional) |
| **What TGF Gives** | Status updates, test results |
| **Test Without Cloud** | Local test execution |

---

### Container Infrastructure

#### Docker

| Attribute | Value |
|-----------|-------|
| **Integration Style** | Build and runtime |
| **What TGF Needs** | Docker daemon |
| **What TGF Gives** | Container images, compose files |
| **Test Without Cloud** | Docker available locally |

---

### Kubernetes Packaging

#### Helm / Kustomize

| Attribute | Value |
|-----------|-------|
| **Integration Style** | Chart/overlay generation |
| **What TGF Needs** | Chart templates |
| **What TGF Gives** | Rendered manifests |
| **Test Without Cloud** | helm template, kustomize build |

---

### Observability (Optional)

#### Prometheus Metrics Export

| Attribute | Value |
|-----------|-------|
| **Integration Style** | /metrics endpoint |
| **What TGF Needs** | Scrape configuration |
| **What TGF Gives** | Prometheus metrics |
| **Test Without Cloud** | curl /metrics |

**Metrics Exported**:
```
# Adapter metrics
tgf_adapters_total{route_key, channel} gauge
tgf_adapter_promotions_total{route_key} counter
tgf_adapter_rollbacks_total{route_key} counter

# Training metrics
tgf_training_runs_total{route_key, status} counter
tgf_training_duration_seconds{route_key} histogram

# Resolve metrics
tgf_resolve_requests_total{route_key} counter
tgf_resolve_latency_seconds{route_key} histogram

# Integration health
tgf_integration_health{provider, category} gauge
tgf_integration_check_duration_seconds{provider} histogram
```

---

## Quick Reference: Integration Styles

| Style | Description | Example |
|-------|-------------|---------|
| **Read** | TGF reads from external system | S3, GCS data sources |
| **Export** | TGF generates artifacts for external system | K8s YAML, SageMaker JSON |
| **API** | TGF calls external API | KMS Sign, Vault Transit |
| **Resolve** | External system calls TGF | vLLM calling /resolve |
| **Sink** | TGF pushes data to external system | MLflow, W&B metrics |
| **Reference** | TGF stores reference, no direct access | HuggingFace dataset IDs |

---

## Quick Reference: Test Without Cloud

| System | Local Test Method |
|--------|------------------|
| AWS S3 | LocalStack, MinIO |
| GCS | fake-gcs-server |
| Azure Blob | Azurite |
| Kubernetes | Kind, Minikube, schema validation |
| SageMaker | Schema validation only |
| Vertex AI | Schema validation only |
| Azure ML | Schema validation only |
| Databricks | Schema validation only |
| vLLM | Schema validation, local vLLM |
| TGI | Schema validation |
| Triton | Schema validation |
| AWS KMS | LocalStack |
| Vault | Vault dev server |
| MLflow | Local MLflow server |
| W&B | Offline mode |
| N2HE | Always available (internal) |

---

## Appendix: Environment Variables

```bash
# Remote submission (default: disabled)
TG_ENABLE_REMOTE_SUBMIT=false

# AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# GCP
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
GOOGLE_CLOUD_PROJECT=my-project

# Azure
AZURE_STORAGE_CONNECTION_STRING=...
AZURE_SUBSCRIPTION_ID=...

# Vault
VAULT_ADDR=https://vault.example.com:8200
VAULT_TOKEN=...

# MLflow
MLFLOW_TRACKING_URI=http://mlflow:5000

# W&B
WANDB_API_KEY=...
WANDB_PROJECT=...

# N2HE
TG_N2HE_ENABLED=true
TG_N2HE_ENCRYPTION_MODE=FULL
```
