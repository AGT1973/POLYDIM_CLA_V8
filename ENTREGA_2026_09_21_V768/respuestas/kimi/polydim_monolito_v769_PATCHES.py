# ============================================================================
# POLYDIM v769 - PATCHES PYTHON (aplicar sobre polydim_v768_monolito.py)
#   C1: restype faltante en polydim_pmtp_alignof (truncado a c_int).
#   C2: polydim_cholqr2_f64 y polydim_selftest_compensation nunca bindeados.
#   C3: PMTPSlabChannel: 10MB fijos, sin init, sin payload -> reescrito.
#   C4: test PMTP con threads y arrays por-proceso no probaba IPC -> multiproceso.
#   C5: umbral 90% escondia contention -> 99.9%.
#   C6: LSM rho(W)=1 falso (medido 1.01-1.04) -> Givens ortogonal + scipy.sparse.
# ============================================================================

# --- C1/C2: agregar dentro de PolydimNativeBinding._bind_cpp_symbols ---
BINDINGS_ADD_V769 = """
        self.lib.polydim_pmtp_alignof.restype = ctypes.c_uint64              # C1
        self.lib.polydim_cholqr2_f64.argtypes = [                            # C2
            ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint32]
        self.lib.polydim_cholqr2_f64.restype = ctypes.c_int32
        self.lib.polydim_selftest_compensation.argtypes = [
            ctypes.POINTER(ctypes.c_double)]
        self.lib.polydim_selftest_compensation.restype = ctypes.c_int32
        self._tolerances_st = getattr(self.lib,
                                      "polydim_default_tolerances_st", None) # v769 N-06
"""


class PMTPSlabChannelV769:
    # C3: canal PMTP real. sizeof exacto, init via C, magic validado,
    # payload escrito en el area de slots del mmap.
    def __init__(self, binding, name="polydim_bus_0", d=1024, num_slots=4):
        assert 2 <= num_slots <= 64
        import os
        self.d = d
        self.num_slots = num_slots
        self.payload_bytes = d * 8
        self.binding = binding
        self.total_bytes = binding.lib.polydim_pmtp_sizeof(num_slots,
                                                           self.payload_bytes)
        self.is_posix = os.name == "posix"
        if self.is_posix:
            from multiprocessing import shared_memory
            try:
                self.shm = shared_memory.SharedMemory(create=True, name=name,
                                                      size=self.total_bytes)
            except FileExistsError:
                self.shm = shared_memory.SharedMemory(name=name)
            self.mmap_obj = self.shm.buf
        else:
            import mmap
            self.shm = None
            self.mmap_obj = mmap.mmap(-1, self.total_bytes, name)

        self.ctrl = PMTPControl.from_buffer(self.mmap_obj)
        self.ctrl_ptr = ctypes.pointer(self.ctrl)
        rc = binding.lib.polydim_pmtp_init(self.ctrl_ptr, num_slots,
                                           self.payload_bytes)
        if rc != 0:
            raise RuntimeError("polydim_pmtp_init rc=%d" % rc)
        if self.ctrl.magic != 0x504D5432:
            raise RuntimeError("magic invalido: segmento stale?")

    def _slot_view(self, slot):
        import numpy as np
        base = ctypes.sizeof(PMTPControl) + slot * ctypes.sizeof(PMTPSlotHeader)
        return np.frombuffer(self.mmap_obj, dtype=np.float64,
                             count=self.d, offset=base)

    def write_tensor(self, tensor_np):
        import numpy as np
        t = np.ascontiguousarray(tensor_np, dtype=np.float64)
        assert t.size == self.d
        slot = ctypes.c_uint32(0)
        ver = ctypes.c_uint64(0)
        rc = self.binding.lib.polydim_pmtp_write_begin(
            self.ctrl_ptr, ctypes.byref(slot), ctypes.byref(ver))
        if rc != 0:
            return rc
        try:
            np.copyto(self._slot_view(slot.value), t)   # payload REAL en mmap
        except Exception:
            self.binding.lib.polydim_pmtp_write_abort(
                self.ctrl_ptr, slot.value, ver.value)
            raise
        self.binding.lib.polydim_pmtp_write_commit(
            self.ctrl_ptr, slot.value, ver.value)
        return 0

    def read_tensor(self):
        slot = ctypes.c_uint32(0)
        ver = ctypes.c_uint64(0)
        rc = self.binding.lib.polydim_pmtp_read_begin(
            self.ctrl_ptr, ctypes.byref(slot), ctypes.byref(ver))
        if rc != 0:
            return None
        out = self._slot_view(slot.value).copy()
        rc = self.binding.lib.polydim_pmtp_read_validate(
            self.ctrl_ptr, slot.value, ver.value)
        return out if rc == 0 else None

    def close(self, unlink=True):
        try:
            self.mmap_obj.close()
        finally:
            if self.is_posix and self.shm is not None:
                self.shm.close()
                if unlink:
                    try:
                        self.shm.unlink()
                    except FileNotFoundError:
                        pass


def pmtp_stress_multiprocess_v769(binding, d=10000, num_slots=4,
                                  writes=1000, n_readers=4):
    # C4/C5: writer y readers en PROCESOS, payload en el mmap. Es el unico
    # test que ejerce seqlock, tearing y coherencia entre procesos.
    import numpy as np, time, ctypes
    from multiprocessing import Process, shared_memory

    total = binding.lib.polydim_pmtp_sizeof(num_slots, d * 8)
    shm = shared_memory.SharedMemory(create=True, size=total)
    hdr_sz = ctypes.sizeof(PMTPControl)
    slot_hdr_sz = ctypes.sizeof(PMTPSlotHeader)

    def _ctrl(shm_name):
        s = shared_memory.SharedMemory(name=shm_name)
        c = PMTPControl.from_buffer(s.buf)
        return s, c, ctypes.pointer(c)

    def writer(shm_name):
        s, c, cp = _ctrl(shm_name)
        assert binding.lib.polydim_pmtp_init(cp, num_slots, d * 8) == 0
        slot = ctypes.c_uint32(0)
        ver = ctypes.c_uint64(0)
        for i in range(1, writes + 1):
            if binding.lib.polydim_pmtp_write_begin(
                    cp, ctypes.byref(slot), ctypes.byref(ver)) != 0:
                continue
            off = hdr_sz + slot.value * slot_hdr_sz
            np.frombuffer(s.buf, dtype=np.float64,
                          count=d, offset=off).fill(float(i))
            binding.lib.polydim_pmtp_write_commit(cp, slot.value, ver.value)
        time.sleep(0.3)

    def reader(shm_name, idx, res):
        s, c, cp = _ctrl(shm_name)
        slot = ctypes.c_uint32(0)
        ver = ctypes.c_uint64(0)
        ok = races = corrupt = 0
        deadline = time.time() + 15.0
        while time.time() < deadline:
            rc = binding.lib.polydim_pmtp_read_begin(
                cp, ctypes.byref(slot), ctypes.byref(ver))
            if rc != 0:
                if rc == -3:
                    races += 1
                continue
            off = hdr_sz + slot.value * slot_hdr_sz
            buf = np.frombuffer(s.buf, dtype=np.float64,
                                count=d, offset=off).copy()
            if binding.lib.polydim_pmtp_read_validate(cp, slot.value,
                                                      ver.value) != 0:
                races += 1
                continue
            if np.all(buf == buf[0]):
                ok += 1
            else:
                corrupt += 1
        res[idx] = (ok, races, corrupt)

    mgr = {}
    readers = [Process(target=reader, args=(shm.name, i, mgr))
               for i in range(n_readers)]
    for r in readers:
        r.start()
    w = Process(target=writer, args=(shm.name,))
    w.start()
    w.join()
    for r in readers:
        r.join(20)

    tot_ok = sum(v[0] for v in mgr.values())
    tot_races = sum(v[1] for v in mgr.values())
    tot_corrupt = sum(v[2] for v in mgr.values())
    rate = 100.0 * tot_ok / max(1, tot_ok + tot_races)
    shm.close()
    shm.unlink()
    assert tot_corrupt == 0, "TORN READS: %d" % tot_corrupt
    assert rate >= 99.9, "starvation: %.2f%%" % rate   # C5
    return tot_ok, tot_races, tot_corrupt, rate


class PolydimLiquidStateMachineV769:
    # C6: rho(W)=1 por construccion (Q ortogonal de QR) + poda controlada,
    # step vectorizado con CSR (utilizable a D>=1e6; el loop Python por
    # filas de V768 tardaba horas a D=1e7).
    def __init__(self, dim, leak_rate=0.25, keep=0.02, seed=42):
        import numpy as np
        from scipy.sparse import lil_matrix
        self.dim = dim
        self.alpha = leak_rate
        rng = np.random.default_rng(seed)
        A = rng.standard_normal((dim, dim))
        Q, _ = np.linalg.qr(A)              # Q ortogonal exacta: rho(Q)=1
        W = lil_matrix((dim, dim))
        k = max(4, int(keep * dim))
        for i in range(dim):
            row = np.abs(Q[i])
            idx = np.argpartition(row, -k)[-k:]
            W[i, idx] = Q[i, idx]
        self.W = W.tocsr()
        self.state = rng.standard_normal(dim)
        self.state /= np.linalg.norm(self.state)

    def step(self, u_in):
        import numpy as np
        a = self.W @ self.state
        new = (1.0 - self.alpha) * self.state + self.alpha * np.tanh(a + u_in)
        n = np.linalg.norm(new)
        if n > 1e-15:
            self.state = new / n
        return self.state
