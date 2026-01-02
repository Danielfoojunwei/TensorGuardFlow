# Product Requirement Document: TensorGuard Edge Agent

## 1. Executive Summary
The Edge Agent (`tensorguard-agent`) is the lightweight, secure runtime that lives on end devices (servers, robots, IoT gateways). It is responsible for establishing trust with the platform, securely pulling/decrypting TGSP packages, and enforcing privacy policies on network traffic.

## 2. Target Persona
-   **Embedded Engineer:** Cares about resource usage (RAM/CPU) and stability.
-   **Security Engineer:** Cares about root-of-trust and attack surface.

## 3. Core Features (Must Haves)

### 3.1 Establishing Trust (Identity)
-   **Requirement:** Prove the device's identity and integrity to the Platform.
-   **Spec:**
    -   **Bootstrapping:** CSR-based enrollment using a registration token.
    -   **Automatic Renewal:** Rotates mTLS certificates automatically before expiry (short-lived certs, e.g., 24h).
    -   **Attestation:** (Future) Integration with TPM 2.0 / TEE for hardware-backed identity.

### 3.2 Secure Runtime (The "Guardian")
-   **Requirement:** Managing the model lifecycle securely.
-   **Spec:**
    -   **TGSP Handling:** Download -> Verify Signature -> Verify Policy -> Decrypt in memory (never to disk if possible) -> Load into Inference Engine.
    -   **Key Storage:** Secure local storage of identity keys (encrypted at rest).

### 3.3 Network Guardian (RTPL Enforcer)
-   **Requirement:** Intercept and shape traffic.
-   **Spec:**
    -   Transparent proxy for outbound ML traffic.
    -   Applies padding and dummy traffic as configured by the Platform policy.

### 3.4 Resilience & Self-Healing
-   **Requirement:** Must not crash the host device; must recover from network partitions.
-   **Spec:**
    -   Offline mode (cache latest valid policy).
    -   Resource limits (cgroups/Docker limits).
    -   Watchdog process to restart daemon.

## 4. Technical Constraints
-   **Footprint:** < 100MB RAM usage when idle.
-   **Binary Size:** < 50MB.
-   **OS Support:** Linux (Ubuntu 20.04+, Yocto), Windows 10/11.

## 5. Success Metrics
-   **Stability:** 99.9% uptime on devices.
-   **Security:** 0 privilege escalations.
