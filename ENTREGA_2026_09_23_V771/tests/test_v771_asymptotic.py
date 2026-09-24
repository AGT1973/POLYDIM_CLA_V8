import sys
import os
import time
import ctypes
import numpy as np

# Bind to monolith
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from polydim_v771_monolito import PolydimNativeBinding, PolydimReport, PolydimTolerances

def run_tests():
    print("================================================================================")
    print("🏛️ POLYDIM V771 — ASYMPTOTIC L1 CACHE & STACK VERIFICATION SUITE")
    print("================================================================================")
    
    dll_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    binding = PolydimNativeBinding(dll_dir)
    lib = binding.lib

    report = PolydimReport()
    tols = PolydimTolerances(
        basis_ortho=1e-12, point_norm=1e-12, gram_ortho=1e-12, pivot_rel=1e-12, reject_subnormal=1
    )

    np.random.seed(42)

    # 1. Test Orthogonalize Pair (Parallel NaN Check)
    D_pair = 10_000_000
    print(f"  [TEST 1] Orthogonalize Pair (Parallel NaN Check) | D = {D_pair:,}...")
    u = np.random.randn(D_pair).astype(np.float64)
    v = np.random.randn(D_pair).astype(np.float64)
    
    t0 = time.perf_counter()
    rc = lib.polydim_orthonormalize_pair_f64(
        u.ctypes.data_as(ctypes.c_void_p),
        v.ctypes.data_as(ctypes.c_void_p),
        ctypes.c_uint64(D_pair),
        ctypes.byref(report)
    )
    t1 = time.perf_counter()
    assert rc == 0, f"Failed with rc={rc}"
    print(f"           -> PASSED in {(t1-t0)*1000:.2f} ms | Ortho Err: {report.basis_uv_err:.2e}")

    # 2. Test Tangent Projection (L1 Cache Blocking)
    # Using D=50,000, K=256 to ensure heavy cache pressure without exceeding common RAM
    D_mat = 50_000
    K_mat = 256
    print(f"  [TEST 2] Tangent Projection (L1 Blocked GEMM)    | D = {D_mat:,}, K = {K_mat}...")
    X = np.random.randn(D_mat, K_mat).astype(np.float64)
    G = np.random.randn(D_mat, K_mat).astype(np.float64)
    G_out = np.zeros_like(G)
    
    # Orthonormalize X columns to avoid manifold errors
    q, r = np.linalg.qr(X, mode='reduced')
    X = np.ascontiguousarray(q)

    t0 = time.perf_counter()
    rc = lib.polydim_project_tangent_stiefel_f64(
        X.ctypes.data_as(ctypes.c_void_p),
        G.ctypes.data_as(ctypes.c_void_p),
        G_out.ctypes.data_as(ctypes.c_void_p),
        ctypes.c_uint64(D_mat),
        ctypes.c_uint32(K_mat)
    )
    t1 = time.perf_counter()
    assert rc == 0, f"Failed with rc={rc}"
    print(f"           -> PASSED in {(t1-t0)*1000:.2f} ms | No segfaults, extreme cache load handled.")

    # 3. Test Cayley-SMW Retraction (L1 Blocked GEMM & Stack Guard)
    D_cayley = 10_000
    print(f"  [TEST 3] Cayley-SMW Retraction (L1 Blocked GEMM) | D = {D_cayley:,}, K = {K_mat}...")
    X_c = X[:D_cayley, :]
    q_c, _ = np.linalg.qr(X_c, mode='reduced')
    X_c = np.ascontiguousarray(q_c)
    G_c = G_out[:D_cayley, :]
    Y_out = np.zeros_like(X_c)
    tau = 0.01
    t0 = time.perf_counter()
    rc = lib.polydim_stiefel_cayley_smw_f64(
        X_c.ctypes.data_as(ctypes.c_void_p),
        G_c.ctypes.data_as(ctypes.c_void_p),
        Y_out.ctypes.data_as(ctypes.c_void_p),
        ctypes.c_uint64(D_cayley),
        ctypes.c_uint32(K_mat),
        ctypes.c_double(tau),
        ctypes.byref(tols),
        ctypes.byref(report)
    )
    t1 = time.perf_counter()
    assert rc == 0, f"Failed with rc={rc}"
    print(f"           -> PASSED in {(t1-t0)*1000:.2f} ms | Point Norm Err: {report.point_norm_err:.2e}")

    # 4. Critical K=512 Stack Overflow regression test
    print(f"  [TEST 4] Stack Overflow Guard in CholQR2         | D = 10,000, K = 512...")
    D_stack = 10_000
    K_stack = 512
    X_stack = np.random.randn(D_stack, K_stack).astype(np.float64)
    t0 = time.perf_counter()
    rc = lib.polydim_cholqr2_f64(
        X_stack.ctypes.data_as(ctypes.c_void_p),
        ctypes.c_uint64(D_stack),
        ctypes.c_uint32(K_stack)
    )
    t1 = time.perf_counter()
    assert rc == 0, f"Failed with rc={rc}"
    print(f"           -> PASSED in {(t1-t0)*1000:.2f} ms | No Segfault with K=512.")

    print("================================================================================")
    print("✅ V771 ASYMPTOTIC TESTS COMPLETED SUCCESSFULLY")
    print("================================================================================")

if __name__ == "__main__":
    run_tests()
