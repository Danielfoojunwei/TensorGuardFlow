# MOAI Inference Service (TensorGuard v2.0)

TensorGuard MOAI (Module-Optimising Architecture for Non-Interactive Secure Transformer Inference) enables robust, privacy-preserving inference services for robotic fleets.

## Architecture

MOAI splits the lifecycle into two phases:
1. **Training (N2HE)**: Existing TensorGuard flow (Secure Aggregation).
2. **Inference (CKKS)**: non-interactive queries using FHE.

### Threat Model
- **Server**: Honest-but-curious. Sees only encrypted ModelPack and encrypted query inputs.
- **Client (Robot)**: Trusted hardware. Holds secret keys.

## Workflow
1. **Model Export**: A trained checkpoint is stripped to only essential submodules (e.g., `policy_head`) via `FHEExportAdapter`.
2. **Model Packaging**: Weights are quantized and packed into a `ModelPack` optimized for SIMD CKKS operations.
3. **Serving**: The `ModelPack` is loaded into the **MOAI Gateway**.
4. **Inference**:
    - Robot encrypts state vector $x$ -> $ct_x$.
    - Gateway computes $ct_y = FHE(ct_x, W_{pack})$.
    - Robot decrypts $ct_y$ -> logits $y$.

## Key Components
- **`src/tensorguard/moai`**: Core crypto configs headers and key management.
- **`src/tensorguard/serving`**: FastAPI gateway and backend interfaces.
- **`src/tensorguard/integrations`**: Adapters for Open-RMF and VDA5050.

## Usage

### Starting the Server
```bash
docker run -p 8000:8000 tensorguard-moai-serve
```

### Client Example
```python
encryptor = MoaiEncryptor(key_id, config)
ct = encryptor.encrypt_vector(input_vec)
# POST /v1/infer
decryptor = MoaiDecryptor(key_id, sk)
result = decryptor.decrypt_vector(resp.result)
```
