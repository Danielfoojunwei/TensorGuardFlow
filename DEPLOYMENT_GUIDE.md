<<<<<<< HEAD
# Deployment Guide: TensorGuard Enterprise (v2.3)
=======
# TensorGuard Deployment Guide v2.3.0 (Production Ready)
## Complete Step-by-Step for Production Deployments
>>>>>>> 9ac05e7 (v2.3 Release: Empirical Research Validation & High-Fidelity FastUMI Benchmarking. (Verified non-theoretical metrics for ML success, bandwidth efficiency, and MoE routing))

This guide covers the deployment of the entire TensorGuard fabric: the **Management Platform** (cloud/on-prem) and the **Edge Agents** (robots).

## 1. Prerequisites

### Infrastructure
- **Server**: 8+ vCPUs, 32GB RAM, Ubuntu 22.04 / Windows Server 2022.
- **Database**: PostgreSQL 14+ (or SQLite for testing).
- **Network**: Port 8000 (HTTP), 9000 (gRPC), 4173 (Frontend).

### Dependencies
- Python 3.10+
<<<<<<< HEAD
- Node.js 18+ (for Frontend build)
- NVIDIA Drivers 535+ (if using GPU acceleration)
=======
- liboqs-python (Production requirement)
- 8GB+ RAM
- CUDA-capable GPU (optional, for acceleration)
>>>>>>> 9ac05e7 (v2.3 Release: Empirical Research Validation & High-Fidelity FastUMI Benchmarking. (Verified non-theoretical metrics for ML success, bandwidth efficiency, and MoE routing))

## 2. Platform Installation (The Hub)

### Step 1: Clone & Install
```bash
git clone https://github.com/Danielfoojunwei/TensorGuardFlow
cd TensorGuardFlow
pip install -r requirements.txt
```

<<<<<<< HEAD
### Step 2: Initialize Database
=======
### Generate Your First Key

```python
from tensorguard.core.crypto import generate_key

# Generate 128-bit post-quantum secure key
generate_key("keys/my_enterprise_key.npy", security_level=128)
```

### Security Hardening (v2.0)

TensorGuard v2.0 includes hardened security by default:

| Feature | Implementation |
|:--------|:---------------|
| **CSPRNG Key Generation** | Uses `secrets`-seeded PCG64 |
| **Safe Serialization** | msgpack instead of pickle (no RCE) |
| **Skellam DP Noise** | Cryptographically secure sampling |
| **Fail-Closed Enforcement** | Insecure simulators blocked in production |
| **HSM Integration** | See [`docs/HSM_INTEGRATION.md`](docs/HSM_INTEGRATION.md) |

For enterprise key management with AWS KMS, Azure Key Vault, or GCP Cloud KMS, refer to the [HSM Integration Guide](docs/HSM_INTEGRATION.md).

### Related Documentation

- **[Product Requirements Document](docs/PRD.md)**: User personas, flows, acceptance criteria
- **[Expert Routing Configuration](docs/EXPERT_ROUTING.md)**: Customize MoE expert routing
- **[HSM Integration](docs/HSM_INTEGRATION.md)**: Cloud KMS and HSM setup

---

## 2. Step-by-Step User Flow

### Phase 1: Initial Setup (Day 1)

**Step 1: Generate Enterprise Key**
```python
from tensorguard.core.crypto import generate_key

# One-time key generation for your fleet
generate_key("keys/warehouse_fleet_v1.npy", security_level=128)
```

**Step 2: Register Key with KMS**
```python
from tensorguard.core.production import KeyManagementSystem, KeyMetadata
from datetime import datetime
from pathlib import Path

kms = KeyManagementSystem(audit_log_path=Path("logs/key_audit.log"))
kms.register_key("warehouse_v1", KeyMetadata(
    key_id="warehouse_v1",
    created_at=datetime.utcnow(),
    owner="GlobalLogistics",
    security_level=128
))
```

**Step 3: Configure Operating Envelope**
```python
from tensorguard.core.production import OperatingEnvelope

envelope = OperatingEnvelope(
    trainable_modules=["policy_head", "vision_adapter"],
    max_trainable_params=5_000_000,  # 5M params max
    round_interval_seconds=3600,      # Hourly updates
    target_update_size_kb=500         # 500KB target
)
```

---

### Phase 2: Edge Deployment (Per Robot)

**Step 4: Initialize Secured Client**
```python
from tensorguard.core.client import create_client
from tensorguard.core.adapters import MoEAdapter

client = create_client(
    security_level=128,
    cid="robot_warehouse_01",
    key_path="keys/warehouse_fleet_v1.npy"
)

# Attach your task-aware FedMoE adapter (v2.0)
client.set_adapter(MoEAdapter())
```

**Step 5: Buffer Training Demonstrations**
```python
from tensorguard.api.schemas import Demonstration
import numpy as np

# As robot operates, buffer successful episodes
demo = Demonstration(
    observations=[np.zeros((224, 224, 3))],
    actions=[np.zeros(7)]
)
client.add_demonstration(demo)
```

**Step 6: Trigger Secure Update**
```python
# After enough demos (e.g., end of shift)
update_package = client.process_round()

# Check update was created
print(f"Package size: {len(update_package.serialize()) / 1024:.1f} KB")
print(f"Privacy spent: ε={update_package.safety_stats.dp_epsilon_consumed:.4f}")
```

---

### Phase 3: Server Aggregation

**Step 7: Run Aggregation Server**
>>>>>>> 9ac05e7 (v2.3 Release: Empirical Research Validation & High-Fidelity FastUMI Benchmarking. (Verified non-theoretical metrics for ML success, bandwidth efficiency, and MoE routing))
```bash
# Set DB URL (defaults to sqlite:///tensorguard.db)
set DATABASE_URL=postgresql://user:pass@localhost:5432/tensorguard

# Apply Alembic migrations
alembic upgrade head
```

### Step 3: Seed Default Policies
This creates the "Default Fleet", the "CISO Admin" account, and the **Global Optimization Policy**.
```bash
python scripts/seed_db.py --admin-email admin@corp.com --optimize-policy FORCE
```

### Step 4: Start Services
Use the unified launcher:
```bash
python qa_simulation_600.py
# OR for production:
uvicorn src.tensorguard.platform.main:app --host 0.0.0.0 --port 8000
```

## 3. Edge Agent Deployment (The Robots)

### Step 1: Install SDK
On the robot (e.g., Jetson Orin):
```bash
pip install tensorguard-edge
```

### Step 2: Provision Identity
1. Go to **Mission Control** -> **Fleets** -> **Add Device**.
2. Download the `identity.json` (contains mTLS certs).
3. Place in `/etc/tensorguard/identity.json`.

### Step 3: Run Worker
```bash
tensorguard-worker --config /etc/tensorguard/identity.json
```
*Note: The worker will auto-negotiate with the server and compile local TensorRT engines upon first connection.*

## 4. Verification

1. **Dashboard**: Visit `http://localhost:8000`. You should see the **System Health** gauge at 100%.
2. **Telemetry**: Connect a test worker. Check **Mission Control** > **Efficiency Card**. You should see "Compute Speedup: ~5.4x".
3. **Logs**: Check server logs for `[POLICY] Enforcing Global 2:4 Sparsity Strategy`.

## 5. Troubleshooting

<<<<<<< HEAD
- **gRPC Connection Failed**: Check firewall on port 9000.
- **TensorRT Compilation Error**: Ensure `trtutil` is in PATH on the edge device.
- **High Latency**: Check `Efficiency Card` for "Bandwidth Saved". If low, Rand-K sparsity might be disabled in Policy.
=======
### Scenario C: Healthcare (HIPAA Compliant)

| Parameter | Value |
|-----------|-------|
| **Environment** | Certified cloud region |
| **Robots** | 5x Assistive robots |
| **Privacy** | DP ε=0.5 (strict) |
| **Audit** | Full compliance logging |

```python
config = ShieldConfig(
    model_type="custom",
    key_path="/secure/hipaa_key.pem",
    dp_epsilon=0.5,  # Stricter privacy
    security_level=128
)
```

---

## 4. Production Blueprint

### Operating Envelope

The envelope enforces hard constraints to prevent drift:

```python
envelope = OperatingEnvelope(
    peft_strategy=PEFTStrategy.LORA,
    trainable_modules=["policy_head", "last_4_blocks"],
    max_trainable_params=10_000_000,
    round_interval_seconds=3600,
    target_update_size_kb=500,
    enable_canary=True,
    canary_percentage=0.1
)
```

### Privacy Controls

Separate knobs for security and ML teams:

```python
# DP Profile (Security Team)
dp_profile = DPPolicyProfile(
    clipping_norm=1.0,
    epsilon_budget=10.0,
    hard_stop_enabled=True
)

# Training Profile (ML Team)
training_profile = TrainingPolicyProfile(
    compression_ratio=32,
    sparsity=0.01,
    max_quality_mse=0.05
)
```

### Resilient Aggregation

Handle real-world failures:

```python
from tensorguard.server.aggregator import ExpertDrivenStrategy

strategy = ExpertDrivenStrategy(
    quorum_threshold=2,
    enable_bayesian_eval=True
)
```

---

## 5. SDK Reference

### Core Classes

| Class | Purpose |
|-------|---------|
| `EdgeClient` | Main client for edge robots |
| `TensorGuardStrategy` | Flower-compatible aggregation strategy |
| `N2HEEncryptor` | Homomorphic encryption engine |
| `UpdatePackage` | Wire format for encrypted updates |
| `KeyManagementSystem` | Enterprise key lifecycle |
| `EvaluationGate` | Safety checks before deployment |

### Configuration

```python
@dataclass
class ShieldConfig:
    model_type: str = "pi0"
    key_path: str = "keys/node_key.pem"
    security_level: int = 128
    compression_ratio: int = 32
    sparsity: float = 0.01
    dp_epsilon: float = 1.0
    # v2.0: Skellam DP noise + Expert Gating active
```

### Performance Specs

| Operation | Jetson Orin NX | Jetson AGX Orin |
|-----------|----------------|-----------------|
| Expert Gradient Computation | ~240ms | ~120ms |
| Skellam-N2HE Encryption | ~80ms | ~35ms |
| Upload (Compressed UpdatePackage) | ~2KB/demo | ~2KB/demo |

---

## 6. Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Edge Compute | Jetson Orin Nano 8GB | Jetson AGX Orin 64GB |
| Storage | 32GB NVMe | 256GB NVMe |
| Network | 100Mbps | 1Gbps |
| RAM | 8GB | 32GB+ |

---

## 7. FAQ

### General

**Q: Can I use TensorGuard without N2HE encryption?**
A: Yes. Set `security_level=0` in config to use DP-only mode for trusted networks.

**Q: What VLA models are supported?**
A: OpenVLA, Pi0, RT-2, and any custom model with a gradient function.

### Security

**Q: Where are keys stored?**
A: Keys are stored locally on your hardware. TensorGuard never transmits private keys.

**Q: What happens if a robot is stolen?**
A: Use `KeyManagementSystem.revoke_key()` to immediately invalidate that robot's contributions.

### Performance

**Q: How much bandwidth does it save?**
A: Random sparsification + compression achieves **50x reduction** (15MB → 300KB) while maintaining model quality.

**Q: Does encryption slow inference?**
A: No. TensorGuard only operates during training. Inference runs at full speed.

---

## Production Checklist

Before deploying TensorGuard in production:

- [ ] Generate enterprise key with `generate_key()`
- [ ] Register key with `KeyManagementSystem`
- [ ] Configure `OperatingEnvelope` with hard limits
- [ ] Set up `DPPolicyProfile` with privacy budget
- [ ] Enable `EvaluationGate` with safety thresholds
- [ ] Configure observability (metrics → monitoring stack)
- [ ] Run benchmarks to validate SLAs
- [ ] Test key rotation procedure
- [ ] Document break-glass key revocation process
- [ ] Verify `liboqs-python` installation on all nodes
- [ ] Confirm `TENSORGUARD_PRODUCTION_MODE=true` set in `.env`

---

## Support

- **Documentation**: https://github.com/Danielfoojunwei/TensorGuard
- **Issues**: https://github.com/Danielfoojunwei/TensorGuard/issues

---

© 2025 TensorGuard Team | DTC @ NTU | HintSight Technology
>>>>>>> 9ac05e7 (v2.3 Release: Empirical Research Validation & High-Fidelity FastUMI Benchmarking. (Verified non-theoretical metrics for ML success, bandwidth efficiency, and MoE routing))
