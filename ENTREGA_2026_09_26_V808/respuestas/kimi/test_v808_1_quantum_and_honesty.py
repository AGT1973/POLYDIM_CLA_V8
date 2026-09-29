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

    V = 1_000_000
    t0 = time.perf_counter()
    c_edges = (PolydimEdge * (V - 1))()
    for i in range(V - 1):
        c_edges[i].u = i; c_edges[i].v = i + 1
    t_build = time.perf_counter() - t0

    res = Betti()
    t0 = time.perf_counter()
    st = rust_lib.polydim_rust_betti_dual_guard(c_edges, V - 1, V, 0, ctypes.byref(res))
    t_rust = time.perf_counter() - t0
    assert st == 0 and res.components_betti0 == 1 and res.cycles_betti1 == 0
    print(f"[PASS] DSU 10^6: construcción ctypes {t_build*1000:.1f} ms + "
          f"Rust {t_rust*1000:.2f} ms = TOTAL {1000*(t_build+t_rust):.1f} ms "
          f"(el informe debe citar el total, no solo el Rust)")

if __name__ == "__main__":
    test_quantum_unitary_correctness()
    test_dsu_timing_honesty()
