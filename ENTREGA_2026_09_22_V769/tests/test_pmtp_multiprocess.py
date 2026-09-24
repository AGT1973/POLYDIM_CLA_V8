"""
POLYDIM V769 — MULTIPROCESS PMTP ZERO-COPY IPC VERIFICATION SUITE
===================================================================
Tests real multi-process OS memory sharing via native SeqLock & SharedMemory.
Proves zero torn reads, zero deadlocks, and zero data corruptions under 
concurrent cross-process execution without 1D tokenization.

Part of the CI gate to terminate the 600-iteration failure cycle.
"""

import sys
import os
import time
import math
import ctypes
import numpy as np
import multiprocessing as mp
from multiprocessing import shared_memory

# Determine test environment paths
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TEST_DIR)
AUDIT_DIR = os.path.join(ROOT_DIR, "auditoria_externa")
DLL_DIR = AUDIT_DIR if os.path.exists(os.path.join(AUDIT_DIR, "polydim_kernel.dll")) else ROOT_DIR

# --- STRUCT DEFINITIONS ---

class PMTPControl(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("magic", ctypes.c_uint32),
        ("num_slots", ctypes.c_uint32),
        ("payload_bytes", ctypes.c_uint64),
        ("pub_seq", ctypes.c_uint64),
        ("pub_slot", ctypes.c_uint32),
        ("wlock", ctypes.c_uint32),
        ("wticket", ctypes.c_uint32),
        ("reserved_", ctypes.c_uint8 * 28)
    ]

def load_binding(dll_dir):
    if sys.platform == "win32":
        mingw_bin = r"E:\winlibs_gcc14_zip\mingw64\bin"
        if os.path.exists(mingw_bin):
            try:
                os.add_dll_directory(mingw_bin)
            except Exception:
                pass
        try:
            os.add_dll_directory(dll_dir)
        except Exception:
            pass
            
    c_dll_path = os.path.join(dll_dir, "polydim_kernel.dll")
    lib = ctypes.CDLL(c_dll_path, winmode=0 if sys.platform == "win32" else None)
    
    lib.polydim_pmtp_sizeof.argtypes = [ctypes.c_uint32, ctypes.c_uint64]
    lib.polydim_pmtp_sizeof.restype = ctypes.c_uint64
    
    lib.polydim_pmtp_alignof.restype = ctypes.c_uint64
    
    lib.polydim_pmtp_init.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32, ctypes.c_uint64]
    lib.polydim_pmtp_init.restype = ctypes.c_int32
    
    lib.polydim_pmtp_payload_offset.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32]
    lib.polydim_pmtp_payload_offset.restype = ctypes.c_uint64
    
    lib.polydim_pmtp_write_begin.argtypes = [ctypes.POINTER(PMTPControl), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint64)]
    lib.polydim_pmtp_write_begin.restype = ctypes.c_int32
    
    lib.polydim_pmtp_write_commit.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32, ctypes.c_uint64]
    lib.polydim_pmtp_write_commit.restype = None
    
    lib.polydim_pmtp_write_abort.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32, ctypes.c_uint64]
    lib.polydim_pmtp_write_abort.restype = None
    
    lib.polydim_pmtp_read_begin.argtypes = [ctypes.POINTER(PMTPControl), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint64)]
    lib.polydim_pmtp_read_begin.restype = ctypes.c_int32
    
    lib.polydim_pmtp_read_validate.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32, ctypes.c_uint64]
    lib.polydim_pmtp_read_validate.restype = ctypes.c_int32
    
    return lib

# ==============================================================================
# WORKER PROCESSES (OS-LEVEL CONCURRENCY)
# ==============================================================================

def writer_process_func(shm_name, dll_path, d, num_slots, num_writes, aligned_offset):
    """OS Process: Writes D-dimensional tensors directly to physical shared memory."""
    lib = load_binding(dll_path)
    shm = shared_memory.SharedMemory(name=shm_name)
    raw_addr = ctypes.cast(ctypes.c_char_p(ctypes.addressof(ctypes.c_char.from_buffer(shm.buf))), ctypes.c_void_p).value
    ctrl_addr = raw_addr + aligned_offset
    ctrl = ctypes.cast(ctrl_addr, ctypes.POINTER(PMTPControl))
    
    slot_out = ctypes.c_uint32(0)
    ver_out = ctypes.c_uint64(0)
    
    # Pre-generate tensor template
    tensor_scratch = np.zeros(d, dtype=np.float64)
    
    for i in range(1, num_writes + 1):
        rc = lib.polydim_pmtp_write_begin(ctrl, ctypes.byref(slot_out), ctypes.byref(ver_out))
        if rc != 0:
            time.sleep(0.0001)
            continue
            
        slot = slot_out.value
        off = lib.polydim_pmtp_payload_offset(ctrl, slot)
        
        # Construct unified payload with monotonic identity
        # Coherence signature: element[j] = float(i) + j * 1e-9
        tensor_scratch.fill(float(i))
        tensor_scratch[-1] = float(i) * 2.0  # End-marker for torn-read detection
        
        # Zero-copy write directly to shared memory slab
        slot_view = np.ndarray((d,), dtype=np.float64, buffer=shm.buf, offset=aligned_offset + off)
        np.copyto(slot_view, tensor_scratch)
        
        lib.polydim_pmtp_write_commit(ctrl, slot, ver_out.value)
        
        # High-frequency burst with small yield
        if i % 100 == 0:
            time.sleep(0.001)
            
    shm.close()

def reader_process_func(shm_name, dll_path, d, num_slots, reader_id, duration_sec, aligned_offset, results_queue):
    """OS Process: Reads and validates tensors from physical shared memory under contention."""
    lib = load_binding(dll_path)
    shm = shared_memory.SharedMemory(name=shm_name)
    raw_addr = ctypes.cast(ctypes.c_char_p(ctypes.addressof(ctypes.c_char.from_buffer(shm.buf))), ctypes.c_void_p).value
    ctrl_addr = raw_addr + aligned_offset
    ctrl = ctypes.cast(ctrl_addr, ctypes.POINTER(PMTPControl))
    
    slot_out = ctypes.c_uint32(0)
    ver_out = ctypes.c_uint64(0)
    local_tensor = np.empty(d, dtype=np.float64)
    
    reads = 0
    success = 0
    races = 0
    corruptions = 0
    
    t_end = time.time() + duration_sec
    
    while time.time() < t_end:
        reads += 1
        rc = lib.polydim_pmtp_read_begin(ctrl, ctypes.byref(slot_out), ctypes.byref(ver_out))
        if rc != 0:
            if rc == -3:
                races += 1
            time.sleep(0.00005)
            continue
            
        slot = slot_out.value
        ver = ver_out.value
        off = lib.polydim_pmtp_payload_offset(ctrl, slot)
        
        # Read from physical slab
        slot_view = np.ndarray((d,), dtype=np.float64, buffer=shm.buf, offset=aligned_offset + off)
        np.copyto(local_tensor, slot_view)
        
        rc_val = lib.polydim_pmtp_read_validate(ctrl, slot, ver)
        if rc_val != 0:
            races += 1
            continue
            
        # Verify internal payload coherence (Anti-Torn-Read verification)
        val = local_tensor[0]
        expected_end = val * 2.0
        
        if not np.all(local_tensor[:-1] == val) or local_tensor[-1] != expected_end:
            corruptions += 1
        else:
            success += 1
            
        time.sleep(0.00002)
        
    shm.close()
    results_queue.put({
        "reader_id": reader_id,
        "reads": reads,
        "success": success,
        "races": races,
        "corruptions": corruptions
    })

# ==============================================================================
# MULTIPROCESS TEST RUNNER
# ==============================================================================

def run_multiprocess_pmtp_test():
    print("=" * 80)
    print("🏛️ POLYDIM V769 — MULTIPROCESS PMTP ZERO-COPY IPC STRESS TEST")
    print("=" * 80)
    
    D = 10000
    NUM_SLOTS = 4
    NUM_READERS = 3
    NUM_WRITES = 2000
    TEST_DURATION = 3.5  # seconds
    SHM_NAME = f"polydim_pmtp_ci_{os.getpid()}"
    
    lib = load_binding(DLL_DIR)
    payload_bytes = D * 8
    total_sz = lib.polydim_pmtp_sizeof(NUM_SLOTS, payload_bytes)
    assert total_sz > 0, "Invalid total_sz from polydim_pmtp_sizeof"
    
    print(f"  Configuration: D={D} ({payload_bytes / 1024:.1f} KB/slot) | Slots={NUM_SLOTS} | Total Slab={total_sz / 1024:.1f} KB")
    print(f"  Concurrency: 1 Writer OS Process + {NUM_READERS} Reader OS Processes")
    
    # Allocate SharedMemory with 64-byte padding for strict alignment
    shm_alloc_sz = total_sz + 64
    try:
        old_shm = shared_memory.SharedMemory(name=SHM_NAME)
        old_shm.close()
        old_shm.unlink()
    except Exception:
        pass
        
    shm = shared_memory.SharedMemory(create=True, name=SHM_NAME, size=shm_alloc_sz)
    
    # Compute 64-byte aligned offset
    raw_addr = ctypes.cast(ctypes.c_char_p(ctypes.addressof(ctypes.c_char.from_buffer(shm.buf))), ctypes.c_void_p).value
    aligned_addr = (raw_addr + 63) & ~63
    aligned_offset = aligned_addr - raw_addr
    
    ctrl = ctypes.cast(aligned_addr, ctypes.POINTER(PMTPControl))
    rc_init = lib.polydim_pmtp_init(ctrl, NUM_SLOTS, payload_bytes)
    assert rc_init == 0, f"polydim_pmtp_init failed: {rc_init}"
    print(f"  [PMTP_INIT] Slab initialized at aligned offset {aligned_offset} | rc={rc_init}")
    
    # Spawn OS processes
    results_queue = mp.Queue()
    readers = []
    
    for r_id in range(NUM_READERS):
        p = mp.Process(
            target=reader_process_func,
            args=(SHM_NAME, DLL_DIR, D, NUM_SLOTS, r_id, TEST_DURATION, aligned_offset, results_queue)
        )
        p.start()
        readers.append(p)
        
    writer = mp.Process(
        target=writer_process_func,
        args=(SHM_NAME, DLL_DIR, D, NUM_SLOTS, NUM_WRITES, aligned_offset)
    )
    writer.start()
    
    print(f"  Processes launched. Running concurrent stress test for {TEST_DURATION}s...")
    
    writer.join(timeout=TEST_DURATION + 5.0)
    for p in readers:
        p.join(timeout=5.0)
        
    # Collect results
    total_reads = 0
    total_success = 0
    total_races = 0
    total_corruptions = 0
    
    while not results_queue.empty():
        res = results_queue.get()
        total_reads += res["reads"]
        total_success += res["success"]
        total_races += res["races"]
        total_corruptions += res["corruptions"]
        print(f"    * Reader {res['reader_id']}: {res['reads']} reads | {res['success']} validated | {res['races']} races | {res['corruptions']} corruptions")
        
    # Cleanup shared memory
    shm.close()
    shm.unlink()
    
    success_rate = (total_success / (total_success + total_races) * 100.0) if (total_success + total_races) > 0 else 0.0
    
    print("-" * 80)
    print(f"  TOTALS: Reads={total_reads} | Validated={total_success} | Races Handled={total_races} | Corruptions={total_corruptions}")
    print(f"  Validation Success Rate: {success_rate:.2f}% (Target: >90%)")
    print(f"  Data Integrity: {'PERFECT (0 TORN READS)' if total_corruptions == 0 else 'CORRUPTED'}")
    print("-" * 80)
    
    # Strict Assertions for CI Gate
    assert total_corruptions == 0, f"FATAL: Memory corruption detected! {total_corruptions} torn reads!"
    assert total_success > 500, f"Too few successful reads: {total_success} (starvation/deadlock suspected)"
    assert success_rate >= 90.0, f"Success rate below target: {success_rate:.2f}%"
    
    print("✅ MULTIPROCESS PMTP TEST PASSED WITH EXIT CODE 0")
    print("=" * 80)

if __name__ == "__main__":
    # Required for Windows multiprocessing spawn
    mp.freeze_support()
    run_multiprocess_pmtp_test()
