"""
MOAI Module - Secure Transformer Inference with TenSEAL CKKS

This module provides client-side encryption/decryption for MOAI (IACR 2025/991)
secure transformer inference.

Optional Dependency:
    TenSEAL is required for encryption operations. Install with:
    pip install tensorguard[fl]

The module imports will succeed without TenSEAL, but encryption/decryption
operations will raise ImportError with installation instructions.
"""

from .moai_config import MoaiConfig, PackingStrategy

# Lazy imports for tenseal-dependent modules
# These will succeed on import but fail on actual use if tenseal is missing


def __getattr__(name: str):
    """Lazy import for tenseal-dependent classes."""
    if name in ("MoaiKeyManager", "CkksKeyMetadata"):
        from .keys import MoaiKeyManager, CkksKeyMetadata
        return {"MoaiKeyManager": MoaiKeyManager, "CkksKeyMetadata": CkksKeyMetadata}[name]
    elif name in ("MoaiEncryptor", "MoaiDecryptor"):
        from .encrypt import MoaiEncryptor, MoaiDecryptor
        return {"MoaiEncryptor": MoaiEncryptor, "MoaiDecryptor": MoaiDecryptor}[name]
    elif name in ("ModelPack", "ModelPackMetadata"):
        from .modelpack import ModelPack, ModelPackMetadata
        return {"ModelPack": ModelPack, "ModelPackMetadata": ModelPackMetadata}[name]
    elif name in ("MoaiExporter", "export_moai_modelpack"):
        from .exporter import MoaiExporter, export_moai_modelpack
        return {"MoaiExporter": MoaiExporter, "export_moai_modelpack": export_moai_modelpack}[name]
    raise AttributeError(f"module 'tensorguard.moai' has no attribute '{name}'")
