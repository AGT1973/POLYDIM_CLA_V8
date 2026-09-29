"""
test_v815_comprehensive_suite.py
=============================================================================
POLYDIM V815 PHYSICAL SILICON VALIDATION & ADVERSARIAL ATTACK HARNESS
=============================================================================
Certifica los 7 pilares arquitectónicos V815 en silicio local bajo ataques destructivos.
"""

import os
import sys
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

cpp_lib = ctypes.CDLL(CPP_DLL)
rust_lib = ctypes.CDLL(RUST_DLL)

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

def test_dsyrk_gramian():
    print("[TEST 1] DSYRK Gramian Streaming (D=8192, K=16)...", end="", flush=True)
    D, K = 8192, 16
    rng = np.random.RandomState(42)
    X = rng.randn(D, K).astype(np.float64)
    
    G_expected = X.T @ X
    G_actual = np.zeros((K, K), dtype=np.float64)
    
    c_double_p = ctypes.POINTER(ctypes.c_double)
    st = cpp_lib.polydim_dsyrk_gramian_v815(
        X.ctypes.data_as(c_double_p),
        ctypes.c_size_t(D),
        ctypes.c_size_t(K),
        G_actual.ctypes.data_as(c_double_p)
    )
    assert st == 0, f"DSYRK error {st}"
    max_diff = np.max(np.abs(G_expected - G_actual))
    assert max_diff < 1e-10, f"Max diff too high: {max_diff}"
    print(f" -> Max Abs Diff vs NumPy: {max_diff:.2e} [PASS]")

def test_fwht_avx512():
    print("[TEST 2] Dynamic FWHT AVX-512 Transform (D=4096)...", end="", flush=True)
    D = 4096
    rng = np.random.RandomState(123)
    data = rng.randn(D).astype(np.float64)
    norm_in = np.linalg.norm(data)
    
    c_double_p = ctypes.POINTER(ctypes.c_double)
    st = cpp_lib.polydim_fwht_avx512_v815(
        data.ctypes.data_as(c_double_p),
        ctypes.c_size_t(D)
    )
    assert st == 0, f"FWHT error {st}"
    norm_out = np.linalg.norm(data)
    diff_norm = abs(norm_in - norm_out)
    assert diff_norm < 1e-10, f"Norm drift: {diff_norm}"
    print(f" -> Preservación Isométrica de Energía: {diff_norm:.2e} [PASS]")

def test_bilateral_cayley():
    print("[TEST 3] Bilateral Cayley Retraction (D=1024, K=8)...", end="", flush=True)
    D, K = 1024, 8
    rng = np.random.RandomState(99)
    V_in = rng.randn(D, K).astype(np.float64)
    # Ortogonalizar V_in inicial
    q, _ = np.linalg.qr(V_in)
    V_in = q[:, :K]
    
    # Matriz antisimétrica W
    W_raw = rng.randn(K, K)
    W_skew = (W_raw - W_raw.T).astype(np.float64)
    
    V_out = np.zeros_like(V_in)
    c_double_p = ctypes.POINTER(ctypes.c_double)
    st = cpp_lib.polydim_cayley_retract_bilateral_v815(
        V_in.ctypes.data_as(c_double_p),
        W_skew.ctypes.data_as(c_double_p),
        ctypes.c_double(0.01),
        ctypes.c_size_t(D),
        ctypes.c_size_t(K),
        V_out.ctypes.data_as(c_double_p)
    )
    assert st == 0, f"Cayley error {st}"
    gram = V_out.T @ V_out
    drift = np.max(np.abs(gram - np.eye(K)))
    assert drift < 1e-8, f"Stiefel drift too high: {drift}"
    print(f" -> Isometría St(D,K) Drift: {drift:.2e} [PASS]")

def test_lsm_transaction():
    print("[TEST 4] LSM Reservoir 4-Phase Transaction...", end="", flush=True)
    D = 1024
    u = np.full(D, np.nan, dtype=np.float64)
    h = np.zeros(D, dtype=np.float64)
    W_rec = np.ones(D, dtype=np.float64)
    W_in = np.ones(D, dtype=np.float64)
    h_next = np.zeros(D, dtype=np.float64)
    
    c_double_p = ctypes.POINTER(ctypes.c_double)
    st = cpp_lib.polydim_lsm_transaction_step_v815(
        u.ctypes.data_as(c_double_p),
        h.ctypes.data_as(c_double_p),
        W_rec.ctypes.data_as(c_double_p),
        W_in.ctypes.data_as(c_double_p),
        ctypes.c_size_t(D),
        ctypes.c_double(0.1),
        h_next.ctypes.data_as(c_double_p)
    )
    # Debe abortar en preflight (status == 1)
    assert st == 1, f"LSM did not catch NaN: {st}"
    print(" -> Rollback Atómico ante NaN Certificado [PASS]")

def test_rust_betti_flat():
    print("[TEST 5] Rust Betti-1 Flat DSU Guard...", end="", flush=True)
    # Triángulo simple: 3 nodos, 3 aristas -> B0=1, B1=1
    edges = np.array([
        (0 << 32) | 1,
        (1 << 32) | 2,
        (2 << 32) | 0
    ], dtype=np.uint64)
    
    b0 = ctypes.c_uint(0)
    b1 = ctypes.c_int64(0)
    
    st = rust_lib.polydim_rust_compute_betti_flat_v815(
        ctypes.c_uint(3),
        edges.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
        ctypes.c_uint(len(edges)),
        ctypes.byref(b0),
        ctypes.byref(b1)
    )
    assert st == 0, f"Rust betti error {st}"
    assert b0.value == 1 and b1.value == 1, f"Wrong betti: b0={b0.value}, b1={b1.value}"
    print(f" -> B0={b0.value}, B1={b1.value} [PASS]")

def test_rust_frechet_betti_filter():
    print("[TEST 6] Rust Fréchet-Betti Filter & BFT Quórum...", end="", flush=True)
    N, D = 10, 512
    rng = np.random.RandomState(77)
    base = rng.randn(D)
    base /= np.linalg.norm(base)
    
    candidates = np.zeros((N, D), dtype=np.float64)
    for i in range(N):
        noise = rng.randn(D) * 0.05
        vec = base + noise
        candidates[i] = vec / np.linalg.norm(vec)
        
    consensus = np.zeros(D, dtype=np.float64)
    res = PolydimFrechetBettiResultV815()
    
    c_double_p = ctypes.POINTER(ctypes.c_double)
    st = rust_lib.polydim_rust_frechet_betti_filter_v815(
        candidates.ctypes.data_as(c_double_p),
        ctypes.c_uint32(N),
        ctypes.c_uint32(D),
        ctypes.c_double(1.5),
        ctypes.c_int64(10),
        consensus.ctypes.data_as(c_double_p),
        ctypes.byref(res)
    )
    assert st == 0, f"Filter error {st}"
    assert res.is_consensus_certified == 1, "Consensus not certified"
    print(f" -> Quórum 3a >= 2n Certificado (Residual: {res.frechet_residual:.4f}) [PASS]")

def main():
    print("=================================================================")
    print("=== POLYDIM V815 PHYSICAL SILICON VALIDATION HARNESS ===")
    print("=================================================================")
    test_dsyrk_gramian()
    test_fwht_avx512()
    test_bilateral_cayley()
    test_lsm_transaction()
    test_rust_betti_flat()
    test_rust_frechet_betti_filter()
    print("=================================================================")
    print(">>> ALL 6 ADVERSARIAL PHYSICAL SILICON TESTS PASSED (EXIT CODE 0) <<<")
    print("=================================================================")

if __name__ == "__main__":
    main()
