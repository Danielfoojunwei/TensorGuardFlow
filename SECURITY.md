# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in TensorGuard, please report it responsibly:

1. **DO NOT** create a public GitHub issue
2. Email security concerns to the maintainers directly
3. Include detailed steps to reproduce the issue
4. Allow reasonable time for a fix before public disclosure

## Key Management

### NEVER Commit Secrets

The following should **NEVER** be committed to version control:

- Private keys (`*.key`, `*.pem`, `*.p12`)
- API keys and tokens
- Database credentials
- Environment files with secrets (`.env`)
- Any file in the `keys/` directory

### Development Key Generation

For development and testing, generate keys locally:

```bash
# Generate identity keys for testing
python -c "
from tensorguard.identity.keys.provider import FileKeyProvider
provider = FileKeyProvider('./keys/identity')
key_id = provider.generate_key()
print(f'Generated test key: {key_id}')
"

# Generate N2HE keys for aggregation testing
python -c "
from tensorguard.core.crypto import N2HEContext
ctx = N2HEContext()
print('N2HE context initialized with fresh keys')
"
```

### Production Key Management

For production deployments:

1. Use a proper Key Management System (KMS):
   - AWS KMS
   - Google Cloud KMS
   - HashiCorp Vault
   - Hardware Security Modules (HSM)

2. Rotate keys regularly
3. Use separate keys for each environment
4. Enable audit logging for all key operations

## Cryptographic Notices

### Post-Quantum Cryptography (PQC)

**IMPORTANT**: The PQC implementations in `src/tensorguard/crypto/pqc/` support dual-mode operation:
- **Production Mode**: Requires `liboqs-python` and the native `liboqs` library. Enforced by default when `TENSORGUARD_PRODUCTION_MODE=true`.
- **Simulator Mode**: Used for development only. Provides **NO CRYPTOGRAPHIC SECURITY**.

In production mode, the system will **Fail-Closed** if `liboqs` is missing. To override for research:
```bash
export TENSORGUARD_ENABLE_EXPERIMENTAL_CRYPTO=true
```

For production PQC, ensure:
- `liboqs-python` is installed
- NIST Level 3 parameters are verified for your latency requirements

### Custom Cryptography

The N2HE (Noise-Tolerant Homomorphic Encryption) implementation in
`src/tensorguard/core/crypto.py` is a research prototype. 

**Enforcement**: In production mode, the native N2HE prototype is **BLOCKED** to prevent accidental deployment of unaudited code. Users must:
1. set `TENSORGUARD_ENABLE_EXPERIMENTAL_CRYPTO=true` to acknowledge the risk.
2. Integrate with audited libraries (SEAL, OpenFHE) for production use.

## Serialization Security

### Avoid Pickle

Never use `pickle` for untrusted data. TensorGuard uses:
- `msgpack` for safe binary serialization
- `json` for human-readable formats
- Protocol Buffers for structured data (where applicable)

If you must handle legacy pickle files, use `safetensors` or similar
restricted unpicklers.

## Network Security

### TLS Requirements

All production deployments should:
- Use TLS 1.3 (minimum TLS 1.2)
- Enable certificate verification
- Use strong cipher suites
- Implement certificate pinning for critical paths

### API Authentication

- Use short-lived JWT tokens
- Implement proper token rotation
- Rate limit authentication endpoints
- Log all authentication failures

## Compliance

TensorGuard's evidence fabric supports compliance documentation for:
- SOC 2 Type II
- ISO 27001
- NIST CSF

However, achieving compliance requires:
- Proper operational controls
- Security monitoring
- Incident response procedures
- Regular audits

The software alone does not guarantee compliance.
