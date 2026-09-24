# ============================================================================
# POLYDIM V765 — LINUX POSIX IPC /dev/shm SHARED MEMORY BENCHMARK
# Compiles C++ kernel on Linux, runs Multi-Process 4-Slot Seqlock in /dev/shm
# ============================================================================

import os
import sys
import time
import subprocess
import multiprocessing
import ctypes
import numpy as np

CPP_SOURCE = """
#include <cstdint>
#include <atomic>
#include <cstring>

#define POLYDIM_PMTP_SLOTS 4

struct alignas(64) PMTP_Control {
    std::atomic<uint64_t> seq[POLYDIM_PMTP_SLOTS];
    std::atomic<uint32_t> latest_slot;
    std::atomic<uint32_t> write_index;
    uint8_t pad[64 - sizeof(std::atomic<uint64_t>)*POLYDIM_PMTP_SLOTS - sizeof(std::atomic<uint32_t>)*2];
};

extern "C" {
void polydim_pmtp_init(PMTP_Control* c) {
    if (!c) return;
    for (int i = 0; i < POLYDIM_PMTP_SLOTS; ++i) c->seq[i].store(0, std::memory_order_seq_cst);
    c->latest_slot.store(0xFFFFFFFF, std::memory_order_seq_cst);
    c->write_index.store(0, std::memory_order_seq_cst);
}

int32_t polydim_pmtp_begin_write(PMTP_Control* c, uint64_t* slot_out) {
    if (!c || !slot_out) return -1;
    uint32_t idx = c->write_index.fetch_add(1, std::memory_order_relaxed);
    uint32_t slot = idx % POLYDIM_PMTP_SLOTS;
    c->seq[slot].fetch_add(1, std::memory_order_acquire);
    *slot_out = static_cast<uint64_t>(slot);
    return 0;
}

int32_t polydim_pmtp_commit_write(PMTP_Control* c, uint64_t slot) {
    if (!c || slot >= POLYDIM_PMTP_SLOTS) return -1;
    c->seq[slot].fetch_add(1, std::memory_order_release);
    c->latest_slot.store(static_cast<uint32_t>(slot), std::memory_order_release);
    return 0;
}

int32_t polydim_pmtp_acquire_read(PMTP_Control* c, uint64_t* slot_out, uint64_t* ticket_out) {
    if (!c || !slot_out || !ticket_out) return -1;
    uint32_t slot = c->latest_slot.load(std::memory_order_acquire);
    if (slot >= POLYDIM_PMTP_SLOTS) return 0;
    uint64_t seq = c->seq[slot].load(std::memory_order_acquire);
    if (seq % 2 != 0 || seq == 0) return 0;
    *slot_out = static_cast<uint64_t>(slot);
    *ticket_out = seq;
    return 1;
}

int32_t polydim_pmtp_validate_read(const PMTP_Control* c, uint64_t slot, uint64_t ticket) {
    if (!c || slot >= POLYDIM_PMTP_SLOTS) return -6;
    std::atomic_thread_fence(std::memory_order_acquire);
    uint64_t current_seq = c->seq[slot].load(std::memory_order_acquire);
    if (current_seq != ticket || (current_seq % 2 != 0)) return -6;
    return 0;
}
}
"""

def compile_linux_kernel():
    with open("libpolydim_linux.cpp", "w") as f:
        f.write(CPP_SOURCE)
    cmd = ["g++", "-O3", "-shared", "-fPIC", "-ffp-contract=off", "-fno-fast-math", "-o", "libpolydim_linux.so", "libpolydim_linux.cpp"]
    print(f"[*] Compiling Linux kernel: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print("[OK] libpolydim_linux.so compiled successfully.")

def load_linux_lib():
    lib = ctypes.CDLL("./libpolydim_linux.so")
    lib.polydim_pmtp_init.argtypes = [ctypes.c_void_p]
    lib.polydim_pmtp_init.restype = None
    lib.polydim_pmtp_begin_write.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]
    lib.polydim_pmtp_begin_write.restype = ctypes.c_int32
    lib.polydim_pmtp_commit_write.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    lib.polydim_pmtp_commit_write.restype = ctypes.c_int32
    lib.polydim_pmtp_acquire_read.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64)]
    lib.polydim_pmtp_acquire_read.restype = ctypes.c_int32
    lib.polydim_pmtp_validate_read.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64]
    lib.polydim_pmtp_validate_read.restype = ctypes.c_int32
    return lib

def run_linux_shm_benchmark():
    print("=" * 78)
    print("POLYDIM V765 — LINUX POSIX SHARED MEMORY /dev/shm BENCHMARK")
    print("=" * 78)

    compile_linux_kernel()
    lib = load_linux_lib()

    import mmap
    D = 1000000  # 1 Million dimensions (8 MB float64)
    tensor_bytes = D * 8
    total_bytes = 64 + 4 * tensor_bytes
    shm_path = "/dev/shm/polydim_linux_posix_shm.dat"

    with open(shm_path, "wb") as f:
        f.write(b'\x00' * total_bytes)

    f_master = open(shm_path, "r+b")
    mmap_master = mmap.mmap(f_master.fileno(), total_bytes)

    c_buf_master = (ctypes.c_uint8 * total_bytes).from_buffer(mmap_master)
    buf_ptr = ctypes.c_void_p(ctypes.addressof(c_buf_master))
    lib.polydim_pmtp_init(buf_ptr)

    # 1. Test Single-Process Fast Roundtrip
    print("\n[LINUX TEST 1] Single Process Zero-Copy /dev/shm Write & Read (D=1,000,000)...")
    test_tensor = np.full(D, 42.0, dtype=np.float64)

    slot = ctypes.c_uint64(0)
    lib.polydim_pmtp_begin_write(buf_ptr, ctypes.byref(slot))
    s = slot.value
    offset = 64 + s * tensor_bytes

    t0 = time.perf_counter_ns()
    dest = np.frombuffer(mmap_master, dtype=np.float64, count=D, offset=offset)
    np.copyto(dest, test_tensor)
    del dest
    lib.polydim_pmtp_commit_write(buf_ptr, s)
    t_write = (time.perf_counter_ns() - t0) / 1000.0

    # Read back
    slot_out = ctypes.c_uint64(0)
    ticket_out = ctypes.c_uint64(0)
    has_data = lib.polydim_pmtp_acquire_read(buf_ptr, ctypes.byref(slot_out), ctypes.byref(ticket_out))
    assert has_data == 1, "Failed to acquire read on Linux shm"

    t0 = time.perf_counter_ns()
    src = np.frombuffer(mmap_master, dtype=np.float64, count=D, offset=64 + slot_out.value * tensor_bytes)
    read_copy = np.copy(src)
    del src
    rc = lib.polydim_pmtp_validate_read(buf_ptr, slot_out.value, ticket_out.value)
    t_read = (time.perf_counter_ns() - t0) / 1000.0

    assert rc == 0, "Seqlock validation failed on Linux"
    assert np.all(read_copy == 42.0), "Data corruption detected on Linux /dev/shm"

    print(f"  -> Write 8 MB to /dev/shm: {t_write:.2f} us ({ (8.0 / (t_write*1e-6)) / 1024.0 :.2f} GB/s)")
    print(f"  -> Read 8 MB from /dev/shm: {t_read:.2f} us ({ (8.0 / (t_read*1e-6)) / 1024.0 :.2f} GB/s)")
    print(f"  -> Verification: 100% Bitwise Exact Match, 0 Torn Reads (Exit Code 0).")

    # 2. Multi-Process Saturation Test on Linux
    print("\n[LINUX TEST 2] Multi-Process Concurrency Stress (4 Concurrent Readers, 1 Writer)...")
    CYCLES = 3000

    def linux_writer(shm_file, cycles):
        try:
            f = open(shm_file, "r+b")
            mm = mmap.mmap(f.fileno(), total_bytes)
            c_buf = (ctypes.c_uint8 * total_bytes).from_buffer(mm)
            b_ptr = ctypes.c_void_p(ctypes.addressof(c_buf))
            l_lib = load_linux_lib()
            t_arr = np.empty(D, dtype=np.float64)
            for c in range(cycles):
                t_arr.fill(float(c + 1))
                sl = ctypes.c_uint64(0)
                l_lib.polydim_pmtp_begin_write(b_ptr, ctypes.byref(sl))
                off = 64 + sl.value * tensor_bytes
                view = np.frombuffer(mm, dtype=np.float64, count=D, offset=off)
                np.copyto(view, t_arr)
                del view
                l_lib.polydim_pmtp_commit_write(b_ptr, sl.value)
                if c % 200 == 0:
                    time.sleep(0.0005)
            del c_buf
            mm.close()
            f.close()
        except Exception:
            import traceback
            traceback.print_exc()

    def linux_reader(shm_file, duration, v_ok, v_torn, r_id):
        try:
            f = open(shm_file, "r+b")
            mm = mmap.mmap(f.fileno(), total_bytes)
            c_buf = (ctypes.c_uint8 * total_bytes).from_buffer(mm)
            b_ptr = ctypes.c_void_p(ctypes.addressof(c_buf))
            l_lib = load_linux_lib()
            ok_count = 0
            torn_count = 0
            t_end = time.time() + duration
            while time.time() < t_end:
                sl = ctypes.c_uint64(0)
                tk = ctypes.c_uint64(0)
                if l_lib.polydim_pmtp_acquire_read(b_ptr, ctypes.byref(sl), ctypes.byref(tk)) == 1:
                    off = 64 + sl.value * tensor_bytes
                    view = np.frombuffer(mm, dtype=np.float64, count=D, offset=off)
                    arr = np.copy(view)
                    del view
                    if l_lib.polydim_pmtp_validate_read(b_ptr, sl.value, tk.value) == 0:
                        v0 = arr[0]
                        if v0 > 0.0:
                            if arr[-1] != v0 or not np.all(arr == v0):
                                torn_count += 1
                            else:
                                ok_count += 1
                time.sleep(0.00001)
            with v_ok.get_lock():
                v_ok.value += ok_count
            with v_torn.get_lock():
                v_torn.value += torn_count
            del c_buf
            mm.close()
            f.close()
        except Exception:
            import traceback
            traceback.print_exc()

    val_ok = multiprocessing.Value('i', 0)
    val_torn = multiprocessing.Value('i', 0)
    readers = [multiprocessing.Process(target=linux_reader, args=(shm_path, 5.0, val_ok, val_torn, i)) for i in range(4)]
    writer = multiprocessing.Process(target=linux_writer, args=(shm_path, CYCLES))

    for r in readers: r.start()
    time.sleep(0.05)
    writer.start()
    writer.join()
    for r in readers: r.join()

    total_ok = val_ok.value
    total_torn = val_torn.value

    print(f"\n[LINUX TOTALS] Atomic Reads: {total_ok} | Torn Reads: {total_torn}")
    assert total_torn == 0 and total_ok > 0, f"Linux Multi-Process PMTP Test FAILED (total_ok={total_ok})"
    print("-> [CERTIFIED] LINUX NATIVE /dev/shm 4-SLOT SEQLOCK AIR TIGHT (Exit Code 0).")

    del buf_ptr, c_buf_master
    mmap_master.close()
    f_master.close()
    try:
        os.remove(shm_path)
    except Exception:
        pass

    os.makedirs("kaggle_output", exist_ok=True)
    with open("kaggle_output/linux_shm_results.json", "w") as f:
        json.dump({"status": "PASS", "atomic_reads": total_ok, "torn_reads": total_torn}, f)

if __name__ == "__main__":
    run_linux_shm_benchmark()
