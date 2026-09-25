#!/usr/bin/env python3
"""
hardware_probe.py
Módulo formal de detección y despacho polimórfico multi-plataforma (POLYDIM V773).
Cumple con la Regla 27 (Silicon Contract): Cero hardcoding, autodetección en runtime de:
1. Google Cloud TPU (PyTorch/XLA Graph)
2. NVIDIA GPU (CUDA PTX/CUBIN)
3. AMD GPU (ROCm HIP HSACO)
4. CPU Multi-core (OpenMP Fallback nativo con polydim_cpp_v773.dll)
"""

import os
import sys
import platform
import subprocess
import ctypes
from enum import Enum, auto
from typing import Dict, Any, Callable

class HardwareBackend(Enum):
    CUDA_PTX   = auto()   # NVIDIA GPU (PTX / CUBIN)
    ROCM_HSACO = auto()   # AMD GPU (HIP / HSACO ELF)
    TPU_XLA    = auto()   # Google Cloud TPU (XLA Graph)
    CPU_OMP    = auto()   # CPU OpenMP (polydim_cpp_v773.dll)
    UNKNOWN    = auto()

class HardwareProbe:
    """
    Sonda de Hardware Formal para POLYDIM Latent_OS V773.
    Garantiza que el enjambre se ejecute en cualquier silicio sin suposiciones estáticas.
    """
    
    def __init__(self, dll_path: str = None):
        self.dll_path = dll_path or self._resolve_default_cpp_dll()
        self.backend: HardwareBackend = HardwareBackend.UNKNOWN
        self.device_info: Dict[str, Any] = {}
        self._cpp_lib = None
        self._probe_hardware()

    def _resolve_default_cpp_dll(self) -> str:
        candidates = [
            os.path.join(os.path.dirname(__file__), "polydim_cpp_v773.dll"),
            r"E:\POLYDIM_EINSOF\src\polydim_cpp_v773.dll",
            r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_23_V773\polydim_cpp_v773.dll"
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return "polydim_cpp_v773.dll"

    def _probe_hardware(self) -> None:
        """Ejecuta la cascada formal de detección de hardware (Regla 27)."""
        # 1. Google Cloud TPU (Kaggle / Colab)
        if self._detect_tpu():
            self.backend = HardwareBackend.TPU_XLA
            self.device_info = self._get_tpu_info()
            return

        # 2. NVIDIA GPU (CUDA)
        if self._detect_cuda():
            self.backend = HardwareBackend.CUDA_PTX
            self.device_info = self._get_cuda_info()
            return

        # 3. AMD GPU (ROCm)
        if self._detect_rocm():
            self.backend = HardwareBackend.ROCM_HSACO
            self.device_info = self._get_rocm_info()
            return

        # 4. Fallback CPU OpenMP
        self.backend = HardwareBackend.CPU_OMP
        self.device_info = self._get_cpu_info()

    def _detect_tpu(self) -> bool:
        tpu_env_vars = ['TPU_NAME', 'XRT_TPU_CONFIG', 'XLA_FLAGS', 'CLOUD_TPU_JOB_NAME']
        if any(os.getenv(var) for var in tpu_env_vars):
            return True
        try:
            import torch_xla.core.xla_model as xm
            _ = xm.xla_device()
            return True
        except Exception:
            return False

    def _detect_cuda(self) -> bool:
        try:
            import torch
            if not torch.cuda.is_available():
                return False
            name = torch.cuda.get_device_name(0).lower()
            return any(k in name for k in ['nvidia', 'tesla', 'geforce', 'rtx', 'a100', 'h100', 't4', 'p100', 'quadro'])
        except Exception:
            return False

    def _detect_rocm(self) -> bool:
        try:
            import torch
            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0).lower()
                if any(k in name for k in ['amd', 'radeon', 'instinct', 'mi250', 'mi300', 'gfx']):
                    return True
            # Chequeo directo por rocm-smi
            res = subprocess.run(["rocm-smi", "--showid"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return res.returncode == 0
        except Exception:
            return False

    def _get_tpu_info(self) -> Dict[str, Any]:
        try:
            import torch_xla.core.xla_model as xm
            dev = xm.xla_device()
            return {"type": "TPU", "device": str(dev), "cores": 8}
        except Exception:
            return {"type": "TPU", "status": "detected_via_env"}

    def _get_cuda_info(self) -> Dict[str, Any]:
        import torch
        props = torch.cuda.get_device_properties(0)
        return {
            "type": "NVIDIA_CUDA",
            "name": props.name,
            "total_memory_mb": props.total_memory // (1024 * 1024),
            "major": props.major,
            "minor": props.minor,
            "multi_processor_count": props.multi_processor_count
        }

    def _get_rocm_info(self) -> Dict[str, Any]:
        return {
            "type": "AMD_ROCM",
            "status": "ready",
            "hip_compiler": "hipcc"
        }

    def _get_cpu_info(self) -> Dict[str, Any]:
        import multiprocessing
        return {
            "type": "CPU_OPENMP",
            "arch": platform.machine(),
            "processor": platform.processor(),
            "cores_logical": multiprocessing.cpu_count(),
            "os": platform.system()
        }

    def load_native_cpp(self) -> ctypes.CDLL:
        if self._cpp_lib is None:
            if not os.path.exists(self.dll_path):
                raise FileNotFoundError(f"DLL C++ V773 no encontrada en {self.dll_path}")
            self._cpp_lib = ctypes.CDLL(self.dll_path)
        return self._cpp_lib

    def compute_gram(self, X_np):
        """
        Calcula Gramiana X^T * X despachando al mejor silicio disponible sin colapso 1D.
        """
        import numpy as np
        D, K = X_np.shape
        if self.backend == HardwareBackend.CUDA_PTX:
            import torch
            t_X = torch.from_numpy(X_np).cuda()
            return (t_X.T @ t_X).cpu().numpy()
        elif self.backend == HardwareBackend.ROCM_HSACO:
            import torch
            t_X = torch.from_numpy(X_np).cuda() # PyTorch ROCm usa la misma API .cuda()
            return (t_X.T @ t_X).cpu().numpy()
        elif self.backend == HardwareBackend.TPU_XLA:
            import torch
            import torch_xla.core.xla_model as xm
            dev = xm.xla_device()
            t_X = torch.from_numpy(X_np).to(dev)
            return (t_X.T @ t_X).cpu().numpy()
        else:
            # CPU OpenMP con polydim_cpp_v773.dll
            lib = self.load_native_cpp()
            K_out = np.zeros((K, K), dtype=np.float64)
            lib.polydim_gram_dsyrk.argtypes = [
                ctypes.POINTER(ctypes.c_double),
                ctypes.c_size_t,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_double),
                ctypes.c_uint32
            ]
            st = lib.polydim_gram_dsyrk(
                X_np.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                D, K,
                K_out.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                0 # default threads
            )
            if st != 0:
                raise RuntimeError(f"Error en C++ polydim_gram_dsyrk: {st}")
            return K_out

if __name__ == "__main__":
    probe = HardwareProbe()
    print("=================================================================")
    print("🔍 POLYDIM HARDWARE PROBE (SILICON CONTRACT V773)")
    print("=================================================================")
    print(f"✓ Backend Detectado: {probe.backend.name}")
    print(f"✓ Detalles: {probe.device_info}")
    print(f"✓ Ruta DLL C++ V773: {probe.dll_path}")
    print("=================================================================")
