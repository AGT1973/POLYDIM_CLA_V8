# ============================================================================
# POLYDIM V765 — AUTONOMOUS INFINITE RED TEAM HARDENING & STRESS ENGINE
# Runs continuously without limits: Fuzzing Stiefel, Rodrigues, CholQR2 & PMTP Ring
# Operating strictly in Vector Space (Shared Memory) per Rule 28 & Rule 29
# ============================================================================

import ctypes
import numpy as np
import time
import os
import sys
import multiprocessing

if sys.platform == 'win32':
    os.add_dll_directory(r'E:\winlibs_gcc14_zip\mingw64\bin')

DIR_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(DIR_PATH)
from polydim_v764_monolito import PMTPSlabChannel

DLL_PATH = os.path.join(DIR_PATH, "build", "libpolydim.dll")

def fuzzer_stiefel_worker(worker_id):
    lib = ctypes.CDLL(DLL_PATH)
    lib.polydim_stiefel_cayley_smw_f64.argtypes = [
        ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
        ctypes.c_uint64, ctypes.c_uint32, ctypes.c_double, ctypes.c_void_p, ctypes.c_void_p
    ]
    lib.polydim_stiefel_cayley_smw_f64.restype = ctypes.c_int32

    D = 512
    K = 16
    X = np.zeros((D, K), dtype=np.float64)
    G = np.zeros((D, K), dtype=np.float64)
    Y = np.zeros((D, K), dtype=np.float64)
    
    X_ptr = X.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    G_ptr = G.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    Y_ptr = Y.ctypes.data_as(ctypes.POINTER(ctypes.c_double))

    iteration = 0
    while True:
        r = np.random.rand()
        if r < 0.15:
            X.fill(np.nan)
            G.fill(np.random.randn())
        elif r < 0.30:
            X.fill(np.random.randn())
            G.fill(np.inf)
        elif r < 0.45:
            X.fill(1e-315)
            G.fill(1e-310)
        elif r < 0.60:
            X.fill(0.0)
            G.fill(0.0)
        else:
            X[:] = np.random.randn(D, K)
            G[:] = np.random.randn(D, K)
            
        status = lib.polydim_stiefel_cayley_smw_f64(X_ptr, G_ptr, Y_ptr, D, K, 0.1, None, None)
        if status == 0 and (np.isnan(Y).any() or np.isinf(Y).any()):
            print(f"[ALERT] Stiefel worker {worker_id}: Silent NaN escape at iteration {iteration}!")
        iteration += 1

def fuzzer_rodrigues_worker(worker_id):
    lib = ctypes.CDLL(DLL_PATH)
    lib.polydim_rodrigues_geodesic_f64.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_double, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_void_p
    ]
    lib.polydim_rodrigues_geodesic_f64.restype = ctypes.c_int32

    D = 1024
    y = np.zeros(D, dtype=np.float64)
    u = np.zeros(D, dtype=np.float64)
    v = np.zeros(D, dtype=np.float64)
    o = np.zeros(D, dtype=np.float64)

    iteration = 0
    while True:
        r = np.random.rand()
        if r < 0.2:
            y.fill(np.nan)
        elif r < 0.4:
            u.fill(np.inf)
        elif r < 0.6:
            y.fill(0.0)
        else:
            y[:] = np.random.randn(D)
            y /= max(1e-12, np.linalg.norm(y))
            u[:] = np.random.randn(D)
            u /= max(1e-12, np.linalg.norm(u))
            v[:] = np.random.randn(D)
            v /= max(1e-12, np.linalg.norm(v))
            
        status = lib.polydim_rodrigues_geodesic_f64(
            y.ctypes.data, u.ctypes.data, v.ctypes.data, o.ctypes.data,
            0.5, D, None, None
        )
        if status == 0 and (np.isnan(o).any() or np.isinf(o).any()):
            print(f"[ALERT] Rodrigues worker {worker_id}: Silent NaN escape at iteration {iteration}!")
        iteration += 1

def pmtp_ring_fuzzer():
    tag = "continuous_pmtp_stress"
    D_RING = 100000
    channel = PMTPSlabChannel(tag, D_RING, DLL_PATH, create=True)
    buf = np.empty(D_RING, dtype=np.float64)
    cycle = 0
    while True:
        buf.fill(float(cycle + 1))
        channel.write_tensor(buf)
        read_back = channel.read_tensor(max_retries=10)
        if read_back is not None:
            v0 = read_back[0]
            if v0 > 0.0 and (read_back[-1] != v0 or not np.all(read_back == v0)):
                print(f"[ALERT] PMTP Ring Fuzzer detected torn read at cycle {cycle}!")
        cycle += 1
        if cycle % 1000 == 0:
            time.sleep(0.001)

if __name__ == "__main__":
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Launching POLYDIM V765 Autonomous Infinite Fuzzer Engine...")
    processes = []
    
    # 4 Stiefel workers
    for i in range(4):
        p = multiprocessing.Process(target=fuzzer_stiefel_worker, args=(i,))
        p.start()
        processes.append(p)
        
    # 4 Rodrigues workers
    for i in range(4):
        p = multiprocessing.Process(target=fuzzer_rodrigues_worker, args=(i,))
        p.start()
        processes.append(p)
        
    # 1 PMTP continuous shared memory fuzzer
    p_pmtp = multiprocessing.Process(target=pmtp_ring_fuzzer)
    p_pmtp.start()
    processes.append(p_pmtp)
    
    for p in processes:
        p.join()
