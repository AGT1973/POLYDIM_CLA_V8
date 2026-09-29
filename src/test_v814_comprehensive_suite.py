"""
test_v814_comprehensive_suite.py
POLYDIM V814 Comprehensive Validation Suite (Physical Silicon Hardening)
Adversarial & Numerical Integrity Test for C++ and Rust Kernels
"""

import os
import sys
import ctypes
import numpy as np
import time

# Paths
BASE_DIR = r"E:\POLYDIM_EINSOF\src"
MINGW_BIN = r"E:\winlibs_gcc14_zip\mingw64\bin"
if os.path.exists(MINGW_BIN):
    try:
        os.add_dll_directory(MINGW_BIN)
    except Exception as e:
        print(f"Warning adding dll dir: {e}")

CPP_DLL_PATH = os.path.join(BASE_DIR, "polydim_cpp_v814.dll")
RUST_DLL_PATH = os.path.join(BASE_DIR, "polydim_rust_v814.dll")

print(f"=== POLYDIM V814 PHYSICAL SILICON VALIDATION HARNESS ===")
print(f"CPP DLL:  {CPP_DLL_PATH} (Exists: {os.path.exists(CPP_DLL_PATH)})")
print(f"RUST DLL: {RUST_DLL_PATH} (Exists: {os.path.exists(RUST_DLL_PATH)})")

assert os.path.exists(CPP_DLL_PATH), "C++ DLL missing"
assert os.path.exists(RUST_DLL_PATH), "Rust DLL missing"

cpp_lib = ctypes.CDLL(CPP_DLL_PATH)
rust_lib = ctypes.CDLL(RUST_DLL_PATH)

# =========================================================================
# 1. TEST DSYRK GRAMIAN STREAMING
# =========================================================================
print("\n[TEST 1] Testing Hierarchical Streaming DSYRK (D=8192, K=16)...")
D, K = 8192, 16
X = np.random.randn(D, K).astype(np.float64)
K_out = np.zeros((K, K), dtype=np.float64)

cpp_lib.polydim_gram_dsyrk.argtypes = [
    ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t,
    ctypes.c_void_p, ctypes.c_uint32
]
cpp_lib.polydim_gram_dsyrk.restype = ctypes.c_int32

ret = cpp_lib.polydim_gram_dsyrk(
    X.ctypes.data_as(ctypes.c_void_p),
    ctypes.c_size_t(D),
    ctypes.c_size_t(K),
    K_out.ctypes.data_as(ctypes.c_void_p),
    ctypes.c_uint32(4)
)
assert ret == 0, f"DSYRK failed with error {ret}"
expected_K = X.T @ X
err_dsyrk = np.max(np.abs(K_out - expected_K))
print(f"  -> DSYRK Max Abs Diff vs NumPy: {err_dsyrk:.2e}")
assert err_dsyrk < 1e-10, f"DSYRK numerical drift too high: {err_dsyrk}"
print("  -> TEST 1 PASSED: DSYRK Streaming verified.")

# =========================================================================
# 2. TEST SPSC RING BATCH DRAIN ZERO-COPY
# =========================================================================
print("\n[TEST 2] Testing SPSC Ring Buffer Batch Drain...")
class PolydimTelemetryEvent(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("timestamp_ns", ctypes.c_uint64),
        ("event_type", ctypes.c_uint32),
        ("thread_id", ctypes.c_uint32),
        ("metrics", ctypes.c_double * 14)
    ]

class PolydimSpscRing(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("write_index", ctypes.c_uint64),
        ("pad_write", ctypes.c_uint8 * 120),
        ("read_index", ctypes.c_uint64),
        ("pad_read", ctypes.c_uint8 * 120),
        ("capacity", ctypes.c_size_t),
        ("capacity_mask", ctypes.c_size_t),
        ("ring_buffer", ctypes.c_void_p)
    ]

cpp_lib.polydim_spsc_init.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
cpp_lib.polydim_spsc_init.restype = ctypes.c_int32
cpp_lib.polydim_spsc_push.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
cpp_lib.polydim_spsc_push.restype = ctypes.c_int32
cpp_lib.polydim_spsc_drain_batch.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
cpp_lib.polydim_spsc_drain_batch.restype = ctypes.c_int32
cpp_lib.polydim_spsc_destroy.argtypes = [ctypes.c_void_p]
cpp_lib.polydim_spsc_destroy.restype = None

ring = PolydimSpscRing()
ret = cpp_lib.polydim_spsc_init(ctypes.byref(ring), ctypes.c_size_t(1024))
assert ret == 0, f"SPSC init failed: {ret}"

# Push 500 events
for i in range(500):
    ev = PolydimTelemetryEvent()
    ev.timestamp_ns = 1000 + i
    ev.event_type = 1
    ev.thread_id = i
    ev.metrics[0] = float(i)
    ret = cpp_lib.polydim_spsc_push(ctypes.byref(ring), ctypes.byref(ev))
    assert ret == 0, f"SPSC push failed at {i}"

# Batch drain
out_buf = (PolydimTelemetryEvent * 1024)()
drained_count = ctypes.c_size_t(0)
ret = cpp_lib.polydim_spsc_drain_batch(ctypes.byref(ring), out_buf, ctypes.c_size_t(1024), ctypes.byref(drained_count))
assert ret == 0, f"SPSC drain failed: {ret}"
assert drained_count.value == 500, f"Expected 500 drained events, got {drained_count.value}"
assert out_buf[0].thread_id == 0 and out_buf[499].thread_id == 499, "Corrupted event payload"

cpp_lib.polydim_spsc_destroy(ctypes.byref(ring))
print("  -> TEST 2 PASSED: SPSC Ring Batch Drain verified (500 events drained).")

# =========================================================================
# 3. TEST TRANSACTIONAL LSM RESERVOIR STEP & PRE-ACTIVATION BARRICADE
# =========================================================================
print("\n[TEST 3] Testing Transactional LSM Reservoir Step & Barricade (D=1024)...")
D_lsm = 1024
state = np.random.randn(D_lsm).astype(np.float64) * 0.1
state_backup = state.copy()
input_vec = np.random.randn(D_lsm).astype(np.float64) * 0.05
d1 = np.ones(D_lsm, dtype=np.int8)
p1 = np.arange(D_lsm, dtype=np.uint32)
d2 = np.ones(D_lsm, dtype=np.int8)
p2 = np.arange(D_lsm, dtype=np.uint32)

cpp_lib.polydim_structured_lsm_step.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_size_t, ctypes.c_double, ctypes.c_double
]
cpp_lib.polydim_structured_lsm_step.restype = ctypes.c_int32

ret = cpp_lib.polydim_structured_lsm_step(
    state.ctypes.data_as(ctypes.c_void_p),
    input_vec.ctypes.data_as(ctypes.c_void_p),
    d1.ctypes.data_as(ctypes.c_void_p),
    p1.ctypes.data_as(ctypes.c_void_p),
    d2.ctypes.data_as(ctypes.c_void_p),
    p2.ctypes.data_as(ctypes.c_void_p),
    ctypes.c_size_t(D_lsm),
    ctypes.c_double(0.8),
    ctypes.c_double(1.0)
)
assert ret == 0, f"LSM step nominal failed: {ret}"
assert np.all(np.isfinite(state)), "LSM state contains NaN/Inf"
print("  -> Nominal step: OK")

# Adversarial NaN injection in input -> Transactional rollback
corrupt_input = input_vec.copy()
corrupt_input[42] = np.nan
state_before_attack = state.copy()

ret_nan = cpp_lib.polydim_structured_lsm_step(
    state.ctypes.data_as(ctypes.c_void_p),
    corrupt_input.ctypes.data_as(ctypes.c_void_p),
    d1.ctypes.data_as(ctypes.c_void_p),
    p1.ctypes.data_as(ctypes.c_void_p),
    d2.ctypes.data_as(ctypes.c_void_p),
    p2.ctypes.data_as(ctypes.c_void_p),
    ctypes.c_size_t(D_lsm),
    ctypes.c_double(0.8),
    ctypes.c_double(1.0)
)
assert ret_nan != 0, "LSM failed to catch NaN input"
assert np.array_equal(state, state_before_attack), "LSM transactional state corrupted on error"
print("  -> Adversarial NaN barricade & atomic rollback: OK")
print("  -> TEST 3 PASSED: Transactional LSM verified.")

# =========================================================================
# 4. TEST LEVI-CIVITA PARALLEL TRANSPORT ON St(D,K)
# =========================================================================
print("\n[TEST 4] Testing Levi-Civita Parallel Transport on St(D,K) (D=512, K=8)...")
D_st, K_st = 512, 8
Y, _ = np.linalg.qr(np.random.randn(D_st, K_st))
# Tangent vector Xi at Y (Y^T Xi + Xi^T Y = 0)
Xi_raw = np.random.randn(D_st, K_st)
Xi = Xi_raw - Y @ (Y.T @ Xi_raw + Xi_raw.T @ Y) / 2.0
# Vector Eta to transport
Eta_raw = np.random.randn(D_st, K_st)
Eta = Eta_raw - Y @ (Y.T @ Eta_raw + Eta_raw.T @ Y) / 2.0
Delta_out = np.zeros((D_st, K_st), dtype=np.float64)

cpp_lib.polydim_stiefel_parallel_transport.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t,
    ctypes.c_double, ctypes.c_double
]
cpp_lib.polydim_stiefel_parallel_transport.restype = ctypes.c_int32

ret = cpp_lib.polydim_stiefel_parallel_transport(
    Y.ctypes.data_as(ctypes.c_void_p),
    Xi.ctypes.data_as(ctypes.c_void_p),
    Eta.ctypes.data_as(ctypes.c_void_p),
    Delta_out.ctypes.data_as(ctypes.c_void_p),
    ctypes.c_size_t(D_st),
    ctypes.c_size_t(K_st),
    ctypes.c_double(0.5),
    ctypes.c_double(1.0)
)
assert ret == 0, f"Parallel transport failed: {ret}"
assert np.all(np.isfinite(Delta_out)), "Transported vector contains NaN/Inf"
norm_eta = np.linalg.norm(Eta)
norm_delta = np.linalg.norm(Delta_out)
print(f"  -> Input Norm: {norm_eta:.6f}, Output Norm: {norm_delta:.6f}")
assert norm_delta > 0.0, "Delta output is zero"
print("  -> TEST 4 PASSED: Levi-Civita Parallel Transport verified.")

# =========================================================================
# 5. TEST RUST BETTI-1 FLAT DSU GUARD
# =========================================================================
print("\n[TEST 5] Testing Rust Betti-1 Dual Guard (Flat DSU u64)...")
class PolydimEdge(ctypes.Structure):
    _fields_ = [("u", ctypes.c_uint32), ("v", ctypes.c_uint32)]

class PolydimBettiResult(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_int32),
        ("components_betti0", ctypes.c_uint32),
        ("cycles_betti1", ctypes.c_int64),
        ("num_vertices", ctypes.c_uint32),
        ("num_edges", ctypes.c_uint32),
        ("is_critically_healthy", ctypes.c_uint8),
        ("is_optimally_healthy", ctypes.c_uint8),
        ("pad", ctypes.c_uint8 * 102)
    ]

rust_lib.polydim_rust_betti_dual_guard.argtypes = [
    ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
    ctypes.c_int64, ctypes.c_void_p
]
rust_lib.polydim_rust_betti_dual_guard.restype = ctypes.c_int32

# Create a graph: Triangle (0-1, 1-2, 2-0) -> Betti-0 = 1, Betti-1 = 1
edges = (PolydimEdge * 3)(
    PolydimEdge(0, 1),
    PolydimEdge(1, 2),
    PolydimEdge(2, 0)
)
res = PolydimBettiResult()
ret = rust_lib.polydim_rust_betti_dual_guard(edges, 3, 3, 2, ctypes.byref(res))
assert ret == 0, f"Betti guard failed: {ret}"
assert res.components_betti0 == 1, f"Expected B0=1, got {res.components_betti0}"
assert res.cycles_betti1 == 1, f"Expected B1=1, got {res.cycles_betti1}"
assert res.is_critically_healthy == 1, "Expected critical health"
assert res.is_optimally_healthy == 1, "Expected optimal health"
print(f"  -> Triangle Graph: Betti-0={res.components_betti0}, Betti-1={res.cycles_betti1} -> OK")
print("  -> TEST 5 PASSED: Rust Betti-1 Flat DSU Guard verified.")

# =========================================================================
# 6. TEST RUST FRECHET-BETTI CONSENSUS & BFT QUORUM
# =========================================================================
print("\n[TEST 6] Testing Rust Fréchet-Betti Filter & BFT Quorum...")
class PolydimFrechetBettiResult(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_int32),
        ("num_candidates", ctypes.c_uint32),
        ("dimension", ctypes.c_uint32),
        ("connected_components_betti0", ctypes.c_uint32),
        ("cycles_betti1", ctypes.c_int64),
        ("consensus_node_idx", ctypes.c_uint32),
        ("active_swarm_count", ctypes.c_uint32),
        ("rejected_outliers_count", ctypes.c_uint32),
        ("frechet_residual", ctypes.c_double),
        ("is_consensus_certified", ctypes.c_uint8),
        ("pad", ctypes.c_uint8 * 79)
    ]

rust_lib.polydim_rust_frechet_betti_filter.argtypes = [
    ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
    ctypes.c_double, ctypes.c_int64,
    ctypes.c_void_p, ctypes.c_void_p
]
rust_lib.polydim_rust_frechet_betti_filter.restype = ctypes.c_int32

N_nodes = 5
D_vec = 64
base_vec = np.random.randn(D_vec)
base_vec /= np.linalg.norm(base_vec)
# 5 nodes tightly clustered on S^{D-1}
candidates = np.array([base_vec + 0.01 * np.random.randn(D_vec) for _ in range(N_nodes)], dtype=np.float64)
for i in range(N_nodes):
    candidates[i] /= np.linalg.norm(candidates[i])

out_consensus = np.zeros(D_vec, dtype=np.float64)
fb_res = PolydimFrechetBettiResult()

ret = rust_lib.polydim_rust_frechet_betti_filter(
    candidates.ctypes.data_as(ctypes.c_void_p),
    ctypes.c_uint32(N_nodes),
    ctypes.c_uint32(D_vec),
    ctypes.c_double(0.5), # dist threshold
    ctypes.c_int64(10),   # max tau
    out_consensus.ctypes.data_as(ctypes.c_void_p),
    ctypes.byref(fb_res)
)
assert ret == 0, f"Frechet-Betti filter failed: {ret}"
assert fb_res.is_consensus_certified == 1, "Consensus should be certified"
norm_c = np.linalg.norm(out_consensus)
assert abs(norm_c - 1.0) < 1e-10, f"Consensus vector not normalized: {norm_c}"
print(f"  -> Consensus certified: {fb_res.is_consensus_certified}, B0={fb_res.connected_components_betti0}, Norm={norm_c:.6f}")
print("  -> TEST 6 PASSED: Rust Fréchet-Betti Consensus verified.")

# =========================================================================
# 7. TEST RUST ROSS-SELINGER QUANTUM SYNTHESIZER
# =========================================================================
print("\n[TEST 7] Testing Rust Ross-Selinger Quantum Synthesizer...")
rust_lib.polydim_rust_quantum_quantize_clifford_grid.argtypes = [
    ctypes.c_double, ctypes.c_uint32, ctypes.c_double, ctypes.c_uint32,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
]
rust_lib.polydim_rust_quantum_quantize_clifford_grid.restype = ctypes.c_int32

theta = np.pi / 2.0 # Exact 2 T-gates
out_opcodes = (ctypes.c_uint8 * 64)()
out_num_gates = ctypes.c_uint32(0)
out_err = ctypes.c_double(0.0)

ret = rust_lib.polydim_rust_quantum_quantize_clifford_grid(
    ctypes.c_double(theta),
    ctypes.c_uint32(0),
    ctypes.c_double(1e-4),
    ctypes.c_uint32(64),
    out_opcodes,
    ctypes.byref(out_num_gates),
    ctypes.byref(out_err)
)
assert ret == 0, f"Quantum synth failed: {ret}"
assert out_num_gates.value == 2, f"Expected 2 T-gates, got {out_num_gates.value}"
assert out_err.value < 1e-12, f"Expected zero residual, got {out_err.value}"
print(f"  -> Target angle: pi/2 -> Gates: {out_num_gates.value} T-gates, Residual Error: {out_err.value:.2e}")
print("  -> TEST 7 PASSED: Ross-Selinger Quantum Synthesizer verified.")

print("\n=================================================================")
print(">>> ALL 7 ADVERSARIAL PHYSICAL SILICON TESTS PASSED (EXIT CODE 0) <<<")
print("=================================================================")
sys.exit(0)
