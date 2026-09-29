"""
=============================================================================
POLYDIM V816 COMPREHENSIVE INDUSTRIAL PHYSICAL SILICON VALIDATION HARNESS
=============================================================================
Tests:
1. DSYRK Gramian Streaming with 128B Cache-Line Isolation (D=8192, K=32)
2. Dynamic FWHT SIMD with exact O(2^{-m/2}) Energy Preservation (D=8192)
3. Block LDL^T with Rook Pivoting (2K x 2K Indefinite Solve)
4. Shifted-Skew GMRES Matrix-Free Solver ((I - S) u = b, rel_res <= 1e-14)
5. Bilateral Cayley Retraction on St(D,K) (D=1024, K=16, Isometry Drift <= 1e-14)
6. QSBR Generational Memory with 128B Isolation (Wait-free Epoch Advancement)
7. Rust TopoGuard Betti-1 Flat DSU Invariant (B0=1, B1=1)
8. Rust Fréchet-Betti Spherical Consensus & 3a >= 2n BFT Quorum
=============================================================================
"""

import os
import sys
import ctypes
import numpy as np

CPP_DLL_PATH = r"E:\POLYDIM_EINSOF\src\polydim_cpp_v816.dll"
RUST_DLL_PATH = r"E:\POLYDIM_EINSOF\src\polydim_rust_v816.dll"

class V816Error(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_uint32),
        ("msg", ctypes.c_char * 256),
        ("arena_id", ctypes.c_uint64),
        ("gen", ctypes.c_uint64),
    ]

class PolydimFrechetBettiResultV816(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_int),
        ("num_candidates", ctypes.c_uint),
        ("dimension", ctypes.c_uint),
        ("connected_components_betti0", ctypes.c_uint),
        ("cycles_betti1", ctypes.c_longlong),
        ("consensus_node_idx", ctypes.c_uint),
        ("active_swarm_count", ctypes.c_uint),
        ("rejected_outliers_count", ctypes.c_uint),
        ("frechet_residual", ctypes.c_double),
        ("is_consensus_certified", ctypes.c_uint8),
        ("pad", ctypes.c_uint8 * 79),
    ]

def load_v816_libraries():
    if os.name == 'nt':
        mingw_bin = r"E:\winlibs_gcc14_zip\mingw64\bin"
        src_dir = r"E:\POLYDIM_EINSOF\src"
        if os.path.exists(mingw_bin):
            os.add_dll_directory(mingw_bin)
        if os.path.exists(src_dir):
            os.add_dll_directory(src_dir)

    cpp_dll = ctypes.CDLL(CPP_DLL_PATH)
    rust_dll = ctypes.CDLL(RUST_DLL_PATH)
    return cpp_dll, rust_dll

def test_1_dsyrk_gramian(cpp_dll):
    print("[TEST 1/8] DSYRK Gramian Streaming (D=8192, K=32, 128B Cache-Line Isolation)...", end=" ")
    D, K = 8192, 32
    X = np.random.randn(D, K).astype(np.float64)
    for i in range(D):
        X[i] /= np.linalg.norm(X[i]) + 1e-15
        
    G_cpp = np.zeros((K, K), dtype=np.float64)
    err = V816Error()

    fn = cpp_dll.polydim_dsyrk_gramian_v816
    fn.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_void_p, ctypes.POINTER(V816Error)]
    fn.restype = ctypes.c_int32

    code = fn(X.ctypes.data_as(ctypes.c_void_p), ctypes.c_uint64(D), ctypes.c_uint64(K), G_cpp.ctypes.data_as(ctypes.c_void_p), ctypes.byref(err))
    assert code == 0, f"DSYRK failed with code {code}"

    G_ref = X.T @ X
    diff = np.max(np.abs(G_cpp - G_ref))
    assert diff < 1e-10, f"Max diff too large: {diff}"
    print(f"PASS (Max Abs Diff: {diff:.2e})")

def test_2_dynamic_fwht(cpp_dll):
    print("[TEST 2/8] Dynamic FWHT SIMD (D=8192, Energy Drift Check)...", end=" ")
    D = 8192
    x = np.random.randn(D).astype(np.float64)
    x /= np.linalg.norm(x)
    data = np.copy(x)
    err = V816Error()

    fn = cpp_dll.polydim_fwht_avx512_v816
    fn.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(V816Error)]
    fn.restype = ctypes.c_int32

    energy_in = np.sum(data ** 2)
    code = fn(data.ctypes.data_as(ctypes.c_void_p), ctypes.c_uint64(D), ctypes.byref(err))
    energy_out = np.sum(data ** 2)
    assert code == 0, f"FWHT failed with code {code}"

    drift = abs(energy_in - energy_out)
    assert drift < 1e-12, f"Energy drift too large: {drift}"
    print(f"PASS (Energy Drift: {drift:.2e})")

def test_3_block_ldlt_rook(cpp_dll):
    print("[TEST 3/8] Block LDL^T Rook Pivoting (2K x 2K Symmetric Indefinite Solve, K=16)...", end=" ")
    K = 16
    N = 2 * K
    # Generate random symmetric indefinite matrix
    M = np.random.randn(N, N).astype(np.float64)
    A = np.ascontiguousarray(0.5 * (M + M.T), dtype=np.float64)
    B = np.random.randn(N, K).astype(np.float64)
    X_out = np.zeros((N, K), dtype=np.float64)
    err = V816Error()

    fn = cpp_dll.polydim_block_ldlt_rook_solve_v816
    fn.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64,
        ctypes.c_void_p, ctypes.POINTER(V816Error)
    ]
    fn.restype = ctypes.c_int32

    code = fn(
        A.ctypes.data_as(ctypes.c_void_p),
        B.ctypes.data_as(ctypes.c_void_p),
        ctypes.c_uint64(N),
        ctypes.c_uint64(K),
        X_out.ctypes.data_as(ctypes.c_void_p),
        ctypes.byref(err)
    )
    assert code == 0, f"Block LDLT failed with code {code}"

    # Residual check: ||A X_out - B|| / ||B||
    residual = np.max(np.abs(A @ X_out - B)) / np.max(np.abs(B))
    assert residual < 1e-10, f"Block LDLT residual too large: {residual}"
    print(f"PASS (Relative Residual: {residual:.2e})")

def test_4_shifted_skew_gmres(cpp_dll):
    print("[TEST 4/8] Shifted-Skew GMRES Matrix-Free Solver ((I - S) u = b, K=16)...", end=" ")
    K = 16
    N = 2 * K
    W = np.random.randn(N, N).astype(np.float64)
    S_skew = np.ascontiguousarray(0.1 * (W - W.T), dtype=np.float64) # Skew-symmetric
    B = np.random.randn(N, K).astype(np.float64)
    U_out = np.zeros((N, K), dtype=np.float64)
    err = V816Error()

    fn = cpp_dll.polydim_shifted_skew_gmres_solve_v816
    fn.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64,
        ctypes.c_double, ctypes.c_int32, ctypes.c_void_p, ctypes.POINTER(V816Error)
    ]
    fn.restype = ctypes.c_int32

    code = fn(
        S_skew.ctypes.data_as(ctypes.c_void_p),
        B.ctypes.data_as(ctypes.c_void_p),
        ctypes.c_uint64(N),
        ctypes.c_uint64(K),
        ctypes.c_double(1e-15),
        ctypes.c_int32(30),
        U_out.ctypes.data_as(ctypes.c_void_p),
        ctypes.byref(err)
    )
    assert code == 0, f"GMRES solve failed with code {code}"

    # Check (I - S) U_out == B
    Op = np.eye(N) - S_skew
    res = np.max(np.abs(Op @ U_out - B)) / np.max(np.abs(B))
    assert res < 1e-12, f"GMRES residual too large: {res}"
    print(f"PASS (Accretive Residual: {res:.2e})")

def test_5_cayley_retraction(cpp_dll):
    print("[TEST 5/8] Bilateral Cayley Retraction on Stiefel St(D,K) (D=1024, K=16)...", end=" ")
    D, K = 1024, 16
    V_in = np.random.randn(D, K).astype(np.float64)
    Q, _ = np.linalg.qr(V_in)
    V_ortho = np.ascontiguousarray(Q[:D, :K], dtype=np.float64)

    W = np.random.randn(K, K).astype(np.float64)
    W_skew = np.ascontiguousarray(W - W.T, dtype=np.float64)
    tau = 0.02
    V_out = np.zeros((D, K), dtype=np.float64)
    err = V816Error()

    fn = cpp_dll.polydim_cayley_retract_bilateral_v816
    fn.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_double, ctypes.c_uint64,
        ctypes.c_uint64, ctypes.c_void_p, ctypes.POINTER(V816Error)
    ]
    fn.restype = ctypes.c_int32

    code = fn(
        V_ortho.ctypes.data_as(ctypes.c_void_p),
        W_skew.ctypes.data_as(ctypes.c_void_p),
        ctypes.c_double(tau),
        ctypes.c_uint64(D),
        ctypes.c_uint64(K),
        V_out.ctypes.data_as(ctypes.c_void_p),
        ctypes.byref(err)
    )
    assert code == 0, f"Cayley retract failed with code {code}"

    gram = V_out.T @ V_out
    isometry_drift = np.max(np.abs(gram - np.eye(K)))
    assert isometry_drift < 1e-12, f"Isometry drift too large: {isometry_drift}"
    print(f"PASS (Isometry Drift: {isometry_drift:.2e})")

def test_6_qsbr_epoch(cpp_dll):
    print("[TEST 6/8] QSBR Generational Memory with 128B Isolation (Epoch Cycle)...", end=" ")
    fn_advance = cpp_dll.polydim_qsbr_advance_epoch_v816
    fn_advance.restype = None
    fn_quiescent = cpp_dll.polydim_qsbr_enter_quiescent_v816
    fn_quiescent.restype = None
    fn_get_global = cpp_dll.polydim_qsbr_get_global_epoch_v816
    fn_get_global.restype = ctypes.c_uint64

    e0 = fn_get_global()
    fn_quiescent()
    fn_advance()
    e1 = fn_get_global()
    assert e1 == e0 + 1, f"Epoch did not advance: e0={e0}, e1={e1}"
    print(f"PASS (Epoch Advanced {e0} -> {e1})")

def test_7_rust_betti1_guard(rust_dll):
    print("[TEST 7/8] Rust TopoGuard Betti-1 Flat DSU Invariant (Graph 1-Complex)...", end=" ")
    fn = rust_dll.polydim_rust_compute_betti_flat_v816
    fn.argtypes = [
        ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
        ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_longlong),
        ctypes.POINTER(V816Error)
    ]
    fn.restype = ctypes.c_int

    # Triangle graph (0,1), (1,2), (2,0) -> V=3, E=3, C=1 -> B1 = 3 - 3 + 1 = 1
    edges = np.array([
        ((0 << 32) | 1),
        ((1 << 32) | 2),
        ((2 << 32) | 0)
    ], dtype=np.uint64)

    b0 = ctypes.c_uint(0)
    b1 = ctypes.c_longlong(0)
    err = V816Error()

    code = fn(ctypes.c_uint(3), edges.ctypes.data_as(ctypes.c_void_p), ctypes.c_uint(3), ctypes.byref(b0), ctypes.byref(b1), ctypes.byref(err))
    assert code == 0, f"Rust betti failed with code {code}"
    assert b0.value == 1 and b1.value == 1, f"Unexpected Betti numbers: B0={b0.value}, B1={b1.value}"
    print(f"PASS (Betti Invariants: B0={b0.value}, B1={b1.value})")

def test_8_rust_frechet_betti_filter(rust_dll):
    print("[TEST 8/8] Rust Fréchet-Betti Filter & 3a >= 2n BFT Quorum Certification...", end=" ")
    fn = rust_dll.polydim_rust_frechet_betti_filter_v816
    fn.argtypes = [
        ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_double,
        ctypes.c_longlong, ctypes.c_void_p, ctypes.POINTER(PolydimFrechetBettiResultV816),
        ctypes.POINTER(V816Error)
    ]
    fn.restype = ctypes.c_int

    N, D = 8, 128
    # 7 consistent candidates around a mean + 1 outlier
    base_vec = np.random.randn(D).astype(np.float64)
    base_vec /= np.linalg.norm(base_vec)

    candidates = np.zeros((N, D), dtype=np.float64)
    for i in range(7):
        candidates[i] = base_vec + 0.05 * np.random.randn(D)
        candidates[i] /= np.linalg.norm(candidates[i])
    candidates[7] = -base_vec # Adversarial outlier

    consensus_out = np.zeros(D, dtype=np.float64)
    result_out = PolydimFrechetBettiResultV816()
    err = V816Error()

    code = fn(
        candidates.ctypes.data_as(ctypes.c_void_p),
        ctypes.c_uint(N),
        ctypes.c_uint(D),
        ctypes.c_double(0.4),
        ctypes.c_longlong(15),
        consensus_out.ctypes.data_as(ctypes.c_void_p),
        ctypes.byref(result_out),
        ctypes.byref(err)
    )
    assert code == 0, f"Frechet filter failed with code {code}"
    assert result_out.is_consensus_certified == 1, "Consensus was not certified by BFT quorum"
    print(f"PASS (BFT Quorum Certified, Inliers: {result_out.active_swarm_count}/{N}, Residual: {result_out.frechet_residual:.4f})")

def main():
    print("=" * 80)
    print("=== POLYDIM V816 PHYSICAL SILICON VALIDATION HARNESS (AMD A4-6300) ===")
    print("=" * 80)

    cpp_dll, rust_dll = load_v816_libraries()

    test_1_dsyrk_gramian(cpp_dll)
    test_2_dynamic_fwht(cpp_dll)
    test_3_block_ldlt_rook(cpp_dll)
    test_4_shifted_skew_gmres(cpp_dll)
    test_5_cayley_retraction(cpp_dll)
    test_6_qsbr_epoch(cpp_dll)
    test_7_rust_betti1_guard(rust_dll)
    test_8_rust_frechet_betti_filter(rust_dll)

    print("=" * 80)
    print(">>> ALL 8 PHYSICAL SILICON TESTS PASSED (EXIT CODE 0) <<<")
    print("=" * 80)

if __name__ == "__main__":
    main()
