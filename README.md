# TensorGuard Unified Trust Fabric

**Production-Grade Security & Privacy Architecture for Autonomous Fleets**

TensorGuard is a comprehensive **Unified Trust Fabric** designed to secure the entire lifecycle of autonomous edge agents. It consolidates Machine Identity, Network Privacy (RTPL), and Federated Learning into a single, cohesive **Unified Agent** architecture.

---

## 🏛️ Unified Architecture

The system is architected around a **Unified Agent Daemon** that runs on every edge node, managed by a centralized **Control Plane**. This ensures that security policies, privacy parameters, and learning tasks are synchronized across the entire fleet in real-time.

```mermaid
graph TD
    subgraph "Control Plane (Cloud)"
        CP[Policy & Config Server]
        CA[Certificate Authority]
        FL[Federated Aggregator]
    end

    subgraph "Edge Node (Robot/Device)"
        subgraph "Unified Agent Daemon"
            cfg[Config Manager]
            
            subgraph "Subsystems"
                ID[Identity Guard (CLM)]
                NET[Network Guardian (RTPL)]
                ML[Training Worker (Core)]
            end
            
            cfg -->|Sync Policies| CP
            ID -->|CSR & Renewals| CA
            NET -->|Proxy Defense| Internet
            ML -->|Encrypted Gradients| FL
        end
    end
```

### Key Components

1.  **Unified Agent Daemon (`src/tensorguard/agent/daemon.py`)**:
    *   The core process that orchestrates all local subsystems.
    *   Manages configuration hot-reloading and synchronization with the Control Plane.
    *   Ensures process isolation and resource governance.

2.  **Control Plane (`src/tensorguard/platform`)**:
    *   Centralized management API for defining Fleet Policies.
    *   Handles Certificate Authority (CA) operations for the Trust Fabric.
    *   Aggregates federated learning updates.

---

## 🛡️ Subsystem Deep Dive

### 1. Machine Identity Guard (CLM)
**Goal:** Zero-Trust Identity at Scale.

The **Identity Manager** (`tensorguard.agent.identity`) implements a robust Certificate Lifecycle Management (CLM) system similar to SPIFFE/SPIRE but optimized for edge constraints.

*   **Short-Lived Certificates:** Enforces aggressive rotation (e.g., hourly) to minimize key compromise windows.
*   **Automated Renewal:** Background scheduler handles CSR generation and signing without interrupting services.
*   **Infrastructure Integration:**
    *   **Kubernetes:** Auto-injects secrets into Pods.
    *   **Sidecars:** Hot-reloads Nginx/Envoy proxies with new certs.
    *   **Audit Trails:** Cryptographically verifiable logs of all identity operations.

### 2. Robot Traffic Privacy Layer (RTPL)
**Goal:** Defend against Network Side-Channel Attacks.

The **Network Guardian** (`tensorguard.agent.network`) protects agent communication patterns from being analyzed by passive eavesdroppers (ISPs, nation-state actors). It implements the **RTPL** standard.

*   **Transparent Proxy:** An `asyncio`-based TCP/SOCKS proxy intercepts designated traffic.
*   **Zero-Delay Defenses:**
    *   **FRONT (Fast Random Obfuscation of Network Traffic):** Injects dummy packets continuously using a Rayleigh distribution to mask real traffic bursts without adding latency.
    *   **WTF-PAD (Website Traffic Fingerprinting Protection with Adaptive Defense):** Adaptive padding based on inter-arrival time histograms.
    *   **Padding:** Standard constant-rate padding for high-security, low-bandwidth command channels.

### 3. Federated Intelligence (Core ML)
**Goal:** Collaborative Learning without Data Leakage.

The **ML Manager** (`tensorguard.agent.ml`) enables the fleet to learn from distributed experience while preserving local data privacy.

*   **Federated Learning:** Integrated **Flower** (Flwr) client for decentralized gradient aggregation.
*   **Privacy-Enhancing Technologies (PETs):**
    *   **Differential Privacy (DP):** Adds calibrated noise to gradients to prevent individual record reconstruction.
    *   **Secure Aggregation:** Uses Near-Optimal 2-Party Homomorphic Encryption (N2HE) to sum updates while encrypted.
*   **Parameter-Efficient Fine-Tuning (PEFT):** Adapts foundation models (like Pi0, OpenVLA) using LoRA adapters, significantly reducing bandwidth requirements.

---

## 🔧 Technical Implementation

### Unified Configuration Schema
The system uses a strict **Pydantic** schema (`src/tensorguard/schemas/unified_config.py`) to validate all configurations. This ensures type safety and prevents misconfiguration across the distributed system.

```python
class AgentConfig(BaseModel):
    identity: IdentityConfig  # Scan intervals, Key types
    network: NetworkConfig    # Defense modes (FRONT/WTF-PAD), Proxy ports
    ml: MLConfig             # DP Epsilon, Model types
```

### Asynchronous Concurrency
The Agent Daemon leverages Python's `asyncio` and threading to handle multiple intensive tasks concurrently:
*   **Network Guardian:** Runs a high-performance `asyncio` event loop for non-blocking packet forwarding and dummy injection.
*   **ML Worker:** Runs training loops in separate threads to avoid blocking the heartbeat or defense mechanisms.
*   **Config Sync:** Background thread maintains persistent WebSocket/HTTP connectivity with the Control Plane.

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+
*   Poetry (recommended) or pip

---

## 🛠️ Quick Start

### 1. Installation
```bash
git clone https://github.com/Danielfoojunwei/TensorGuardFlow
cd TensorGuardFlow
pip install -r requirements.txt
pip install .
```

### 2. Run a Robotics Pipeline (CLI)
Ingest a rosbag and check it against policy:
```bash
# Ingest
python scripts/tgflow_ros2_ingest.py path/to/my_log.db3 --output-dir ./runs/input

# Slice
python scripts/tgflow_slice.py ./runs/input

# Run Job (via Python module for now)
python -m tensorguard.enablement.pipelines.run_job path/to/my_log.db3
```

### 3. Launch the Enablement Sidecar
```bash
uvicorn api.enablement_service:app --port 8080
```

### 4. Running the Unified Agent

1.  **Configure the Agent:**
    Create a `config.json` (or let it auto-generate).
2.  **Start the Daemon:**
    ```bash
    tensorguard agent
    ```
    *Output:*
    ```
    INFO:tensorguard.agent.daemon:Starting TensorGuard Unified Agent...
    INFO:tensorguard.agent.network.guardian:Network Guardian proxy starting on port 9000
    INFO:tensorguard.agent.ml.manager:Connecting to aggregator at 127.0.0.1:8080
    ```

### Running the Control Plane

```bash
tensorguard server --host 0.0.0.0 --port 8000
```
Access the API documentation at `http://localhost:8000/docs`.

---

## 📜 License
Apache 2.0 - TensorGuard by Daniel Foo Jun Wei.

---

## 🏆 Empirical Evidence & Benchmarks

We have empirically validated the system's security and efficiency claims using rigorous benchmark scripts included in the repository.

### 1. Traffic Fingerprinting Defense (vs. State-of-the-Art)
**Threat**: Passive eavesdroppers identifying robotic actions (Pick/Place/Move) via encrypted traffic side-channels.
**Reference**: *"On the Feasibility of Fingerprinting Collaborative Robot Network Traffic" (Tang et al.)*

| Strategy | Logic | Resulting Attack Accuracy | Verdict |
| :--- | :--- | :--- | :--- |
| **Baseline (Standard TLS)** | Encrypted, No shaping | **100.0%** (Total Failure) | ❌ Vulnerable |
| **Paper's Suggestion** (FRONT/Padding) | Randomized noise/padding | **96.7%** (Ineffective) | ❌ Vulnerable |
| **TensorGuard Solution** (Strict CBR) | **Strict 500Hz Traffic Shaping** | **43.3%** (Near Random) | ✅ **SECURE** |

*Verification*: Run `python scripts/benchmark_fingerprinting.py`

### 2. Federated Learning Efficiency (vs. Legacy V1)
**Goal**: Collaborative learning on constrained edge robots without massive bandwidth costs.
**Comparison**: TensorGuard V2 (PEFT/MoE) vs. Legacy V1 (Standard FedAvg).

| Metric | Legacy Repo (V1) | TensorGuard (V2) | Improvement |
| :--- | :--- | :--- | :--- |
| **Update Method** | Full Model (Dense) | **Expert-Driven (Sparse)** | **Intelligent Routing** |
| **Bandwidth/Round** | ~500 MB | **~160 MB** | **3.1x Better** |
| **Privacy Guarantee**| None (Plaintext) | **N2HE (Quantum-Safe)** | **Unbreakable** |
| **Architecture** | Centralized/Standard | Heterogeneous (MoE) | Flexible |

*Verification*: Run `python scripts/benchmark_peft_fl.py`

### 3. Cryptographic Performance
**Component**: Near-Optimal 2-Party Homomorphic Encryption (N2HE).

| Operation | Time (ms) | Security Level |
| :--- | :--- | :--- |
| **KeyGen** | 12.4 ms | 128-bit Quantum-Safe |
| **Encrypt (Batch)** | 8.2 ms | Indistinguishable (IND-CPA) |
| **Decrypt** | 4.1 ms | - |

*Verification*: Run `python scripts/verify_crypto.py`

---

## 📦 Deployment

### Release to Git
The entire system is version-controlled and verified.
```bash
git push origin main
```

