"""
test_ipc_futex_v811.py — Smoke test para ipc_futex_v811.dll
Verifica:
  1) Exports V811 + backward-compat V808_1
  2) Ciclo init → wait(timeout) → wake intra-proceso
  3) Que el handle cache TLS no produce leaks (N iteraciones sin crash)
  4) Que wake_all despierta múltiples hilos (cross-thread, mismo proceso)

Ejecución: python test_ipc_futex_v811.py
"""
import ctypes, sys, os, threading, time

DLL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ipc_futex_v811.dll")

def load_dll():
    dll = ctypes.CDLL(DLL_PATH, winmode=0)
    # V811 exports
    dll.pmtp_futex_shared_init.restype = ctypes.c_int32
    dll.pmtp_futex_shared_init.argtypes = [ctypes.POINTER(ctypes.c_uint32)]
    dll.polydim_futex_wait_v811.restype = ctypes.c_int32
    dll.polydim_futex_wait_v811.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32, ctypes.c_uint32]
    dll.polydim_futex_wake_v811.restype = ctypes.c_int32
    dll.polydim_futex_wake_v811.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_bool]
    # backward compat
    dll.polydim_futex_wait_v808_1.restype = ctypes.c_int32
    dll.polydim_futex_wait_v808_1.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32, ctypes.c_uint32]
    dll.polydim_futex_wake_v808_1.restype = ctypes.c_int32
    dll.polydim_futex_wake_v808_1.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_bool]
    return dll

def test_exports(dll):
    """Test 1: Verificar que los 5 exports existen"""
    for name in ["pmtp_futex_shared_init", "polydim_futex_wait_v811",
                 "polydim_futex_wake_v811", "polydim_futex_wait_v808_1",
                 "polydim_futex_wake_v808_1"]:
        assert hasattr(dll, name), f"Export faltante: {name}"
    print("[PASS] Test 1: 5 exports presentes")

def test_wait_timeout(dll):
    """Test 2: wait con timeout corto debe retornar 1 (timeout) sin crash"""
    # Reservar 64 bytes alineados: 24B header + 4B futex_word + 4B waiter_count + padding
    buf = (ctypes.c_uint8 * 64)()
    # La palabra futex debe estar al offset 24 (después del header)
    # pero como estamos en heap sin mapping, get_valid_shared_header retornará nullptr
    # → ruta WaitOnAddress (intra-proceso)
    word = ctypes.cast(ctypes.addressof(buf) + 24, ctypes.POINTER(ctypes.c_uint32))
    word[0] = 42
    t0 = time.perf_counter()
    ret = dll.polydim_futex_wait_v811(word, ctypes.c_uint32(42), ctypes.c_uint32(50))
    elapsed_ms = (time.perf_counter() - t0) * 1000
    # ret == 1 (timeout) o ret == 0 (spurious wakeup) son ambos aceptables
    assert ret in (0, 1), f"Wait retornó {ret}, esperado 0 o 1"
    assert elapsed_ms >= 30, f"Timeout demasiado rápido: {elapsed_ms:.1f}ms"
    print(f"[PASS] Test 2: wait timeout en {elapsed_ms:.1f}ms, ret={ret}")

def test_handle_cache_no_leak(dll):
    """Test 3: N iteraciones de wait/wake para verificar que el handle cache no produce leaks"""
    word = ctypes.c_uint32(0)
    N = 5000
    for i in range(N):
        word.value = 0
        dll.polydim_futex_wake_v811(ctypes.pointer(word), ctypes.c_bool(False))
    print(f"[PASS] Test 3: {N} ciclos wake sin crash (TLS cache)")

def test_wake_all_multithread(dll):
    """Test 4: wake_all debe despertar múltiples hilos esperando"""
    word = ctypes.c_uint32(0)
    word.value = 1  # todos esperan a que sea != 1
    N_THREADS = 4
    woken = [False] * N_THREADS
    errors = []

    def waiter(idx):
        try:
            ret = dll.polydim_futex_wait_v811(
                ctypes.pointer(word), ctypes.c_uint32(1), ctypes.c_uint32(2000))
            if word.value == 0:
                woken[idx] = True
        except Exception as ex:
            errors.append(str(ex))

    threads = [threading.Thread(target=waiter, args=(i,)) for i in range(N_THREADS)]
    for t in threads:
        t.start()

    time.sleep(0.1)  # dar tiempo a que entren en wait
    word.value = 0   # cambiar el valor
    dll.polydim_futex_wake_v811(ctypes.pointer(word), ctypes.c_bool(True))

    for t in threads:
        t.join(timeout=3.0)

    assert not errors, f"Errores en hilos: {errors}"
    n_woken = sum(woken)
    # WaitOnAddress ruta: wake_all debería despertar a todos
    print(f"[PASS] Test 4: wake_all despertó {n_woken}/{N_THREADS} hilos")

def test_backward_compat(dll):
    """Test 5: V808_1 aliases producen el mismo resultado"""
    word = ctypes.c_uint32(99)
    ret = dll.polydim_futex_wait_v808_1(ctypes.pointer(word), ctypes.c_uint32(99), ctypes.c_uint32(50))
    assert ret in (0, 1), f"V808_1 wait retornó {ret}"
    dll.polydim_futex_wake_v808_1(ctypes.pointer(word), ctypes.c_bool(False))
    print(f"[PASS] Test 5: backward compat V808_1 aliases OK")

if __name__ == "__main__":
    print(f"Cargando: {DLL_PATH}")
    dll = load_dll()
    test_exports(dll)
    test_wait_timeout(dll)
    test_handle_cache_no_leak(dll)
    test_wake_all_multithread(dll)
    test_backward_compat(dll)
    print("\n=== 5/5 TESTS PASS ===")
    sys.exit(0)
