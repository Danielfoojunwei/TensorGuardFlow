# Integration Topology Model

> **Document Version**: 1.0.0
> **Last Updated**: 2026-01-27
> **Status**: Production Reference

## Overview

The Integration Topology Model defines the JSON schema for representing TensorGuardFlow's integration graph. This model captures all connected systems, their relationships, and operational status.

The topology is used by:
- **Dashboard**: Visualize integration connections and health
- **API**: Return topology snapshots via `/api/v1/integrations/topology`
- **Audit**: Record integration state at specific points in time
- **Diagnostics**: Debug connectivity and data flow issues

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          INTEGRATION TOPOLOGY GRAPH                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────┐                                           ┌─────────┐              │
│  │  C.1    │                                           │  G.1    │              │
│  │  S3     │◄────────────────────────────────────────►│  KMS    │              │
│  └────┬────┘                                           └────┬────┘              │
│       │                                                     │                    │
│       │ file                                                │ api                │
│       ▼                                                     ▼                    │
│  ┌─────────┐         ┌─────────┐         ┌─────────┐  ┌─────────┐              │
│  │  D.1    │ export  │  E.1    │ export  │  F.1    │  │  G.2    │              │
│  │  K8s    │────────►│Registry │────────►│  vLLM   │  │  N2HE   │              │
│  └─────────┘         └────┬────┘         └────┬────┘  └────┬────┘              │
│                           │                    │            │                    │
│                           │ export             │ api        │ api               │
│                           ▼                    ▼            ▼                    │
│                      ┌─────────┐         ┌─────────┐  ┌─────────┐              │
│                      │  E.2    │         │Runtime  │  │Privacy  │              │
│                      │ MLflow  │         │/resolve │  │Receipts │              │
│                      └─────────┘         └─────────┘  └─────────┘              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## JSON Schema

### Root Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://tensorguardflow.io/schemas/integration-topology/v1",
  "title": "TensorGuardFlow Integration Topology",
  "description": "Describes the integration graph for a TensorGuardFlow tenant",
  "type": "object",
  "required": ["version", "tenant_id", "timestamp", "nodes", "edges"],
  "properties": {
    "version": {
      "type": "string",
      "const": "1.0.0",
      "description": "Schema version"
    },
    "tenant_id": {
      "type": "string",
      "description": "Tenant identifier"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp when topology was captured"
    },
    "nodes": {
      "type": "array",
      "items": { "$ref": "#/$defs/IntegrationNode" },
      "description": "All integration nodes"
    },
    "edges": {
      "type": "array",
      "items": { "$ref": "#/$defs/IntegrationEdge" },
      "description": "Connections between nodes"
    },
    "summary": {
      "$ref": "#/$defs/TopologySummary",
      "description": "Aggregate health and capability summary"
    }
  }
}
```

### IntegrationNode Schema

```json
{
  "$defs": {
    "IntegrationNode": {
      "type": "object",
      "required": ["id", "category", "provider", "status"],
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^[a-z0-9-]+$",
          "description": "Unique node identifier (e.g., 'aws-s3-prod', 'k8s-training')"
        },
        "category": {
          "type": "string",
          "enum": ["C", "D", "E", "F", "G"],
          "description": "Integration category"
        },
        "category_name": {
          "type": "string",
          "enum": ["data", "training", "eval_registry", "serving", "trust_privacy"],
          "description": "Human-readable category name"
        },
        "provider": {
          "type": "string",
          "description": "Provider name (e.g., 'aws_s3', 'kubernetes', 'vllm', 'aws_kms')"
        },
        "provider_display": {
          "type": "string",
          "description": "Human-readable provider name"
        },
        "status": {
          "type": "string",
          "enum": ["OK", "WARN", "FAIL", "UNKNOWN", "DISABLED"],
          "description": "Current health status"
        },
        "status_message": {
          "type": "string",
          "description": "Human-readable status explanation"
        },
        "last_health_check": {
          "type": "string",
          "format": "date-time",
          "description": "Timestamp of last health check"
        },
        "health_check_latency_ms": {
          "type": "integer",
          "minimum": 0,
          "description": "Latency of last health check in milliseconds"
        },
        "capabilities": {
          "type": "array",
          "items": { "type": "string" },
          "description": "List of capabilities this node provides"
        },
        "endpoints_used": {
          "type": "array",
          "items": { "$ref": "#/$defs/EndpointUsage" },
          "description": "Endpoints this node uses or exposes"
        },
        "artifacts_generated": {
          "type": "array",
          "items": { "$ref": "#/$defs/ArtifactInfo" },
          "description": "Artifacts generated for this integration"
        },
        "config_fingerprint": {
          "type": "string",
          "description": "Hash of configuration (for change detection)"
        },
        "enabled": {
          "type": "boolean",
          "default": true,
          "description": "Whether this integration is enabled"
        },
        "metadata": {
          "type": "object",
          "additionalProperties": true,
          "description": "Provider-specific metadata"
        }
      }
    }
  }
}
```

### IntegrationEdge Schema

```json
{
  "$defs": {
    "IntegrationEdge": {
      "type": "object",
      "required": ["from_node", "to_node", "protocol"],
      "properties": {
        "from_node": {
          "type": "string",
          "description": "Source node ID"
        },
        "to_node": {
          "type": "string",
          "description": "Target node ID"
        },
        "protocol": {
          "type": "string",
          "enum": ["export", "api", "file", "stream", "webhook"],
          "description": "Type of connection"
        },
        "direction": {
          "type": "string",
          "enum": ["unidirectional", "bidirectional"],
          "default": "unidirectional"
        },
        "artifacts": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Artifact paths transferred via this edge"
        },
        "data_types": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Types of data flowing through this edge"
        },
        "status": {
          "type": "string",
          "enum": ["ACTIVE", "INACTIVE", "ERROR"],
          "default": "ACTIVE"
        },
        "last_transfer": {
          "type": "string",
          "format": "date-time",
          "description": "Timestamp of last data transfer"
        },
        "notes": {
          "type": "string",
          "description": "Human-readable notes about this connection"
        }
      }
    }
  }
}
```

### Supporting Schemas

```json
{
  "$defs": {
    "EndpointUsage": {
      "type": "object",
      "required": ["endpoint", "type"],
      "properties": {
        "endpoint": {
          "type": "string",
          "description": "Endpoint URL or identifier"
        },
        "type": {
          "type": "string",
          "enum": ["inbound", "outbound"],
          "description": "Whether TGF calls this endpoint or exposes it"
        },
        "protocol": {
          "type": "string",
          "enum": ["https", "grpc", "file", "s3", "gcs"],
          "description": "Communication protocol"
        },
        "auth_method": {
          "type": "string",
          "enum": ["none", "api_key", "oauth", "iam", "mtls"],
          "description": "Authentication method used"
        },
        "last_used": {
          "type": "string",
          "format": "date-time"
        }
      }
    },
    "ArtifactInfo": {
      "type": "object",
      "required": ["name", "type"],
      "properties": {
        "name": {
          "type": "string",
          "description": "Artifact filename"
        },
        "type": {
          "type": "string",
          "enum": ["yaml", "json", "pbtxt", "tar", "zip"],
          "description": "Artifact format"
        },
        "path": {
          "type": "string",
          "description": "Path where artifact is generated"
        },
        "checksum": {
          "type": "string",
          "description": "SHA256 checksum of artifact"
        },
        "generated_at": {
          "type": "string",
          "format": "date-time"
        }
      }
    },
    "TopologySummary": {
      "type": "object",
      "properties": {
        "total_nodes": {
          "type": "integer",
          "minimum": 0
        },
        "nodes_by_status": {
          "type": "object",
          "properties": {
            "OK": { "type": "integer" },
            "WARN": { "type": "integer" },
            "FAIL": { "type": "integer" },
            "UNKNOWN": { "type": "integer" },
            "DISABLED": { "type": "integer" }
          }
        },
        "nodes_by_category": {
          "type": "object",
          "properties": {
            "C": { "type": "integer" },
            "D": { "type": "integer" },
            "E": { "type": "integer" },
            "F": { "type": "integer" },
            "G": { "type": "integer" }
          }
        },
        "total_edges": {
          "type": "integer",
          "minimum": 0
        },
        "overall_health": {
          "type": "string",
          "enum": ["HEALTHY", "DEGRADED", "UNHEALTHY"],
          "description": "Aggregate health status"
        },
        "capabilities": {
          "type": "array",
          "items": { "type": "string" },
          "description": "All capabilities available across nodes"
        },
        "last_full_check": {
          "type": "string",
          "format": "date-time"
        }
      }
    }
  }
}
```

---

## Example Topology

### Minimal Setup (Local Development)

```json
{
  "version": "1.0.0",
  "tenant_id": "dev-local",
  "timestamp": "2026-01-27T10:00:00Z",
  "nodes": [
    {
      "id": "local-filesystem",
      "category": "C",
      "category_name": "data",
      "provider": "local_fs",
      "provider_display": "Local Filesystem",
      "status": "OK",
      "status_message": "Path accessible",
      "last_health_check": "2026-01-27T10:00:00Z",
      "health_check_latency_ms": 5,
      "capabilities": ["read_data", "hash_verification"],
      "endpoints_used": [
        {
          "endpoint": "/data/training",
          "type": "outbound",
          "protocol": "file"
        }
      ],
      "enabled": true
    },
    {
      "id": "local-gpu",
      "category": "D",
      "category_name": "training",
      "provider": "cuda_local",
      "provider_display": "Local GPU (CUDA)",
      "status": "OK",
      "status_message": "1x NVIDIA RTX 4090 available",
      "last_health_check": "2026-01-27T10:00:00Z",
      "health_check_latency_ms": 50,
      "capabilities": ["local_training", "mixed_precision"],
      "metadata": {
        "cuda_version": "12.1",
        "device_count": 1,
        "device_names": ["NVIDIA GeForce RTX 4090"]
      },
      "enabled": true
    },
    {
      "id": "tgf-registry",
      "category": "E",
      "category_name": "eval_registry",
      "provider": "tgf_internal",
      "provider_display": "TGF Internal Registry",
      "status": "OK",
      "status_message": "Database connected",
      "last_health_check": "2026-01-27T10:00:00Z",
      "health_check_latency_ms": 10,
      "capabilities": ["adapter_registry", "channel_management", "evidence_chain", "gate_evaluation"],
      "enabled": true
    },
    {
      "id": "local-signing",
      "category": "G",
      "category_name": "trust_privacy",
      "provider": "local_dev",
      "provider_display": "Local Dev Signing",
      "status": "WARN",
      "status_message": "Development signing only - not for production",
      "last_health_check": "2026-01-27T10:00:00Z",
      "health_check_latency_ms": 1,
      "capabilities": ["sign", "verify"],
      "enabled": true
    }
  ],
  "edges": [
    {
      "from_node": "local-filesystem",
      "to_node": "local-gpu",
      "protocol": "file",
      "data_types": ["training_data"],
      "status": "ACTIVE"
    },
    {
      "from_node": "local-gpu",
      "to_node": "tgf-registry",
      "protocol": "api",
      "data_types": ["adapter_weights", "metrics"],
      "status": "ACTIVE"
    },
    {
      "from_node": "tgf-registry",
      "to_node": "local-signing",
      "protocol": "api",
      "data_types": ["tgsp_manifest"],
      "status": "ACTIVE"
    }
  ],
  "summary": {
    "total_nodes": 4,
    "nodes_by_status": {
      "OK": 3,
      "WARN": 1,
      "FAIL": 0,
      "UNKNOWN": 0,
      "DISABLED": 0
    },
    "nodes_by_category": {
      "C": 1,
      "D": 1,
      "E": 1,
      "F": 0,
      "G": 1
    },
    "total_edges": 3,
    "overall_health": "HEALTHY",
    "capabilities": [
      "read_data",
      "hash_verification",
      "local_training",
      "mixed_precision",
      "adapter_registry",
      "channel_management",
      "evidence_chain",
      "gate_evaluation",
      "sign",
      "verify"
    ],
    "last_full_check": "2026-01-27T10:00:00Z"
  }
}
```

### Production Setup (AWS + Kubernetes + vLLM)

```json
{
  "version": "1.0.0",
  "tenant_id": "acme-corp-prod",
  "timestamp": "2026-01-27T10:00:00Z",
  "nodes": [
    {
      "id": "aws-s3-training-data",
      "category": "C",
      "category_name": "data",
      "provider": "aws_s3",
      "provider_display": "AWS S3",
      "status": "OK",
      "status_message": "Bucket accessible, 1.2TB data indexed",
      "last_health_check": "2026-01-27T09:55:00Z",
      "health_check_latency_ms": 120,
      "capabilities": ["read_data", "hash_verification", "versioning"],
      "endpoints_used": [
        {
          "endpoint": "s3://acme-ml-training-data/",
          "type": "outbound",
          "protocol": "s3",
          "auth_method": "iam"
        }
      ],
      "config_fingerprint": "sha256:abc123...",
      "metadata": {
        "bucket": "acme-ml-training-data",
        "region": "us-west-2",
        "total_size_bytes": 1288490188800
      },
      "enabled": true
    },
    {
      "id": "k8s-training-cluster",
      "category": "D",
      "category_name": "training",
      "provider": "kubernetes",
      "provider_display": "Kubernetes",
      "status": "OK",
      "status_message": "Cluster reachable, 8 GPU nodes available",
      "last_health_check": "2026-01-27T09:58:00Z",
      "health_check_latency_ms": 80,
      "capabilities": ["k8s_job_export", "gpu_scheduling"],
      "endpoints_used": [
        {
          "endpoint": "https://k8s.acme.internal:6443",
          "type": "outbound",
          "protocol": "https",
          "auth_method": "mtls"
        }
      ],
      "artifacts_generated": [
        {
          "name": "training-job.yaml",
          "type": "yaml",
          "path": "/exports/k8s/",
          "generated_at": "2026-01-27T08:00:00Z"
        }
      ],
      "metadata": {
        "namespace": "ml-training",
        "gpu_node_count": 8,
        "gpu_type": "nvidia.com/gpu"
      },
      "enabled": true
    },
    {
      "id": "tgf-registry",
      "category": "E",
      "category_name": "eval_registry",
      "provider": "tgf_internal",
      "provider_display": "TGF Internal Registry",
      "status": "OK",
      "status_message": "Primary database connected, 847 adapters tracked",
      "last_health_check": "2026-01-27T10:00:00Z",
      "health_check_latency_ms": 15,
      "capabilities": [
        "adapter_registry",
        "channel_management",
        "evidence_chain",
        "gate_evaluation",
        "tgsp_packaging"
      ],
      "metadata": {
        "adapter_count": 847,
        "route_count": 12
      },
      "enabled": true
    },
    {
      "id": "mlflow-tracking",
      "category": "E",
      "category_name": "eval_registry",
      "provider": "mlflow",
      "provider_display": "MLflow",
      "status": "OK",
      "status_message": "Connected to Databricks MLflow",
      "last_health_check": "2026-01-27T09:50:00Z",
      "health_check_latency_ms": 250,
      "capabilities": ["metrics_sink", "experiment_tracking"],
      "endpoints_used": [
        {
          "endpoint": "https://acme.cloud.databricks.com/api/2.0/mlflow",
          "type": "outbound",
          "protocol": "https",
          "auth_method": "api_key"
        }
      ],
      "metadata": {
        "experiment_count": 45
      },
      "enabled": true
    },
    {
      "id": "vllm-serving",
      "category": "F",
      "category_name": "serving",
      "provider": "vllm",
      "provider_display": "vLLM",
      "status": "OK",
      "status_message": "3 instances serving, all healthy",
      "last_health_check": "2026-01-27T09:59:00Z",
      "health_check_latency_ms": 45,
      "capabilities": ["serving_pack_export", "resolve_integration", "lora_loading"],
      "endpoints_used": [
        {
          "endpoint": "/tgflow/resolve",
          "type": "inbound",
          "protocol": "https",
          "auth_method": "api_key",
          "last_used": "2026-01-27T09:59:55Z"
        }
      ],
      "artifacts_generated": [
        {
          "name": "vllm-config.yaml",
          "type": "yaml",
          "path": "/exports/vllm/",
          "checksum": "sha256:def456...",
          "generated_at": "2026-01-27T08:30:00Z"
        }
      ],
      "metadata": {
        "instance_count": 3,
        "base_model": "meta-llama/Llama-3.1-8B"
      },
      "enabled": true
    },
    {
      "id": "aws-kms-signing",
      "category": "G",
      "category_name": "trust_privacy",
      "provider": "aws_kms",
      "provider_display": "AWS KMS",
      "status": "OK",
      "status_message": "Signing key accessible",
      "last_health_check": "2026-01-27T09:57:00Z",
      "health_check_latency_ms": 100,
      "capabilities": ["sign", "verify", "key_rotation"],
      "endpoints_used": [
        {
          "endpoint": "kms.us-west-2.amazonaws.com",
          "type": "outbound",
          "protocol": "https",
          "auth_method": "iam"
        }
      ],
      "config_fingerprint": "sha256:xyz789...",
      "metadata": {
        "key_id": "alias/tgf-adapter-signing",
        "key_spec": "RSA_4096",
        "signing_algorithm": "RSASSA_PSS_SHA_256"
      },
      "enabled": true
    },
    {
      "id": "n2he-privacy",
      "category": "G",
      "category_name": "trust_privacy",
      "provider": "n2he",
      "provider_display": "N2HE Privacy Mode",
      "status": "OK",
      "status_message": "Privacy mode active, receipts enabled",
      "last_health_check": "2026-01-27T10:00:00Z",
      "health_check_latency_ms": 5,
      "capabilities": ["encrypted_routing", "privacy_receipts", "safe_logging"],
      "metadata": {
        "encryption_mode": "FULL",
        "receipts_generated_24h": 15420
      },
      "enabled": true
    }
  ],
  "edges": [
    {
      "from_node": "aws-s3-training-data",
      "to_node": "k8s-training-cluster",
      "protocol": "file",
      "data_types": ["training_data"],
      "status": "ACTIVE",
      "notes": "S3 mounted via CSI driver"
    },
    {
      "from_node": "k8s-training-cluster",
      "to_node": "tgf-registry",
      "protocol": "api",
      "data_types": ["adapter_weights", "metrics", "evidence"],
      "status": "ACTIVE"
    },
    {
      "from_node": "tgf-registry",
      "to_node": "mlflow-tracking",
      "protocol": "api",
      "data_types": ["metrics", "parameters"],
      "status": "ACTIVE",
      "notes": "Metrics sink only"
    },
    {
      "from_node": "tgf-registry",
      "to_node": "vllm-serving",
      "protocol": "export",
      "artifacts": ["/exports/vllm/vllm-config.yaml"],
      "data_types": ["serving_config", "adapter_reference"],
      "status": "ACTIVE"
    },
    {
      "from_node": "vllm-serving",
      "to_node": "tgf-registry",
      "protocol": "api",
      "data_types": ["resolve_request"],
      "status": "ACTIVE",
      "notes": "Runtime calls /resolve endpoint"
    },
    {
      "from_node": "tgf-registry",
      "to_node": "aws-kms-signing",
      "protocol": "api",
      "data_types": ["sign_request", "verify_request"],
      "status": "ACTIVE"
    },
    {
      "from_node": "tgf-registry",
      "to_node": "n2he-privacy",
      "protocol": "api",
      "data_types": ["routing_decision", "receipt_request"],
      "status": "ACTIVE"
    }
  ],
  "summary": {
    "total_nodes": 7,
    "nodes_by_status": {
      "OK": 7,
      "WARN": 0,
      "FAIL": 0,
      "UNKNOWN": 0,
      "DISABLED": 0
    },
    "nodes_by_category": {
      "C": 1,
      "D": 1,
      "E": 2,
      "F": 1,
      "G": 2
    },
    "total_edges": 7,
    "overall_health": "HEALTHY",
    "capabilities": [
      "read_data",
      "hash_verification",
      "versioning",
      "k8s_job_export",
      "gpu_scheduling",
      "adapter_registry",
      "channel_management",
      "evidence_chain",
      "gate_evaluation",
      "tgsp_packaging",
      "metrics_sink",
      "experiment_tracking",
      "serving_pack_export",
      "resolve_integration",
      "lora_loading",
      "sign",
      "verify",
      "key_rotation",
      "encrypted_routing",
      "privacy_receipts",
      "safe_logging"
    ],
    "last_full_check": "2026-01-27T10:00:00Z"
  }
}
```

---

## Pydantic Models

For implementation, use these Pydantic models:

```python
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class IntegrationCategory(str, Enum):
    """Integration categories mapping to value chain stages."""
    C = "C"  # Data Sources
    D = "D"  # Training Execution
    E = "E"  # Eval / Registry
    F = "F"  # Serving / Inference
    G = "G"  # Trust & Privacy


class CategoryName(str, Enum):
    """Human-readable category names."""
    DATA = "data"
    TRAINING = "training"
    EVAL_REGISTRY = "eval_registry"
    SERVING = "serving"
    TRUST_PRIVACY = "trust_privacy"


class NodeStatus(str, Enum):
    """Health status for integration nodes."""
    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    DISABLED = "DISABLED"


class EdgeProtocol(str, Enum):
    """Types of connections between nodes."""
    EXPORT = "export"
    API = "api"
    FILE = "file"
    STREAM = "stream"
    WEBHOOK = "webhook"


class EdgeStatus(str, Enum):
    """Status of edges between nodes."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ERROR = "ERROR"


class EdgeDirection(str, Enum):
    """Direction of data flow."""
    UNIDIRECTIONAL = "unidirectional"
    BIDIRECTIONAL = "bidirectional"


class EndpointType(str, Enum):
    """Whether TGF calls or exposes the endpoint."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class EndpointProtocol(str, Enum):
    """Communication protocols."""
    HTTPS = "https"
    GRPC = "grpc"
    FILE = "file"
    S3 = "s3"
    GCS = "gcs"


class AuthMethod(str, Enum):
    """Authentication methods."""
    NONE = "none"
    API_KEY = "api_key"
    OAUTH = "oauth"
    IAM = "iam"
    MTLS = "mtls"


class ArtifactType(str, Enum):
    """Artifact formats."""
    YAML = "yaml"
    JSON = "json"
    PBTXT = "pbtxt"
    TAR = "tar"
    ZIP = "zip"


class OverallHealth(str, Enum):
    """Aggregate health status."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class EndpointUsage(BaseModel):
    """Endpoint usage details."""
    endpoint: str
    type: EndpointType
    protocol: Optional[EndpointProtocol] = None
    auth_method: Optional[AuthMethod] = None
    last_used: Optional[datetime] = None


class ArtifactInfo(BaseModel):
    """Information about generated artifacts."""
    name: str
    type: ArtifactType
    path: Optional[str] = None
    checksum: Optional[str] = None
    generated_at: Optional[datetime] = None


class IntegrationNode(BaseModel):
    """A node in the integration topology graph."""
    id: str = Field(..., pattern=r"^[a-z0-9-]+$")
    category: IntegrationCategory
    category_name: Optional[CategoryName] = None
    provider: str
    provider_display: Optional[str] = None
    status: NodeStatus
    status_message: Optional[str] = None
    last_health_check: Optional[datetime] = None
    health_check_latency_ms: Optional[int] = Field(None, ge=0)
    capabilities: List[str] = []
    endpoints_used: List[EndpointUsage] = []
    artifacts_generated: List[ArtifactInfo] = []
    config_fingerprint: Optional[str] = None
    enabled: bool = True
    metadata: Dict[str, Any] = {}


class IntegrationEdge(BaseModel):
    """A connection between integration nodes."""
    from_node: str
    to_node: str
    protocol: EdgeProtocol
    direction: EdgeDirection = EdgeDirection.UNIDIRECTIONAL
    artifacts: List[str] = []
    data_types: List[str] = []
    status: EdgeStatus = EdgeStatus.ACTIVE
    last_transfer: Optional[datetime] = None
    notes: Optional[str] = None


class TopologySummary(BaseModel):
    """Aggregate summary of topology health."""
    total_nodes: int = Field(..., ge=0)
    nodes_by_status: Dict[str, int] = {}
    nodes_by_category: Dict[str, int] = {}
    total_edges: int = Field(..., ge=0)
    overall_health: OverallHealth
    capabilities: List[str] = []
    last_full_check: Optional[datetime] = None


class IntegrationTopology(BaseModel):
    """Complete integration topology for a tenant."""
    version: str = "1.0.0"
    tenant_id: str
    timestamp: datetime
    nodes: List[IntegrationNode]
    edges: List[IntegrationEdge]
    summary: Optional[TopologySummary] = None

    def compute_summary(self) -> TopologySummary:
        """Compute summary from nodes and edges."""
        nodes_by_status = {}
        nodes_by_category = {}
        all_capabilities = set()

        for node in self.nodes:
            nodes_by_status[node.status.value] = nodes_by_status.get(node.status.value, 0) + 1
            nodes_by_category[node.category.value] = nodes_by_category.get(node.category.value, 0) + 1
            all_capabilities.update(node.capabilities)

        # Determine overall health
        fail_count = nodes_by_status.get("FAIL", 0)
        warn_count = nodes_by_status.get("WARN", 0)

        if fail_count > 0:
            overall_health = OverallHealth.UNHEALTHY
        elif warn_count > 0:
            overall_health = OverallHealth.DEGRADED
        else:
            overall_health = OverallHealth.HEALTHY

        return TopologySummary(
            total_nodes=len(self.nodes),
            nodes_by_status=nodes_by_status,
            nodes_by_category=nodes_by_category,
            total_edges=len(self.edges),
            overall_health=overall_health,
            capabilities=sorted(all_capabilities),
            last_full_check=self.timestamp
        )
```

---

## API Response Format

The `/api/v1/integrations/topology` endpoint returns:

```json
{
  "success": true,
  "data": {
    // Full IntegrationTopology object
  },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-01-27T10:00:00Z",
    "tenant_id": "acme-corp-prod"
  }
}
```

---

## Validation Rules

1. **Node IDs must be unique** within a topology
2. **Edge endpoints must reference existing nodes**
3. **Category consistency**: `category_name` must match `category`
4. **Health check recency**: Warn if `last_health_check` > 5 minutes old
5. **Capabilities must be non-empty** for enabled nodes
6. **At least one E category node** (registry) must exist

---

## Dashboard Visualization

The topology should be rendered as an interactive graph:

- **Nodes**: Circles colored by status (green=OK, yellow=WARN, red=FAIL)
- **Edges**: Lines with arrows showing data flow direction
- **Layout**: Left-to-right flow following C → D → E → F, with G overlay
- **Interactions**:
  - Click node to see details panel
  - Hover edge to see data types and artifacts
  - Filter by category or status
  - Highlight path from data to serving

---

## Change Detection

Use `config_fingerprint` to detect configuration changes:

```python
import hashlib
import json

def compute_config_fingerprint(config: dict) -> str:
    """Compute deterministic hash of configuration."""
    # Sort keys for deterministic serialization
    serialized = json.dumps(config, sort_keys=True, default=str)
    return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"
```

---

## Related Documents

- [VALUE_CHAIN_JTBD.md](../product/VALUE_CHAIN_JTBD.md) - Value chain and JTBD definitions
- [STACK_REFERENCE.md](./STACK_REFERENCE.md) - External system inventory
- [SETUP_AND_OPERATE_RUNBOOK.md](./SETUP_AND_OPERATE_RUNBOOK.md) - Operational procedures
