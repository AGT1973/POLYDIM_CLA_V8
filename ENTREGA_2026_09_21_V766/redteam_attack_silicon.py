import os, sys, time, ctypes, mmap
import numpy as np

# Configurar ruta MinGW en Windows
if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
    mingw_bin = r"E:\winlibs_gcc14_zip\mingw64\bin"
    if os.path.exists(mingw_bin):
        os.add_dll_directory(mingw_bin)

cpp_dll_path = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_19_V764\build\polydim.dll"
rust_dll_path = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_19_V764\build\polydim_verify.dll"

cpp = ctypes.CDLL(cpp_dll_path)
rust = ctypes.CDLL(rust_dll_path)

print("=== SABUESO RED TEAM: BATERÍA DESTRUCTIVA ASINTÓTICA ===")

# Configurar firmas C++
cpp.polydim_rodrigues_geodesic_f64.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_double, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_void_p
]
cpp.polydim_rodrigues_geodesic_f64.restype = ctypes.c_int32

cpp.polydim_stiefel_cayley_smw_f64.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_uint64, ctypes.c_uint32, ctypes.c_double,
    ctypes.c_void_p, ctypes.c_void_p
]
cpp.polydim_stiefel_cayley_smw_f64.restype = ctypes.c_int32

# 1. ATAQUE ASINTÓTICO S^(D-1) a D = 1,000,000 (Subnormales + Deriva Límite)
D = 1000000
print(f"\n[Ataque 1] Rodrigues Asintótico D={D} con componentes subnormales...")
y = np.zeros(D, dtype=np.float64)
y[0] = 1.0
y[1:1000] = 1e-308 # Subnormales en el soporte

u = np.zeros(D, dtype=np.float64)
u[0] = 1.0

v = np.zeros(D, dtype=np.float64)
v[D-1] = 1.0

y_out = np.empty(D, dtype=np.float64)

st = cpp.polydim_rodrigues_geodesic_f64(
    y.ctypes.data, u.ctypes.data, v.ctypes.data, y_out.ctypes.data,
    ctypes.c_double(0.7853981633974483), ctypes.c_uint64(D), None, None
)

norm_out = np.linalg.norm(y_out)
drift = abs(norm_out - 1.0)
print(f" -> Retorno status: {st}, Norma out: {norm_out:.16f}, Deriva: {drift:.2e}")
assert st == 0 and drift < 1e-14, "Falla en Ataque 1"

# 2. ATAQUE DE ALIASING IN-PLACE EN STIEFEL (Y_out == X)
print(f"\n[Ataque 2] Stiefel Cayley-SMW: Aliasing In-Place (Y_out == X) D=512, K=8...")
D_s, K_s = 512, 8
np.random.seed(1337)
# Crear base ortonormal inicial para X
Q, _ = np.linalg.qr(np.random.randn(D_s, K_s))
X = np.ascontiguousarray(Q, dtype=np.float64)
G = np.ascontiguousarray(np.random.randn(D_s, K_s), dtype=np.float64)

# Pasar el mismo buffer X como Y_out (In-Place)
st_alias = cpp.polydim_stiefel_cayley_smw_f64(
    X.ctypes.data, G.ctypes.data, X.ctypes.data,
    ctypes.c_uint64(D_s), ctypes.c_uint32(K_s), ctypes.c_double(0.1), None, None
)
ortho_err = np.max(np.abs(X.T @ X - np.eye(K_s)))
print(f" -> Aliasing In-Place Status: {st_alias}, Error Ortogonalidad resultante: {ortho_err:.2e}")

# 3. ATAQUE DE SINGULARIDAD EN STIEFEL (Gradiente Nulo G = 0)
print(f"\n[Ataque 3] Stiefel Cayley-SMW con Gradiente Cero (G = 0)...")
G_zero = np.zeros((D_s, K_s), dtype=np.float64)
Y_zero = np.empty((D_s, K_s), dtype=np.float64)
st_zero = cpp.polydim_stiefel_cayley_smw_f64(
    X.ctypes.data, G_zero.ctypes.data, Y_zero.ctypes.data,
    ctypes.c_uint64(D_s), ctypes.c_uint32(K_s), ctypes.c_double(0.1), None, None
)
diff_x = np.max(np.abs(Y_zero - X))
print(f" -> Status G=0: {st_zero}, Diferencia con X (|Y-X|): {diff_x:.2e}")

print("\n=== TODOS LOS ATAQUES DEL RED TEAM COMPLETADOS ===")
