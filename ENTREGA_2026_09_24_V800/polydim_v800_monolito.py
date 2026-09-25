import numpy as np
import ctypes
import os
import sys

# ============================================================================
# POLYDIM V800 - LATENT OS (GHOST PROTOCOL)
# ORQUESTADOR MONOLÍTICO - SOTA PYTHON FFI
# ============================================================================

class PolydimError(Exception):
    pass

class PolydimSlabAllocator:
    def __init__(self, d: int, k: int):
        self.d = d
        self.k = k
        self.bytes_len = int(np.uint64(d) * np.uint64(k) * np.uint64(8))
        self._alloc()
        
    def _alloc(self):
        # Asignación C-contiguous obligatoria por diseño SOTA
        self.tensor = np.zeros((self.d, self.k), dtype=np.float64, order='C')
        self._verify_c_contiguous()

    def _verify_c_contiguous(self):
        # SOTA FIX (FFI-01): CERO COPIAS SILENCIOSAS
        # Erradicado np.require. Aserción dura de topología.
        if not (self.tensor.flags.c_contiguous and self.tensor.flags.aligned):
            raise ValueError("SOTA FATAL: El tensor no es C-Contiguous o no está alineado. Se prohíbe la copia silenciosa.")

    def get_ptr(self):
        return self.tensor.ctypes.data_as(ctypes.POINTER(ctypes.c_double))

    def __del__(self):
        if hasattr(self, 'tensor'):
            del self.tensor

class PolydimV800Kernel:
    def __init__(self, dll_path: str):
        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"DLL no encontrada: {dll_path}")
        self.lib = ctypes.CDLL(dll_path)
        
        # Binding de Cayley SMW Matrix-Free (C++)
        self.lib.polydim_kernel_cayley_smw_v800.argtypes = [
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_int64,
            ctypes.c_int64,
            ctypes.POINTER(ctypes.c_double)
        ]
        self.lib.polydim_kernel_cayley_smw_v800.restype = ctypes.c_int32

    def execute_cayley_smw(self, x: np.ndarray, u: np.ndarray, v: np.ndarray, y_out: np.ndarray):
        # Validación topológica estricta sin copias
        for arr in (x, u, v, y_out):
            if not (arr.flags.c_contiguous and arr.flags.aligned):
                raise ValueError("SOTA FATAL: Tensor mal alineado pasado al kernel C++.")
        
        if not (x.shape == u.shape == v.shape == y_out.shape):
            raise ValueError("SOTA FATAL: Mismatch de dimensiones entre tensores de entrada X, U, V e Y_out.")

        d = x.shape[0]
        k = x.shape[1]
        
        x_ptr = x.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        u_ptr = u.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        v_ptr = v.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        y_ptr = y_out.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        
        ret = self.lib.polydim_kernel_cayley_smw_v800(x_ptr, u_ptr, v_ptr, d, k, y_ptr)
        
        if ret == -99:
            raise PolydimError("SOTA FPU ERROR: NaN o Inf detectado asintóticamente en el kernel (IEEE-754 Trap).")
        elif ret == -999:
            raise PolydimError("SOTA FATAL: Excepción C++ atrapada en el cortafuegos FFI.")
        elif ret != 0:
            raise PolydimError(f"Error desconocido en C++: {ret}")

if __name__ == "__main__":
    print("Iniciando validación V800 Monolito...")
    
    # Prueba de allocation topológica
    try:
        D = 100_000 # Dummy size for quick test
        K = 32
        
        X = PolydimSlabAllocator(D, K)
        U = PolydimSlabAllocator(D, K)
        V = PolydimSlabAllocator(D, K)
        Y_OUT = PolydimSlabAllocator(D, K)
        
        print("Slab Allocation 100% Zero-Copy OK.")
        
    except Exception as e:
        print(f"Falla crítica: {e}")
