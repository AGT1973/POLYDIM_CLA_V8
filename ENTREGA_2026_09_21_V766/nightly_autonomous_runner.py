import ctypes
import numpy as np
import time
import os
import sys
import multiprocessing

if sys.platform == 'win32':
    os.add_dll_directory(r'E:\winlibs_gcc14_zip\mingw64\bin')

# Fuzzing limits
K_DIM = 16

def run_nightly_attack(worker_id):
    dll_path = os.path.abspath("build/libpolydim.so")
    if not os.path.exists(dll_path):
        dll_path = os.path.abspath("build/libpolydim.dll")
        
    lib = ctypes.CDLL(dll_path)
    
    lib.polydim_stiefel_cayley_smw_f64.argtypes = [
        ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
        ctypes.c_uint64, ctypes.c_uint32, ctypes.c_double, ctypes.c_void_p, ctypes.c_void_p
    ]
    lib.polydim_stiefel_cayley_smw_f64.restype = ctypes.c_int32

    os.makedirs("REPORTES_NOCTURNOS", exist_ok=True)
    log_file = f"REPORTES_NOCTURNOS/nightly_log_worker_{worker_id}.md"
    
    with open(log_file, "w") as f:
        f.write(f"# WORKER {worker_id} - NIGHT MODE FUZZER START\n")

    iteration = 0
    # Arrays for small tests to go extremely fast (Millions of iterations)
    D_FAST = 512
    X = np.empty((D_FAST, K_DIM), dtype=np.float64)
    G = np.empty((D_FAST, K_DIM), dtype=np.float64)
    Y = np.empty((D_FAST, K_DIM), dtype=np.float64)
    
    X_ptr = X.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    G_ptr = G.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    Y_ptr = Y.ctypes.data_as(ctypes.POINTER(ctypes.c_double))

    while True:
        try:
            # 1. Randomization / Mutation
            rand_val = np.random.rand()
            if rand_val < 0.1:
                # NaN Injection
                X.fill(np.nan)
                G.fill(np.random.randn())
            elif rand_val < 0.2:
                # Inf Injection
                X.fill(np.random.randn())
                G.fill(np.inf)
            elif rand_val < 0.3:
                # Subnormal Flood
                X.fill(1e-310)
                G.fill(1e-315)
            elif rand_val < 0.4:
                # Exact Zero / Perfect Singularity
                X.fill(0.0)
                G.fill(0.0)
            elif rand_val < 0.5:
                # Collinearity
                G[:] = np.random.randn(D_FAST, K_DIM)
                G[:, 0] = G[:, 1]
                G[:, 2] = G[:, 1] * 1e-16
            else:
                # Normal chaotic inputs
                X[:] = np.random.randn(D_FAST, K_DIM)
                G[:] = np.random.randn(D_FAST, K_DIM)
                
            status = lib.polydim_stiefel_cayley_smw_f64(X_ptr, G_ptr, Y_ptr, D_FAST, K_DIM, 0.1, None, None)
            
            # Check for silent failures (NaNs passed silently)
            if status == 0:
                if np.isnan(Y).any() or np.isinf(Y).any():
                    with open(log_file, "a") as f:
                        f.write(f"CATASTROPHIC SILENT FAILURE at Iter {iteration}: Status 0 but Output contains NaN/Inf! Type: {rand_val}\n")
                        
            if iteration % 1000000 == 0:
                with open(log_file, "a") as f:
                    f.write(f"Iter {iteration}: 1 Million passed. Latest status: {status}\n")
                
        except Exception as e:
            with open(log_file, "a") as f:
                f.write(f"SEGFAULT OR CRASH at Iter {iteration}: {str(e)}\n")
            
        iteration += 1

if __name__ == "__main__":
    print("Spawning 10 Brutal Fuzzer Workers for Asymptotic Destruction...")
    workers = []
    for i in range(10):
        p = multiprocessing.Process(target=run_nightly_attack, args=(i,))
        p.start()
        workers.append(p)
        
    for p in workers:
        p.join()
