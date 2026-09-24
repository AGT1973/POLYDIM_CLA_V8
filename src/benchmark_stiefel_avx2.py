# ============================================================================
# POLYDIM V800 — BENCHMARK STIEFEL CAYLEY-SMW AVX2/AVX-512 ON PHYSICAL SILICON
# Matrix-Free Tall-Skinny DGEMM with L2 Cache Tiling
# ============================================================================

import os
import sys
import time
import ctypes
import numpy as np

if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(r"E:\winlibs_gcc14_zip\mingw64\bin")

# Load the compiled DLL
dll_path = r"E:\POLYDIM_EINSOF\lib\stiefel_cayley_smw_avx2.dll"
if not os.path.exists(dll_path):
    print(f"ERROR: DLL not found at {dll_path}")
    sys.exit(1)

stiefel_lib = ctypes.CDLL(dll_path)

# Signature:
# int32_t polydim_stiefel_cayley_smw_avx512_f64(
#     const double* X, const double* G, double* Y_out, uint64_t D, uint32_t K, double tau
# )
stiefel_func = stiefel_lib.polydim_stiefel_cayley_smw_avx512_f64
stiefel_func.argtypes = [
    ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(ctypes.c_double),
    ctypes.c_uint64,
    ctypes.c_uint32,
    ctypes.c_double
]
stiefel_func.restype = ctypes.c_int32

def test_stiefel_benchmark(D, K, tau=0.1):
    print(f"\n[BENCHMARK] Stiefel Cayley-SMW: D = {D:,}, K = {K}, tau = {tau}", flush=True)
    
    # Generate orthonormal X (D x K) using QR
    print("  -> Generating orthonormal base X (D x K)...", flush=True)
    np.random.seed(42)
    raw_X = np.random.randn(min(D, 2000), K).astype(np.float64)
    Q, _ = np.linalg.qr(raw_X)
    
    # Tile Q to D x K and normalize columns
    repeats = (D + Q.shape[0] - 1) // Q.shape[0]
    X_full = np.tile(Q, (repeats, 1))[:D, :].copy()
    for col in range(K):
        X_full[:, col] /= np.linalg.norm(X_full[:, col])
    
    # Generate tangent gradient G = H - X (X^T H + H^T X)/2
    H = np.random.randn(D, K).astype(np.float64) * 0.01
    XT_H = np.dot(X_full.T, H)
    sym_XTH = 0.5 * (XT_H + XT_H.T)
    G_full = H - np.dot(X_full, sym_XTH)
    
    # Allocate output Y
    Y_out = np.zeros((D, K), dtype=np.float64)
    
    # Get pointers
    X_ptr = X_full.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    G_ptr = G_full.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    Y_ptr = Y_out.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    
    # Warmup
    stiefel_func(X_ptr, G_ptr, Y_ptr, D, K, tau)
    
    # Timed run
    t0 = time.perf_counter()
    status = stiefel_func(X_ptr, G_ptr, Y_ptr, D, K, tau)
    t1 = time.perf_counter()
    
    elapsed_ms = (t1 - t0) * 1000.0
    
    if status != 0:
        print(f"  [FAIL] Status code: {status}", flush=True)
        return False, elapsed_ms, 0.0
    
    # Check orthogonality error: ||Y^T Y - I_K||_F
    print("  -> Verifying Stiefel Isometry Invariant ||Y^T Y - I_K||_F...", flush=True)
    YT_Y = np.dot(Y_out.T, Y_out)
    I_K = np.eye(K, dtype=np.float64)
    ortho_drift = np.linalg.norm(YT_Y - I_K, ord='fro')
    
    print(f"  -> Execution Time: {elapsed_ms:.2f} ms ({elapsed_ms/1000.0:.3f} s)", flush=True)
    print(f"  -> Orthogonality Drift: {ortho_drift:.4e}", flush=True)
    
    is_valid = (ortho_drift < 1e-11)
    status_str = "PASS" if is_valid else "FAIL"
    print(f"  -> Result: [{status_str}]", flush=True)
    return is_valid, elapsed_ms, ortho_drift

if __name__ == "__main__":
    print("=" * 70, flush=True)
    print("POLYDIM V800 — PHYSICAL SILICON BENCHMARK (AVX2/AVX-512 L2-TILED)", flush=True)
    print("=" * 70, flush=True)
    
    results = []
    configs = [
        (100_000, 8),
        (1_000_000, 8),
        (1_000_000, 32),
        (1_000_000, 64)
    ]
    
    for D, K in configs:
        ok, ms, drift = test_stiefel_benchmark(D, K)
        results.append((D, K, ms, drift, ok))
        
    print("\n" + "=" * 70, flush=True)
    print("RESUMEN ASINTÓTICO DE ESCALABILIDAD STIEFEL CAYLEY-SMW (V800)", flush=True)
    print("=" * 70, flush=True)
    print(f"{'D':>12} | {'K':>5} | {'Tiempo (ms)':>12} | {'Tiempo (s)':>10} | {'Deriva ||Y^TY-I||':>18} | {'Status':>6}", flush=True)
    print("-" * 75, flush=True)
    for D, K, ms, drift, ok in results:
        status_txt = "PASS" if ok else "FAIL"
        print(f"{D:>12,d} | {K:>5d} | {ms:>12.2f} | {ms/1000.0:>10.3f} | {drift:>18.4e} | {status_txt:>6}", flush=True)
    print("=" * 70, flush=True)
