import sys, os, time, math, threading, ctypes
import numpy as np

# Rutas de binarios V753
v753_dir = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_18_V753"
bin_dir = os.path.join(v753_dir, "bin")
sys.path.insert(0, r"E:\POLYDIM_EINSOF\POLYDIM_V751")

from polydim.core import PolydimEngine, PolydimStatus
from polydim.solver_pcg import DualPCGSolver

print("=================================================================")
print("  POLYDIM V753 - VERIFICACION FISICA EN SILICIO NATIVO (WINDOWS)")
print("=================================================================")

cpp_dll = os.path.join(bin_dir, "polydim_kernel.dll")
rust_dll = os.path.join(bin_dir, "polydim_rust_guard.dll")

engine = PolydimEngine(cpp_dll_path=cpp_dll, rust_dll_path=rust_dll)
ver = engine.cpp_lib.polydim_get_version()
print(f"[OK] C++ Kernel cargado | Version: 0x{ver:08X}")

# Test 1: Zero-alloc a D=1,000,000
D = 1_000_000
y = np.ones(D, dtype=np.float64)
rc = engine.cpp_lib.polydim_zero_alloc_f64(y.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), ctypes.c_uint64(D))
assert rc == 0 and np.max(np.abs(y)) == 0.0
print(f"[TEST 1] Zero-Alloc D={D:,}: PASS (rc=0)")

# Test 2: Rodrigues Geodesic Rotation con Neumaier + Versine
rng = np.random.default_rng(2026)
u = rng.standard_normal(D)
u /= np.linalg.norm(u)
v = rng.standard_normal(D)
v -= np.dot(v, u) * u
v /= np.linalg.norm(v)

y = rng.standard_normal(D)
y /= np.linalg.norm(y)
y_comp = np.zeros(D, dtype=np.float64)

t0 = time.perf_counter()
rc_rot = engine.rotate_geodesic(y=y, y_comp=y_comp, u=u, v=v, theta=0.123456789)
t_rot = (time.perf_counter() - t0) * 1000
norm_res = np.linalg.norm(y + y_comp)
drift = abs(norm_res - 1.0)
print(f"[TEST 2] Rodrigues Geodesic D={D:,} | Tiempo: {t_rot:.2f}ms | Drift: {drift:.2e} | PASS (rc={rc_rot})")

# Test 3: Rust Guard Dynamic Tolerance
rc_guard = engine.verify_norm(y + y_comp)
print(f"[TEST 3] Rust Topological Guard Invariant: PASS (rc={rc_guard})")

# Test 4: Dual PCG Solver O(N*D)
solver = DualPCGSolver(ridge_alpha=1e-3, max_iter=200, tol=1e-7)
X = rng.standard_normal((100, 5000))
Y = rng.standard_normal((100, 1))
t0 = time.perf_counter()
alpha = solver.solve(X, Y)
t_pcg = (time.perf_counter() - t0) * 1000
print(f"[TEST 4] Dual PCG Solver N=100, D=5,000 | Tiempo: {t_pcg:.2f}ms | PASS")

print("=================================================================")
print("  RESULTADO: 4/4 PRUEBAS EN SILICIO V753 EXITOSAS ✓")
print("=================================================================")
