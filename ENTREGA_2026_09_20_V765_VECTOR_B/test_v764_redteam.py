import os, sys, time, ctypes
import numpy as np

# Configure MinGW bin
mingw_bin = r"E:\winlibs_gcc14_zip\mingw64\bin"
if os.path.exists(mingw_bin):
    os.add_dll_directory(mingw_bin)

cpp_dll_path = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_20_V764\build\libpolydim.dll"
cpp = ctypes.CDLL(cpp_dll_path)

print("=== SABUESO RED TEAM V764: BATERÍA DESTRUCTIVA ASINTÓTICA ===")

# Signatures
cpp.polydim_rodrigues_geodesic_f64.argtypes = [
    np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),
    np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),
    np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),
    np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),
    ctypes.c_double, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_void_p
]
cpp.polydim_rodrigues_geodesic_f64.restype = ctypes.c_int32

cpp.polydim_stiefel_cayley_smw_f64.argtypes = [
    np.ctypeslib.ndpointer(dtype=np.float64, ndim=2, flags='C_CONTIGUOUS'),
    np.ctypeslib.ndpointer(dtype=np.float64, ndim=2, flags='C_CONTIGUOUS'),
    np.ctypeslib.ndpointer(dtype=np.float64, ndim=2, flags='C_CONTIGUOUS'),
    ctypes.c_uint64, ctypes.c_uint32, ctypes.c_double,
    ctypes.c_void_p, ctypes.c_void_p
]
cpp.polydim_stiefel_cayley_smw_f64.restype = ctypes.c_int32

cpp.polydim_cholqr2_f64.argtypes = [
    np.ctypeslib.ndpointer(dtype=np.float64, ndim=2, flags='C_CONTIGUOUS'),
    ctypes.c_uint64, ctypes.c_uint32
]
cpp.polydim_cholqr2_f64.restype = ctypes.c_int32

# 1. ATAQUE ASINTÓTICO S^(D-1) a D = 1,000,000
D = 1000000
print(f"\n[Ataque 1] Rodrigues Asintótico D={D} con componentes subnormales...")
y = np.zeros(D, dtype=np.float64)
y[0] = 1.0
y[1:1000] = 1e-308
u = np.zeros(D, dtype=np.float64)
u[0] = 1.0
v = np.zeros(D, dtype=np.float64)
v[D-1] = 1.0
y_out = np.empty(D, dtype=np.float64)

st = cpp.polydim_rodrigues_geodesic_f64(y, u, v, y_out, 0.7853981633974483, D, None, None)
drift = abs(np.linalg.norm(y_out) - 1.0)
print(f" -> Status: {st}, Deriva: {drift:.2e}")
assert st == 0 and drift < 1e-14, "Falla en Ataque 1"

# 2. ATAQUE CHOLQR2 TILING
print(f"\n[Ataque 2] CholQR2 Tiling D={32768}, K=16...")
D_chol, K_chol = 32768, 16
np.random.seed(1337)
X = np.random.randn(D_chol, K_chol).astype(np.float64)
rc = cpp.polydim_cholqr2_f64(X, D_chol, K_chol)
err = np.max(np.abs(X.T @ X - np.eye(K_chol)))
print(f" -> CholQR2 Status: {rc}, Ortho Error: {err:.2e}")
assert rc == 0 and err < 1e-13, "Falla en Ataque 2"

# 3. ATAQUE ALIASING IN-PLACE EN STIEFEL (Y_out == X)
print(f"\n[Ataque 3] Stiefel Cayley-SMW: Aliasing In-Place (Y_out == X)...")
D_s, K_s = 512, 8
X_s = np.ascontiguousarray(np.linalg.qr(np.random.randn(D_s, K_s))[0], dtype=np.float64)
G_s = np.ascontiguousarray(np.random.randn(D_s, K_s), dtype=np.float64)

st_alias = cpp.polydim_stiefel_cayley_smw_f64(X_s, G_s, X_s, D_s, K_s, 0.1, None, None)
print(f" -> Aliasing In-Place Status (debería ser -11): {st_alias}")
assert st_alias == -11, "Falla en Ataque 3: Aliasing no fue detectado"

print("\n=== SILICON CONTRACT VERIFIED: TODAS LAS PRUEBAS RED TEAM SUPERADAS ===")
