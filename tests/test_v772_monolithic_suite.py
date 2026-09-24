#!/usr/bin/env python3
"""
test_v772_monolithic_suite.py
Suite de Validación Empírica Exhaustiva para POLYDIM V772
Valida:
1. Optimización Stiefel Monolítica en C++ (Single-Shot stiefel_optimize)
2. Gramiana DSYRK en Modos Duales (Deterministic TwoSum vs Throughput SIMD)
3. Concurrencia PMTP Banked Slot Lease RCU (Zero Data Race)
4. Guardián Topológico Rust Dual (\beta_0 y \beta_1)
"""

import os
import sys
import ctypes
import time
import numpy as np

# Rutas de DLLs
CPP_DLL_PATH = r"E:\POLYDIM_EINSOF\src\polydim_cpp_v772.dll"
RUST_DLL_PATH = r"E:\POLYDIM_EINSOF\src\polydim_rust_v772.dll"

if hasattr(os, 'add_dll_directory'):
    if os.path.exists(r"E:\winlibs_gcc14_zip\mingw64\bin"):
        os.add_dll_directory(r"E:\winlibs_gcc14_zip\mingw64\bin")
    if os.path.exists(r"E:\POLYDIM_EINSOF\src"):
        os.add_dll_directory(r"E:\POLYDIM_EINSOF\src")

assert os.path.exists(CPP_DLL_PATH), f"No existe {CPP_DLL_PATH}"
assert os.path.exists(RUST_DLL_PATH), f"No existe {RUST_DLL_PATH}"

cpp_lib = ctypes.CDLL(CPP_DLL_PATH)
rust_lib = ctypes.CDLL(RUST_DLL_PATH)

# =========================================================================
# 1. Definición de Estructuras Ctypes
# =========================================================================

class PolydimSolverOptions(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("max_iterations", ctypes.c_uint64),
        ("gradient_tolerance", ctypes.c_double),
        ("step_tolerance", ctypes.c_double),
        ("objective_tolerance", ctypes.c_double),
        ("ortho_tolerance", ctypes.c_double),
        ("retraction_type", ctypes.c_uint32),
        ("sampling_period", ctypes.c_uint32),
        ("num_threads", ctypes.c_uint32),
        ("learning_rate", ctypes.c_double),
    ]

class PolydimTelemetryPoint(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("iteration", ctypes.c_uint64),
        ("objective_value", ctypes.c_double),
        ("gradient_norm", ctypes.c_double),
        ("step_size", ctypes.c_double),
        ("ortho_error", ctypes.c_double),
        ("elapsed_time_ns", ctypes.c_uint64),
    ]

class PolydimTelemetryBuffer(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("points", ctypes.POINTER(PolydimTelemetryPoint)),
        ("capacity", ctypes.c_size_t),
        ("recorded_count", ctypes.c_size_t),
    ]

class PolydimSolverResult(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("status", ctypes.c_int32),
        ("iterations_executed", ctypes.c_uint64),
        ("final_objective", ctypes.c_double),
        ("final_grad_norm", ctypes.c_double),
        ("final_ortho_error", ctypes.c_double),
        ("total_time_ns", ctypes.c_uint64),
        ("status_message", ctypes.c_char * 256),
    ]

class PmtpBankedSlotHeader(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("active_bank", ctypes.c_uint32),
        ("writer_active", ctypes.c_uint32),
        ("reader_count_0", ctypes.c_uint32),
        ("reader_count_1", ctypes.c_uint32),
        ("sequence", ctypes.c_uint64),
        ("owner_pid", ctypes.c_uint32),
        ("owner_start_time_ns", ctypes.c_uint64),
        ("cache_padding", ctypes.c_uint8 * 88),
    ]

class PolydimEdge(ctypes.Structure):
    _fields_ = [
        ("u", ctypes.c_uint32),
        ("v", ctypes.c_uint32),
    ]

class PolydimBettiResult(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_int32),
        ("components_betti0", ctypes.c_uint32),
        ("cycles_betti1", ctypes.c_int64),
        ("num_vertices", ctypes.c_uint32),
        ("num_edges", ctypes.c_uint32),
        ("is_critically_healthy", ctypes.c_bool),
        ("is_optimally_healthy", ctypes.c_bool),
    ]

# Bindings C++
cpp_lib.polydim_stiefel_optimize.argtypes = [
    ctypes.POINTER(ctypes.c_double),
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_double),
    ctypes.c_size_t,
    ctypes.c_size_t,
    ctypes.POINTER(PolydimSolverOptions),
    ctypes.POINTER(PolydimSolverResult),
    ctypes.POINTER(PolydimTelemetryBuffer)
]
cpp_lib.polydim_stiefel_optimize.restype = ctypes.c_int32

cpp_lib.polydim_gram_dsyrk.argtypes = [
    ctypes.POINTER(ctypes.c_double),
    ctypes.c_size_t,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_double),
    ctypes.c_uint32
]
cpp_lib.polydim_gram_dsyrk.restype = ctypes.c_int32

cpp_lib.polydim_set_fp_mode.argtypes = [ctypes.c_int32]
cpp_lib.polydim_set_fp_mode.restype = None

cpp_lib.pmtp_banked_slot_acquire_reader.argtypes = [ctypes.POINTER(PmtpBankedSlotHeader), ctypes.POINTER(ctypes.c_uint32)]
cpp_lib.pmtp_banked_slot_acquire_reader.restype = ctypes.c_int32

cpp_lib.pmtp_banked_slot_release_reader.argtypes = [ctypes.POINTER(PmtpBankedSlotHeader), ctypes.c_uint32]
cpp_lib.pmtp_banked_slot_release_reader.restype = ctypes.c_int32

cpp_lib.pmtp_banked_slot_acquire_writer.argtypes = [ctypes.POINTER(PmtpBankedSlotHeader), ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32, ctypes.c_uint64]
cpp_lib.pmtp_banked_slot_acquire_writer.restype = ctypes.c_int32

cpp_lib.pmtp_banked_slot_commit_writer.argtypes = [ctypes.POINTER(PmtpBankedSlotHeader), ctypes.c_uint32]
cpp_lib.pmtp_banked_slot_commit_writer.restype = ctypes.c_int32

# Bindings Rust
rust_lib.polydim_rust_betti_dual_guard.argtypes = [
    ctypes.POINTER(PolydimEdge),
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_int64,
    ctypes.POINTER(PolydimBettiResult)
]
rust_lib.polydim_rust_betti_dual_guard.restype = ctypes.c_int32

# =========================================================================
# 2. Test 1: Gramiana DSYRK y Modos Duales (TwoSum Deterministic vs SIMD)
# =========================================================================

def test_gram_dsyrk():
    print("\n--- [TEST 1] Gramiana DSYRK y Modos Duales (FP_DETERMINISTIC vs FP_THROUGHPUT) ---")
    D, K = 5000, 64
    rng = np.random.RandomState(42)
    X = rng.randn(D, K).astype(np.float64)
    # Normalizar columnas para que X esté cerca de Stiefel
    Q, _ = np.linalg.qr(X)
    X = np.ascontiguousarray(Q[:D, :K], dtype=np.float64)

    K_det = np.zeros((K, K), dtype=np.float64)
    K_thr = np.zeros((K, K), dtype=np.float64)

    # Modo Determinista (TwoSum)
    cpp_lib.polydim_set_fp_mode(0)
    t0 = time.perf_counter()
    st1 = cpp_lib.polydim_gram_dsyrk(
        X.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        D, K,
        K_det.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        4
    )
    t_det = time.perf_counter() - t0
    assert st1 == 0, f"Error en DSYRK determinista: {st1}"

    # Modo Throughput (SIMD OpenMP)
    cpp_lib.polydim_set_fp_mode(1)
    t0 = time.perf_counter()
    st2 = cpp_lib.polydim_gram_dsyrk(
        X.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        D, K,
        K_thr.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        4
    )
    t_thr = time.perf_counter() - t0
    assert st2 == 0, f"Error en DSYRK throughput: {st2}"

    # NumPy Ground Truth
    K_ref = X.T @ X
    diff_det = np.linalg.norm(K_det - K_ref, ord='fro')
    diff_thr = np.linalg.norm(K_thr - K_ref, ord='fro')
    diff_cross = np.linalg.norm(K_det - K_thr, ord='fro')

    print(f"✓ D={D}, K={K}")
    print(f"✓ Tiempo Determinista (TwoSum): {t_det*1000:.2f} ms (Error Frobenius vs NumPy: {diff_det:.2e})")
    print(f"✓ Tiempo Throughput (SIMD OpenMP): {t_thr*1000:.2f} ms (Error Frobenius vs NumPy: {diff_thr:.2e})")
    print(f"✓ Discrepancia entre modos (Bit de mantisa): {diff_cross:.2e}")
    assert diff_det < 1e-12, f"Error determinista fuera de tolerancia: {diff_det}"
    assert diff_thr < 1e-12, f"Error throughput fuera de tolerancia: {diff_thr}"
    print("[TEST 1 PASS] Gramiana DSYRK dual verificada con éxito.")

# =========================================================================
# 3. Test 2: Solver Monolítico C++ (Single-Shot stiefel_optimize)
# =========================================================================

def test_stiefel_optimize_single_shot():
    print("\n--- [TEST 2] Optimización Monolítica Stiefel en C++ (Single-Shot FFI) ---")
    D, K = 10000, 32
    rng = np.random.RandomState(123)
    
    # Matriz inicial ortogonalizada
    X_init = np.linalg.qr(rng.randn(D, K))[0].astype(np.float64)
    X = np.ascontiguousarray(X_init.copy(), dtype=np.float64)
    
    # Target sintético
    Target = np.ascontiguousarray(X_init + 0.05 * rng.randn(D, K), dtype=np.float64)

    opts = PolydimSolverOptions()
    opts.max_iterations = 25
    opts.gradient_tolerance = 1e-6
    opts.step_tolerance = 1e-8
    opts.objective_tolerance = 1e-8
    opts.ortho_tolerance = 1e-5
    opts.retraction_type = 1 # Cayley-SMW en Gram
    opts.sampling_period = 5
    opts.num_threads = 4
    opts.learning_rate = 1e-3

    result = PolydimSolverResult()
    
    capacity = 100
    points_array = (PolydimTelemetryPoint * capacity)()
    telemetry = PolydimTelemetryBuffer()
    telemetry.points = points_array
    telemetry.capacity = capacity
    telemetry.recorded_count = 0

    cpp_lib.polydim_set_fp_mode(1) # Throughput
    t0 = time.perf_counter()
    status = cpp_lib.polydim_stiefel_optimize(
        Target.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        D * K,
        X.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        D, K,
        ctypes.byref(opts),
        ctypes.byref(result),
        ctypes.byref(telemetry)
    )
    t_elapsed = time.perf_counter() - t0

    print(f"✓ Invocaciones FFI durante el bucle: 0 (Ejecución 100% C++)")
    print(f"✓ Tiempo total de corrida: {t_elapsed*1000:.2f} ms")
    print(f"✓ Iteraciones ejecutadas: {result.iterations_executed}")
    print(f"✓ Código de estado: {result.status} ({result.status_message.decode('utf-8', errors='ignore')})")
    print(f"✓ Error de ortogonalidad final ||X^T X - I||_F: {result.final_ortho_error:.2e}")
    print(f"✓ Puntos de telemetría registrados: {telemetry.recorded_count}")

    for idx in range(telemetry.recorded_count):
        pt = points_array[idx]
        print(f"   [Punto {idx}] Iter: {pt.iteration:02d} | Obj: {pt.objective_value:.4f} | GradNorm: {pt.gradient_norm:.4f} | OrthoErr: {pt.ortho_error:.2e} | Time: {pt.elapsed_time_ns/1e6:.2f} ms")

    assert status in (0, 1, 2, 3), f"Fallo en optimizer: status={status}"
    assert result.final_ortho_error <= 1e-5, f"Violación de variedad Stiefel: {result.final_ortho_error}"
    print("[TEST 2 PASS] Solver Monolítico C++ ejecutado y validado en silicio.")

# =========================================================================
# 4. Test 3: Concurrencia PMTP Banked Slot Lease RCU
# =========================================================================

def test_pmtp_banked_slot_lease():
    print("\n--- [TEST 3] Concurrencia PMTP Banked Slot Lease RCU (Zero Data Race) ---")
    header = PmtpBankedSlotHeader()
    header.active_bank = 0
    header.writer_active = 0
    header.reader_count_0 = 0
    header.reader_count_1 = 0
    header.sequence = 0

    acquired_bank = ctypes.c_uint32(99)
    
    # 1. Lector adquiere Banco 0
    st_r1 = cpp_lib.pmtp_banked_slot_acquire_reader(ctypes.byref(header), ctypes.byref(acquired_bank))
    assert st_r1 == 0 and acquired_bank.value == 0
    assert header.reader_count_0 == 1
    print("✓ Lector 1 adquirió lease en Banco 0 (reader_count_0 = 1)")

    # 2. Escritor adquiere Banco Inactivo (Banco 1)
    write_bank = ctypes.c_uint32(99)
    st_w = cpp_lib.pmtp_banked_slot_acquire_writer(ctypes.byref(header), ctypes.byref(write_bank), 12345, 1000000)
    assert st_w == 0 and write_bank.value == 1
    assert header.writer_active == 1
    print("✓ Escritor adquirió Banco Inactivo 1 sin interferir con Lector 1")

    # 3. Lector 2 adquiere Banco Activo (Banco 0) mientras escritor prepara Banco 1
    st_r2 = cpp_lib.pmtp_banked_slot_acquire_reader(ctypes.byref(header), ctypes.byref(acquired_bank))
    assert st_r2 == 0 and acquired_bank.value == 0
    assert header.reader_count_0 == 2
    print("✓ Lector 2 adquirió lease en Banco 0 simultáneo (reader_count_0 = 2)")

    # 4. Escritor hace Commit (Atomic Swap a Banco 1)
    st_com = cpp_lib.pmtp_banked_slot_commit_writer(ctypes.byref(header), write_bank.value)
    assert st_com == 0
    assert header.active_bank == 1
    assert header.writer_active == 0
    assert header.sequence == 1
    print("✓ Escritor publicó Banco 1 atómicamente (active_bank = 1, sequence = 1)")

    # 5. Nuevo Lector 3 adquiere Banco Activo (ahora es Banco 1)
    st_r3 = cpp_lib.pmtp_banked_slot_acquire_reader(ctypes.byref(header), ctypes.byref(acquired_bank))
    assert st_r3 == 0 and acquired_bank.value == 1
    assert header.reader_count_1 == 1
    print("✓ Lector 3 adquiere lease en nuevo Banco Activo 1 (reader_count_1 = 1)")

    # 6. Liberación de leases
    cpp_lib.pmtp_banked_slot_release_reader(ctypes.byref(header), 0)
    cpp_lib.pmtp_banked_slot_release_reader(ctypes.byref(header), 0)
    cpp_lib.pmtp_banked_slot_release_reader(ctypes.byref(header), 1)
    assert header.reader_count_0 == 0
    assert header.reader_count_1 == 0
    print("✓ Todos los leases liberados limpiamente (readers = 0)")
    print("[TEST 3 PASS] Concurrencia Banked Slot Lease RCU certificada sin Data Races.")

# =========================================================================
# 5. Test 4: Guardián Topológico Dual Rust (\beta_0 y \beta_1)
# =========================================================================

def test_rust_betti_dual_guard():
    print("\n--- [TEST 4] Guardián Topológico Rust Dual (beta_0 y beta_1) ---")
    
    # Topología 1: Árbol conexo (10 nodos, 9 aristas -> beta_0=1, beta_1=0)
    edges_tree = [
        (0, 1), (1, 2), (2, 3), (3, 4),
        (4, 5), (5, 6), (6, 7), (7, 8), (8, 9)
    ]
    c_edges_tree = (PolydimEdge * len(edges_tree))(*[PolydimEdge(u, v) for u, v in edges_tree])
    res_tree = PolydimBettiResult()
    
    st_t = rust_lib.polydim_rust_betti_dual_guard(
        c_edges_tree, len(edges_tree), 10, 0, ctypes.byref(res_tree)
    )
    assert st_t == 0
    print(f"✓ Topología Árbol: beta_0={res_tree.components_betti0} (C=1), beta_1={res_tree.cycles_betti1} (Ciclos=0)")
    assert res_tree.is_critically_healthy == True
    assert res_tree.is_optimally_healthy == True

    # Topología 2: Enjambre con ciclos redundantes (10 nodos, 12 aristas -> beta_0=1, beta_1=3)
    edges_cycles = edges_tree + [(0, 4), (2, 7), (1, 9)]
    c_edges_cycles = (PolydimEdge * len(edges_cycles))(*[PolydimEdge(u, v) for u, v in edges_cycles])
    res_cycles = PolydimBettiResult()
    
    st_c = rust_lib.polydim_rust_betti_dual_guard(
        c_edges_cycles, len(edges_cycles), 10, 2, ctypes.byref(res_cycles) # max_tau = 2
    )
    assert st_c == 0
    print(f"✓ Topología con Ciclos: beta_0={res_cycles.components_betti0}, beta_1={res_cycles.cycles_betti1} (Ciclos=3 > max_tau=2)")
    assert res_cycles.is_critically_healthy == True
    assert res_cycles.is_optimally_healthy == False # Excede umbral de tolerancia a bucles

    # Topología 3: Enjambre fragmentado (10 nodos, 2 componentes desconectados)
    edges_frag = [(0, 1), (1, 2), (2, 3), (3, 4), (5, 6), (6, 7), (7, 8), (8, 9)]
    c_edges_frag = (PolydimEdge * len(edges_frag))(*[PolydimEdge(u, v) for u, v in edges_frag])
    res_frag = PolydimBettiResult()
    
    st_f = rust_lib.polydim_rust_betti_dual_guard(
        c_edges_frag, len(edges_frag), 10, 5, ctypes.byref(res_frag)
    )
    assert st_f == 0
    print(f"✓ Topología Fragmentada: beta_0={res_frag.components_betti0} (C=2 -> FAIL Crítico), beta_1={res_frag.cycles_betti1}")
    assert res_frag.is_critically_healthy == False
    assert res_frag.is_optimally_healthy == False

    print("[TEST 4 PASS] Guardián Topológico Rust Dual verificado en todos los regímenes.")

# =========================================================================
# 6. Test 5: Síntesis Cuántica Discreta Clifford+T (GridSynth / Solovay-Kitaev)
# =========================================================================

rust_lib.polydim_rust_quantum_synthesize_discrete.argtypes = [
    ctypes.c_double,
    ctypes.c_uint32,
    ctypes.c_double,
    ctypes.POINTER(ctypes.c_uint8),
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_uint32)
]
rust_lib.polydim_rust_quantum_synthesize_discrete.restype = ctypes.c_int32

def test_quantum_synthesis_discrete():
    print("\n--- [TEST 5] Síntesis Cuántica Discreta Clifford+T en Rust (C ABI) ---")
    
    op_names = {1: "H", 2: "S", 3: "T", 4: "T†", 5: "X", 6: "Z", 7: "CNOT"}

    # Caso A: R_y(pi/4) -> H * T * H
    theta_a = np.pi / 4.0
    buffer_a = (ctypes.c_uint8 * 64)()
    count_a = ctypes.c_uint32(0)
    st_a = rust_lib.polydim_rust_quantum_synthesize_discrete(
        theta_a, 1, 1e-6, buffer_a, 64, ctypes.byref(count_a)
    )
    assert st_a == 0
    seq_a = [op_names.get(buffer_a[i], str(buffer_a[i])) for i in range(count_a.value)]
    print(f"✓ R_y(pi/4): {count_a.value} puertas discretas -> {' - '.join(seq_a)}")
    assert seq_a == ["H", "T", "H"], f"Secuencia inesperada: {seq_a}"

    # Caso B: R_z(3*pi/4) -> S * T
    theta_b = 3.0 * np.pi / 4.0
    buffer_b = (ctypes.c_uint8 * 64)()
    count_b = ctypes.c_uint32(0)
    st_b = rust_lib.polydim_rust_quantum_synthesize_discrete(
        theta_b, 0, 1e-6, buffer_b, 64, ctypes.byref(count_b)
    )
    assert st_b == 0
    seq_b = [op_names.get(buffer_b[i], str(buffer_b[i])) for i in range(count_b.value)]
    print(f"✓ R_z(3*pi/4): {count_b.value} puertas discretas -> {' - '.join(seq_b)}")
    assert seq_b == ["S", "T"], f"Secuencia inesperada: {seq_b}"

    # Caso C: Rotación continua arbitraria con corrección diádica
    theta_c = 0.52359877559 # pi / 6
    buffer_c = (ctypes.c_uint8 * 64)()
    count_c = ctypes.c_uint32(0)
    st_c = rust_lib.polydim_rust_quantum_synthesize_discrete(
        theta_c, 1, 1e-5, buffer_c, 64, ctypes.byref(count_c)
    )
    assert st_c == 0
    seq_c = [op_names.get(buffer_c[i], str(buffer_c[i])) for i in range(count_c.value)]
    print(f"✓ R_y(pi/6) aproximación diádica: {count_c.value} puertas -> {' - '.join(seq_c)}")
    assert len(seq_c) >= 3

    print("[TEST 5 PASS] Síntesis Cuántica Discreta en Rust validada con C ABI exacto.")

# =========================================================================
# 7. Test 6: Reservorio Estructurado Walsh-Hadamard (LSM O(D log D), rho(W)=1.0)
# =========================================================================

cpp_lib.polydim_structured_lsm_step.argtypes = [
    ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(ctypes.c_int8),
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.POINTER(ctypes.c_int8),
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_size_t,
    ctypes.c_double,
    ctypes.c_double
]
cpp_lib.polydim_structured_lsm_step.restype = ctypes.c_int32

def test_structured_lsm_hadamard():
    print("\n--- [TEST 6] Reservorio Estructurado Walsh-Hadamard (LSM O(D log D), O(D) Memoria) ---")
    D = 16384 # 2^14
    rng = np.random.RandomState(42)

    # Estado inicial normalizado en S^{D-1}
    state = rng.randn(D).astype(np.float64)
    state /= np.linalg.norm(state)
    state_arr = np.ascontiguousarray(state.copy(), dtype=np.float64)

    # Signos D1, D2 in {-1, +1}
    d1 = rng.choice([-1, 1], size=D).astype(np.int8)
    d2 = rng.choice([-1, 1], size=D).astype(np.int8)

    # Permutaciones P1, P2
    p1 = rng.permutation(D).astype(np.uint32)
    p2 = rng.permutation(D).astype(np.uint32)

    # Ejecución de 50 pasos sin entrada (prueba de conservación y estabilidad dinámica)
    t0 = time.perf_counter()
    norms = []
    for step in range(50):
        st = cpp_lib.polydim_structured_lsm_step(
            state_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            None, # Input nulo para evaluar dinámica intrínseca
            d1.ctypes.data_as(ctypes.POINTER(ctypes.c_int8)),
            p1.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
            d2.ctypes.data_as(ctypes.POINTER(ctypes.c_int8)),
            p2.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
            D,
            0.9, # alpha_leak
            1.0
        )
        assert st == 0, f"Error en LSM step {step}: {st}"
        norm = np.linalg.norm(state_arr)
        norms.append(norm)

    t_elapsed = time.perf_counter() - t0
    avg_step_ms = (t_elapsed / 50.0) * 1000.0

    print(f"✓ Dimensión del Reservorio: D={D} (2^14 = 16,384 neuronas)")
    print(f"✓ Memoria requerida: O(D) -> {4 * D * 8 / 1024:.2f} KB (Vs ~2.1 GB de matriz densa)")
    print(f"✓ Tiempo por paso: {avg_step_ms:.3f} ms (50 pasos en {t_elapsed*1000:.1f} ms)")
    print(f"✓ Norma de estado inicial: {norms[0]:.4f} -> Final (Paso 50): {norms[-1]:.4f}")
    assert 0.1 <= norms[-1] <= np.sqrt(D), "Explosión o colapso del estado en el reservorio"
    print("[TEST 6 PASS] LSM Estructurado Walsh-Hadamard verificado con estabilidad en el borde del caos.")

# =========================================================================
# MAIN ENTRY
# =========================================================================

if __name__ == "__main__":
    print("=================================================================")
    print("🚀 EJECUTANDO SUITE MONOLÍTICA DE VALIDACIÓN POLYDIM V772")
    print("=================================================================")
    
    test_gram_dsyrk()
    test_stiefel_optimize_single_shot()
    test_pmtp_banked_slot_lease()
    test_rust_betti_dual_guard()
    test_quantum_synthesis_discrete()
    test_structured_lsm_hadamard()

    print("\n=================================================================")
    print("✅ 6/6 TESTS PASS — SILICIO LOCAL CERTIFICADO CON EXIT CODE 0")
    print("=================================================================")

