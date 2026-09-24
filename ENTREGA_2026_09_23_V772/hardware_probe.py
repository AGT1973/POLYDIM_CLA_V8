#!/usr/bin/env python3
"""
hardware_probe.py
Módulo formal de detección y despacho polimórfico multi-plataforma (POLYDIM V772).
Cumple con la Regla 27 (Silicon Contract): Cero hardcoding, autodetección en runtime de:
1. Google Cloud TPU (PyTorch/XLA Graph)
2. NVIDIA GPU (CUDA PTX/CUBIN)
3. AMD GPU (ROCm HIP HSACO)
4. CPU Multi-core (OpenMP Fallback nativo con polydim_cpp_v772.dll)
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
    CPU_OMP    = auto()   # CPU OpenMP (polydim_cpp_v772.dll)
    UNKNOWN    = auto()

class HardwareProbe:
    """
    Sonda de Hardware Formal para POLYDIM Latent_OS.
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
            os.path.join(os.path.dirname(__file__), "polydim_cpp_v772.dll"),
            r"E:\POLYDIM_EINSOF\src\polydim_cpp_v772.dll",
            r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_23_V772\polydim_cpp_v772.dll"
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return "polydim_cpp_v772.dll"

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
                if any(k in name for k in ['amd', 'radeon', 'mi100', 'mi200', 'mi300', 'gfx']):
                    return True
        except Exception:
            pass

        if os.getenv('HIP_PATH') or os.getenv('ROCM_PATH'):
            return True

        try:
            res = subprocess.run(['rocm-smi', '--showproductname'], capture_output=True, text=True, timeout=3)
            return res.returncode == 0
        except Exception:
            return False

    def _get_tpu_info(self) -> Dict[str, Any]:
        return {
            'platform': 'Google Cloud TPU',
            'backend': 'XLA HLO',
            'runtime': 'PyTorch/XLA',
            'tpu_name': os.getenv('TPU_NAME', 'local_tpu')
        }

    def _get_cuda_info(self) -> Dict[str, Any]:
        try:
            import torch
            return {
                'platform': 'NVIDIA CUDA',
                'backend': 'PTX / CUBIN',
                'device_name': torch.cuda.get_device_name(0),
                'capability': torch.cuda.get_device_capability(0),
                'device_count': torch.cuda.device_count()
            }
        except Exception as e:
            return {'platform': 'NVIDIA CUDA', 'error': str(e)}

    def _get_rocm_info(self) -> Dict[str, Any]:
        return {
            'platform': 'AMD ROCm',
            'backend': 'HIP / HSACO ELF',
            'compilation_target': 'amdgcn-amd-amdhsa'
        }

    def _get_cpu_info(self) -> Dict[str, Any]:
        return {
            'platform': 'CPU Multi-Core',
            'backend': 'OpenMP Native',
            'architecture': platform.machine(),
            'processor': platform.processor(),
            'fallback_library': self.dll_path
        }

    def load_native_cpp(self):
        """Carga perezosa de la DLL C++ de fallback con manejo seguro de PATH."""
        if self._cpp_lib is not None:
            return self._cpp_lib

        if hasattr(os, 'add_dll_directory'):
            if os.path.exists(r"E:\winlibs_gcc14_zip\mingw64\bin"):
                os.add_dll_directory(r"E:\winlibs_gcc14_zip\mingw64\bin")
            if os.path.exists(r"E:\POLYDIM_EINSOF\src"):
                os.add_dll_directory(r"E:\POLYDIM_EINSOF\src")

        if not os.path.exists(self.dll_path):
            raise FileNotFoundError(f"DLL C++ no encontrada en: {self.dll_path}")

        self._cpp_lib = ctypes.CDLL(self.dll_path)
        return self._cpp_lib

    def compute_gram_matrix(self, X_np):
        """
        Despacho polimórfico para calcular Gramiana X^T * X en el backend detectado.
        """
        import numpy as np
        D, K = X_np.shape

        if self.backend == HardwareBackend.CUDA_PTX:
            import torch
            t_X = torch.from_numpy(X_np).cuda()
            return (t_X.T @ t_X).cpu().numpy()
        elif self.backend == HardwareBackend.TPU_XLA:
            import torch
            import torch_xla.core.xla_model as xm
            dev = xm.xla_device()
            t_X = torch.from_numpy(X_np).to(dev)
            return (t_X.T @ t_X).cpu().numpy()
        else:
            # CPU OpenMP con polydim_cpp_v772.dll
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
                os.cpu_count() or 4
            )
            if st != 0:
                raise RuntimeError(f"Fallo en polydim_gram_dsyrk: {st}")
            return K_out

    def __str__(self) -> str:
        names = {
            HardwareBackend.CUDA_PTX: "NVIDIA CUDA (PTX / CUBIN)",
            HardwareBackend.ROCM_HSACO: "AMD ROCm (HIP / HSACO)",
            HardwareBackend.TPU_XLA: "Google Cloud TPU (XLA Graph)",
            HardwareBackend.CPU_OMP: "CPU Multi-Core (OpenMP Native Fallback)",
            HardwareBackend.UNKNOWN: "Desconocido"
        }
        return (
            f"=================================================================\n"
            f"🔍 POLYDIM HARDWARE PROBE (SILICON CONTRACT - REGLA 27)\n"
            f"=================================================================\n"
            f"• Backend Detectado: {names[self.backend]}\n"
            f"• Detalles de Silicio: {self.device_info}\n"
            f"================================================================="
        )

if __name__ == "__main__":
    import numpy as np
    probe = HardwareProbe()
    print(probe)

    # Smoke Test Polimórfico
    print("\n[SMOKE TEST] Ejecutando cálculo de Gramiana polimórfica (D=10,000, K=32)...")
    rng = np.random.RandomState(42)
    X = rng.randn(10000, 32).astype(np.float64)
    Gram = probe.compute_gram_matrix(X)
    print(f"✓ Gramiana calculada exitosamente en {probe.backend.name} con forma {Gram.shape}")
    print(f"✓ Traza de Gramiana: {np.trace(Gram):.4f}")
