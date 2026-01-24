# Product Requirement Document: TensorGuard Secure Package - TGSP (v1.2 Spec / v2.3 Ready)

## 1. Executive Summary
The TensorGuard Secure Package (TGSP) is the standardized container format for distributing machine learning models to untrusted edge devices. It ensures that models are encrypted at rest, verified for integrity before execution, and only decryptable by authorized devices.

> [!NOTE]
> **Versioning Enforcement**: v2.3 of the SDK strictly enforces the v1.2 TGSP specification to prevent downgrade attacks.
It ensures that models can only be opened by authorized agents and that their integrity is guaranteed.

## 2. Target Persona
-   **AI Engineer:** Wants to package models easily (`tgsp pack`) without learning complex crypto.
-   **Security Engineer:** Requirements stronger encryption (no AES-ECB) and secure key distribution.
-   **Compliance Officer:** Needs to know exactly what version of a model is deployed.

## 3. Core Features (Must Haves)

### 3.1 Secure Containerization
-   **Requirement:** Encrypt model weights and metadata.
-   **Spec:** 
    -   **Cipher:** ChaCha20-Poly1305 or AES-256-GCM.
    -   **Key Management:** Hybrid encryption. Data Encryption Key (DEK) wrapped by Key Encryption Keys (KEK) using ECDH (X25519).
    -   **Integrity:** Poly1305 MAC tag verified before decryption.

### 3.2 Canonical Manifest
-   **Requirement:** A metadata layer that is byte-for-byte reproducible for signing.
-   **Spec:**
    -   Format: CBOR (Concise Binary Object Representation) utilizing Deterministic Encoding.
    -   Fields: `package_id`, `version`, `author_id`, `created_at`, `content_hash` (SHA-256), `policy_constraints`.

### 3.3 Access Control Policies
-   **Requirement:** The package itself dictates *who* can open it.
-   **Spec:**
    -   `target_fleet`: Only decryptable by agents belonging to Fleet ID X.
    -   `not_before` / `not_after`: Temporal validity.

### 3.4 CLI & SDK Support
-   **Requirement:** Easy tooling.
-   **Commands:**
    -   `tgsp build <model_dir>`
    -   `tgsp inspect <package.tgsp>`
    -   `tgsp verify <package.tgsp>`

## 4. Technical Constraints
-   **Performance:** Decryption overhead must be < 5% of model load time.
-   **Size:** Container overhead must be < 1MB + 1% of payload.
-   **Cross-Platform:** Must work on Linux (Server), Windows (Dev), and Jetson/Edge (ARM).

## 5. Success Metrics
-   **Adoption:** % of deployed models in fleet using TGSP vs raw files.
-   **Security:** 0 known instances of unauthorized decryption.
-   **Performance:** P99 Packaging time < 1min for 1GB model.
