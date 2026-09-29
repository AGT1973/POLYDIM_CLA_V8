"""
POLYDIM NIGHTLY ACTIVE SILICON RUNNER & SOTA HOUND ENGINE
=========================================================
Continuous autonomous execution daemon for nocturnal validation (Rule 4, Rule 26).
Executes physical silicon tests on local C++ / Rust DLLs, monitors condition bounds,
and persists logs to disk.
"""

import os
import sys
import time
import ctypes
import numpy as np
import csv
from datetime import datetime

CPP_DLL_PATH = r"E:\POLYDIM_EINSOF\src\polydim_cpp_v815.dll"
RUST_DLL_PATH = r"E:\POLYDIM_EINSOF\src\polydim_rust_v815.dll"
LOG_CSV_PATH = r"E:\POLYDIM_EINSOF\nocturno_silicon_active_log.csv"
SWARM_LOG_PATH = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_28_V815\auditoria_externa\NIGHT_AUTONOMOUS_SWARM_LOG.md"

class PolydimFrechetBettiResultV815(ctypes.Structure):
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

def load_dlls():
    cpp_dll = None
    rust_dll = None
    
    if os.name == 'nt':
        mingw_bin = r"E:\winlibs_gcc14_zip\mingw64\bin"
        src_dir = r"E:\POLYDIM_EINSOF\src"
        if os.path.exists(mingw_bin):
            try:
                os.add_dll_directory(mingw_bin)
            except Exception:
                pass
        if os.path.exists(src_dir):
            try:
                os.add_dll_directory(src_dir)
            except Exception:
                pass
                
    if os.path.exists(CPP_DLL_PATH):
        try:
            cpp_dll = ctypes.CDLL(CPP_DLL_PATH)
        except Exception as e:
            print(f"[WARN] Failed to load C++ DLL: {e}")
            
    if os.path.exists(RUST_DLL_PATH):
        try:
            rust_dll = ctypes.CDLL(RUST_DLL_PATH)
        except Exception as e:
            print(f"[WARN] Failed to load Rust DLL: {e}")
            
    return cpp_dll, rust_dll

def init_csv():
    if not os.path.exists(LOG_CSV_PATH):
        with open(LOG_CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "iteration", "test_name", "dimension_D", "rank_K", "metric_drift", "condition_bound", "exit_code", "status"])

def log_test_result(iteration, test_name, d, k, drift, cond, exit_code, status):
    timestamp = datetime.now().isoformat()
    with open(LOG_CSV_PATH, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, iteration, test_name, d, k, f"{drift:.6e}", f"{cond:.4e}", exit_code, status])
    print(f"[{timestamp}] [Iter {iteration}] {test_name} (D={d}, K={k}) -> Drift: {drift:.3e}, Status: {status}")

def run_dsyrk_test(cpp_dll, iteration, D=8192, K=16):
    try:
        X = np.random.randn(D, K).astype(np.float64) # D x K layout
        for i in range(D):
            X[i] /= np.linalg.norm(X[i]) + 1e-15
        
        G_cpp = np.zeros((K, K), dtype=np.float64)
        
        if cpp_dll and hasattr(cpp_dll, 'polydim_dsyrk_gramian_v815'):
            fn = cpp_dll.polydim_dsyrk_gramian_v815
            fn.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint64,
                ctypes.c_uint64,
                ctypes.c_void_p
            ]
            fn.restype = ctypes.c_int32
            
            code = fn(
                X.ctypes.data_as(ctypes.c_void_p),
                ctypes.c_uint64(D),
                ctypes.c_uint64(K),
                G_cpp.ctypes.data_as(ctypes.c_void_p)
            )
            G_ref = X.T @ X
            diff = np.max(np.abs(G_cpp - G_ref))
            status = "PASS" if (diff < 1e-9 and code == 0) else "FAIL"
            log_test_result(iteration, "DSYRK_GRAMIAN", D, K, diff, 1.0, code, status)
        else:
            log_test_result(iteration, "DSYRK_GRAMIAN", D, K, 0.0, 1.0, 0, "DLL_FUNC_NOT_FOUND")
    except Exception as e:
        log_test_result(iteration, "DSYRK_GRAMIAN", D, K, 999.0, 999.0, 1, f"ERROR: {str(e)[:40]}")

def run_fwht_test(cpp_dll, iteration, D=4096):
    try:
        x = np.random.randn(D).astype(np.float64)
        x_norm = x / (np.linalg.norm(x) + 1e-15)
        data = np.copy(x_norm)
        
        if cpp_dll and hasattr(cpp_dll, 'polydim_fwht_avx512_v815'):
            fn = cpp_dll.polydim_fwht_avx512_v815
            fn.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
            fn.restype = ctypes.c_int32
            
            energy_in = np.sum(data ** 2)
            code = fn(data.ctypes.data_as(ctypes.c_void_p), ctypes.c_uint64(D))
            energy_out = np.sum(data ** 2)
            drift = abs(energy_in - energy_out)
            status = "PASS" if (drift < 1e-12 and code == 0) else "FAIL"
            log_test_result(iteration, "DYNAMIC_FWHT", D, 1, drift, 1.0, code, status)
        else:
            log_test_result(iteration, "DYNAMIC_FWHT", D, 1, 0.0, 1.0, 0, "DLL_FUNC_NOT_FOUND")
    except Exception as e:
        log_test_result(iteration, "DYNAMIC_FWHT", D, 1, 999.0, 999.0, 1, f"ERROR: {str(e)[:40]}")

def run_cayley_retraction_test(cpp_dll, iteration, D=1024, K=8):
    try:
        V_in = np.random.randn(D, K).astype(np.float64)
        Q, _ = np.linalg.qr(V_in)
        V_ortho = np.ascontiguousarray(Q[:D, :K], dtype=np.float64)
        
        W = np.random.randn(K, K).astype(np.float64)
        W_skew = np.ascontiguousarray(W - W.T, dtype=np.float64) # Skew-symmetric
        tau = 0.01
        
        V_out = np.zeros((D, K), dtype=np.float64)
        
        if cpp_dll and hasattr(cpp_dll, 'polydim_cayley_retract_bilateral_v815'):
            fn = cpp_dll.polydim_cayley_retract_bilateral_v815
            fn.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_double,
                ctypes.c_uint64,
                ctypes.c_uint64,
                ctypes.c_void_p
            ]
            fn.restype = ctypes.c_int32
            
            code = fn(
                V_ortho.ctypes.data_as(ctypes.c_void_p),
                W_skew.ctypes.data_as(ctypes.c_void_p),
                ctypes.c_double(tau),
                ctypes.c_uint64(D),
                ctypes.c_uint64(K),
                V_out.ctypes.data_as(ctypes.c_void_p)
            )
            
            gram = V_out.T @ V_out
            ortho_err = np.max(np.abs(gram - np.eye(K)))
            cond_num = np.linalg.cond(np.eye(K) - (tau * 0.25) * W_skew)
            status = "PASS" if (ortho_err < 1e-12 and code == 0) else "FAIL"
            log_test_result(iteration, "CAYLEY_BILATERAL", D, K, ortho_err, cond_num, code, status)
        else:
            log_test_result(iteration, "CAYLEY_BILATERAL", D, K, 0.0, 1.0, 0, "DLL_FUNC_NOT_FOUND")
    except Exception as e:
        log_test_result(iteration, "CAYLEY_BILATERAL", D, K, 999.0, 999.0, 1, f"ERROR: {str(e)[:40]}")

def run_rust_topo_guard_test(rust_dll, iteration):
    try:
        if rust_dll and hasattr(rust_dll, 'polydim_rust_compute_betti_flat_v815'):
            fn = rust_dll.polydim_rust_compute_betti_flat_v815
            fn.argtypes = [
                ctypes.c_uint,
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.POINTER(ctypes.c_uint),
                ctypes.POINTER(ctypes.c_longlong)
            ]
            fn.restype = ctypes.c_int
            
            # Pack triangle edges (0,1), (1,2), (2,0) -> B0=1, B1=1
            edges = np.array([
                ((0 << 32) | 1),
                ((1 << 32) | 2),
                ((2 << 32) | 0)
            ], dtype=np.uint64)
            
            b0 = ctypes.c_uint(0)
            b1 = ctypes.c_longlong(0)
            
            code = fn(
                ctypes.c_uint(3),
                edges.ctypes.data_as(ctypes.c_void_p),
                ctypes.c_uint(3),
                ctypes.byref(b0),
                ctypes.byref(b1)
            )
            
            status = "PASS" if (b0.value == 1 and b1.value == 1 and code == 0) else "FAIL"
            log_test_result(iteration, "RUST_BETTI_FLAT_DSU", 3, 1, 0.0, 1.0, code, f"B0={b0.value},B1={b1.value}_{status}")
        else:
            log_test_result(iteration, "RUST_BETTI_FLAT_DSU", 3, 1, 0.0, 1.0, 0, "RUST_DLL_NOT_FOUND")
    except Exception as e:
        log_test_result(iteration, "RUST_BETTI_FLAT_DSU", 3, 1, 999.0, 999.0, 1, f"ERROR: {str(e)[:40]}")

def update_swarm_markdown(iteration):
    with open(SWARM_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(f"\n### ⏱️ Swarm Heartbeat — Iteration {iteration} [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n")
        f.write(f"- **Physical Silicon Runner:** Active and executing tests.\n")
        f.write(f"- **Latest Metrics:** Appended to [`nocturno_silicon_active_log.csv`](file:///E:/POLYDIM_EINSOF/nocturno_silicon_active_log.csv).\n")
        f.write(f"- **Exit Code:** 0 (Continuous)\n")

def main():
    print("==================================================================")
    print("=== POLYDIM NOCTURNAL AUTONOMOUS SILICON DAEMON STARTED ===")
    print("==================================================================")
    init_csv()
    cpp_dll, rust_dll = load_dlls()
    
    iteration = 0
    dimensions = [2048, 4096, 8192]
    ranks = [8, 16, 32]
    
    while True:
        iteration += 1
        d = dimensions[iteration % len(dimensions)]
        k = ranks[iteration % len(ranks)]
        
        print(f"\n--- Starting Autonomous Test Cycle #{iteration} (D={d}, K={k}) ---")
        run_dsyrk_test(cpp_dll, iteration, D=d, K=k)
        run_fwht_test(cpp_dll, iteration, D=d)
        run_cayley_retraction_test(cpp_dll, iteration, D=1024, K=k)
        run_rust_topo_guard_test(rust_dll, iteration)
        
        if iteration % 10 == 0:
            update_swarm_markdown(iteration)
            
        print(f"Cycle #{iteration} complete. Sleeping 45 seconds before next adversarial round...")
        time.sleep(45)

if __name__ == "__main__":
    main()
