import os
import sys

if sys.platform == "win32" and os.path.exists(r"E:\winlibs_gcc14_zip\mingw64\bin"):
    os.add_dll_directory(r"E:\winlibs_gcc14_zip\mingw64\bin")

import ctypes
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class GraphCudaResult(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_int32),
        ("num_vertices", ctypes.c_uint32),
        ("num_edges", ctypes.c_uint32),
        ("num_components", ctypes.c_uint32),
        ("giant_component_size", ctypes.c_uint32),
        ("execution_time_ns", ctypes.c_int64),
        ("backend_used", ctypes.c_uint8),
        ("pad", ctypes.c_uint8 * 23),
    ]

class GraphEdge(ctypes.Structure):
    _fields_ = [
        ("u", ctypes.c_uint32),
        ("v", ctypes.c_uint32)
    ]

class HardwareProbe:
    """
    HardwareProbe conforming to Rule 27 (Hardware Agnosticism & Silicon Contract).
    Inspects available compute fabrics without rigid assumptions.
    """
    @staticmethod
    def probe():
        info = {
            "optimal_device": get_optimal_device(),
            "cpu_cores": os.cpu_count() or 1,
            "has_cuda_lib": False,
            "has_graph_cuda_dll": False,
            "graph_cuda_path": os.path.join(BASE_DIR, "graph_cuda.dll")
        }
        if os.path.exists(info["graph_cuda_path"]):
            info["has_graph_cuda_dll"] = True
        return info

def get_optimal_device() -> str:
    """
    Query hardware dynamically to return the optimal device for execution.
    Gracefully falls back to CPU (OpenMP).
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
        device = xm.xla_device()
        if device.type == 'xla':
            return "tpu"
    except Exception:
        pass
        
    # 2. Check for CUDA / HIP
    try:
        import torch
        if hasattr(torch.version, 'hip') and torch.version.hip is not None and torch.cuda.is_available():
            return "hip"
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch, 'xpu') and torch.xpu.is_available():
            return "hip"
    except Exception:
        pass

    # 3. Fallback to OpenMP CPU
    return "cpu"

def dispatch_graph_cc(edges_np: np.ndarray, num_vertices: int):
    """
    Dispatches connected components via graph_cuda.dll (Afforest / GConn).
    Returns (components_array, result_dict).
    """
    dll_path = os.path.join(BASE_DIR, "graph_cuda.dll")
    if not os.path.exists(dll_path):
        raise FileNotFoundError(f"graph_cuda.dll not found at {dll_path}")

    cuda_lib = ctypes.CDLL(dll_path)
    cuda_lib.graph_cuda_afforest_cc.argtypes = [
        ctypes.POINTER(GraphEdge),
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(GraphCudaResult),
        ctypes.c_void_p
    ]
    cuda_lib.graph_cuda_afforest_cc.restype = ctypes.c_int32

    num_edges = edges_np.shape[0]
    out_components = np.empty(num_vertices, dtype=np.uint32)
    res = GraphCudaResult()

    st = cuda_lib.graph_cuda_afforest_cc(
        edges_np.ctypes.data_as(ctypes.POINTER(GraphEdge)),
        ctypes.c_uint32(num_edges),
        ctypes.c_uint32(num_vertices),
        out_components.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
        ctypes.byref(res),
        None
    )
    if st != 0:
        raise RuntimeError(f"graph_cuda_afforest_cc failed with code {st}")

    return out_components, {
        "num_vertices": res.num_vertices,
        "num_edges": res.num_edges,
        "num_components": res.num_components,
        "giant_component_size": res.giant_component_size,
        "execution_time_ms": res.execution_time_ns / 1e6,
        "backend": "CUDA_GPU" if res.backend_used == 1 else "CPU_OPENMP"
    }
