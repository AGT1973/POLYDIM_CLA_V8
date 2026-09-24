# ============================================================================
# POLYDIM V764 — MONOLITHIC PRODUCTION ORCHESTRATOR
# IEEE-754 Strict Precision | S^(D-1) Manifold Geometry | PMTP Zero-Copy IPC
# Multi-Platform Hardware Agnostic | C++/Rust/Triton FFI | Topological Guard
# ============================================================================

import os
import sys
import gc
import time
import mmap
import ctypes
import platform
import numpy as np
from typing import Tuple, Optional, Dict, Any

# Ensure Windows finds MinGW runtime DLLs
if platform.system() == "Windows" and hasattr(os, "add_dll_directory"):
    mingw_bin = r"E:\winlibs_gcc14_zip\mingw64\bin"
    if os.path.exists(mingw_bin):
        try:
            os.add_dll_directory(mingw_bin)
        except Exception:
            pass

# ============================================================================
# 1. HARDWARE PROBE & DYNAMIC SILICON DISCOVERY
# ============================================================================
class HardwareProbe:
    @staticmethod
    def detect_environment() -> Dict[str, Any]:
        info = {
            "os": sys.platform,
            "cpu_threads": os.cpu_count() or 4,
            "cuda_available": False,
            "rocm_available": False,
            "recommended_backend": "CPU_OPENMP"
        }
        try:
            import torch
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                info["cuda_available"] = True
                info["gpu_name"] = device_name
                info["recommended_backend"] = "CUDA_TRITON"
        except Exception:
            pass

        return info

# ============================================================================
# 2. PMTP ZERO-COPY SHARED MEMORY CHANNEL
# ============================================================================
class PMTPSlabChannel:
    NUM_SLOTS = 4

    def __init__(self, tag: str, dimension: int, cpp_dll_path: str, create: bool = True):
        self.tag = tag
        self.D = dimension
        self.tensor_bytes = dimension * 8
        self.total_bytes = 64 + self.NUM_SLOTS * self.tensor_bytes
        self.shm_name = f"polydim_pmtp_{tag}"
        self.create = create
        
        if sys.platform == "win32":
            self.mmap_obj = mmap.mmap(-1, self.total_bytes, tagname=self.shm_name, access=mmap.ACCESS_WRITE)
        else:
            import posix_ipc
            flags = posix_ipc.O_CREAT if create else 0
            self.posix_shm = posix_ipc.SharedMemory(f"/{self.shm_name}", flags, size=self.total_bytes)
            self.mmap_obj = mmap.mmap(self.posix_shm.fd, self.total_bytes)

        # FFI Bridge to avoid TSO/Weak-Ordering data races on ARM/Apple Silicon
        self.lib = ctypes.CDLL(cpp_dll_path)
        self.lib.polydim_pmtp_init.argtypes = [ctypes.c_void_p]
        self.lib.polydim_pmtp_init.restype = None
        self.lib.polydim_pmtp_begin_write.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]
        self.lib.polydim_pmtp_begin_write.restype = ctypes.c_int32
        self.lib.polydim_pmtp_commit_write.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        self.lib.polydim_pmtp_commit_write.restype = ctypes.c_int32
        self.lib.polydim_pmtp_acquire_read.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64)]
        self.lib.polydim_pmtp_acquire_read.restype = ctypes.c_int32
        self.lib.polydim_pmtp_validate_read.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64]
        self.lib.polydim_pmtp_validate_read.restype = ctypes.c_int32

        # Obtenemos puntero void al mmap y conservamos el buffer para evitar GC
        buffer_type = ctypes.c_uint8 * self.total_bytes
        self._ctypes_buf = buffer_type.from_buffer(self.mmap_obj)
        self.mmap_ptr = ctypes.addressof(self._ctypes_buf)

        if create:
            self.lib.polydim_pmtp_init(self.mmap_ptr)

    def write_tensor(self, tensor_f64: np.ndarray) -> int:
        assert tensor_f64.dtype == np.float64 and tensor_f64.size == self.D
        
        # 1. Acquire slot (memory_order_acquire barrier inside C++)
        slot = ctypes.c_uint64(0)
        self.lib.polydim_pmtp_begin_write(self.mmap_ptr, ctypes.byref(slot))
        s = slot.value
        
        # 2. Direct copy to the reserved slot
        offset = 64 + s * self.tensor_bytes
        dest_view = np.frombuffer(self.mmap_obj, dtype=np.float64, count=self.D, offset=offset)
        np.copyto(dest_view, tensor_f64)
        del dest_view
        
        # 3. Commit (memory_order_release barrier inside C++)
        self.lib.polydim_pmtp_commit_write(self.mmap_ptr, s)
        return s

    def read_tensor(self, max_retries: int = 20) -> Optional[np.ndarray]:
        for _ in range(max_retries):
            observed_seq = ctypes.c_uint64(0)
            slot_out = ctypes.c_uint64(0)
            ticket_out = ctypes.c_uint64(0)
            
            # memory_order_acquire inside C++
            has_new = self.lib.polydim_pmtp_acquire_read(
                self.mmap_ptr, ctypes.byref(observed_seq), ctypes.byref(slot_out), ctypes.byref(ticket_out)
            )
            if has_new == 0:
                time.sleep(0.000005)
                continue
                
            s = slot_out.value
            t = ticket_out.value
            offset = 64 + s * self.tensor_bytes
            src_view = np.frombuffer(self.mmap_obj, dtype=np.float64, count=self.D, offset=offset)
            tensor_copy = np.copy(src_view)
            del src_view
            
            # Post-copy atomic validation barrier: verify writer did not cycle into slot during copy
            rc = self.lib.polydim_pmtp_validate_read(self.mmap_ptr, s, t)
            if rc == 0:
                return tensor_copy
            # Seqlock race detected, loop to re-read latest stable slot
            time.sleep(0.000005)
        return None

    def close(self):
        gc.collect()
        if hasattr(self, 'mmap_obj') and self.mmap_obj:
            try:
                self.mmap_obj.close()
            except BufferError:
                pass

# ============================================================================
# 3. NATIVE FFI KERNEL WRAPPER (C++ & RUST)
# ============================================================================
class PolydimNativeCore:
    def __init__(self, cpp_dll_path: str, rust_dll_path: str):
        if not os.path.exists(cpp_dll_path):
            raise FileNotFoundError(f"C++ Kernel DLL not found: {cpp_dll_path}")
        if not os.path.exists(rust_dll_path):
            raise FileNotFoundError(f"Rust Guard DLL not found: {rust_dll_path}")

        bin_dir = os.path.dirname(os.path.abspath(cpp_dll_path))
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(bin_dir)
            except Exception:
                pass

        self.cpp_lib = ctypes.CDLL(cpp_dll_path)
        self.rust_lib = ctypes.CDLL(rust_dll_path)

        # C++ Rodrigues
        self.cpp_lib.polydim_rodrigues_geodesic_f64.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_double, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_void_p
        ]
        self.cpp_lib.polydim_rodrigues_geodesic_f64.restype = ctypes.c_int32

        # C++ Stiefel Cayley-SMW
        self.cpp_lib.polydim_stiefel_cayley_smw_f64.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_uint64, ctypes.c_uint32, ctypes.c_double,
            ctypes.c_void_p, ctypes.c_void_p
        ]
        self.cpp_lib.polydim_stiefel_cayley_smw_f64.restype = ctypes.c_int32

        # C++ Selftest (P1.4: detect -ffast-math at load time)
        self.cpp_lib.polydim_selftest_all.argtypes = []
        self.cpp_lib.polydim_selftest_all.restype = ctypes.c_int32
        rc = self.cpp_lib.polydim_selftest_all()
        if rc != 0:
            raise RuntimeError(f"polydim_selftest_all FAILED: rc={rc} — DLL compiled with -ffast-math?")

        # C++ Build Info
        self.cpp_lib.polydim_build_info.argtypes = []
        self.cpp_lib.polydim_build_info.restype = ctypes.c_char_p

        # Rust Invariant Guard (5 args: y, u, v, d, *mut VerifyReport)
        class VerifyReport(ctypes.Structure):
            _fields_ = [
                ('norm_drift', ctypes.c_double),
                ('basis_uu_err', ctypes.c_double),
                ('basis_vv_err', ctypes.c_double),
                ('basis_uv_err', ctypes.c_double),
                ('bound_used', ctypes.c_double),
                ('subnormal_count', ctypes.c_uint64),
                ('nonfinite_count', ctypes.c_uint64),
            ]
        self.VerifyReport = VerifyReport

        self.rust_lib.polydim_rust_verify_invariants.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_size_t, ctypes.POINTER(VerifyReport)
        ]
        self.rust_lib.polydim_rust_verify_invariants.restype = ctypes.c_int32


    def apply_rodrigues_geodesic(
        self,
        y: np.ndarray,
        u: np.ndarray,
        v: np.ndarray,
        theta: float
    ) -> Tuple[np.ndarray, int]:
        assert y.dtype == np.float64 and u.dtype == np.float64 and v.dtype == np.float64
        D = y.size
        y_out = np.zeros(D, dtype=np.float64)

        status = self.cpp_lib.polydim_rodrigues_geodesic_f64(
            y.ctypes.data,
            u.ctypes.data,
            v.ctypes.data,
            y_out.ctypes.data,
            ctypes.c_double(theta),
            ctypes.c_uint64(D),
            None,
            None
        )
        return y_out, status

    def apply_stiefel_retraction(
        self,
        X: np.ndarray,
        G: np.ndarray,
        tau: float
    ) -> Tuple[np.ndarray, int]:
        assert X.dtype == np.float64 and G.dtype == np.float64
        D, K = X.shape
        Y_out = np.zeros((D, K), dtype=np.float64)

        status = self.cpp_lib.polydim_stiefel_cayley_smw_f64(
            X.ctypes.data,
            G.ctypes.data,
            Y_out.ctypes.data,
            ctypes.c_uint64(D),
            ctypes.c_uint32(K),
            ctypes.c_double(tau),
            None,
            None
        )
        return Y_out, status

    def verify_rust_invariants(self, tensor: np.ndarray) -> Tuple[int, float]:
        assert tensor.dtype == np.float64
        D = tensor.size
        report = self.VerifyReport()
        status = self.rust_lib.polydim_rust_verify_invariants(
            tensor.ctypes.data,
            None,
            None,
            ctypes.c_size_t(D),
            ctypes.byref(report)
        )
        return status, report.norm_drift

    def verify_betti1(self, adj_matrix: np.ndarray, threshold: float = 0.5) -> int:
        assert adj_matrix.dtype == np.float64
        N = adj_matrix.shape[0]
        return self.rust_lib.polydim_rust_betti1_guard(
            adj_matrix.ctypes.data,
            ctypes.c_size_t(N),
            ctypes.c_double(threshold)
        )

# ============================================================================
# 4. CANARY & SANITY EXECUTION ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    print("============================================================================")
    print("POLYDIM V764 — PRODUCTION MONOLITH INGESTION CANARY")
    print("============================================================================")
    hw = HardwareProbe.detect_environment()
    print(f"Hardware Discovery: {hw}")
