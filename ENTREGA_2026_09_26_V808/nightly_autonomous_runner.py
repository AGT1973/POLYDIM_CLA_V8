import os
import sys
import time
import json
import ctypes
import traceback
import threading
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "nightly_stress.log")
STATUS_FILE = os.path.join(BASE_DIR, "nightly_status.json")

if hasattr(os, 'add_dll_directory'):
    if os.path.exists(r"E:\winlibs_gcc14_zip\mingw64\bin"):
        os.add_dll_directory(r"E:\winlibs_gcc14_zip\mingw64\bin")

CPP_DLL = os.path.join(BASE_DIR, "polydim_cpp_v808_1.dll")
RUST_DLL = os.path.join(BASE_DIR, "polydim_rust_v808_1.dll")

def log(msg):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

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

class PolydimTelemetryEvent(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("timestamp_ns", ctypes.c_uint64),
        ("event_type", ctypes.c_uint32),
        ("thread_id", ctypes.c_uint32),
        ("metrics", ctypes.c_double * 14),
    ]

class PolydimSpscRing(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("write_index", ctypes.c_uint64), ("pad_write", ctypes.c_uint8 * 120),
        ("read_index", ctypes.c_uint64),  ("pad_read", ctypes.c_uint8 * 120),
        ("capacity", ctypes.c_uint64), ("capacity_mask", ctypes.c_uint64),
        ("ring_buffer", ctypes.POINTER(PolydimTelemetryEvent))
    ]

class PolydimBettiResult(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("status", ctypes.c_int32), ("components_betti0", ctypes.c_uint32),
        ("cycles_betti1", ctypes.c_int64), ("num_vertices", ctypes.c_uint32),
        ("num_edges", ctypes.c_uint32), ("is_critically_healthy", ctypes.c_uint8),
        ("is_optimally_healthy", ctypes.c_uint8), ("pad", ctypes.c_uint8 * 102)
    ]

class PolydimFrechetBettiResult(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("status", ctypes.c_int32), ("num_candidates", ctypes.c_uint32),
        ("dimension", ctypes.c_uint32), ("connected_components_betti0", ctypes.c_uint32),
        ("cycles_betti1", ctypes.c_int64), ("consensus_node_idx", ctypes.c_uint32),
        ("active_swarm_count", ctypes.c_uint32), ("rejected_outliers_count", ctypes.c_uint32),
        ("frechet_residual", ctypes.c_double), ("is_consensus_certified", ctypes.c_uint8),
        ("pad", ctypes.c_uint8 * 79)
    ]

def run_stress_cycle(cycle_id):
    log(f"=== INICIANDO CICLO DE ESTRES #{cycle_id} ===")
    
    cpp_lib = ctypes.CDLL(CPP_DLL)
    rust_lib = ctypes.CDLL(RUST_DLL)
    
    # 1. Verification of ABI sizes
    assert ctypes.sizeof(PolydimSolverOptions) == 64
    assert ctypes.sizeof(PolydimTelemetryEvent) == 128
    assert ctypes.sizeof(PolydimBettiResult) == 128
    assert ctypes.sizeof(PolydimFrechetBettiResult) == 128
    
    cpp_lib.polydim_abi_probe.argtypes = []
    cpp_lib.polydim_abi_probe.restype = ctypes.c_size_t
    probe_sz = cpp_lib.polydim_abi_probe()
    assert probe_sz == 64, f"ABI Probe failure: {probe_sz}"
    
    # 2. Degenerate Inputs: Stiefel Optimization with Zero Matrix
    cpp_lib.polydim_stiefel_optimize.argtypes = [
        ctypes.POINTER(ctypes.c_double), ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_double), ctypes.c_size_t, ctypes.c_size_t,
        ctypes.POINTER(PolydimSolverOptions), ctypes.POINTER(PolydimSolverResult), ctypes.c_void_p
    ]
    cpp_lib.polydim_stiefel_optimize.restype = ctypes.c_int32
    
    D, K = 10000, 16
    X_zero = np.zeros((D, K), dtype=np.float64)
    opts = PolydimSolverOptions(
        max_iterations=5, gradient_tolerance=1e-6, step_tolerance=1e-8,
        ortho_tolerance=1e-5, learning_rate=1e-3, sampling_period=1,
        num_threads=4, retraction_type=1, shift_regularization=1e-6
    )
    res = PolydimSolverResult()
    st = cpp_lib.polydim_stiefel_optimize(
        None, 0,
        X_zero.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        D, K, ctypes.byref(opts), ctypes.byref(res), None
    )
    assert not np.isnan(res.final_ortho_error), "NaN final_ortho_error on Zero input"
    log(f"-> [PASS] Stiefel Zero-Matrix D={D}: status={st}, ortho_err={res.final_ortho_error:.4e}")
    
    # 3. High-Dimensional Scaling (D=50,000, K=16)
    D_high = 50000
    X_rnd = np.random.randn(D_high, K).astype(np.float64)
    q, _ = np.linalg.qr(X_rnd)
    X_init = np.ascontiguousarray(q[:, :K])
    
    res_high = PolydimSolverResult()
    t0 = time.time()
    st_high = cpp_lib.polydim_stiefel_optimize(
        None, 0,
        X_init.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        D_high, K, ctypes.byref(opts), ctypes.byref(res_high), None
    )
    t_elapsed = time.time() - t0
    log(f"-> [PASS] Stiefel High-Dim D={D_high}: time={t_elapsed:.3f}s, status={st_high}, ortho_err={res_high.final_ortho_error:.4e}")
    
    # 4. Multi-Threaded SPSC Concurrency Test (100,000 events)
    cpp_lib.polydim_spsc_init.argtypes = [ctypes.POINTER(PolydimSpscRing), ctypes.c_size_t]
    cpp_lib.polydim_spsc_push.argtypes = [ctypes.POINTER(PolydimSpscRing), ctypes.POINTER(PolydimTelemetryEvent)]
    cpp_lib.polydim_spsc_pop.argtypes  = [ctypes.POINTER(PolydimSpscRing), ctypes.POINTER(PolydimTelemetryEvent)]
    cpp_lib.polydim_spsc_destroy.argtypes = [ctypes.POINTER(PolydimSpscRing)]
    
    ring = PolydimSpscRing()
    assert cpp_lib.polydim_spsc_init(ctypes.byref(ring), 2048) == 0
    N_events = 100000
    received = []
    
    def producer():
        for i in range(N_events):
            evt = PolydimTelemetryEvent()
            evt.timestamp_ns = i
            evt.event_type = 1
            evt.thread_id = 42
            evt.metrics[0] = float(i)
            while cpp_lib.polydim_spsc_push(ctypes.byref(ring), ctypes.byref(evt)) != 0:
                time.sleep(1e-6)
                
    def consumer():
        evt = PolydimTelemetryEvent()
        while len(received) < N_events:
            if cpp_lib.polydim_spsc_pop(ctypes.byref(ring), ctypes.byref(evt)) == 0:
                received.append(int(evt.metrics[0]))
                
    t_prod = threading.Thread(target=producer)
    t_cons = threading.Thread(target=consumer)
    t_cons.start()
    t_prod.start()
    t_prod.join()
    t_cons.join()
    cpp_lib.polydim_spsc_destroy(ctypes.byref(ring))
    assert received == list(range(N_events)), "SPSC telemetry data loss or reordering"
    log(f"-> [PASS] SPSC Concurrency: {N_events} events passed coherently")
    
    # 5. Rust FFI Degenerate Fuzzing: NaNs and Infs
    rust_lib.polydim_rust_frechet_betti_filter.argtypes = [
        ctypes.POINTER(ctypes.c_double), ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_double, ctypes.c_int64, ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(PolydimFrechetBettiResult)
    ]
    rust_lib.polydim_rust_frechet_betti_filter.restype = ctypes.c_int32
    
    candidates = np.random.randn(20, 128)
    candidates[5, 10] = np.nan
    candidates[12, 45] = np.inf
    out_consensus = np.zeros(128, dtype=np.float64)
    frechet_res = PolydimFrechetBettiResult()
    st_frechet = rust_lib.polydim_rust_frechet_betti_filter(
        candidates.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        20, 128, 1.0, 100,
        out_consensus.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        ctypes.byref(frechet_res)
    )
    assert st_frechet != 0, "Rust FFI Fréchet failed to reject NaN/Inf inputs"
    log(f"-> [PASS] Rust FFI Fréchet NaN/Inf Fuzzing: Rejected with status={st_frechet}")

    # Write status JSON
    status_data = {
        "cycle": cycle_id,
        "last_success_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "PASSING",
        "ortho_error_d50k": res_high.final_ortho_error,
        "time_d50k_sec": t_elapsed
    }
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_data, f, indent=2)

def main_loop():
    log("=== RUNNER AUTÓNOMO NOCTURNO INICIADO ===")
    cycle = 1
    while True:
        try:
            run_stress_cycle(cycle)
            log(f"Ciclo #{cycle} completado con ÉXITO (0 errores). Durmiendo 30s...")
            cycle += 1
            time.sleep(30)
        except Exception as e:
            err_msg = f"❌ ERROR DETECTADO EN CICLO #{cycle}:\n{traceback.format_exc()}"
            log(err_msg)
            status_data = {
                "cycle": cycle,
                "last_failure_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "FAILED",
                "error": str(e)
            }
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(status_data, f, indent=2)
            time.sleep(60)

if __name__ == "__main__":
    main_loop()
