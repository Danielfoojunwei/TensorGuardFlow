# TensorGuard User & Workflow Guide

Welcome to the TensorGuard Enterprise PLM. This guide explains how to operate the platform and manage your robotic fleet's security lifecycle.

## 🧭 Navigating the Dashboard

The **Trust Console** is organized into four primary functional areas:

### 1. Unified Dashboard
- **Active Identifiers**: Count of verified agents currently connected to the Trust Fabric.
- **Model Lineage Score**: Percentage of model updates that have been cryptographically verified through the audit trail.
- **Privacy Budget (ε)**: Current cumulative Differential Privacy cost. The system prevents training when the epsilon budget is exhausted.

### 2. Model Lineage
View the history of model adaptations (LoRA weights, MoE gates). Every change is linked to:
- The **Source Dataset** ID.
- The **Audit Proof** (Hash of the training payload).
- The **System Time** of deployment.

### 3. Compliance Registry
Monitor real-time adherence to global standards:
- **SOC 2**: Status of the Audit Ledger synchronization.
- **GDPR**: Confirmation of active FRONT/WTF-PAD network defenses.
- **HIPAA**: Verification of Homomorphic Encryption batching.

### 4. Audit Trail
A live feed of all security-critical system events. Each entry includes a **Trace ID** for complete accountability.

### 5. Expert-Driven Adaptation (IOSP)
Real-time visualization of how the system parses instructions and routes them to specific "experts" (LoRA adapters).
- **Gating Confidence**: Percentage agreement between scene-parsing keywords and expert mapping.
- **Expert Distribution**: Proportional weighting of Visual, Language, and Manipulation blocks.

---

## 🛠️ Common Workflows

### Triggering a New Enablement Run
When new demonstration data is collected by the robots:
1.  Navigate to the **Dashboard**.
2.  Click **New Enablement Run**.
3.  The system will automatically partition the fleet, allocate privacy budget, and begin the federated training loop.

### Exporting Evidence for ISO 9001
1.  Navigate to **Model Lineage**.
2.  Select the model version.
3.  Click **Export Proof Report** to download a signed PDF containing the cryptographic provenance of the model.

### Managing Keys (UKF)
In the **Vault** tab, you can manual rotate master keys or verify the health of the Certificate Authority.
> [!NOTE]
> Most key management is automated; manual intervention is only recommended for emergency decommissioning.

### Configuring Expert Gating (IOSP)
To optimize performance for specialized tasks, you can customize the keyword mapping for the MoE experts.

1.  Initialize the **MoEAdapter**.
2.  Define **Expert Prototypes** with semantic keywords.

```python
from tensorguard.core.adapters import MoEAdapter

adapter = MoEAdapter()
# View default mapping
print(adapter.expert_prototypes)

# Example: Custom 'Surgical' expert
adapter.expert_prototypes["surgical_precision"] = ["incision", "suture", "vessel"]
```

The system will automatically increase the weighting for the `surgical_precision` block when task instructions contain these keywords.
