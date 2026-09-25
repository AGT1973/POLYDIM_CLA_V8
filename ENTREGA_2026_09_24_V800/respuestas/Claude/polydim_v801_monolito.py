import numpy as np
import ctypes
import os

# ============================================================================
# POLYDIM V801 - LATENT OS (GHOST PROTOCOL)
# ORQUESTADOR MONOLITICO - SOTA PYTHON FFI
#
# CHANGELOG vs V800:
#   [FIX-13] *** The headline fix. *** V800 loaded the Rust DLL and bound
#            polydim_validate_tensor_v800 / polydim_higham_bound_v800 /
#            polydim_weiszfeld_swap_v800 -- but ONLY inside the test suite.
#            The production orchestrator (this file) never loaded the Rust
#            library at all, so every claim in the README about a "Rust
#            topological guard" protecting the FFI boundary was true only
#            of the test process, never of a real call from user code.
#            execute_cayley_smw now loads the Rust guard and calls
#            polydim_validate_tensor_v801 BEFORE touching the C++ kernel.
#   [FIX-14] polydim_check_isa_support_v801 (C++) is now called once at
#            PolydimV801Kernel construction time, so a binary built for an
#            instruction set the host CPU doesn't have fails immediately
#            with a clear PolydimError instead of risking a SIGILL deep
#            inside a long-running batch.
#   [FIX-15] PolydimSlabAllocator.bytes_len used np.uint64 arithmetic, which
#            wraps silently on overflow (no exception) -- the opposite of
#            what "prevención de desbordamientos de 64 bits" promised.
#            Now computed as a plain Python int (arbitrary precision, never
#            wraps) and only cast down after an explicit range check against
#            what ctypes.c_size_t can hold on this platform.
#   [FIX-16] execute_cayley_smw now checks D>0/K>0 itself before calling into
#            C++, instead of relying entirely on the C++ side's -2 return
#            (defense in depth at the FFI boundary, not just inside it).
# ============================================================================


class PolydimError(Exception):
    pass


class PolydimSlabAllocator:
    def __init__(self, d: int, k: int):
        if d <= 0 or k <= 0:
            raise ValueError(f"SOTA FATAL: dimensiones invalidas d={d}, k={k}.")
        self.d = d
        self.k = k

        # [FIX-15] Python ints never overflow; only cast down at the very
        # end, after checking the result actually fits where ctypes needs it.
        bytes_len = d * k * 8
        max_size_t = (1 << (8 * ctypes.sizeof(ctypes.c_size_t))) - 1
        if bytes_len > max_size_t:
            raise ValueError(
                f"SOTA FATAL: tensor de {bytes_len} bytes excede el size_t de esta plataforma "
                f"({max_size_t} bytes max). No se permite wrap-around silencioso."
            )
        self.bytes_len = bytes_len
        self._alloc()

    def _alloc(self):
        self.tensor = np.zeros((self.d, self.k), dtype=np.float64, order='C')
        self._verify_c_contiguous()

    def _verify_c_contiguous(self):
        if not (self.tensor.flags.c_contiguous and self.tensor.flags.aligned):
            raise ValueError("SOTA FATAL: El tensor no es C-Contiguous o no esta alineado. Se prohibe la copia silenciosa.")

    def get_ptr(self):
        return self.tensor.ctypes.data_as(ctypes.POINTER(ctypes.c_double))


class PolydimV801Kernel:
    def __init__(self, cpp_dll_path: str, rust_dll_path: str):
        if not os.path.exists(cpp_dll_path):
            raise FileNotFoundError(f"DLL C++ no encontrada: {cpp_dll_path}")
        if not os.path.exists(rust_dll_path):
            raise FileNotFoundError(f"DLL Rust no encontrada: {rust_dll_path}")

        self.cpp_lib = ctypes.CDLL(cpp_dll_path)
        self.cpp_lib.polydim_kernel_cayley_smw_v801.argtypes = [
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_int64,
            ctypes.c_int64,
            ctypes.POINTER(ctypes.c_double)
        ]
        self.cpp_lib.polydim_kernel_cayley_smw_v801.restype = ctypes.c_int32
        self.cpp_lib.polydim_check_isa_support_v801.restype = ctypes.c_int32

        # [FIX-13] Rust guard is now ALWAYS loaded by the production path.
        self.rust_lib = ctypes.CDLL(rust_dll_path)
        self.rust_lib.polydim_validate_tensor_v801.argtypes = [ctypes.c_int64, ctypes.c_int64, ctypes.c_size_t]
        self.rust_lib.polydim_validate_tensor_v801.restype = ctypes.c_int32

        # [FIX-14] fail fast if this binary can't safely run on this CPU.
        isa_ret = self.cpp_lib.polydim_check_isa_support_v801()
        if isa_ret != 0:
            raise PolydimError(
                f"SOTA FATAL: el kernel C++ fue compilado para un set de instrucciones que "
                f"esta CPU no soporta (codigo {isa_ret}). Recompilar con flags acordes al "
                f"Silicon Contract real de este host (ver CHANGELOG_V801.md FIX-04)."
            )

    def execute_cayley_smw(self, x: np.ndarray, u: np.ndarray, v: np.ndarray, y_out: np.ndarray):
        for arr in (x, u, v, y_out):
            if not (arr.flags.c_contiguous and arr.flags.aligned):
                raise ValueError("SOTA FATAL: Tensor mal alineado pasado al kernel C++.")

        if not (x.shape == u.shape == v.shape == y_out.shape):
            raise ValueError("SOTA FATAL: Mismatch de dimensiones entre tensores de entrada X, U, V e Y_out.")

        d, k = x.shape[0], x.shape[1]
        if d <= 0 or k <= 0:  # [FIX-16]
            raise ValueError(f"SOTA FATAL: dimensiones invalidas d={d}, k={k}.")

        # [FIX-13] the guard V800 certified in isolation but never actually called.
        validate_ret = self.rust_lib.polydim_validate_tensor_v801(d, k, x.nbytes)
        if validate_ret != 0:
            raise PolydimError(f"SOTA FATAL: validacion Rust de tensor fallo (codigo {validate_ret}).")

        x_ptr = x.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        u_ptr = u.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        v_ptr = v.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        y_ptr = y_out.ctypes.data_as(ctypes.POINTER(ctypes.c_double))

        ret = self.cpp_lib.polydim_kernel_cayley_smw_v801(x_ptr, u_ptr, v_ptr, d, k, y_ptr)

        if ret == -99:
            raise PolydimError("SOTA FPU ERROR: NaN o Inf detectado (IEEE-754 Trap). Y_out tiene NaN explicito en cada celda afectada.")
        elif ret == -999:
            raise PolydimError("SOTA FATAL: Excepcion C++ atrapada en el cortafuegos FFI.")
        elif ret != 0:
            raise PolydimError(f"Error desconocido en C++: {ret}")
