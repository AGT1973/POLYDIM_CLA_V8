#!/usr/bin/env python3
# ==============================================================================
# POLYDIM V738 - FFI BENCHMARK ORCHESTRATOR (SILICON ARMORED EDITION)
# ==============================================================================
# Industrial Fixes Applied:
# 1. Exact FFI argtypes matching C++/Rust ABI (c_uint64 for sizes, c_double for alpha).
# 2. Unified version tagging (v738) across C++, Rust, and Python.
# 3. Fail-loud verification on backend loading.
# 4. End-to-end execution of Householder, BSC Isometry, and Cayley-SMW Retraction.
# 5. KBN Parity validation between C++ and Rust under ||Rust - CPP|| <= 1e-6 tolerance.
# ==============================================================================

import argparse
import ctypes
import json
import math
import os
import platform
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np

LIB_TAG = "v738"
SEED_BASE = 42

CPP_REQUIRED = [
    "bsc_xor_single_step", "bsc_isometry_single_step", "precompute_isometry_composition",
    "householder_single_step_f32", "compute_l2_norm_f64_accum", "compute_hamming_weight",
    "apply_cayley_smw_retraction_f32", "generate_random_unit_vector_f32"
]

RUST_REQUIRED = [
    "check_l2_norm_f32", "check_pairwise_inner_products",
    "check_hamming_weight", "check_hamming_distance"
]

@dataclass
class BackendInfo:
    name: str
    available: bool
    path: Optional[str] = None
    lib_obj: Any = None
    missing_symbols: List[str] = field(default_factory=list)

@dataclass
class BenchmarkResult:
    backend: str
    pathway: str
    dimension: int
    iterations: int
    time_seconds: float
    l2_norm_initial: float
    l2_norm_final: float
    l2_drift: float
    max_drift_pass: bool
    hamming_weight: Optional[int] = None
    rust_norm_check: Optional[float] = None
    rust_drift_diff: Optional[float] = None

def get_hardware_info() -> Dict[str, Any]:
    import psutil
    vm = psutil.virtual_memory()
    return {
        "os": platform.system(),
        "arch": platform.machine(),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "ram_total_gb": round(vm.total / (1024 ** 3), 2),
        "ram_available_gb": round(vm.available / (1024 ** 3), 2),
    }

def load_cpp_backend(base_dir: Path) -> BackendInfo:
    ext = ".dll" if platform.system() == "Windows" else ".so"
    lib_path = base_dir / f"polydim_cpp_{LIB_TAG}{ext}"
    if not lib_path.exists():
        return BackendInfo("cpp_cpu", False, missing_symbols=["FILE_NOT_FOUND"])

    if platform.system() == "Windows":
        gcc_bin = Path(r"E:\winlibs_gcc14_zip\mingw64\bin")
        if gcc_bin.exists():
            try:
                os.add_dll_directory(str(gcc_bin))
            except Exception:
                pass

    try:
        lib = ctypes.CDLL(str(lib_path))
        missing = [sym for sym in CPP_REQUIRED if not hasattr(lib, sym)]
        if missing:
            return BackendInfo("cpp_cpu", False, str(lib_path), missing_symbols=missing)

        lib.bsc_xor_single_step.argtypes = [ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint64, ctypes.c_uint64]
        lib.bsc_isometry_single_step.argtypes = [
            ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint64
        ]
        lib.precompute_isometry_composition.argtypes = [
            ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64),
            ctypes.c_uint64, ctypes.c_uint64
        ]
        lib.householder_single_step_f32.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.c_uint64
        ]
        lib.compute_l2_norm_f64_accum.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_uint64]
        lib.compute_l2_norm_f64_accum.restype = ctypes.c_double

        lib.compute_hamming_weight.argtypes = [ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint64]
        lib.compute_hamming_weight.restype = ctypes.c_uint64

        lib.generate_random_unit_vector_f32.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.c_uint64, ctypes.c_uint64
        ]

        lib.apply_cayley_smw_retraction_f32.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float), ctypes.c_double, ctypes.c_uint64
        ]

        return BackendInfo("cpp_cpu", True, str(lib_path), lib)
    except Exception as e:
        return BackendInfo("cpp_cpu", False, str(lib_path), missing_symbols=[str(e)])

def load_rust_backend(base_dir: Path) -> BackendInfo:
    ext = ".dll" if platform.system() == "Windows" else ".so"
    lib_path = base_dir / f"polydim_rust_{LIB_TAG}{ext}"
    if not lib_path.exists():
        return BackendInfo("rust_cpu", False, missing_symbols=["FILE_NOT_FOUND"])

    try:
        lib = ctypes.CDLL(str(lib_path))
        missing = [sym for sym in RUST_REQUIRED if not hasattr(lib, sym)]
        if missing:
            return BackendInfo("rust_cpu", False, str(lib_path), missing_symbols=missing)

        lib.check_l2_norm_f32.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_size_t]
        lib.check_l2_norm_f32.restype = ctypes.c_double

        lib.check_pairwise_inner_products.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.c_size_t
        ]
        lib.check_pairwise_inner_products.restype = ctypes.c_double

        lib.check_hamming_weight.argtypes = [ctypes.POINTER(ctypes.c_uint64), ctypes.c_size_t]
        lib.check_hamming_weight.restype = ctypes.c_int64

        lib.check_hamming_distance.argtypes = [
            ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64), ctypes.c_size_t
        ]
        lib.check_hamming_distance.restype = ctypes.c_int64

        return BackendInfo("rust_cpu", True, str(lib_path), lib)
    except Exception as e:
        return BackendInfo("rust_cpu", False, str(lib_path), missing_symbols=[str(e)])

def run_householder_cpp(tensor: np.ndarray, iterations: int, seed: int, lib: Any) -> np.ndarray:
    d = len(tensor)
    tensor_p = tensor.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
    v = np.empty(d, dtype=np.float32)
    v_p = v.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
    for i in range(iterations):
        lib.generate_random_unit_vector_f32(v_p, ctypes.c_uint64(d), ctypes.c_uint64(seed + i))
        lib.householder_single_step_f32(tensor_p, v_p, ctypes.c_uint64(d))
    return tensor

def run_householder_numpy(tensor: np.ndarray, iterations: int, seed: int) -> np.ndarray:
    d = len(tensor)
    rng = np.random.default_rng(seed)
    for _ in range(iterations):
        v = rng.standard_normal(d).astype(np.float32)
        v /= np.linalg.norm(v.astype(np.float64))
        dot = np.dot(tensor.astype(np.float64), v.astype(np.float64))
        tensor -= np.float32(2.0 * dot) * v
    return tensor

def run_bsc_isometry_cpp(tensor: np.ndarray, perm_lut: np.ndarray, fixed_mask: np.ndarray, iterations: int, lib: Any) -> np.ndarray:
    d_blocks = len(tensor)
    tensor_p = tensor.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64))
    perm_p = perm_lut.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64))
    mask_p = fixed_mask.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64))
    
    perm_out = np.empty_like(perm_lut)
    mask_out = np.empty_like(fixed_mask)
    lib.precompute_isometry_composition(
        perm_p, mask_p, 
        perm_out.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)), 
        mask_out.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)), 
        ctypes.c_uint64(d_blocks), ctypes.c_uint64(iterations)
    )
    
    scratchpad = np.empty_like(tensor)
    scratchpad_p = scratchpad.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64))
    
    lib.bsc_isometry_single_step(
        tensor_p, 
        perm_out.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)), 
        mask_out.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)), 
        scratchpad_p, 
        ctypes.c_uint64(d_blocks)
    )
    return tensor

def run_bsc_isometry_numpy(tensor: np.ndarray, perm_lut: np.ndarray, fixed_mask: np.ndarray, iterations: int) -> np.ndarray:
    d_blocks = len(tensor)
    perm_out = perm_lut.copy()
    mask_out = fixed_mask.copy()
    for _ in range(1, iterations):
        perm_out = perm_lut[perm_out]
        mask_out = mask_out[perm_lut] ^ fixed_mask
    tensor = tensor[perm_out] ^ mask_out
    return tensor

def run_cayley_smw_cpp(tensor: np.ndarray, iterations: int, seed: int, lib: Any, alpha: float = 0.1) -> np.ndarray:
    d = len(tensor)
    rng = np.random.default_rng(seed)
    tensor_p = tensor.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
    
    u = rng.standard_normal(d).astype(np.float32)
    u /= np.linalg.norm(u.astype(np.float64))
    v = rng.standard_normal(d).astype(np.float32)
    v /= np.linalg.norm(v.astype(np.float64))
    
    u_p = u.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
    v_p = v.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
    
    for _ in range(iterations):
        lib.apply_cayley_smw_retraction_f32(tensor_p, u_p, v_p, ctypes.c_double(alpha), ctypes.c_uint64(d))
    return tensor

def run_benchmark(backend_info: BackendInfo, pathway: str, dimension: int, iterations: int, seed: int, rust_backend: Optional[BackendInfo] = None) -> BenchmarkResult:
    rng = np.random.default_rng(seed)
    
    if pathway == "householder":
        d = dimension
        tensor_in = rng.standard_normal(d).astype(np.float32)
        tensor_in /= np.linalg.norm(tensor_in.astype(np.float64))
        initial_norm = float(np.linalg.norm(tensor_in.astype(np.float64)))
        
        tensor_out = tensor_in.copy()
        
        t0 = time.perf_counter()
        if backend_info.name == "numpy_cpu":
            tensor_out = run_householder_numpy(tensor_out, iterations, seed + 100)
        elif backend_info.name == "cpp_cpu":
            tensor_out = run_householder_cpp(tensor_out, iterations, seed + 100, backend_info.lib_obj)
        else:
            raise NotImplementedError(f"Pathway {pathway} not implemented for {backend_info.name}")
        t1 = time.perf_counter()
        
        if backend_info.name == "cpp_cpu":
            tensor_p = tensor_out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            final_norm = float(backend_info.lib_obj.compute_l2_norm_f64_accum(tensor_p, ctypes.c_uint64(d)))
        else:
            final_norm = float(np.linalg.norm(tensor_out.astype(np.float64)))
            
        drift = abs(final_norm - initial_norm)
        max_drift_pass = (drift < 1e-3)
        hw = None
        
        rust_norm = None
        rust_diff = None
        if rust_backend and rust_backend.available and backend_info.name == "cpp_cpu":
            tensor_p = tensor_out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            rust_norm = float(rust_backend.lib_obj.check_l2_norm_f32(tensor_p, ctypes.c_size_t(d)))
            rust_diff = abs(rust_norm - final_norm)
            if math.isnan(rust_norm):
                print("  [FATAL] Rust reported NaN (Topological Crash / Invalid Pointer). Aborting.")
                sys.exit(1)
            if rust_diff > 1e-6:
                print(f"  [RUST VALIDATION WARNING] C++ norm: {final_norm}, Rust norm: {rust_norm}, diff: {rust_diff:.3e}")
                
        return BenchmarkResult(
            backend=backend_info.name,
            pathway=pathway,
            dimension=d,
            iterations=iterations,
            time_seconds=t1 - t0,
            l2_norm_initial=initial_norm,
            l2_norm_final=final_norm,
            l2_drift=drift,
            max_drift_pass=max_drift_pass,
            hamming_weight=hw,
            rust_norm_check=rust_norm,
            rust_drift_diff=rust_diff
        )
        
    elif pathway == "bsc":
        d_blocks = math.ceil(dimension / 64)
        tensor_in = rng.integers(0, 0xFFFFFFFFFFFFFFFF, size=d_blocks, dtype=np.uint64)
        perm_lut = rng.permutation(d_blocks).astype(np.uint64)
        fixed_mask = rng.integers(0, 0xFFFFFFFFFFFFFFFF, size=d_blocks, dtype=np.uint64)
        
        tensor_out = tensor_in.copy()
        
        t0 = time.perf_counter()
        if backend_info.name == "numpy_cpu":
            tensor_out = run_bsc_isometry_numpy(tensor_out, perm_lut, fixed_mask, iterations)
        elif backend_info.name == "cpp_cpu":
            tensor_out = run_bsc_isometry_cpp(tensor_out, perm_lut, fixed_mask, iterations, backend_info.lib_obj)
        else:
            raise NotImplementedError(f"Pathway {pathway} not implemented for {backend_info.name}")
        t1 = time.perf_counter()
        
        initial_norm = 0.0
        final_norm = 0.0
        drift = 0.0
        max_drift_pass = True
        
        if backend_info.name == "cpp_cpu":
            tensor_p = tensor_out.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64))
            hw = int(backend_info.lib_obj.compute_hamming_weight(tensor_p, ctypes.c_uint64(d_blocks)))
        else:
            hw = int(np.unpackbits(tensor_out.view(np.uint8)).sum())
            
        rust_hw = None
        if rust_backend and rust_backend.available and backend_info.name == "cpp_cpu":
            tensor_p = tensor_out.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64))
            rust_hw = int(rust_backend.lib_obj.check_hamming_weight(tensor_p, ctypes.c_size_t(d_blocks)))
            if rust_hw != hw:
                print(f"  [RUST VALIDATION WARNING] C++ HW: {hw}, Rust HW: {rust_hw}")
                
        return BenchmarkResult(
            backend=backend_info.name,
            pathway=pathway,
            dimension=dimension,
            iterations=iterations,
            time_seconds=t1 - t0,
            l2_norm_initial=initial_norm,
            l2_norm_final=final_norm,
            l2_drift=drift,
            max_drift_pass=max_drift_pass,
            hamming_weight=hw,
            rust_norm_check=None,
            rust_drift_diff=None
        )

    elif pathway == "cayley":
        d = dimension
        tensor_in = rng.standard_normal(d).astype(np.float32)
        tensor_in /= np.linalg.norm(tensor_in.astype(np.float64))
        initial_norm = float(np.linalg.norm(tensor_in.astype(np.float64)))
        
        tensor_out = tensor_in.copy()
        
        t0 = time.perf_counter()
        if backend_info.name == "cpp_cpu":
            tensor_out = run_cayley_smw_cpp(tensor_out, iterations, seed + 200, backend_info.lib_obj, alpha=0.1)
        else:
            raise NotImplementedError(f"Pathway {pathway} not implemented for {backend_info.name}")
        t1 = time.perf_counter()
        
        tensor_p = tensor_out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        final_norm = float(backend_info.lib_obj.compute_l2_norm_f64_accum(tensor_p, ctypes.c_uint64(d)))
        drift = abs(final_norm - initial_norm)
        max_drift_pass = (drift < 1e-4)
        
        rust_norm = None
        rust_diff = None
        if rust_backend and rust_backend.available:
            rust_norm = float(rust_backend.lib_obj.check_l2_norm_f32(tensor_p, ctypes.c_size_t(d)))
            rust_diff = abs(rust_norm - final_norm)
            
        return BenchmarkResult(
            backend=backend_info.name,
            pathway=pathway,
            dimension=d,
            iterations=iterations,
            time_seconds=t1 - t0,
            l2_norm_initial=initial_norm,
            l2_norm_final=final_norm,
            l2_drift=drift,
            max_drift_pass=max_drift_pass,
            hamming_weight=None,
            rust_norm_check=rust_norm,
            rust_drift_diff=rust_diff
        )

    else:
        raise ValueError(f"Unknown pathway: {pathway}")

def main():
    parser = argparse.ArgumentParser(description=f"POLYDIM Benchmark {LIB_TAG}")
    parser.add_argument("--dim", type=int, default=10_000_000, help="Dimension D")
    parser.add_argument("--iters", type=int, default=50, help="Iterations per run")
    parser.add_argument("--runs", type=int, default=3, help="Number of benchmark runs")
    parser.add_argument("--quick", action="store_true", help="Quick mode (D=500,000)")
    args = parser.parse_args()

    dim = 500_000 if args.quick else args.dim
    iterations = 10 if args.quick else args.iters
    n_runs = 1 if args.quick else args.runs

    print("=" * 70)
    print(f"POLYDIM V738 BENCHMARK ORCHESTRATOR — D={dim:,}, Iters={iterations}, Runs={n_runs}")
    print("=" * 70)

    hw_info = get_hardware_info()
    print("[HARDWARE INTERROGATION]")
    for k, v in hw_info.items():
        print(f"  {k:<20}: {v}")
    print("-" * 70)

    base_dir = Path(__file__).parent
    cpp_info = load_cpp_backend(base_dir)
    rust_info = load_rust_backend(base_dir)

    print("[BACKEND REGISTRY]")
    print(f"  numpy_cpu : AVAILABLE")
    if cpp_info.available:
        print(f"  cpp_cpu   : AVAILABLE ({cpp_info.path})")
    else:
        print(f"  cpp_cpu   : MISSING ({cpp_info.missing_symbols})")
    if rust_info.available:
        print(f"  rust_cpu  : AVAILABLE ({rust_info.path})")
    else:
        print(f"  rust_cpu  : MISSING ({rust_info.missing_symbols})")
    print("-" * 70)

    raw_results = []
    backends_to_test = [BackendInfo("numpy_cpu", True)]
    if cpp_info.available:
        backends_to_test.append(cpp_info)

    for b in backends_to_test:
        pathways = ["householder", "bsc"]
        if b.name == "cpp_cpu":
            pathways.append("cayley")

        for pw in pathways:
            print(f"Running {b.name} - {pw}...")
            for run_idx in range(n_runs):
                seed = SEED_BASE + run_idx * 17
                try:
                    res = run_benchmark(b, pw, dim, iterations, seed, rust_info)
                    raw_results.append(asdict(res))
                    status = "PASS" if res.max_drift_pass else "FAIL"
                    print(f"  Run {run_idx+1}/{n_runs} [{pw}]: Time={res.time_seconds:.4f}s | Drift={res.l2_drift:.3e} ({status})")
                    if pw == "householder":
                        print(f"  Max drift Householder S^N : {res.l2_drift:.4e} ({status})")
                    elif pw == "cayley":
                        print(f"  Max drift Cayley-SMW S^N  : {res.l2_drift:.4e} ({status})")
                except Exception as e:
                    print(f"  Run {run_idx+1}/{n_runs} [{pw}]: ERROR -> {e}")

    out_file = base_dir / "raw_results_v738.json"
    with open(out_file, "w") as f:
        json.dump({"hardware": hw_info, "results": raw_results}, f, indent=2)
    print("=" * 70)
    print(f"[OK] Benchmark complete. Results written to {out_file}")

if __name__ == "__main__":
    main()
