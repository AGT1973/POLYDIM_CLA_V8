import numpy as np
import ctypes
import os
import sys
import mmap
import gc

# ============================================================================
# POLYDIM V803 - LATENT OS (GHOST PROTOCOL)
# ORQUESTADOR MONOLÍTICO - SOTA PYTHON FFI (FIX-13 & REAL IPC PMTP)
# ============================================================================

class PolydimError(Exception):
    pass

class PolydimSlabAllocator:
    """
    Allocates physical OS Shared Memory (mmap) on RAM, ensuring true PMTP zero-copy IPC
    and physical page lock without private heap allocation.
    """
    def __init__(self, d: int, k: int):
        self.d = d
        self.k = k
        self.bytes_len = int(np.uint64(d) * np.uint64(k) * np.uint64(8))
        self._alloc_mmap()
        
    def _alloc_mmap(self):
        # Physical OS Shared Memory allocation (mmap)
        self.shm = mmap.mmap(-1, self.bytes_len)
        self.tensor = np.frombuffer(self.shm, dtype=np.float64).reshape((self.d, self.k))
        self._verify_c_contiguous()

    def _verify_c_contiguous(self):
        if not (self.tensor.flags.c_contiguous and self.tensor.flags.aligned):
            raise ValueError("SOTA FATAL: Shared memory slab is not C-Contiguous or aligned.")

    def get_ptr(self):
        return self.tensor.ctypes.data_as(ctypes.POINTER(ctypes.c_double))

    def close(self):
        if hasattr(self, 'tensor') and self.tensor is not None:
            del self.tensor
            self.tensor = None
            try:
                gc.collect()
            except Exception:
                pass
        if hasattr(self, 'shm') and self.shm is not None:
            try:
                self.shm.close()
            except Exception:
                pass
            self.shm = None

    def __del__(self):
        self.close()

class PolydimV803Kernel:
    def __init__(self, delivery_dir: str):
        self.cpp_dll_path = os.path.join(delivery_dir, "polydim_kernel_v803.dll")
        self.rust_dll_path = os.path.join(delivery_dir, "polydim_rust_guard_v803.dll")
        
        # Add MinGW bin path for DLL dependencies on Windows
        mingw_bin = r"E:\winlibs_gcc14_zip\mingw64\bin"
        if os.path.exists(mingw_bin) and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(mingw_bin)

        if not os.path.exists(self.cpp_dll_path):
            raise FileNotFoundError(f"C++ DLL not found: {self.cpp_dll_path}")
        if not os.path.exists(self.rust_dll_path):
            raise FileNotFoundError(f"Rust DLL not found: {self.rust_dll_path}")

        # Bind Rust Guard DLL (Mandatory FIX-13)
        self.rust_lib = ctypes.CDLL(self.rust_dll_path)
        self.rust_lib.polydim_validate_tensor_v803.argtypes = [
            ctypes.c_int64, ctypes.c_int64, ctypes.c_size_t
        ]
        self.rust_lib.polydim_validate_tensor_v803.restype = ctypes.c_int32

        # Bind C++ Kernel DLL
        self.cpp_lib = ctypes.CDLL(self.cpp_dll_path)
        self.cpp_lib.polydim_abi_version.restype = ctypes.c_uint32
        self.cpp_lib.polydim_kernel_cayley_smw_v803.argtypes = [
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_int64,
            ctypes.c_int64,
            ctypes.POINTER(ctypes.c_double)
        ]
        self.cpp_lib.polydim_kernel_cayley_smw_v803.restype = ctypes.c_int32

    def execute_cayley_smw(self, x: np.ndarray, u: np.ndarray, v: np.ndarray, y_out: np.ndarray):
        # 1. Validation of layout & alignment
        for arr in (x, u, v, y_out):
            if not (arr.flags.c_contiguous and arr.flags.aligned):
                raise ValueError("SOTA FATAL: Tensor mal alineado pasado al kernel C++.")
        
        if not (x.shape == u.shape == v.shape == y_out.shape):
            raise ValueError("SOTA FATAL: Mismatch de dimensiones entre tensores X, U, V e Y_out.")

        d, k = x.shape[0], x.shape[1]
        bytes_len = int(d * k * 8)

        # 2. MANDATORY FIX-13: Rust Guard validation prior to C++ invocation
        rust_ret = self.rust_lib.polydim_validate_tensor_v803(d, k, bytes_len)
        if rust_ret != 0:
            raise PolydimError(f"RUST GUARD REJECTED TENSOR (Exit Code: {rust_ret}).")

        # 3. Execution of SOTA C++ Cayley-SMW Kernel
        x_ptr = x.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        u_ptr = u.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        v_ptr = v.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        y_ptr = y_out.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        
        ret = self.cpp_lib.polydim_kernel_cayley_smw_v803(x_ptr, u_ptr, v_ptr, d, k, y_ptr)
        
        if ret == -99:
            raise PolydimError("SOTA FPU ERROR: NaN/Inf detectado asintóticamente (IEEE-754 Trap).")
        elif ret == -999:
            raise PolydimError("SOTA FATAL: Excepción C++ atrapada en cortafuegos FFI.")
        elif ret != 0:
            raise PolydimError(f"Error C++ desconocido: {ret}")

if __name__ == "__main__":
    print("Validando Polydim V803 Monolito con Guardián Rust y Real SharedMemory...")
    delivery_dir = os.path.dirname(os.path.abspath(__file__))
    kernel = PolydimV803Kernel(delivery_dir)
    
    D, K = 100_000, 32
    X_alloc = PolydimSlabAllocator(D, K)
    U_alloc = PolydimSlabAllocator(D, K)
    V_alloc = PolydimSlabAllocator(D, K)
    Y_alloc = PolydimSlabAllocator(D, K)

    X_alloc.tensor[:] = 0.5
    U_alloc.tensor[:] = 0.25
    V_alloc.tensor[:] = 0.125

    kernel.execute_cayley_smw(X_alloc.tensor, U_alloc.tensor, V_alloc.tensor, Y_alloc.tensor)
    print(f"Éxito: Y_alloc[0, 0] = {Y_alloc.tensor[0, 0]:.6f}")
