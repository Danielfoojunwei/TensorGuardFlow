# TensorGuardFlow: Zero-Trust Robotics VLA Platform

**TensorGuardFlow** is a production-ready SDK for secure Vision-Language-Action (VLA) model development and deployment. It provides the cryptographic and statistical guardrails needed for collaborative robotic learning across heterogeneous fleets without compromising proprietary IP or sensitive site data.

---

## 🏛️ System Architecture

TensorGuardFlow operates on two core pillars designed for the robotics edge:

### 1. Federated Edge (N2HE Training)
Decentralized fine-tuning using **Near-Optimal 2-Party Homomorphic Encryption (N2HE)**.
- **Privacy**: High-utility lattice-based encryption (LWE) with Skellam noise (Valovich, 2016).
- **Efficiency**: Expert-Driven Aggregation (EDA) for Mixture-of-Experts (MoE) architectures.
- **Resilience**: MAD-based outlier detection and straggler-resistant aggregation.

### 2. MOAI (Secure Inference)
A **Module-Optimising Architecture for Non-Interactive Secure Transformer Inference** (IACR 2025/991).
- **Technology**: Real Fully Homomorphic Encryption (FHE) using TenSEAL (CKKS).
- **Flow**: Secured inputs → Encrypted cloud inference → Secured responses.
- **Integrations**: Native bridges for **Open-RMF**, **VDA5050**, and **Formant**.

---

## 🚀 Key Features (De-Mocked v2.1)

- ✅ **Real FHE Backend**: TenSEAL-based CKKS runtime replacing all mock inference stubs.
- ✅ **Homomorphic Aggregator**: Server-side summation of encrypted gradients ($E(a) + E(b) = E(a+b)$).
- ✅ **Differential Privacy**: Formal ε-DP guarantees via Skellam noise sampling.
- ✅ **Platform Governance**: Enterprise-grade Management Platform with:
    - **Argon2** password hashing.
    - **SHA-256** Fleet API keys.
    - **HTTP Dispatcher** with graceful network degradation.
- ✅ **Benchmark Suite**: Empirical verification of privacy, robustness, and performance.

---

## 🛠️ Quick Start

### 1. Installation
```bash
git clone https://github.com/Danielfoojunwei/TensorGuardFlow
cd TensorGuardFlow
pip install -r requirements.txt
pip install .
```

### 2. Run E2E MOAI Demo
Verify the real FHE inference flow (KeyGen -> Encrypt -> Infer -> Decrypt):
```bash
python scripts/demo_moai_flow.py
```

### 3. Run Benchmark Suite
Generate a comprehensive performance and privacy report:
```bash
python -m tensorguard.bench.cli report
# View output in artifacts/report.html
```

---

## 🏢 Management Platform

The TensorGuard Management Platform provides a multi-tenant console for fleet orchestration.

**Start the Platform:**
```bash
# Frontend assets served from /public
python -m uvicorn tensorguard.platform.main:app --host 0.0.0.0 --port 8000
```
- **Login**: `http://localhost:8000`
- **API Docs**: `http://localhost:8000/docs`

---

## 🧬 Research & References

TensorGuardFlow is built on cutting-edge research from the **Digital Trust Centre (DTC), Nanyang Technological University**:

*   **MOAI**: Zhang et al. (2025). *MOAI: Module-Optimising Architecture for Non-Interactive Secure Transformer Inference.* [IACR 2025/991](https://eprint.iacr.org/2025/991)
*   **N2HE**: Lam et al. (2024). *Efficient FHE-based Privacy-Enhanced Neural Network for Trustworthy AI-as-a-Service.* IEEE TDSC.
*   **DP-LWE**: Valovich (2016). *The Skellam Mechanism for Differential Privacy.*

---

## 📜 License
Licensed under **Apache 2.0**. Developed in partnership with **HintSight Technology** (N2HE-hexl).

© 2025 TensorGuard by Daniel Foo Jun Wei.
