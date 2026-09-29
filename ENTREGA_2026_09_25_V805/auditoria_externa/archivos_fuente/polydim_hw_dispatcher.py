import os
import sys

def get_optimal_device() -> str:
    """
    Query hardware dynamically to return the optimal device for execution.
    Avoids hardcoding 'cuda' and gracefully falls back to CPU (OpenMP).
    Supports TPU (Pallas via jax/torch_xla), CUDA, and ROCm/HIP.
    """
    # 1. Check for TPU (via jax)
    try:
        import jax
        if any(d.platform == 'tpu' for d in jax.local_devices()):
            return "tpu"
    except Exception:
        pass

    # 1b. Check for TPU (via torch_xla)
    try:
        import torch_xla.core.xla_model as xm
        # If xm.xla_device() succeeds and it's a TPU
        device = xm.xla_device()
        if device.type == 'xla':
            return "tpu"
    except Exception:
        pass
        
    # 2. Check for CUDA / HIP
    try:
        import torch
        # ROCm/HIP is often exposed via torch.cuda but with torch.version.hip
        if hasattr(torch.version, 'hip') and torch.version.hip is not None and torch.cuda.is_available():
            return "hip"
            
        if torch.cuda.is_available():
            return "cuda"
            
        if hasattr(torch, 'xpu') and torch.xpu.is_available():
            return "hip" # Mapping XPU/HIP based on prompt instructions
    except Exception:
        pass

    # 3. Fallback to OpenMP CPU
    return "cpu"
