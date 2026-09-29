"""
Batería de Pruebas Destructivas Asintóticas y Casos Degenerados (Regla 16 & Regla 30)
- Ataque 1: Matriz de entrada idénticamente nula (X = 0) a Stiefel
- Ataque 2: Entradas con NaNs / Infs inyectados al filtro de Fréchet Rust
- Ataque 3: Grafo inconexo extremo con V=50,000 vértices y cero aristas
"""

import os
import sys
import ctypes
import threading
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CPP_DLL_PATH = os.path.join(BASE_DIR, "polydim_cpp_v808.dll") if os.path.exists(os.path.join(BASE_DIR, "polydim_cpp_v808.dll")) else os.path.join(BASE_DIR, "polydim_cpp_v807.dll")
RUST_DLL_PATH = os.path.join(BASE_DIR, "polydim_rust_v808.dll") if os.path.exists(os.path.join(BASE_DIR, "polydim_rust_v808.dll")) else os.path.join(BASE_DIR, "polydim_rust_v807.dll")

if hasattr(os, 'add_dll_directory'):
    if os.path.exists(r"E:\winlibs_gcc14_zip\mingw64\bin"):
        os.add_dll_directory(r"E:\winlibs_gcc14_zip\mingw64\bin")
    if os.path.exists(r"E:\POLYDIM_EINSOF\src"):
        os.add_dll_directory(r"E:\POLYDIM_EINSOF\src")

cpp_lib = ctypes.CDLL(CPP_DLL_PATH)
rust_lib = ctypes.CDLL(RUST_DLL_PATH)

# Estructuras ABI
class PolydimSolverOptions(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("max_iterations", ctypes.c_uint64),
        ("gradient_tolerance", ctypes.c_double),
        ("step_tolerance", ctypes.c_double),
        ("ortho_tolerance", ctypes.c_double),
        ("learning_rate", ctypes.c_double),
        ("sampling_period", ctypes.c_uint32),
        ("num_threads", ctypes.c_uint32),
        ("retraction_type", ctypes.c_int32),
        ("shift_regularization", ctypes.c_double),
    ]

class PolydimSolverResult(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("status", ctypes.c_int32),
        ("iterations_executed", ctypes.c_uint64),
        ("final_objective", ctypes.c_double),
        ("final_grad_norm", ctypes.c_double),
        ("final_ortho_error", ctypes.c_double),
        ("total_time_ns", ctypes.c_uint64),
        ("status_message", ctypes.c_char * 256),
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
        ("pad", ctypes.c_uint8 * 102),
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
        ("pad", ctypes.c_uint8 * 79),
    ]

# Signatures
cpp_lib.polydim_stiefel_optimize.argtypes = [
    ctypes.POINTER(ctypes.c_double), ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_double), ctypes.c_size_t, ctypes.c_size_t,
    ctypes.POINTER(PolydimSolverOptions), ctypes.POINTER(PolydimSolverResult), ctypes.c_void_p
]
cpp_lib.polydim_stiefel_optimize.restype = ctypes.c_int32

rust_lib.polydim_rust_frechet_betti_filter.argtypes = [
    ctypes.POINTER(ctypes.c_double), ctypes.c_uint32, ctypes.c_uint32,
    ctypes.c_double, ctypes.c_int64, ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(PolydimFrechetBettiResult)
]
rust_lib.polydim_rust_frechet_betti_filter.restype = ctypes.c_int32

rust_lib.polydim_rust_betti_dual_guard.argtypes = [
    ctypes.POINTER(PolydimEdge), ctypes.c_uint32, ctypes.c_uint32,
    ctypes.c_int64, ctypes.POINTER(PolydimBettiResult)
]
rust_lib.polydim_rust_betti_dual_guard.restype = ctypes.c_int32

def run_adversarial_suite():
    print("=================================================================")
    print("⚔️ INICIANDO BATERÍA ADVERSARIAL Y DESTRUCTIVA (REGLA 16 & 30)")
    print("=================================================================")

    # ATAQUE 1: Matriz completamente nula (X = 0) a Stiefel
    print("\n--- [ATAQUE 1] Matriz Nula Degenerada (D=1024, K=16, X=0) ---")
    D, K = 1024, 16
    X_zero = np.zeros((D, K), dtype=np.float64)
    opts = PolydimSolverOptions(
        max_iterations=10, gradient_tolerance=1e-6, step_tolerance=1e-8,
        ortho_tolerance=1e-5, learning_rate=1e-3, sampling_period=1,
        num_threads=2, retraction_type=1, shift_regularization=1e-6
    )
    res = PolydimSolverResult()
    status = cpp_lib.polydim_stiefel_optimize(
        None, 0,
        X_zero.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        D, K, ctypes.byref(opts), ctypes.byref(res), None
    )
    print(f"Status retornado: {status} | Mensaje: {res.status_message.decode('utf-8', errors='ignore')}")
    assert not np.isnan(res.final_ortho_error), "FALLO: Error de ortogonalidad es NaN ante matriz nula"
    print("✓ Ataque 1 contenido: No hubo crash ni NaNs descontrolados.")

    # ATAQUE 2: Inyección de NaNs e Infs en Rust Fréchet
    print("\n--- [ATAQUE 2] Inyección Maliciosa de NaNs/Infs en Filtro Fréchet ---")
    candidates = np.random.randn(10, 64)
    candidates[2, 5] = np.nan
    candidates[7, 12] = np.inf
    out_consensus = np.zeros(64, dtype=np.float64)
    frechet_res = PolydimFrechetBettiResult()
    st = rust_lib.polydim_rust_frechet_betti_filter(
        candidates.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        10, 64, 1.0, 50,
        out_consensus.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        ctypes.byref(frechet_res)
    )
    print(f"Status retornado ante NaNs: {st} (Esperado MathError = 5 o InvalidArgument = 1)")
    assert st != 0, "FALLO: El filtro aceptó NaNs como válidos (debió rechazar)"
    print("✓ Ataque 2 contenido: NaNs detectados y rechazados por FFI Firewall.")

    # ATAQUE 3: Grafo Disperso sin Aristas (V = 50,000, E = 0)
    print("\n--- [ATAQUE 3] Grafo Totalmente Desconectado (V=50000, E=0) ---")
    betti_out = PolydimBettiResult()
    st = rust_lib.polydim_rust_betti_dual_guard(
        None, 0, 50000, 10, ctypes.byref(betti_out)
    )
    print(f"Status retornado: {st} (NullPointer con E=0 manejado)")
    # Con puntero válido pero 0 aristas
    dummy_edge = (PolydimEdge * 1)()
    st2 = rust_lib.polydim_rust_betti_dual_guard(
        dummy_edge, 0, 50000, 10, ctypes.byref(betti_out)
    )
    print(f"Status con dummy: {st2} | Betti-0: {betti_out.components_betti0} | Betti-1: {betti_out.cycles_betti1}")
    assert betti_out.components_betti0 == 50000, f"FALLO: Betti-0 debió ser 50000, fue {betti_out.components_betti0}"
    assert betti_out.cycles_betti1 == 0, f"FALLO: Betti-1 debió ser 0, fue {betti_out.cycles_betti1}"
    print("✓ Ataque 3 contenido: Cálculo topológico exacto ante desconexión total.")

    print("\n=================================================================")
    print("🛡️ BATERÍA ADVERSARIAL COMPLETADA — CERO CRASHES")
    print("=================================================================")

if __name__ == "__main__":
    run_adversarial_suite()
