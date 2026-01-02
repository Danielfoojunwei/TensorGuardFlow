# TensorGuard™: The Intelligent Privacy & Security Platform for AI Fleets

![TensorGuard Banner](https://img.shields.io/badge/TensorGuard-v2.1.0-0ea5e9?style=for-the-badge) 
![Status](https://img.shields.io/badge/Status-Production_Ready-success?style=for-the-badge)
![Security](https://img.shields.io/badge/Security-Post_Quantum_Hybrid-purple?style=for-the-badge)
![Compliance](https://img.shields.io/badge/Compliance-ISO_27001_Ready-blue?style=for-the-badge)

> **"Secure the Pulse of Artificial Intelligence."**

TensorGuard is the industry-first **Post-Quantum Secure MLOps Platform** designed for high-stakes edge computing environments. It orchestrates the secure lifecycle of AI models on robotic fleets, medical devices, and critical infrastructure, ensuring that proprietary intelligence remains confidential (Model Privacy) and tamper-proof (Integrity) even in hostile environments.

---

## 📑 Table of Contents

1.  [Executive Summary](#executive-summary)
2.  [System Architecture](#system-architecture)
3.  [Post-Quantum Hybrid Cryptography](#post-quantum-hybrid-cryptography)
    *   [Threat Model: Harvest Now, Decrypt Later](#threat-model)
    *   [Hybrid Architecture (Kyber + Dilithium)](#hybrid-architecture)
    *   [Robotics Trade-off Analysis](#robotics-trade-off-analysis)
4.  [Core Components](#core-components)
    *   [Platform (Control Plane)](#platform-control-plane)
    *   [Agent (Data Plane)](#agent-data-plane)
    *   [TGSP (TensorGuard Security Protocol)](#tgsp-tensorguard-security-protocol)
    *   [MOAI (Secure Runtime)](#moai-secure-runtime)
5.  [Key Features & Capabilities](#key-features--capabilities)
    *   [Orthogonal Finetuning (OFT)](#orthogonal-finetuning-oft)
    *   [Federated Learning (FL)](#federated-learning-fl)
    *   [Network Defense (WTFPAD)](#network-defense)
6.  [Compliance & Certifications](#compliance--certifications)
    *   [ISO 27001:2022 Mapping](#iso-27001-mapping)
    *   [NIST CSF 2.0 Mapping](#nist-csf-mapping)
7.  [Performance Benchmarks](#performance-benchmarks)
8.  [Developer Guide](#developer-guide)
9.  [Visual Gallery](#visual-gallery)

---

## 1. <a name="executive-summary"></a>Executive Summary

In the age of ubiquitous AI, the model *is* the IP. deploying advanced neural networks to thousands of edge devices creates a massive attack surface. Traditional TLS and disk encryption are insufficient against physical tampering, side-channel attacks, and the looming threat of Quantum Computing.

TensorGuard solves this by wrapping models in **TGSP v1.0**, a cryptographic envelope that creates a "Secure Enclave" logic without requiring specialized hardware. It combines **Privacy-Preserving Machine Learning (PPML)** with **Post-Quantum Cryptography (PQC)** to guarantee:

*   **Confidentiality**: Weights are decrypted only in volatile memory at the nanosecond of inference.
*   **Integrity**: Every byte of the model is signed by a Quantum-Resistant Digital Signature.
*   **Provenance**: Full custodial chain of custody from training cluster to edge robot.

---

## 2. <a name="system-architecture"></a>System Architecture

The TensorGuard ecosystem consists of a centralized **Control Plane (Platform)** and distributed **Edge Agents**.

```mermaid
graph TD
    subgraph Cloud["☁️ Control Plane (TensorGuard Platform)"]
        API[REST API Gateway]
        DB[(PostgreSQL)]
        Vault[Key Vault (HSM)]
        Auth[Identity Provider]
        
        API --> DB
        API --> Vault
        API --> Auth
    end

    subgraph Edge["🤖 Edge Environment (Robotics/IoT)"]
        Agent[TensorGuard Agent]
        MOAI[MOAI Runtime]
        Defense[Network Defense Layer]
        
        Agent -->|Heartbeat / Stats| API
        Agent -->|Pulls TGSP| API
        MOAI -.->|In-Memory Load| Agent
    end

    subgraph User["Data Scientist"]
        CLI[TensorGuard CLI]
        CLI -->|Build & Sign| TGSP[TGSP v1.0 Package]
        TGSP -->|Upload| API
    end
```

### 2.1 Component Interaction Flow
1.  **Build**: Data Scientist uses `tensorguard tgsp build` to package a PyTorch/TensorFlow model. The CLI generates a `manifest.json`, encapsulates the weights using **Hybrid-Kyber**, and signs the bundle with **Hybrid-Dilithium**.
2.  **Publish**: The `TGSP` file is uploaded to the Platform via the secure API.
3.  **Deploy**: The Platform assigns the package to a specific `Fleet` or `Device ID`.
4.  **Fetch**: The Edge Agent, running on a robot, authenticates via mTLS and requests pending updates.
5.  **Secure Load**: The Agent streams the TGSP file. The **MOAI Orchestrator** intercepts the stream, verifies the PQC signature, and decrypts the weights **directly into RAM**.
6.  **Inference**: The model serves predictions while never persisting plaintext to disk.

---

## 3. <a name="post-quantum-hybrid-cryptography"></a>Post-Quantum Hybrid Cryptography

TensorGuard v2.1 introduces the **Hybrid Post-Quantum (PQC)** architecture, compliant with **NIST FIPS 203 (ML-KEM)** and **NIST FIPS 204 (ML-DSA)**.

### <a name="threat-model"></a>3.1 Threat Model: Harvest Now, Decrypt Later
Attackers are currently intercepting and storing encrypted traffic. While they cannot crack ECC (X25519) today, they will break it instantly once a Cryptographically Relevant Quantum Computer (CRQC) comes online (estimated 2030-2035).

**TensorGuard Defense**: By encrypting with *both* Classical ECC and Quantum-Resistant Kyber, an attacker would need to break *both* algorithms to decrypt the data. Since Kyber is mathematically resistant to Shor's algorithm, the data remains safe even in the post-quantum era.

### <a name="hybrid-architecture"></a>3.2 Hybrid Architecture (Kyber + Dilithium)

We do not replace Classical Crypto; we augment it. This is "Hybrid Mode".

| Component | Classical Primitive | Post-Quantum Primitive | Hybrid Result |
| :--- | :--- | :--- | :--- |
| **Key Exchange (KEM)** | X25519 (ECDH) | **Kyber-768 (ML-KEM)** | `SHA256( ECDH_Shared || Kyber_Shared )` |
| **Signatures** | Ed25519 | **Dilithium-3 (ML-DSA)** | `{ "sig_classic": ..., "sig_pqc": ... }` |

### <a name="robotics-trade-off-analysis"></a>3.3 Robotics Trade-off Analysis

Migrating to PQC incurs costs in bandwidth and startup latency.

| Metric | Classical (v0.2) | Hybrid PQC (v1.0) | Impact |
| :--- | :--- | :--- | :--- |
| **Public Key Size** | 32 Bytes | **1,216 Bytes** | Low (One-time exch) |
| **Signature Size** | 64 Bytes | **3,357 Bytes** | High (Per Package) |
| **Verification Time** | ~0.1 ms | **~5.2 ms** | Medium (Boot only) |
| **Control Loop Latency** | 20 µs | **20 µs** | **Zero Impact** |

**Conclusion**: The ~5ms penalty occurs only at *startup*. Once the model is loaded, inference speed is identical because the payload is encrypted with symmetric ChaCha20Poly1305.

---

## 4. <a name="core-components"></a>Core Components

### <a name="tgsp-tensorguard-security-protocol"></a>4.1 TGSP (TensorGuard Security Protocol)

The TGSP v1.0 Container Format is a binary envelope designed for zero-trust delivery.

**File Structure (`.tgsp`):**
```
+-------------------------------------------------------+
| Magic (6B) "TGSP\x01\x00"                             |
+-------------------------------------------------------+
| Header Len (4B) | Header JSON (Metadata, Hashes)      |
+-------------------------------------------------------+
| Manifest Len (4B) | Manifest JSON (Model Info)        |
+-------------------------------------------------------+
| Recipients Len (4B) | Recipients JSON (KEM Blocks)    |
+-------------------------------------------------------+
| Payload Len (8B) | Encrypted Stream (ChaCha20)        |
+-------------------------------------------------------+
| Sig Len (4B) | Signature JSON (Dual Signed)           |
+-------------------------------------------------------+
```

### <a name="moai-secure-runtime"></a>4.2 MOAI (Secure Runtime)

MOAI (Model Obfuscation & Anonymous Inference) is the runtime engine within the Agent.

*   **SecureMemoryLoader**: A specialized loader that decrypts chunks of the TGSP stream and reassembles the Python object graph (Pickle/SafeTensors) in a protected memory region.
*   **TenSEAL Backend**: Supports homomorphic operations for privacy-preserving aggregation (if enabled).

---

## 5. <a name="key-features--capabilities"></a>Key Features & Capabilities

### <a name="orthogonal-finetuning-oft"></a>5.1 Orthogonal Finetuning (OFT)
TensorGuard supports **OFT** for efficient on-device adaptation. Unlike LoRA which adds adapter matrices, OFT multiplies weights by an orthogonal matrix $R$. This preserves the hyperspherical energy of the pre-trained model, ensuring stability during continuous learning on robotics hardware.

<img src="artifacts/oft_mechanism.png" width="600" alt="OFT Mechanism">

### <a name="federated-learning-fl"></a>5.2 Federated Learning (FL)
Secure Aggregation topology allows thousands of agents to train locally and submit encrypted gradients to the central parameter server.

<img src="artifacts/fl_architecture.png" width="600" alt="Federated Learning">

### <a name="network-defense"></a>5.3 Network Defense (WTFPAD)
**Adaptive Padding** and **Traffic Morphing** are used to defeat Traffic Analysis attacks.
*   **Jitter Buffering**: Randomizes packet inter-arrival times.
*   **Dummy Traffic**: Injects chaff packets to mask idle periods vs. inference bursts.

---

## 6. <a name="compliance--certifications"></a>Compliance & Certifications

TensorGuard helps organizations meet rigorous security standards.

### <a name="iso-27001-mapping"></a>6.1 ISO 27001:2022 Mapping

| Clause | Requirement | TensorGuard Control |
| :--- | :--- | :--- |
| **A.5.15** | Access Control | RBAC enforced in `platform/auth.py` |
| **A.8.24** | Use of Cryptography | TGSP v1.0 enforced in `moai/orchestrator.py` |
| **A.8.12** | Data Leakage Prevention | In-memory decryption prevents disk leaks |

### <a name="nist-csf-mapping"></a>6.2 NIST CSF 2.0 Mapping

| Function | Category | Implementation |
| :--- | :--- | :--- |
| **PROTECT** | PR.DS-01 (Data at Rest) | ChaCha20-Poly1305 Encrypted Storage |
| **DETECT** | DE.CM-01 (Monitoring) | `IdentityAuditLog` tamper-proof trails |
| **RESPOND** | RS.MI-02 (Mitigation) | Automated certificate revocation |

---

## 7. <a name="performance-benchmarks"></a>Performance Benchmarks

**Test Environment**: NVIDIA Jetson Orin Nano (8GB)

| Operation | Metric | Value | Status |
| :--- | :--- | :--- | :--- |
| **Agent Cold Start** | Time to Ready | **1.2s** | ✅ Fast |
| **TGSP Decryption** | Throughput | **210 MB/s** | ✅ Real-time |
| **PQC Sig Verify** | Latency | **5.2 ms** | ⚠️ Noticeable |
| **API Latency** | P99 | **45 ms** | ✅ Reactive |
| **Memory Footprint** | Idle | **64 MB** | ✅ Lightweight |

---

## 8. <a name="developer-guide"></a>Developer Guide

### Installation
```bash
pip install tensorguard
```

### Creating a Secure Package (CLI)
```bash
# 1. Generate Hybrid Identity
tensorguard keygen --type signing --out ./keys

# 2. Package & Sign Model
tensorguard build \
  --input-dir ./my_model_v1 \
  --out ./my_model_v1.tgsp \
  --signing-key ./keys/signing.priv \
  --model-name "perception-net"
```

### Running the Platform Locally
```bash
# Start the server (auto-inits DB)
python -m src.tensorguard.platform.main
```

---

© 2026 TensorGuard AI Inc. | [Security Policy](SECURITY.md) | [Documentation](docs/)
