import os
import sys
import time
import ctypes
import numpy as np
import csv

if hasattr(os, 'add_dll_directory'):
    if os.path.exists(r"E:\winlibs_gcc14_zip\mingw64\bin"):
        os.add_dll_directory(r"E:\winlibs_gcc14_zip\mingw64\bin")
    if os.path.exists(r"E:\POLYDIM_EINSOF\src"):
        os.add_dll_directory(r"E:\POLYDIM_EINSOF\src")

CPP_PATH = r'E:\POLYDIM_EINSOF\src\polydim_cpp_v813.dll'
RUST_PATH = r'E:\POLYDIM_EINSOF\src\polydim_rust_v813.dll'
CSV_OUT = r'E:\POLYDIM_EINSOF\RAW_EMPIRICAL_LOGS\benchmark_v813.csv'

os.makedirs(r'E:\POLYDIM_EINSOF\RAW_EMPIRICAL_LOGS', exist_ok=True)

cpp_lib = ctypes.CDLL(CPP_PATH)
rust_lib = ctypes.CDLL(RUST_PATH)

# Setup Ctypes prototypes
cpp_lib.polydim_gram_dsyrk.argtypes = [
    ctypes.POINTER(ctypes.c_double),
    ctypes.c_size_t, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_double),
    ctypes.c_uint32
]
cpp_lib.polydim_gram_dsyrk.restype = ctypes.c_int32

cpp_lib.polydim_structured_lsm_step.argtypes = [
    ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(ctypes.c_int8),
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.POINTER(ctypes.c_int8),
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_size_t, ctypes.c_double, ctypes.c_double
]
cpp_lib.polydim_structured_lsm_step.restype = ctypes.c_int32

class PolydimEdge(ctypes.Structure):
    _fields_ = [
        ("u", ctypes.c_uint32),
        ("v", ctypes.c_uint32),
    ]

class PolydimBettiResult(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("status", ctypes.c_int32),
        ("components_betti0", ctypes.c_uint32),
        ("cycles_betti1", ctypes.c_int64),
        ("num_vertices", ctypes.c_uint32),
        ("num_edges", ctypes.c_uint32),
        ("is_critically_healthy", ctypes.c_uint8),
        ("is_optimally_healthy", ctypes.c_uint8),
        ("pad", ctypes.c_uint8 * 102),
    ]

class PolydimFrechetBettiResult(ctypes.Structure):
    _pack_ = 8
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
        ("pad", ctypes.c_uint8 * 79),
    ]

rust_lib.polydim_rust_betti_dual_guard.argtypes = [
    ctypes.POINTER(PolydimEdge),
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_int64,
    ctypes.POINTER(PolydimBettiResult)
]
rust_lib.polydim_rust_betti_dual_guard.restype = ctypes.c_int32

rust_lib.polydim_rust_frechet_betti_filter.argtypes = [
    ctypes.POINTER(ctypes.c_double),
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_double,
    ctypes.c_int64,
    ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(PolydimFrechetBettiResult)
]
rust_lib.polydim_rust_frechet_betti_filter.restype = ctypes.c_int32

results = []

print('=== INICIANDO BENCHMARK ASINTOTICO V813 ===')

# Benchmark 1: Gramiana DSYRK (Throughput)
K = 16
for D in [10000, 50000, 100000, 500000, 1000000]:
    print(f'Testing DSYRK D={D}, K={K}...')
    np.random.seed(42)
    X = np.random.randn(D * K).astype(np.float64)
    K_out = np.zeros(K * K, dtype=np.float64)
    
    X_ptr = X.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    K_ptr = K_out.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    
    t0 = time.perf_counter()
    st = cpp_lib.polydim_gram_dsyrk(X_ptr, D, K, K_ptr, 4)
    t1 = time.perf_counter()
    
    elapsed_ms = (t1 - t0) * 1000.0
    results.append({
        'Component': 'Gramiana_DSYRK',
        'Dimension_D': D,
        'Rank_K': K,
        'Metric': 'Execution_Time_ms',
        'Value': elapsed_ms,
        'Status': 'PASS' if st == 0 else 'FAIL'
    })
    print(f'  -> Time: {elapsed_ms:.2f} ms')

# Benchmark 2: Structured LSM FWHT
for D in [4096, 16384, 65536, 262144, 1048576]:
    print(f'Testing Structured LSM FWHT D={D}...')
    rng = np.random.RandomState(42)
    x = rng.randn(D).astype(np.float64)
    x /= np.linalg.norm(x)
    d1 = rng.choice([-1, 1], size=D).astype(np.int8)
    d2 = rng.choice([-1, 1], size=D).astype(np.int8)
    p1 = rng.permutation(D).astype(np.uint32)
    p2 = rng.permutation(D).astype(np.uint32)
    
    x_ptr = x.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    d1_ptr = d1.ctypes.data_as(ctypes.POINTER(ctypes.c_int8))
    p1_ptr = p1.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32))
    d2_ptr = d2.ctypes.data_as(ctypes.POINTER(ctypes.c_int8))
    p2_ptr = p2.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32))
    
    t0 = time.perf_counter()
    st = cpp_lib.polydim_structured_lsm_step(x_ptr, None, d1_ptr, p1_ptr, d2_ptr, p2_ptr, D, 0.85, 1.0)
    t1 = time.perf_counter()
    
    elapsed_ms = (t1 - t0) * 1000.0
    norm = np.linalg.norm(x)
    results.append({
        'Component': 'Structured_LSM_FWHT',
        'Dimension_D': D,
        'Rank_K': 1,
        'Metric': 'Execution_Time_ms',
        'Value': elapsed_ms,
        'Status': f'Norm={norm:.4f}'
    })
    print(f'  -> Time: {elapsed_ms:.2f} ms | Norm={norm:.4f}')

# Benchmark 3: Rust Iterative DSU Homology
for V in [10000, 50000, 100000, 500000, 1000000]:
    print(f'Testing Rust DSU Homology V={V}...')
    E = V - 1
    edges_np = np.empty((E, 2), dtype=np.uint32, order="C")
    edges_np[:, 0] = np.arange(E, dtype=np.uint32)
    edges_np[:, 1] = np.arange(1, V, dtype=np.uint32)
    c_edges = edges_np.ctypes.data_as(ctypes.POINTER(PolydimEdge))
    
    res = PolydimBettiResult()
    
    t0 = time.perf_counter()
    st = rust_lib.polydim_rust_betti_dual_guard(c_edges, E, V, 100, ctypes.byref(res))
    t1 = time.perf_counter()
    
    elapsed_ms = (t1 - t0) * 1000.0
    results.append({
        'Component': 'Rust_DSU_Homology',
        'Dimension_D': V,
        'Rank_K': 0,
        'Metric': 'Execution_Time_ms',
        'Value': elapsed_ms,
        'Status': f'Betti0={res.components_betti0}, Betti1={res.cycles_betti1}'
    })
    print(f'  -> Time: {elapsed_ms:.2f} ms | Betti0={res.components_betti0}, Betti1={res.cycles_betti1}')

# Benchmark 4: Frechet-Betti RPT Consensus
N_agents = 32
for D in [128, 512, 2048, 8192]:
    print(f'Testing Frechet-Betti RPT N={N_agents}, D={D}...')
    rng = np.random.RandomState(42)
    candidates = rng.randn(N_agents, D).astype(np.float64)
    for i in range(N_agents):
        candidates[i] /= np.linalg.norm(candidates[i])
    
    cand_flat = np.ascontiguousarray(candidates.flatten(), dtype=np.float64)
    c_ptr = cand_flat.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    out_vec = np.zeros(D, dtype=np.float64)
    out_ptr = out_vec.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    res = PolydimFrechetBettiResult()
    
    t0 = time.perf_counter()
    st = rust_lib.polydim_rust_frechet_betti_filter(c_ptr, N_agents, D, 1.2, 50, out_ptr, ctypes.byref(res))
    t1 = time.perf_counter()
    
    elapsed_ms = (t1 - t0) * 1000.0
    results.append({
        'Component': 'Frechet_Betti_RPT',
        'Dimension_D': D,
        'Rank_K': N_agents,
        'Metric': 'Execution_Time_ms',
        'Value': elapsed_ms,
        'Status': f'Certified={res.is_consensus_certified}, Betti1={res.cycles_betti1}'
    })
    print(f'  -> Time: {elapsed_ms:.2f} ms | Certified={res.is_consensus_certified}, Betti1={res.cycles_betti1}')

# Save CSV
with open(CSV_OUT, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['Component', 'Dimension_D', 'Rank_K', 'Metric', 'Value', 'Status'])
    writer.writeheader()
    for row in results:
        writer.writerow(row)

print(f'\n=== BENCHMARK V813 GUARDADO EXITOSAMENTE EN: {CSV_OUT} ===')
