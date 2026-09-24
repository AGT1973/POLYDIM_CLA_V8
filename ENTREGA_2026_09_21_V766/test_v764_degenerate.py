import os
import sys
import traceback
import numpy as np

DIR_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(DIR_PATH)
from polydim_v764_monolito import PolydimNativeCore

cpp_dll_path = os.path.join(DIR_PATH, "build", "libpolydim.dll")
rust_dll_path = os.path.join(DIR_PATH, "build", "polydim_verify.dll")
if not os.path.exists(rust_dll_path):
    rust_dll_path = os.path.join(DIR_PATH, "rust", "target", "release", "polydim_verify.dll")

def run_tests():
    print("=== SABUESO RED TEAM: DEGENERATE INPUTS ===")
    
    # Try multiple paths for cpp_dll
    possible_paths = [
        r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_20_V764\build\libpolydim.so",
        r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_20_V764\build\polydim.dll"
    ]
    cpp_path = None
    for p in possible_paths:
        if os.path.exists(p):
            cpp_path = p
            break
            
    if cpp_path is None:
        print("CPP DLL not found!")
        return
        
    try:
        core = PolydimNativeCore(cpp_path, rust_dll_path)
    except Exception as e:
        print(f"Failed to initialize PolydimNativeCore: {e}")
        return

    D = 256
    K = 8
    
    log_content = "# Degenerate Attack Log\n\n"
    
    def log(msg):
        print(msg)
        nonlocal log_content
        log_content += msg + "\n"
        
    def check_result(test_name, y_out, status):
        if status >= 0:
            log(f"CRITICAL FAILURE in {test_name}: Expected negative error code, got {status}")
        else:
            log(f"SUCCESS in {test_name}: Kernel correctly intercepted with status {status}")
        
        if np.any(np.isnan(y_out)):
            log(f"CRITICAL FAILURE in {test_name}: Output contains NaN silently!")
    
    # 1. NaN in vectors (Rodrigues)
    log("## 1. Rodrigues Geodesic with NaN")
    y = np.zeros(D, dtype=np.float64); y[0] = np.nan
    u = np.zeros(D, dtype=np.float64); u[0] = 1.0
    v = np.zeros(D, dtype=np.float64); v[1] = 1.0
    try:
        y_out, status = core.apply_rodrigues_geodesic(y, u, v, 0.1)
        check_result("Rodrigues NaN in y", y_out, status)
    except Exception as e:
        log(f"CRASH in Rodrigues NaN in y: {e}\n{traceback.format_exc()}")
        
    # 2. +Inf in vectors (Rodrigues)
    log("## 2. Rodrigues Geodesic with +Inf")
    y = np.zeros(D, dtype=np.float64); y[0] = 1.0
    u = np.zeros(D, dtype=np.float64); u[0] = np.inf
    v = np.zeros(D, dtype=np.float64); v[1] = 1.0
    try:
        y_out, status = core.apply_rodrigues_geodesic(y, u, v, 0.1)
        check_result("Rodrigues +Inf in u", y_out, status)
    except Exception as e:
        log(f"CRASH in Rodrigues +Inf in u: {e}\n{traceback.format_exc()}")

    # 3. Completely Zero Vectors (Rodrigues)
    log("## 3. Rodrigues Geodesic with Completely Zero Vectors")
    y = np.zeros(D, dtype=np.float64)
    u = np.zeros(D, dtype=np.float64)
    v = np.zeros(D, dtype=np.float64)
    try:
        y_out, status = core.apply_rodrigues_geodesic(y, u, v, 0.1)
        check_result("Rodrigues Zero Vectors", y_out, status)
    except Exception as e:
        log(f"CRASH in Rodrigues Zero Vectors: {e}\n{traceback.format_exc()}")
        
    # 4. Singular Matrix (Stiefel Cayley-SMW)
    log("## 4. Stiefel Cayley-SMW with Singular Matrix")
    # Cond > 1e16 matrix X
    X = np.ones((D, K), dtype=np.float64)
    X += np.random.randn(D, K) * 1e-18
    G = np.random.randn(D, K).astype(np.float64)
    try:
        Y_out, status = core.apply_stiefel_retraction(X, G, 0.1)
        check_result("Stiefel Cayley-SMW Singular Matrix X", Y_out, status)
    except Exception as e:
        log(f"CRASH in Stiefel Cayley-SMW Singular Matrix X: {e}\n{traceback.format_exc()}")

    # 5. Stiefel Cayley-SMW with NaN
    log("## 5. Stiefel Cayley-SMW with NaN")
    Q, _ = np.linalg.qr(np.random.randn(D, K))
    X = np.ascontiguousarray(Q, dtype=np.float64)
    G = np.random.randn(D, K).astype(np.float64)
    G[0,0] = np.nan
    try:
        Y_out, status = core.apply_stiefel_retraction(X, G, 0.1)
        check_result("Stiefel Cayley-SMW NaN in G", Y_out, status)
    except Exception as e:
        log(f"CRASH in Stiefel Cayley-SMW NaN in G: {e}\n{traceback.format_exc()}")

    # Write log
    log_dir = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_20_V764\.agents\SOTA_HOUNDS"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "degenerate_attack_log.md")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(log_content)
        
    print(f"Log written to {log_path}")

if __name__ == '__main__':
    run_tests()
