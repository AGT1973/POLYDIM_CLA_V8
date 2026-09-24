# ============================================================================
# POLYDIM V762 — ADVERSARIAL SILICON VALIDATION & RED TEAM TEST SUITE
# 5/5 Physical Silicon Suites | 4/4 Destructive Adversarial Attacks | D=1,000,000
# ============================================================================

import os
import gc
import sys
import time
import subprocess
import platform
import numpy as np

# Ensure Windows finds MinGW runtime DLLs
if platform.system() == "Windows" and hasattr(os, "add_dll_directory"):
    mingw_bin = r"E:\winlibs_gcc14_zip\mingw64\bin"
    if os.path.exists(mingw_bin):
        try:
            os.add_dll_directory(mingw_bin)
        except Exception:
            pass

ENTREGA_DIR = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_19_V762"
BIN_DIR = os.path.join(ENTREGA_DIR, "bin")
os.makedirs(BIN_DIR, exist_ok=True)

if platform.system() == "Windows" and hasattr(os, "add_dll_directory"):
    try:
        os.add_dll_directory(BIN_DIR)
    except Exception:
        pass

CPP_SRC = os.path.join(ENTREGA_DIR, "kernel_cpp_v762.cpp")
RUST_SRC = os.path.join(ENTREGA_DIR, "kernel_rust_v762.rs")

CPP_DLL = os.path.join(BIN_DIR, "polydim_cpp_v762.dll")
RUST_DLL = os.path.join(BIN_DIR, "polydim_rust_v762.dll")

GCC_PATH = r"E:\winlibs_gcc14_zip\mingw64\bin\g++.exe"
RUSTC_PATH = r"C:\Users\eluithi\.cargo\bin\rustc.exe"

def build_binaries():
    print("\n--- [BUILD] Compiling C++ Kernel V762 (GCC 14.2.0 -O3 -ffp-contract=off -fopenmp) ---")
    cpp_cmd = [
        GCC_PATH,
        "-O3",
        "-shared",
        "-fPIC",
        "-ffp-contract=off",
        "-fno-fast-math",
        "-fopenmp",
        "-static-libgcc",
        "-static-libstdc++",
        CPP_SRC,
        "-o",
        CPP_DLL
    ]
    res_cpp = subprocess.run(cpp_cmd, capture_output=True, text=True)
    if res_cpp.returncode != 0:
        print(f"C++ Compilation FAILED:\n{res_cpp.stderr}")
        sys.exit(1)
    print(f"-> C++ Kernel Compiled Successfully: {CPP_DLL} ({os.path.getsize(CPP_DLL)} bytes)")

    print("\n--- [BUILD] Compiling Rust Guard V762 (rustc opt-level=3 -C panic=unwind) ---")
    rust_cmd = [
        RUSTC_PATH,
        "--crate-type", "cdylib",
        "-C", "opt-level=3",
        "-C", "panic=unwind",
        RUST_SRC,
        "-o",
        RUST_DLL
    ]
    res_rust = subprocess.run(rust_cmd, capture_output=True, text=True)
    if res_rust.returncode != 0:
        print(f"Rust Compilation FAILED:\n{res_rust.stderr}")
        sys.exit(1)
    print(f"-> Rust Guard Compiled Successfully: {RUST_DLL} ({os.path.getsize(RUST_DLL)} bytes)")

def run_tests():
    # Insert delivery dir into path for import
    if ENTREGA_DIR not in sys.path:
        sys.path.insert(0, ENTREGA_DIR)

    from polydim_v762_monolito import PolydimNativeCore, PMTPSlabChannel

    core = PolydimNativeCore(CPP_DLL, RUST_DLL)
    D = 1_000_000
    print(f"\n============================================================================")
    print(f"POLYDIM V762 LIVE SILICON BENCHMARK & DESTRUCTIVE ADVERSARIAL SUITE (D={D:,})")
    print(f"============================================================================")

    # ------------------------------------------------------------------------
    # SUITE 1: Happy Path Geodesic Rotation on S^(D-1)
    # ------------------------------------------------------------------------
    print("\n[SUITE 1/5] Happy Path Rodrigues Geodesic Rotation on S^(D-1)...")
    np.random.seed(42)
    y = np.random.randn(D)
    y /= np.linalg.norm(y)

    u = np.random.randn(D)
    u /= np.linalg.norm(u)

    # Gram-Schmidt orthogonalization for v
    v = np.random.randn(D)
    v = v - np.dot(u, v) * u
    v /= np.linalg.norm(v)

    theta = 0.7853981633974483 # pi / 4

    t0 = time.perf_counter()
    y_out, status = core.apply_rodrigues_geodesic(y, u, v, theta)
    dt_ms = (time.perf_counter() - t0) * 1000.0

    rust_status, rust_drift = core.verify_rust_invariants(y_out)

    print(f"-> Status: {status}, Rust Status: {rust_status}")
    print(f"-> Latency: {dt_ms:.2f} ms, Drift on S^(D-1): {rust_drift:.4e}")
    assert status == 0, f"Rodrigues failed with status {status}"
    assert rust_status == 0, f"Rust validation failed with status {rust_status}"
    assert rust_drift < 1e-10, f"Drift exceeded tolerance: {rust_drift}"
    print("-> SUITE 1 PASS [OK]")

    # ------------------------------------------------------------------------
    # SUITE 2: PMTP Zero-Copy Shared Memory Double-Buffer Throughput
    # ------------------------------------------------------------------------
    print("\n[SUITE 2/5] PMTP Zero-Copy Shared Memory Round-Trip...")
    pmtp = PMTPSlabChannel("v762_test", D, create=True)
    t0 = time.perf_counter()
    pmtp.write_tensor(y_out, 1)
    read_view, seq = pmtp.read_tensor(0)
    dt_shm_ms = (time.perf_counter() - t0) * 1000.0

    assert seq == 1
    assert read_view is not None
    shm_drift = float(np.max(np.abs(read_view - y_out)))
    print(f"-> Latency: {dt_shm_ms:.2f} ms, Max Bit Difference: {shm_drift:.4e}")
    assert shm_drift == 0.0, "Zero-Copy memory corruption detected!"
    
    del read_view
    gc.collect()
    pmtp.close()
    print("-> SUITE 2 PASS [OK]")

    # ------------------------------------------------------------------------
    # SUITE 3: Cayley-SMW Stiefel Retraction St(D, K) for K=8
    # ------------------------------------------------------------------------
    print("\n[SUITE 3/5] Cayley-SMW Stiefel Retraction St(D, K) (K=8)...")
    K = 8
    X = np.random.randn(D, K)
    X, _ = np.linalg.qr(X) # Orthonormalize columns
    G = np.random.randn(D, K) * 0.01 # Small tangent step

    t0 = time.perf_counter()
    Y_stiefel, status_stiefel = core.apply_stiefel_retraction(X, G, 0.1)
    dt_stiefel_ms = (time.perf_counter() - t0) * 1000.0

    # Verify Stiefel orthonormality: Y^T Y = I_K
    YTY = Y_stiefel.T @ Y_stiefel
    stiefel_drift = float(np.max(np.abs(YTY - np.eye(K))))
    print(f"-> Status: {status_stiefel}, Latency: {dt_stiefel_ms:.2f} ms")
    print(f"-> Stiefel Metric Drift ||Y^T Y - I||_max: {stiefel_drift:.4e}")
    assert status_stiefel == 0, f"Stiefel retraction failed: {status_stiefel}"
    assert stiefel_drift < 1e-8, f"Stiefel orthonormality violated: {stiefel_drift}"
    print("-> SUITE 3 PASS [OK]")

    # ------------------------------------------------------------------------
    # SUITE 4: Rust Betti-1 Topological Graph Guard
    # ------------------------------------------------------------------------
    print("\n[SUITE 4/5] Rust Betti-1 Topological Graph Guard (Disjoint Set Union)...")
    N = 10
    # Fully connected clique -> Betti-0 = 1 (Connected)
    adj_connected = np.ones((N, N), dtype=np.float64)
    res_conn = core.verify_betti1(adj_connected, threshold=0.5)
    print(f"-> Connected Graph Status (Expected 0): {res_conn}")
    assert res_conn == 0, f"Connected graph failed: {res_conn}"

    # Disconnected components -> Betti-0 > 1 (Fragmented)
    adj_fragmented = np.zeros((N, N), dtype=np.float64)
    # Component A: {0, 1, 2}
    adj_fragmented[0:3, 0:3] = 1.0
    # Component B: {3, 4, 5, 6, 7, 8, 9}
    adj_fragmented[3:N, 3:N] = 1.0
    res_frag = core.verify_betti1(adj_fragmented, threshold=0.5)
    print(f"-> Fragmented Graph Status (Expected -6): {res_frag}")
    assert res_frag == -6, f"Fragmented graph detection failed: {res_frag}"
    print("-> SUITE 4 PASS [OK]")

    # ------------------------------------------------------------------------
    # SUITE 5: Degenerate Inputs & Adversarial Red Team Attacks
    # ------------------------------------------------------------------------
    print("\n[SUITE 5/5] ADVERSARIAL RED TEAM ATTACKS (4/4 Destructive Tests)...")

    # Attack 1: NaN Injection
    print("  * Attack 1: NaN Tensor Injection...")
    y_nan = y.copy()
    y_nan[100] = np.nan
    _, status_nan = core.apply_rodrigues_geodesic(y_nan, u, v, theta)
    print(f"    -> C++ Status on NaN (Expected -3): {status_nan}")
    assert status_nan == -3

    rust_nan, _ = core.verify_rust_invariants(y_nan)
    print(f"    -> Rust Status on NaN (Expected -3): {rust_nan}")
    assert rust_nan == -3

    # Attack 2: Inf Injection
    print("  * Attack 2: Infinite Tensor Injection...")
    y_inf = y.copy()
    y_inf[500] = np.inf
    _, status_inf = core.apply_rodrigues_geodesic(y_inf, u, v, theta)
    print(f"    -> C++ Status on Inf (Expected -3): {status_inf}")
    assert status_inf == -3

    # Attack 3: Zero / Degenerate Norm
    print("  * Attack 3: Zero Vector Injection...")
    y_zero = np.zeros(D, dtype=np.float64)
    rust_zero, _ = core.verify_rust_invariants(y_zero)
    print(f"    -> Rust Status on Zero (Expected -8): {rust_zero}")
    assert rust_zero == -8

    # Attack 4: Subnormal Denormal Number Attack
    print("  * Attack 4: Subnormal Float Attack...")
    y_sub = y.copy()
    y_sub[42] = 1e-315 # IEEE-754 subnormal
    rust_sub, _ = core.verify_rust_invariants(y_sub)
    print(f"    -> Rust Status on Subnormal (Expected -4): {rust_sub}")
    assert rust_sub == -4

    print("-> ALL 4 ADVERSARIAL ATTACKS SURVIVED WITH HARDENED DEFENSE [OK]")
    print("\n============================================================================")
    print("CERTIFICACION EXITOSA: 5/5 SUITES SILICIO REAL PASS (EXIT CODE 0, DRIFT CERO)")
    print("============================================================================")

if __name__ == "__main__":
    build_binaries()
    run_tests()
