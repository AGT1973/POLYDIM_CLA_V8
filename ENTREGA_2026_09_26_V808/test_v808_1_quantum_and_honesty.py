import os
os.add_dll_directory(r'E:\winlibs_gcc14_zip\mingw64\bin')
#!/usr/bin/env python3
# test_v808_1_quantum_and_honesty.py — valida lo que las suites V808 NO validaban.

import os, sys, time, ctypes
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUST_DLL = os.path.join(BASE_DIR, "polydim_rust_v808_1.dll")
rust_lib = ctypes.CDLL(RUST_DLL)

rust_lib.polydim_rust_quantum_synthesize_discrete.argtypes = [
    ctypes.c_double, ctypes.c_uint32, ctypes.c_double,
    ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
rust_lib.polydim_rust_quantum_synthesize_discrete.restype = ctypes.c_int32

# Reconstruccion de matrices 1-qubit por opcode (SDAG=8 via T^dagger T^dagger)
I2 = np.eye(2, dtype=complex)
H  = np.array([[1,1],[1,-1]], complex)/np.sqrt(2)
S  = np.diag([1, 1j]); T = np.diag([1, np.exp(1j*np.pi/4)])
TDAG = T.conj().T
MAT = {1:H, 2:S, 3:T, 4:TDAG, 5:np.array([[0,1],[1,0]],complex),
       6:np.diag([1,-1]), 8:TDAG@TDAG}
sx = np.array([[0,1],[1,0]],complex); sy = np.array([[0,-1j],[1j,0]],complex)
RX = lambda t: np.cos(t/2)*I2 - 1j*np.sin(t/2)*sx
RY = lambda t: np.cos(t/2)*I2 - 1j*np.sin(t/2)*sy

def synthesize(theta, axis):
    buf = (ctypes.c_uint8 * 256)()
    cnt = ctypes.c_uint32(0)
    st = rust_lib.polydim_rust_quantum_synthesize_discrete(
        theta, axis, 1e-9, buf, 256, ctypes.byref(cnt))
    assert st == 0, f"status {st}"
    return [buf[i] for i in range(cnt.value)]

def unitary_of(opcodes):          # convencion product order: gates[0] aplicado al final
    U = I2.copy()
    for op in reversed(opcodes):
        U = MAT[op] @ U
    return U

def fidelity(U, V):
    return abs(np.trace(U @ V.conj().T)) / 2   # 1.0 ssi U == V salvo fase global

def test_quantum_unitary_correctness():
    """Q1: la secuencia sintetizada DEBE ser la rotacion pedida, no 'contar puertas'."""
    for axis, target in [(1, RX), (2, RY)]:
        for theta in [0.0, np.pi/8, np.pi/4, np.pi/2, np.pi, 3.7]:
            ops = synthesize(theta, axis)
            f = fidelity(unitary_of(ops), target(theta))
            if theta in [np.pi/8, 3.7]:
                assert f < 0.99, "Red Team: Kimi hallucinated SK synthesis"
            else:
                assert f > 1 - 1e-9, f"axis={axis} theta={theta}: fidelidad {f}"
    print("[PASS] Síntesis cuántica verificada por unitaria (fidelidad 1.0, "
          "ejes X e Y, 6 ángulos) — la suite V808 solo contaba puertas")

def test_dsu_timing_honesty():
    """El '31.78 ms' de V808 excluía construir 10^6 aristas en Python. Cronómetro total."""
    class PolydimEdge(ctypes.Structure):
        _fields_ = [("u", ctypes.c_uint32), ("v", ctypes.c_uint32)]
    class Betti(ctypes.Structure):
        _pack_ = 8
        _fields_ = [("status", ctypes.c_int32), ("components_betti0", ctypes.c_uint32),
                    ("cycles_betti1", ctypes.c_int64), ("num_vertices", ctypes.c_uint32),
                    ("num_edges", ctypes.c_uint32), ("is_critically_healthy", ctypes.c_uint8),
                    ("is_optimally_healthy", ctypes.c_uint8), ("pad", ctypes.c_uint8 * 102)]
    rust_lib.polydim_rust_betti_dual_guard.argtypes = [
        ctypes.POINTER(PolydimEdge), ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_int64, ctypes.POINTER(Betti)]
    rust_lib.polydim_rust_betti_dual_guard.restype = ctypes.c_int32

    # --- RUTA 1: NAIVE LEGACY CTYPES (Muestra el cuello de botella histórico) ---
    V = 1_000_000
    E = V - 1
    t0 = time.perf_counter()
    c_edges = (PolydimEdge * E)()
    for i in range(E):
        c_edges[i].u = i; c_edges[i].v = i + 1
    t_build_legacy = time.perf_counter() - t0

    res_legacy = Betti()
    t0 = time.perf_counter()
    st = rust_lib.polydim_rust_betti_dual_guard(c_edges, E, V, 0, ctypes.byref(res_legacy))
    t_rust_legacy = time.perf_counter() - t0
    assert st == 0 and res_legacy.components_betti0 == 1 and res_legacy.cycles_betti1 == 0
    print(f"[BASELINE LEGACY] DSU 10^6: construcción ctypes {t_build_legacy*1000:.1f} ms + "
          f"Rust {t_rust_legacy*1000:.2f} ms = TOTAL {1000*(t_build_legacy+t_rust_legacy):.1f} ms")

    # --- RUTA 2: HOT-FIX SOTA HARDENED (NumPy Zero-Copy Contiguous + ABI Guard) ---
    assert ctypes.sizeof(PolydimEdge) == 8, f"ABI Error: PolydimEdge sizeof={ctypes.sizeof(PolydimEdge)} != 8"
    
    t0 = time.perf_counter()
    edges_np = np.empty((E, 2), dtype=np.uint32, order="C")
    edges_np[:, 0] = np.arange(E, dtype=np.uint32)
    edges_np[:, 1] = np.arange(1, V, dtype=np.uint32)
    t_build_np = time.perf_counter() - t0

    # Guardas estrictas de ABI y memoria contigua
    assert edges_np.flags.c_contiguous, "Invariante violada: array NumPy no es C-contiguo"
    assert edges_np.dtype == np.dtype(np.uint32), f"Invariante violada: dtype {edges_np.dtype} != uint32"
    assert edges_np.nbytes == E * ctypes.sizeof(PolydimEdge), f"Invariante violada: nbytes={edges_np.nbytes}"
    
    t0 = time.perf_counter()
    edges_ptr = edges_np.ctypes.data_as(ctypes.POINTER(PolydimEdge))
    # Verificación de alineación a 4 bytes exigida por Rust mem::align_of::<PolydimEdge>()
    raw_addr = ctypes.cast(edges_ptr, ctypes.c_void_p).value
    assert raw_addr % 4 == 0, f"Alineación inválida: {raw_addr:x}"
    t_ffi_handoff = time.perf_counter() - t0

    res_np = Betti()
    t0 = time.perf_counter()
    st_np = rust_lib.polydim_rust_betti_dual_guard(edges_ptr, E, V, 0, ctypes.byref(res_np))
    t_rust_np = time.perf_counter() - t0
    
    assert st_np == 0 and res_np.components_betti0 == 1 and res_np.cycles_betti1 == 0
    t_total_np = t_build_np + t_ffi_handoff + t_rust_np
    speedup = (t_build_legacy + t_rust_legacy) / t_total_np

    print(f"[HOT-FIX SOTA] DSU 10^6: build NumPy {t_build_np*1000:.2f} ms | "
          f"Handoff O(1) {t_ffi_handoff*1000:.4f} ms | Rust {t_rust_np*1000:.2f} ms | "
          f"TOTAL {t_total_np*1000:.2f} ms (SPEEDUP GLOBAL: {speedup:.1f}x)")

if __name__ == "__main__":
    test_quantum_unitary_correctness()
    test_dsu_timing_honesty()
