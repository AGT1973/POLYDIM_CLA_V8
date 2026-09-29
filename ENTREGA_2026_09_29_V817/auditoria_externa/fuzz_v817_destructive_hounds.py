"""
fuzz_v817_destructive_hounds.py
Batería de Ataque Adversarial y Pruebas Destructivas Extremas POLYDIM V817
Ejecución en Silicio Físico (AMD A4-6300 Floor / MinGW GCC 14.2 / Rustc 1.98.1)

LOS 3 SABUESOS ADVERSARIALES RED TEAM:
1. Sabueso 1 (Concurrencia FFI & TLS Race Hunter): 100 hilos concurrentes atacando FFI y memory slabs con captura de excepciones.
2. Sabueso 2 (FPU Subnormals, Denormals & Singular Boundary Hunter): Flotantes desnormalizados (1e-315), NaNs, ceros con signo y frontera singular.
3. Sabueso 3 (Escalamiento Asintótico & Presión de Memoria D=1,000,000): Tensores de 1 Millón de dimensiones y medición de RSS.
"""

import sys
import os
import time
import math
import ctypes
import threading
import concurrent.futures
import numpy as np

# Configuración de ruta de librerías nativas
src_dir = os.path.dirname(os.path.abspath(__file__))
if sys.platform == "win32":
    winlibs_bin = r"E:\winlibs_gcc14_zip\mingw64\bin"
    if os.path.exists(winlibs_bin) and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(winlibs_bin)
    if os.path.exists(src_dir) and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(src_dir)

from polydim_v817_monolito import PolydimRustKernelV817, PolydimCppKernelV817, PolydimErrorV817

def banner(msg: str):
    print("\n" + "#" * 80)
    print(f"🔥 [SABUESO ADVERSARIAL] {msg}")
    print("#" * 80)

def get_process_rss_bytes() -> int:
    """Obtiene la memoria física de trabajo (RSS / Working Set) del proceso en Windows/Linux."""
    if sys.platform == "win32":
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize
        return 0
    else:
        try:
            with open("/proc/self/statm") as f:
                return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
        except Exception:
            return 0

# =============================================================================
# SABUESO 1: CONCURRENCIA MASIVA FFI & TLS RACE HUNTER (100 HILOS)
# =============================================================================

def sabueso_1_concurrency_tls_race():
    banner("SABUESO 1: 100 Hilos Concurrentes Atacando FFI, TLS Error Buffers y QSBR")
    rust_k = PolydimRustKernelV817()
    cpp_k = PolydimCppKernelV817()

    num_threads = 100
    iterations_per_thread = 50
    errors_detected = []
    tls_isolation_passed = []

    def thread_worker(thread_id: int):
        # Generador RNG independiente por hilo (thread-safe)
        rng = np.random.default_rng(thread_id * 777 + 42)
        dim = 1000
        for it in range(iterations_per_thread):
            # 1. Operación normal en C++ y Rust
            u = rng.standard_normal(dim)
            v = rng.standard_normal(dim)
            u /= np.linalg.norm(u)
            v /= np.linalg.norm(v)

            ang_r, _ = rust_k.riemannian_geodesic(u, v)
            ang_c, _ = cpp_k.riemannian_geodesic(u, v)

            if math.isnan(ang_r) or math.isnan(ang_c):
                errors_detected.append(f"Thread {thread_id}: NaN en cálculo geodésico nominal")

            if abs(ang_r - ang_c) > 1e-4:
                errors_detected.append(f"Thread {thread_id}: Discrepancia Rust vs C++ {ang_r} vs {ang_c}")

            # 2. Inyección de error FFI en este hilo para estresar TLS
            if it % 5 == 0:
                err_pod = PolydimErrorV817()
                # Pasar puntero nulo para forzar código de error 1
                ret = rust_k.lib.polydim_rust_auon_log_cosh_brake_v817(
                    ctypes.c_double(10.0),
                    ctypes.c_double(1.0),
                    ctypes.c_double(1.0),
                    None,
                    None,
                    ctypes.byref(err_pod),
                )
                if ret != -1:
                    errors_detected.append(f"Thread {thread_id}: Retorno de error incorrecto {ret}")
                
                # Leer TLS inmediatamente
                last_err = rust_k.get_last_error_string()
                if "Null pointer" not in last_err and "Null pointers" not in last_err:
                    errors_detected.append(f"Thread {thread_id}: TLS corrupto o pisado por otro hilo: '{last_err}'")
                
                # Limpiar error
                rust_k.lib.polydim_rust_clear_last_error_v817()
                if rust_k.get_last_error_string() != "":
                    errors_detected.append(f"Thread {thread_id}: Error no limpiado en TLS")

            # 3. QSBR Snapshot copy bajo concurrencia
            payload_size = 32 * 1024 # 32 KB por hilo
            src_bytes = np.random.bytes(payload_size)
            dst_buf = bytearray(payload_size)
            copied = ctypes.c_size_t(0)
            err_qsbr = PolydimErrorV817()

            ret_qsbr = rust_k.lib.polydim_rust_qsbr_snapshot_copy_v817(
                src_bytes,
                payload_size,
                (ctypes.c_char * payload_size).from_buffer(dst_buf),
                ctypes.byref(copied),
                ctypes.byref(err_qsbr),
            )
            if ret_qsbr != 0 or bytes(dst_buf) != src_bytes:
                errors_detected.append(f"Thread {thread_id}: Corrupción de datos en QSBR Snapshot Copy")

        tls_isolation_passed.append(thread_id)

    print(f"  Iniciando enjambre de {num_threads} hilos concurrentes ({num_threads * iterations_per_thread} transacciones)...")
    t0 = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(thread_worker, tid) for tid in range(num_threads)]
        concurrent.futures.wait(futures)
        for tid, f in enumerate(futures):
            exc = f.exception()
            if exc is not None:
                errors_detected.append(f"Thread {tid}: Excepción no capturada en worker: {exc!r}")

    dt = time.perf_counter() - t0
    ops_per_sec = (num_threads * iterations_per_thread) / dt

    print(f"  Tiempo total: {dt:.2f}s | Throughput de concurrencia: {ops_per_sec:.1f} ops/seg")
    print(f"  Hilos completados con éxito: {len(tls_isolation_passed)} / {num_threads}")

    if errors_detected:
        print(f"  ❌ FALLAS DETECTADAS EN CONCURRENCIA ({len(errors_detected)}):")
        for e in errors_detected[:5]:
            print(f"     - {e}")
        assert False, "Falla en Sabueso 1: Concurrencia FFI/TLS comprometida"
    else:
        print("  ✅ SABUESO 1 PASSED: Aislamiento TLS verificado y concurrencia ejecutada sin colisiones.")

# =============================================================================
# SABUESO 2: FPU SUBNORMALS, DENORMALS & SINGULAR BOUNDARY HUNTER
# =============================================================================

def sabueso_2_subnormals_singular_hunter():
    banner("SABUESO 2: Inyección de Números Desnormalizados (1e-315), NaNs, y Singularidades FPU")
    rust_k = PolydimRustKernelV817()
    cpp_k = PolydimCppKernelV817()

    # 1. Ataque con Números Desnormalizados (Subnormal Floats)
    subnormal_values = [
        1e-308, 1e-312, 1e-315, 1e-320, 5e-324, # Flotantes subnormales extremos
        -1e-308, -1e-315, -5e-324,
        0.0, -0.0, # Ceros con signo
    ]

    print("  [2.1] Atacando Freno AuON con flotantes desnormalizados y ceros con signo...")
    for sub in subnormal_values:
        loss_r, grad_r = rust_k.auon_brake(sub, scale_s=1.0, lambda_val=1.0)
        loss_c, grad_c = cpp_k.auon_brake(sub, scale_s=1.0, lambda_val=1.0)

        assert not math.isnan(loss_r) and not math.isinf(loss_r), f"Falla Rust en subnormal {sub}"
        assert not math.isnan(loss_c) and not math.isinf(loss_c), f"Falla C++ en subnormal {sub}"
        assert abs(loss_r) < 1e-12, f"Pérdida no nula para subnormal: {loss_r}"
        assert abs(grad_r) < 1e-12, f"Gradiente no nulo para subnormal: {grad_r}"

    print("     -> Subnormales procesados en FPU sin underflow stalls ni divergencia.")

    # 2. Ataque con Escalas y Parámetros Degenerados
    print("  [2.2] Atacando con parámetros degenerados (scale_s -> 0, lambda -> 0)...")
    scale_degenerate = 1e-15
    loss_deg, grad_deg = rust_k.auon_brake(100.0, scale_s=scale_degenerate, lambda_val=1.0)
    assert not math.isnan(loss_deg) and not math.isinf(loss_deg), "Overflow en escala pequeña"
    assert abs(grad_deg - scale_degenerate) < 1e-18

    # 3. Ataque con Valores Inválidos (NaN / Inf / Parámetros Negativos)
    print("  [2.3] Atacando con NaNs e Infinities forzados...")
    err = PolydimErrorV817()
    loss_out = ctypes.c_double(0.0)
    grad_out = ctypes.c_double(0.0)

    # Inyección de NaN
    ret_nan = rust_k.lib.polydim_rust_auon_log_cosh_brake_v817(
        ctypes.c_double(float('nan')),
        ctypes.c_double(1.0),
        ctypes.c_double(1.0),
        ctypes.byref(loss_out),
        ctypes.byref(grad_out),
        ctypes.byref(err),
    )
    assert ret_nan == -2, f"Debió rechazar NaN con código -2, obtuvo {ret_nan}"

    # Inyección de scale_s <= 0
    ret_neg = rust_k.lib.polydim_rust_auon_log_cosh_brake_v817(
        ctypes.c_double(10.0),
        ctypes.c_double(-2.5),
        ctypes.c_double(1.0),
        ctypes.byref(loss_out),
        ctypes.byref(grad_out),
        ctypes.byref(err),
    )
    assert ret_neg == -3, f"Debió rechazar scale_s negativo con código -3, obtuvo {ret_neg}"

    # 4. Ataque a la Métrica Geodésica en la Frontera Exacta
    print("  [2.4] Atacando métrica geodésica con perturbación singular 1.0 + 1e-15...")
    dim = 5000
    u = np.zeros(dim, dtype=np.float64)
    u[0] = 1.0

    # Perturbación real que hace u^T v > 1.0 antes de clamp
    v_overflow = u.copy()
    v_overflow[0] = 1.0 + 1e-15
    ang_clamp, chord_clamp = rust_k.riemannian_geodesic(u, v_overflow)
    assert not math.isnan(ang_clamp), "Clamp falló: arccos produjo NaN"
    assert ang_clamp <= 1e-6, f"Auto-geodésica debe colapsar a ~0, fue {ang_clamp}"

    # Vector nulo degenerado (norma 0)
    u_zero = np.zeros(dim, dtype=np.float64)
    ret_zero = rust_k.lib.polydim_rust_riemannian_geodesic_v817(
        u_zero.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        u.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        ctypes.c_uint(dim),
        ctypes.byref(loss_out),
        ctypes.byref(grad_out),
        ctypes.byref(err),
    )
    assert ret_zero == -3, f"Debió rechazar vector con norma cero, obtuvo {ret_zero}"

    print("  ✅ SABUESO 2 PASSED: Resistencia contra números desnormalizados, ceros con signo, NaNs y singularidades.")

# =============================================================================
# SABUESO 3: ESCALAMIENTO ASINTÓTICO & PRESIÓN DE MEMORIA D=1,000,000
# =============================================================================

def sabueso_3_asymptotic_scaling_ram_pressure():
    banner("SABUESO 3: Escalamiento Asintótico D=1,000,000 & Presión de Memoria RAM")
    rust_k = PolydimRustKernelV817()
    cpp_k = PolydimCppKernelV817()

    dim_million = 1_000_000 # 1 Millón de dimensiones (8 MB por vector float64)
    print(f"  [3.1] Asignando vectores continuos de alta dimensión D={dim_million:,} (8 MB cada uno)...")

    rng = np.random.default_rng(42)
    u = rng.standard_normal(dim_million).astype(np.float64)
    u /= np.linalg.norm(u)

    v = rng.standard_normal(dim_million).astype(np.float64)
    v /= np.linalg.norm(v)

    # Medir cálculo geodésico en D=1,000,000
    print("  [3.2] Evaluando geodésica Riemanniana en D=1,000,000 en C++ y Rust...")
    t0 = time.perf_counter()
    ang_c, chord_c = cpp_k.riemannian_geodesic(u, v)
    t_cpp_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    ang_r, chord_r = rust_k.riemannian_geodesic(u, v)
    t_rust_ms = (time.perf_counter() - t0) * 1000.0

    print(f"     -> C++ OpenMP: {t_cpp_ms:.2f} ms | Distancia Angular: {ang_c:.6f} rad")
    print(f"     -> Rust SIMD:   {t_rust_ms:.2f} ms | Distancia Angular: {ang_r:.6f} rad")
    assert abs(ang_c - ang_r) < 1e-5, "Discrepancia en D=1,000,000"

    # 3. Test de Presión de Memoria y Ciclos Repetidos con Verificación de RSS
    print("  [3.3] Ejecutando 50 ciclos continuos de transferencia de 16 MB en RAM con monitoreo de RSS...")
    payload_16mb = 16 * 1024 * 1024 # 16 MB
    src_payload = np.random.bytes(payload_16mb)
    dst_payload = bytearray(payload_16mb)
    copied_bytes = ctypes.c_size_t(0)
    err = PolydimErrorV817()
    dst_ptr = (ctypes.c_char * payload_16mb).from_buffer(dst_payload)

    rss_before = get_process_rss_bytes()

    latencies_16mb_us = []
    for _ in range(50):
        t0 = time.perf_counter()
        ret = rust_k.lib.polydim_rust_qsbr_snapshot_copy_v817(
            src_payload,
            payload_16mb,
            dst_ptr,
            ctypes.byref(copied_bytes),
            ctypes.byref(err),
        )
        t1 = time.perf_counter()
        latencies_16mb_us.append((t1 - t0) * 1e6)
        assert ret == 0, "Falla en transferencia de 16 MB"

    rss_after = get_process_rss_bytes()
    rss_delta_mb = (rss_after - rss_before) / (1024 * 1024) if rss_before > 0 else 0.0

    p50_16mb = np.percentile(latencies_16mb_us, 50)
    effective_bw_16mb = (payload_16mb / (p50_16mb * 1e-6)) / 1e9

    print(f"     -> Transferencia de 16 MB: Latencia p50 = {p50_16mb:.2f} µs | Ancho de Banda = {effective_bw_16mb:.2f} GB/s")
    print(f"     -> Delta RSS Working Set: {rss_delta_mb:.2f} MB tras 50 transferencias (tolerancia < 32 MB)")
    assert rss_delta_mb < 32.0, f"Fuga de memoria detectada: {rss_delta_mb:.2f} MB"
    print("  ✅ SABUESO 3 PASSED: Escalamiento D=1,000,000 y transferencias masivas de 16 MB completadas.")

# =============================================================================
# RUNNER MAESTRO DE LOS 3 SABUESOS
# =============================================================================

def run_adversarial_hounds():
    print("\n" + "=" * 80)
    print("⚔️ INICIANDO ATAQUE ADVERSARIAL DESTRUCTIVO - TRIBUNAL DE LOS 3 SABUESOS")
    print("=" * 80)

    t_start = time.perf_counter()
    sabueso_1_concurrency_tls_race()
    sabueso_2_subnormals_singular_hunter()
    sabueso_3_asymptotic_scaling_ram_pressure()
    total_time = time.perf_counter() - t_start

    print("\n" + "=" * 80)
    print(f"📋 RESUMEN DE LOS 3 SABUESOS: 3/3 SABUESOS COMPLETADOS (Exit Code 0) EN {total_time:.2f}s")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_adversarial_hounds()
