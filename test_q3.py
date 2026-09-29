import os, sys, ctypes
import numpy as np

BASE_DIR = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808"
RUST_DLL = os.path.join(BASE_DIR, "polydim_rust_v808_1.dll")
rust_lib = ctypes.CDLL(RUST_DLL)
rust_lib.polydim_rust_quantum_synthesize_discrete.argtypes = [
    ctypes.c_double, ctypes.c_uint32, ctypes.c_double,
    ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
rust_lib.polydim_rust_quantum_synthesize_discrete.restype = ctypes.c_int32

buf = (ctypes.c_uint8 * 256)()
cnt = ctypes.c_uint32(0)
rust_lib.polydim_rust_quantum_synthesize_discrete(np.pi/8, 1, 1e-9, buf, 256, ctypes.byref(cnt))
print("Opcodes:", [buf[i] for i in range(cnt.value)])
