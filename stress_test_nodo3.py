"""
POLYDIM V735 - STRESS TEST NODO 3
D = 10_000_000, N_RUNS = 3
Verifica: C++ DLL, Rust DLL, Cayley-SMW, Householder, normas KBN
"""
import ctypes
import time
import os
import platform
import psutil
import numpy as np
from pathlib import Path

BASE = Path(r"E:\POLYDIM_EINSOF\ENTREGA_DOCENTES_ALUMNOS_V735")
D = 10_000_000
N_RUNS = 3
SEED = 42
LOG = []

def log(msg):
    print(msg, flush=True)
    LOG.append(msg)

def get_ram_gb():
    return psutil.virtual_memory().available / 1024**3

# ============================================================
# CARGAR DLLs
# ============================================================
log("=" * 60)
log("POLYDIM V735 - STRESS TEST NODO 3")
log(f"OS: {platform.system()} {platform.release()}")
log(f"CPU cores: {psutil.cpu_count(logical=True)} logical / {psutil.cpu_count(logical=False)} physical")
log(f"RAM total: {psutil.virtual_memory().total/1024**3:.1f} GB  |  disponible: {get_ram_gb():.1f} GB")
log(f"D = {D:,}  |  N_RUNS = {N_RUNS}")
log("=" * 60)

# C++ DLL
try:
    cpp = ctypes.CDLL(str(BASE / "polydim_cpp_v735.dll"))
    cpp.compute_l2_norm_f64_accum.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_uint64]
    cpp.compute_l2_norm_f64_accum.restype = ctypes.c_double
    cpp.householder_single_step_f32.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.c_uint64]
    cpp.householder_single_step_f32.restype = None
    cpp.apply_cayley_smw_retraction_f32.argtypes = [
        ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_float), ctypes.c_double, ctypes.c_uint64
    ]
    cpp.apply_cayley_smw_retraction_f32.restype = None
    log("[CPP DLL] CARGADO OK")
except Exception as e:
    log(f"[CPP DLL] FALLO: {e}")
    cpp = None

# Rust DLL
try:
    rust = ctypes.CDLL(str(BASE / "polydim_rust_v735.dll"))
    rust.check_l2_norm_f32.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_size_t]
    rust.check_l2_norm_f32.restype = ctypes.c_double
    rust.check_pairwise_inner_products.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.c_size_t]
    rust.check_pairwise_inner_products.restype = ctypes.c_double
    log("[RUST DLL] CARGADO OK")
except Exception as e:
    log(f"[RUST DLL] FALLO: {e}")
    rust = None

# ============================================================
# STRESS TEST PRINCIPAL
# ============================================================
rng = np.random.default_rng(SEED)
results = []

log(f"\n{'='*60}")
log(f"ALLOCANDO {D*4/1024**2:.0f} MB RAM para tensor principal...")
ram_antes = get_ram_gb()
tensor = rng.standard_normal(D, dtype=np.float64).astype(np.float32)
# Normalizar a S^(D-1)
norm0 = np.linalg.norm(tensor)
tensor /= norm0
log(f"RAM usada por tensor: {(ram_antes - get_ram_gb()):.2f} GB  |  RAM disponible: {get_ram_gb():.1f} GB")

ptr_t = tensor.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

for run in range(N_RUNS):
    log(f"\n--- RUN {run+1}/{N_RUNS} ---")
    rng2 = np.random.default_rng(SEED + run)

    # --- TEST 1: L2 NORM CPP vs RUST vs NUMPY ---
    if cpp:
        t0 = time.perf_counter()
        norm_cpp = cpp.compute_l2_norm_f64_accum(ptr_t, ctypes.c_uint64(D))
        dt_cpp = (time.perf_counter() - t0) * 1000
    else:
        norm_cpp, dt_cpp = float('nan'), float('nan')

    if rust:
        t0 = time.perf_counter()
        norm_rust = rust.check_l2_norm_f32(ptr_t, ctypes.c_size_t(D))
        dt_rust = (time.perf_counter() - t0) * 1000
    else:
        norm_rust, dt_rust = float('nan'), float('nan')

    norm_np = float(np.linalg.norm(tensor))
    delta_cpp  = abs(norm_cpp - norm_np)
    delta_rust = abs(norm_rust - norm_np)
    log(f"  L2_NORM | numpy={norm_np:.8f} | cpp={norm_cpp:.8f} (d={delta_cpp:.2e}, {dt_cpp:.1f}ms) | rust={norm_rust:.8f} (d={delta_rust:.2e}, {dt_rust:.1f}ms)")

    # --- TEST 2: HOUSEHOLDER STEP ---
    if cpp:
        v = rng2.standard_normal(D).astype(np.float32)
        v /= np.linalg.norm(v)
        tensor_bak = tensor.copy()
        ptr_v = v.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        t0 = time.perf_counter()
        cpp.householder_single_step_f32(ptr_t, ptr_v, ctypes.c_uint64(D))
        dt_hh = (time.perf_counter() - t0) * 1000

        norm_after_hh = cpp.compute_l2_norm_f64_accum(ptr_t, ctypes.c_uint64(D))
        drift_hh = abs(norm_after_hh - 1.0)
        log(f"  HOUSEHOLDER | norm_post={norm_after_hh:.8f}  drift_S^(D-1)={drift_hh:.2e}  time={dt_hh:.1f}ms")
        # Restaurar
        np.copyto(tensor, tensor_bak)
    
    # --- TEST 3: CAYLEY-SMW RETRACTION ---
    if cpp:
        U = rng2.standard_normal(D).astype(np.float32); U /= np.linalg.norm(U)
        V = rng2.standard_normal(D).astype(np.float32); V /= np.linalg.norm(V)
        ptr_u = U.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        ptr_v2 = V.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        alpha = 0.1
        tensor_bak = tensor.copy()

        t0 = time.perf_counter()
        cpp.apply_cayley_smw_retraction_f32(ptr_t, ptr_u, ptr_v2, ctypes.c_double(alpha), ctypes.c_uint64(D))
        dt_smw = (time.perf_counter() - t0) * 1000

        norm_smw = cpp.compute_l2_norm_f64_accum(ptr_t, ctypes.c_uint64(D))
        drift_smw = abs(norm_smw - 1.0)
        log(f"  CAYLEY-SMW  | norm_post={norm_smw:.8f}  drift_S^(D-1)={drift_smw:.2e}  time={dt_smw:.1f}ms")
        np.copyto(tensor, tensor_bak)

    results.append({
        'run': run+1, 'norm_cpp': norm_cpp, 'norm_rust': norm_rust,
        'delta_cpp': delta_cpp, 'delta_rust': delta_rust,
        'drift_hh': drift_hh if cpp else None,
        'drift_smw': drift_smw if cpp else None,
    })

# ============================================================
# RESUMEN FINAL
# ============================================================
log(f"\n{'='*60}")
log("RESUMEN NODO 3 - STRESS TEST D=10,000,000")
log(f"{'='*60}")
max_delta_cpp  = max(r['delta_cpp']  for r in results if r['delta_cpp']  is not None)
max_delta_rust = max(r['delta_rust'] for r in results if r['delta_rust'] is not None)
max_drift_hh   = max(r['drift_hh']  for r in results if r['drift_hh']   is not None)
max_drift_smw  = max(r['drift_smw'] for r in results if r['drift_smw']  is not None)
log(f"Max delta L2 CPP  vs numpy : {max_delta_cpp:.2e}  {'PASS' if max_delta_cpp < 1e-5 else 'FAIL'}")
log(f"Max delta L2 RUST vs numpy : {max_delta_rust:.2e}  {'PASS' if max_delta_rust < 1e-5 else 'FAIL'}")
log(f"Max drift Householder S^N  : {max_drift_hh:.2e}  {'PASS' if max_drift_hh < 1e-4 else 'FAIL'}")
log(f"Max drift Cayley-SMW  S^N  : {max_drift_smw:.2e}  {'PASS' if max_drift_smw < 1e-3 else 'FAIL'}")
log(f"RAM disponible final       : {get_ram_gb():.2f} GB")
log("=" * 60)

# Guardar log
log_path = BASE / "stress_test_nodo3.log"
with open(log_path, "w", encoding="utf-8") as f:
    f.write("\n".join(LOG))
print(f"\nLog guardado: {log_path}")
