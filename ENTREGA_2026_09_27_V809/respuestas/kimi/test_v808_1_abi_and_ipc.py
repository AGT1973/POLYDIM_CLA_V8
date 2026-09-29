#!/usr/bin/env python3
# test_v808_1_abi_and_ipc.py — PATCH C2: suite con ABI corregida.
# Cambios frente a test_v808_ipc_suite.py:
#   1. PolydimSolverOptions SIN objective_tolerance (64 bytes, espejo del header).
#   2. Aserción dura: sizeof(Options) == polydim_abi_probe() en el arranque.
#   3. PolydimTelemetryEvent espejado a 128 bytes (timestamp/event_type/thread_id/metrics[14]).
#   4. Resultados Rust alocados con polydim_alloc_aligned(.,128) -> alineación real.
#   5. retraction_type usa valores definidos por el ABI (0 = CHOLQR2, 1 = CAYLEY_SMW).

import os, sys, ctypes, time, threading
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CPP_DLL = os.path.join(BASE_DIR, "polydim_cpp_v808_1.dll")
RUST_DLL = os.path.join(BASE_DIR, "polydim_rust_v808_1.dll")
cpp_lib = ctypes.CDLL(CPP_DLL)
rust_lib = ctypes.CDLL(RUST_DLL)

# ---------------- Estructuras ABI (espejo exacto de polydim_solver_abi_v808_1.h) ---
class PolydimSolverOptions(ctypes.Structure):
    _pack_ = 8
    _fields_ = [  # 64 bytes — SIN objective_tolerance
        ("max_iterations", ctypes.c_uint64),      # 0
        ("gradient_tolerance", ctypes.c_double),  # 8
        ("step_tolerance", ctypes.c_double),      # 16
        ("ortho_tolerance", ctypes.c_double),     # 24
        ("learning_rate", ctypes.c_double),       # 32
        ("sampling_period", ctypes.c_uint32),     # 40
        ("num_threads", ctypes.c_uint32),         # 44
        ("retraction_type", ctypes.c_int32),      # 48
        ("shift_regularization", ctypes.c_double),# 56
    ]

class PolydimSolverResult(ctypes.Structure):
    _pack_ = 8
    _fields_ = [("status", ctypes.c_int32), ("iterations_executed", ctypes.c_uint64),
                ("final_objective", ctypes.c_double), ("final_grad_norm", ctypes.c_double),
                ("final_ortho_error", ctypes.c_double), ("total_time_ns", ctypes.c_uint64),
                ("status_message", ctypes.c_char * 256)]

class PolydimTelemetryEvent(ctypes.Structure):
    _pack_ = 8
    _fields_ = [  # 128 bytes, espejo exacto del C++
        ("timestamp_ns", ctypes.c_uint64),
        ("event_type", ctypes.c_uint32),
        ("thread_id", ctypes.c_uint32),
        ("metrics", ctypes.c_double * 14),  # [0]=iteration [1]=objective [2]=grad [3]=ortho [4]=step
    ]

class PolydimSpscRing(ctypes.Structure):
    _pack_ = 8
    _fields_ = [("write_index", ctypes.c_uint64), ("pad_write", ctypes.c_uint8 * 120),
                ("read_index", ctypes.c_uint64),  ("pad_read", ctypes.c_uint8 * 120),
                ("capacity", ctypes.c_uint64), ("capacity_mask", ctypes.c_uint64),
                ("ring_buffer", ctypes.POINTER(PolydimTelemetryEvent))]

class PolydimEdge(ctypes.Structure):
    _fields_ = [("u", ctypes.c_uint32), ("v", ctypes.c_uint32)]

class PolydimBettiResult(ctypes.Structure):
    _pack_ = 8
    _fields_ = [("status", ctypes.c_int32), ("components_betti0", ctypes.c_uint32),
                ("cycles_betti1", ctypes.c_int64), ("num_vertices", ctypes.c_uint32),
                ("num_edges", ctypes.c_uint32), ("is_critically_healthy", ctypes.c_uint8),
                ("is_optimally_healthy", ctypes.c_uint8), ("pad", ctypes.c_uint8 * 102)]  # 128

class PolydimFrechetBettiResult(ctypes.Structure):
    _pack_ = 8
    _fields_ = [("status", ctypes.c_int32), ("num_candidates", ctypes.c_uint32),
                ("dimension", ctypes.c_uint32), ("connected_components_betti0", ctypes.c_uint32),
                ("cycles_betti1", ctypes.c_int64), ("consensus_node_idx", ctypes.c_uint32),
                ("active_swarm_count", ctypes.c_uint32), ("rejected_outliers_count", ctypes.c_uint32),
                ("frechet_residual", ctypes.c_double), ("is_consensus_certified", ctypes.c_uint8),
                ("pad", ctypes.c_uint8 * 79)]  # sizeof = 128 con align(8)

assert ctypes.sizeof(PolydimSolverOptions) == 64
assert ctypes.sizeof(PolydimTelemetryEvent) == 128
assert ctypes.sizeof(PolydimBettiResult) == 128
assert ctypes.sizeof(PolydimFrechetBettiResult) == 128

# ---------------- Barrera de deriva de ABI en cada arranque ----------------
cpp_lib.polydim_abi_probe.argtypes = []
cpp_lib.polydim_abi_probe.restype = ctypes.c_size_t
assert cpp_lib.polydim_abi_probe() == ctypes.sizeof(PolydimSolverOptions), f"ABI desync: C++={cpp_lib.polydim_abi_probe()} Python={ctypes.sizeof(PolydimSolverOptions)}"

# ---------------- Resultados Rust en memoria 128-alineada -----------------
cpp_lib.polydim_alloc_aligned.argtypes = [ctypes.c_size_t, ctypes.c_size_t]
cpp_lib.polydim_alloc_aligned.restype = ctypes.c_void_p
cpp_lib.polydim_free_aligned.argtypes = [ctypes.c_void_p]
cpp_lib.polydim_free_aligned.restype = None

def alloc_result(cls):
    n = ctypes.sizeof(cls)
    p = cpp_lib.polydim_alloc_aligned(n, 128)
    assert p and p % 128 == 0
    return ctypes.cast(p, ctypes.POINTER(cls)), p

# ---------------- bindings ----------------
cpp_lib.polydim_spsc_init.argtypes = [ctypes.POINTER(PolydimSpscRing), ctypes.c_size_t]
cpp_lib.polydim_spsc_push.argtypes = [ctypes.POINTER(PolydimSpscRing), ctypes.POINTER(PolydimTelemetryEvent)]
cpp_lib.polydim_spsc_pop.argtypes  = [ctypes.POINTER(PolydimSpscRing), ctypes.POINTER(PolydimTelemetryEvent)]
cpp_lib.polydim_spsc_destroy.argtypes = [ctypes.POINTER(PolydimSpscRing)]

# pmtp RCU V808.1
cpp_lib.pmtp_banked_slot_init.argtypes = [ctypes.c_void_p]
cpp_lib.pmtp_banked_slot_acquire_reader.argtypes = [ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_uint32, ctypes.c_uint64]
cpp_lib.pmtp_banked_slot_release_reader.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
cpp_lib.pmtp_banked_slot_acquire_writer.argtypes = [ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32, ctypes.c_uint64]
cpp_lib.pmtp_banked_slot_commit_writer.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

# ---------------- Test: SPSC con payload coherente ----------------
def test_spsc_payload_coherence():
    ring = PolydimSpscRing()
    assert cpp_lib.polydim_spsc_init(ctypes.byref(ring), 1024) == 0
    N = 50000
    received = []
    def producer():
        for i in range(N):
            evt = PolydimTelemetryEvent()
            evt.timestamp_ns = i
            evt.event_type = 2
            evt.thread_id = 1
            evt.metrics[0] = float(i)            # iteration
            evt.metrics[1] = 1.0 / (i + 1)       # objective
            while cpp_lib.polydim_spsc_push(ctypes.byref(ring), ctypes.byref(evt)) != 0:
                time.sleep(1e-5)
    def consumer():
        evt = PolydimTelemetryEvent()
        while len(received) < N:
            if cpp_lib.polydim_spsc_pop(ctypes.byref(ring), ctypes.byref(evt)) == 0:
                received.append(int(evt.metrics[0]))
    ct = threading.Thread(target=consumer); ct.start()
    pt = threading.Thread(target=producer); pt.start()
    pt.join(); ct.join()
    cpp_lib.polydim_spsc_destroy(ctypes.byref(ring))
    assert received == list(range(N))
    print("[PASS] SPSC con layout ABI coherente (128B por evento)")

# ---------------- Test: RCU rotación de bancos ----------------
def test_rcu_bank_rotation():
    hdr = (ctypes.c_uint8 * ctypes.sizeof(ctypes.c_uint8) * 3200)()  # header compartido
    buf = cpp_lib.polydim_alloc_aligned(3200, 128)
    hdr_p = ctypes.cast(buf, ctypes.c_void_p)
    cpp_lib.pmtp_banked_slot_init(hdr_p)
    seen_banks = []
    for cycle in range(6):
        wb = ctypes.c_uint32(0)
        st = cpp_lib.pmtp_banked_slot_acquire_writer(hdr_p, ctypes.byref(wb), os.getpid(), 0)
        assert st == 0, f"acquire_writer: {st}"
        assert wb.value not in seen_banks[-2:], f"Escritor re-uso un banco en uso: ciclo {cycle} banco {wb.value} historial {seen_banks}"
        seen_banks.append(wb.value)
        assert cpp_lib.pmtp_banked_slot_commit_writer(hdr_p, wb.value) == 0
    assert len(set(seen_banks)) == 3, f"Se esperaban 3 bancos rotando, got {seen_banks}"
    cpp_lib.polydim_free_aligned(buf)
    print(f"[PASS] RCU rota bancos sin reutilizar bancos en uso: {seen_banks}")

if __name__ == "__main__":
    test_spsc_payload_coherence()
    test_rcu_bank_rotation()
    print("OK — ABI v808.1 validada")
