"""
MOAI Serving Gateway (FastAPI)
"""

import fastapi
from fastapi import Request, Depends, HTTPException
from pydantic import BaseModel
import uvicorn
import base64

from ..utils.logging import get_logger
from .backend import MockBackend, MoaiBackend
from .auth import get_current_tenant
from ..moai.modelpack import ModelPack

logger = get_logger(__name__)

app = fastapi.FastAPI(title="TensorGuard MOAI Gateway", version="2.0.0")

# Global State (In-memory for demo)
backend: MoaiBackend = MockBackend()

class InferenceRequest(BaseModel):
    ciphertext_base64: str
    eval_keys_base64: str
    metadata: dict = {}

class InferenceResponse(BaseModel):
    result_ciphertext_base64: str
    compute_time_ms: float

@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    return {"status": "ok", "backend": type(backend).__name__}

@app.post("/v1/infer")
async def infer(req: InferenceRequest, tenant_id: str = Depends(get_current_tenant)):
    """
    Execute encrypted inference.
    """
    try:
        # Decode
        ct_bytes = base64.b64decode(req.ciphertext_base64)
        k_bytes = base64.b64decode(req.eval_keys_base64)
        
        # Infer
        import time
        t0 = time.time()
        res_bytes = backend.infer(ct_bytes, k_bytes)
        dt = (time.time() - t0) * 1000
        
        # Encode Response
        res_b64 = base64.b64encode(res_bytes).decode('ascii')
        
        return InferenceResponse(
            result_ciphertext_base64=res_b64,
            compute_time_ms=dt
        )
    except Exception as e:
        logger.error(f"Inference failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/admin/load_model")
async def load_model(file: bytes = fastapi.File(...), tenant_id: str = Depends(get_current_tenant)):
    """
    Admin endpoint to load a ModelPack binary.
    """
    try:
        import pickle
        pack: ModelPack = pickle.loads(file)
        backend.load_model(pack)
        return {"status": "loaded", "model_id": pack.meta.model_id}
    except Exception as e:
         raise HTTPException(status_code=400, detail=f"Invalid ModelPack: {e}")

def start_server(port=8000):
    uvicorn.run(app, host="0.0.0.0", port=port)
