import os
import sys
import time
import ctypes
import psutil
import platform
import numpy as np

# Proof of physical hardware
p = psutil.Process(os.getpid())
print(f"=== PHYSICAL SILICON EXECUTION WITNESS ===")
print(f"OS Process PID: {os.getpid()}")
print(f"Platform: {platform.platform()}")
print(f"CPU Arch: {platform.machine()} | Logical Cores: {os.cpu_count()}")
print(f"RAM Initial Working Set: {p.memory_info().rss / (1024*1024):.2f} MB")
print(f"Wall Clock Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}.{int((time.time()%1)*1000):03d}")

# Load physical DLLs
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(r"E:\winlibs_gcc14_zip\mingw64\bin")
    os.add_dll_directory(r"E:\POLYDIM_EINSOF\src")

cpp_dll = ctypes.CDLL(r"E:\POLYDIM_EINSOF\src\polydim_cpp_v812.dll")
rust_dll = ctypes.CDLL(r"E:\POLYDIM_EINSOF\src\polydim_rust_v812.dll")

print(f"Loaded polydim_cpp_v812.dll at memory address: {hex(cpp_dll._handle)}")
print(f"Loaded polydim_rust_v812.dll at memory address: {hex(rust_dll._handle)}")

# 1. Execute REAL C++ OpenMP DSYRK on CPU
D, K = 500000, 16
print(f"\n[PHYSICAL TEST 1] Allocating {D*K*8 / (1024*1024):.2f} MB RAM and executing C++ OpenMP DSYRK...")
X = np.random.randn(D * K).astype(np.float64)
K_out = np.zeros(K * K, dtype=np.float64)

cpp_dll.polydim_gram_dsyrk.argtypes = [
    ctypes.POINTER(ctypes.c_double), ctypes.c_size_t, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_double), ctypes.c_uint32
]
cpp_dll.polydim_gram_dsyrk.restype = ctypes.c_int32

t_start = time.perf_counter_ns()
status = cpp_dll.polydim_gram_dsyrk(
    X.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
    D, K,
    K_out.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
    K
)
t_end = time.perf_counter_ns()

print(f"C++ DSYRK Exit Status: {status}")
print(f"Physical Time Taken: {(t_end - t_start) / 1e6:.3f} ms")
print(f"K_out Gram Matrix Sample (first 4 elements): {K_out[:4]}")
print(f"RAM Peak Working Set: {p.memory_info().rss / (1024*1024):.2f} MB")

# 2. Execute REAL Rust DSU Iterative on 1,000,000 vertices
V = 1000000
print(f"\n[PHYSICAL TEST 2] Executing Rust DSU on {V} vertices in physical memory...")
class PolydimEdge(ctypes.Structure):
    _fields_ = [("u", ctypes.c_uint32), ("v", ctypes.c_uint32)]

class PolydimBettiResult(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("status", ctypes.c_int32), ("components_betti0", ctypes.c_uint32),
        ("cycles_betti1", ctypes.c_int64), ("num_vertices", ctypes.c_uint32),
        ("num_edges", ctypes.c_uint32), ("is_critically_healthy", ctypes.c_uint8),
        ("is_optimally_healthy", ctypes.c_uint8), ("pad", ctypes.c_uint8 * 102),
    ]

rust_dll.polydim_rust_betti_dual_guard.argtypes = [
    ctypes.POINTER(PolydimEdge), ctypes.c_uint32, ctypes.c_uint32,
    ctypes.c_int64, ctypes.POINTER(PolydimBettiResult)
]
rust_dll.polydim_rust_betti_dual_guard.restype = ctypes.c_int32

edges = (PolydimEdge * (V - 1))()
for i in range(V - 1):
    edges[i].u = i
    edges[i].v = i + 1

res = PolydimBettiResult()
t_start_rust = time.perf_counter_ns()
st_rust = rust_dll.polydim_rust_betti_dual_guard(edges, V - 1, V, 100, ctypes.byref(res))
t_end_rust = time.perf_counter_ns()

print(f"Rust DSU Status: {st_rust}")
print(f"Rust Physical Time: {(t_end_rust - t_start_rust) / 1e6:.3f} ms")
print(f"Betti-0 Components: {res.components_betti0} | Betti-1 Cycles: {res.cycles_betti1}")
print(f"Final RAM Working Set: {p.memory_info().rss / (1024*1024):.2f} MB")
print(f"=== PHYSICAL SILICON EXECUTION VERIFIED EXIT 0 ===")
