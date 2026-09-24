import ctypes
import numpy as np
import os
import sys

if sys.platform == "win32":
    os.add_dll_directory(r'E:\winlibs_gcc14_zip\mingw64\bin')

DIR_PATH = os.path.dirname(os.path.abspath(__file__))
dll_path = os.path.join(DIR_PATH, "build", "libpolydim.dll")
if not os.path.exists(dll_path):
    raise FileNotFoundError("libpolydim.dll not found")

lib = ctypes.CDLL(dll_path)

lib.polydim_cholqr2_f64.argtypes = [
    np.ctypeslib.ndpointer(dtype=np.float64, ndim=2, flags='C_CONTIGUOUS'),
    ctypes.c_uint64,
    ctypes.c_uint32
]
lib.polydim_cholqr2_f64.restype = ctypes.c_int32

# Test D=32768, K=16
D = 32768
K = 16

# Generate a random matrix X
np.random.seed(42)
X = np.random.randn(D, K).astype(np.float64)

# Call CholQR2
rc = lib.polydim_cholqr2_f64(X, D, K)
print(f"CholQR2 Return Code: {rc}")

if rc == 0:
    # Verify orthonormality: X^T X = I
    XTX = X.T @ X
    I = np.eye(K)
    err = np.max(np.abs(XTX - I))
    print(f"Orthonormality Error: {err:.4e}")
    if err < 1e-13:
        print("CholQR2 Tiling Test PASSED.")
    else:
        print("CholQR2 Tiling Test FAILED: Error too large.")
else:
    print("CholQR2 Tiling Test FAILED: Non-zero return code.")
