"""
polydim_v815_monolito.py
=============================================================================
ORQUESTADOR MONOLÍTICO POLYDIM V815 (SOTA MASTER RELEASE)
=============================================================================
Pipeline Unificado de Computación Hiperdimensional en S^(D-1)
- Memoria Compartida Nativa PMTP (Zero-Copy SPSC Ring & Slabs)
- Retracción Bilátera Cayley-SMW en Variedades de Stiefel St(D, K)
- Guardián Topológico Rust Flat DSU Betti-1 y Filtro Fréchet-BFT
"""

import os
import sys
import mmap
import time
import ctypes
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CPP_DLL = os.path.join(BASE_DIR, "polydim_cpp_v815.dll")
RUST_DLL = os.path.join(BASE_DIR, "polydim_rust_v815.dll")

if hasattr(os, 'add_dll_directory'):
    if os.path.exists(r"E:\winlibs_gcc14_zip\mingw64\bin"):
        os.add_dll_directory(r"E:\winlibs_gcc14_zip\mingw64\bin")
    if os.path.exists(BASE_DIR):
        os.add_dll_directory(BASE_DIR)

class PolydimFrechetBettiResultV815(ctypes.Structure):
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
        ("pad", ctypes.c_uint8 * 79),
    ]

class PolydimOrchestratorV815:
    def __init__(self, dimension=8192, k_rank=16):
        self.dimension = dimension
        self.k_rank = k_rank
        self.cpp_lib = ctypes.CDLL(CPP_DLL)
        self.rust_lib = ctypes.CDLL(RUST_DLL)
        self._setup_ffi_signatures()

    def _setup_ffi_signatures(self):
        c_double_p = ctypes.POINTER(ctypes.c_double)
        
        # C++ DSYRK
        self.cpp_lib.polydim_dsyrk_gramian_v815.argtypes = [
            c_double_p, ctypes.c_size_t, ctypes.c_size_t, c_double_p
        ]
        self.cpp_lib.polydim_dsyrk_gramian_v815.restype = ctypes.c_int32

        # C++ FWHT
        self.cpp_lib.polydim_fwht_avx512_v815.argtypes = [c_double_p, ctypes.c_size_t]
        self.cpp_lib.polydim_fwht_avx512_v815.restype = ctypes.c_int32

        # C++ Bilateral Cayley Retraction
        self.cpp_lib.polydim_cayley_retract_bilateral_v815.argtypes = [
            c_double_p, c_double_p, ctypes.c_double, ctypes.c_size_t, ctypes.c_size_t, c_double_p
        ]
        self.cpp_lib.polydim_cayley_retract_bilateral_v815.restype = ctypes.c_int32

        # C++ LSM Transaction
        self.cpp_lib.polydim_lsm_transaction_step_v815.argtypes = [
            c_double_p, c_double_p, c_double_p, c_double_p, ctypes.c_size_t, ctypes.c_double, c_double_p
        ]
        self.cpp_lib.polydim_lsm_transaction_step_v815.restype = ctypes.c_int32

        # Rust Fréchet-Betti Filter
        self.rust_lib.polydim_rust_frechet_betti_filter_v815.argtypes = [
            c_double_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_double,
            ctypes.c_int64, c_double_p, ctypes.POINTER(PolydimFrechetBettiResultV815)
        ]
        self.rust_lib.polydim_rust_frechet_betti_filter_v815.restype = ctypes.c_int32

    def compute_gramian(self, X):
        D, K = X.shape
        G = np.zeros((K, K), dtype=np.float64)
        c_double_p = ctypes.POINTER(ctypes.c_double)
        st = self.cpp_lib.polydim_dsyrk_gramian_v815(
            X.ctypes.data_as(c_double_p),
            ctypes.c_size_t(D),
            ctypes.c_size_t(K),
            G.ctypes.data_as(c_double_p)
        )
        if st != 0:
            raise RuntimeError(f"Error en DSYRK Gramian: {st}")
        return G

    def compute_fwht(self, data):
        D = len(data)
        out = data.copy().astype(np.float64)
        c_double_p = ctypes.POINTER(ctypes.c_double)
        st = self.cpp_lib.polydim_fwht_avx512_v815(
            out.ctypes.data_as(c_double_p),
            ctypes.c_size_t(D)
        )
        if st != 0:
            raise RuntimeError(f"Error en FWHT: {st}")
        return out

    def retract_bilateral(self, V_in, W_skew, tau):
        D, K = V_in.shape
        V_out = np.zeros_like(V_in, dtype=np.float64)
        c_double_p = ctypes.POINTER(ctypes.c_double)
        st = self.cpp_lib.polydim_cayley_retract_bilateral_v815(
            V_in.ctypes.data_as(c_double_p),
            W_skew.ctypes.data_as(c_double_p),
            ctypes.c_double(tau),
            ctypes.c_size_t(D),
            ctypes.c_size_t(K),
            V_out.ctypes.data_as(c_double_p)
        )
        if st != 0:
            raise RuntimeError(f"Error en Cayley Retraction Bilátera: {st}")
        return V_out

    def filter_frechet_betti(self, candidates, radius=1.5, max_iter=10):
        N, D = candidates.shape
        consensus = np.zeros(D, dtype=np.float64)
        res = PolydimFrechetBettiResultV815()
        c_double_p = ctypes.POINTER(ctypes.c_double)
        st = self.rust_lib.polydim_rust_frechet_betti_filter_v815(
            candidates.ctypes.data_as(c_double_p),
            ctypes.c_uint32(N),
            ctypes.c_uint32(D),
            ctypes.c_double(radius),
            ctypes.c_int64(max_iter),
            consensus.ctypes.data_as(c_double_p),
            ctypes.byref(res)
        )
        if st != 0:
            raise RuntimeError(f"Error en Fréchet-Betti Filter: {st}")
        return consensus, res

if __name__ == "__main__":
    orch = PolydimOrchestratorV815(dimension=8192, k_rank=16)
    print("✓ PolydimOrchestratorV815 instanciado con éxito.")
