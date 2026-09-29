"""
polydim_v814_monolito.py
POLYDIM V814 Master Monolith Orchestrator (Bulldog SOTA Release)
Unified Hyperdimensional Riemannian Computing Engine
"""

import os
import sys
import ctypes
import numpy as np
from typing import Tuple, Optional, List

# Locate DLLs
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(os.path.dirname(BASE_DIR), "src")

MINGW_BIN = r"E:\winlibs_gcc14_zip\mingw64\bin"
if os.path.exists(MINGW_BIN):
    try:
        os.add_dll_directory(MINGW_BIN)
    except Exception:
        pass

def _find_lib(name: str) -> str:
    paths = [
        os.path.join(BASE_DIR, name),
        os.path.join(SRC_DIR, name),
        os.path.join(r"E:\POLYDIM_EINSOF\src", name)
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"Cannot locate native library: {name}")

CPP_LIB_PATH = _find_lib("polydim_cpp_v814.dll")
RUST_LIB_PATH = _find_lib("polydim_rust_v814.dll")

cpp_lib = ctypes.CDLL(CPP_LIB_PATH)
rust_lib = ctypes.CDLL(RUST_LIB_PATH)

# =========================================================================
# 1. ABI STRUCTS
# =========================================================================
class PolydimTelemetryEvent(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("timestamp_ns", ctypes.c_uint64),
        ("event_type", ctypes.c_uint32),
        ("thread_id", ctypes.c_uint32),
        ("metrics", ctypes.c_double * 14)
    ]

class PolydimSpscRing(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("write_index", ctypes.c_uint64),
        ("pad_write", ctypes.c_uint8 * 120),
        ("read_index", ctypes.c_uint64),
        ("pad_read", ctypes.c_uint8 * 120),
        ("capacity", ctypes.c_size_t),
        ("capacity_mask", ctypes.c_size_t),
        ("ring_buffer", ctypes.c_void_p)
    ]

class PolydimEdge(ctypes.Structure):
    _fields_ = [("u", ctypes.c_uint32), ("v", ctypes.c_uint32)]

class PolydimBettiResult(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("status", ctypes.c_int32),
        ("components_betti0", ctypes.c_uint32),
        ("cycles_betti1", ctypes.c_int64),
        ("num_vertices", ctypes.c_uint32),
        ("num_edges", ctypes.c_uint32),
        ("is_critically_healthy", ctypes.c_uint8),
        ("is_optimally_healthy", ctypes.c_uint8),
        ("pad", ctypes.c_uint8 * 102)
    ]

class PolydimFrechetBettiResult(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("status", ctypes.c_int32),
        ("num_candidates", ctypes.c_uint32),
        ("dimension", ctypes.c_uint32),
        ("connected_components_betti0", ctypes.c_uint32),
        ("cycles_betti1", ctypes.c_int64),
        ("consensus_node_idx", ctypes.c_uint32),
        ("active_swarm_count", ctypes.c_uint32),
        ("rejected_outliers_count", ctypes.c_uint32),
        ("frechet_residual", ctypes.c_double),
        ("is_consensus_certified", ctypes.c_uint8),
        ("pad", ctypes.c_uint8 * 79)
    ]

# C++ bindings
cpp_lib.polydim_gram_dsyrk.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_uint32]
cpp_lib.polydim_gram_dsyrk.restype = ctypes.c_int32

cpp_lib.polydim_structured_lsm_step.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_size_t, ctypes.c_double, ctypes.c_double
]
cpp_lib.polydim_structured_lsm_step.restype = ctypes.c_int32

cpp_lib.polydim_stiefel_parallel_transport.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t,
    ctypes.c_double, ctypes.c_double
]
cpp_lib.polydim_stiefel_parallel_transport.restype = ctypes.c_int32

cpp_lib.polydim_spsc_init.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
cpp_lib.polydim_spsc_init.restype = ctypes.c_int32
cpp_lib.polydim_spsc_push.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
cpp_lib.polydim_spsc_push.restype = ctypes.c_int32
cpp_lib.polydim_spsc_drain_batch.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
cpp_lib.polydim_spsc_drain_batch.restype = ctypes.c_int32
cpp_lib.polydim_spsc_destroy.argtypes = [ctypes.c_void_p]
cpp_lib.polydim_spsc_destroy.restype = None

# Rust bindings
rust_lib.polydim_rust_betti_dual_guard.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int64, ctypes.c_void_p]
rust_lib.polydim_rust_betti_dual_guard.restype = ctypes.c_int32

rust_lib.polydim_rust_frechet_betti_filter.argtypes = [
    ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
    ctypes.c_double, ctypes.c_int64,
    ctypes.c_void_p, ctypes.c_void_p
]
rust_lib.polydim_rust_frechet_betti_filter.restype = ctypes.c_int32

rust_lib.polydim_rust_quantum_quantize_clifford_grid.argtypes = [
    ctypes.c_double, ctypes.c_uint32, ctypes.c_double, ctypes.c_uint32,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
]
rust_lib.polydim_rust_quantum_quantize_clifford_grid.restype = ctypes.c_int32


# =========================================================================
# 2. HIGH-LEVEL PYTHON CLASSES
# =========================================================================

class PolydimEngine:
    """Master Interface to Native C++ / Rust Kernels"""

    @staticmethod
    def compute_gramian(X: np.ndarray, num_threads: int = 4) -> np.ndarray:
        D, K = X.shape
        X_c = np.ascontiguousarray(X, dtype=np.float64)
        K_out = np.zeros((K, K), dtype=np.float64)
        ret = cpp_lib.polydim_gram_dsyrk(
            X_c.ctypes.data_as(ctypes.c_void_p),
            ctypes.c_size_t(D),
            ctypes.c_size_t(K),
            K_out.ctypes.data_as(ctypes.c_void_p),
            ctypes.c_uint32(num_threads)
        )
        if ret != 0:
            raise RuntimeError(f"polydim_gram_dsyrk returned error code {ret}")
        return K_out

    @staticmethod
    def parallel_transport_stiefel(Y: np.ndarray, Xi: np.ndarray, Eta: np.ndarray,
                                   alpha_metric: float = 0.5, t: float = 1.0) -> np.ndarray:
        D, K = Y.shape
        Y_c = np.ascontiguousarray(Y, dtype=np.float64)
        Xi_c = np.ascontiguousarray(Xi, dtype=np.float64)
        Eta_c = np.ascontiguousarray(Eta, dtype=np.float64)
        Delta_out = np.zeros((D, K), dtype=np.float64)

        ret = cpp_lib.polydim_stiefel_parallel_transport(
            Y_c.ctypes.data_as(ctypes.c_void_p),
            Xi_c.ctypes.data_as(ctypes.c_void_p),
            Eta_c.ctypes.data_as(ctypes.c_void_p),
            Delta_out.ctypes.data_as(ctypes.c_void_p),
            ctypes.c_size_t(D),
            ctypes.c_size_t(K),
            ctypes.c_double(alpha_metric),
            ctypes.c_double(t)
        )
        if ret != 0:
            raise RuntimeError(f"polydim_stiefel_parallel_transport returned error code {ret}")
        return Delta_out

    @staticmethod
    def verify_topology(edges: List[Tuple[int, int]], num_vertices: int, max_tau_betti1: int = 5) -> PolydimBettiResult:
        n_edges = len(edges)
        edge_array = (PolydimEdge * n_edges)(*[PolydimEdge(u, v) for u, v in edges])
        res = PolydimBettiResult()
        ret = rust_lib.polydim_rust_betti_dual_guard(
            edge_array, ctypes.c_uint32(n_edges), ctypes.c_uint32(num_vertices),
            ctypes.c_int64(max_tau_betti1), ctypes.byref(res)
        )
        if ret != 0:
            raise RuntimeError(f"polydim_rust_betti_dual_guard returned error code {ret}")
        return res

    @staticmethod
    def frechet_consensus(candidates: np.ndarray, dist_threshold: float = 0.5, max_tau_betti1: int = 10) -> Tuple[np.ndarray, PolydimFrechetBettiResult]:
        N, D = candidates.shape
        c_flat = np.ascontiguousarray(candidates, dtype=np.float64)
        out_consensus = np.zeros(D, dtype=np.float64)
        res = PolydimFrechetBettiResult()

        ret = rust_lib.polydim_rust_frechet_betti_filter(
            c_flat.ctypes.data_as(ctypes.c_void_p),
            ctypes.c_uint32(N), ctypes.c_uint32(D),
            ctypes.c_double(dist_threshold), ctypes.c_int64(max_tau_betti1),
            out_consensus.ctypes.data_as(ctypes.c_void_p),
            ctypes.byref(res)
        )
        if ret != 0:
            raise RuntimeError(f"polydim_rust_frechet_betti_filter returned error code {ret}")
        return out_consensus, res


if __name__ == "__main__":
    print("=== POLYDIM V814 MONOLITH SELF-TEST ===")
    D, K = 1024, 8
    X = np.random.randn(D, K)
    Gram = PolydimEngine.compute_gramian(X)
    print(f"Gramian computed successfully. Shape: {Gram.shape}, Trace: {np.trace(Gram):.2f}")
    
    # Topology test
    edges = [(0, 1), (1, 2), (2, 0)]
    topo = PolydimEngine.verify_topology(edges, 3)
    print(f"Topology Betti-0: {topo.components_betti0}, Betti-1: {topo.cycles_betti1}, Healthy: {topo.is_optimally_healthy}")
    print("Monolith ready for production deployment.")
