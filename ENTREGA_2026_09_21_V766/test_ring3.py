# ============================================================================
# POLYDIM V765 — TEST RING 3: HIGH-FREQUENCY ASYMPTOTIC DESTRUCTION (10 kHz)
# D=1,000,000 (8 MB Tensor) | Concurrency Stress | Zero Torn Reads | Memory Barrier Saturation
# ============================================================================

import os
import sys
import time
import multiprocessing
import numpy as np

if sys.platform == "win32":
    os.add_dll_directory(r'E:\winlibs_gcc14_zip\mingw64\bin')

DIR_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(DIR_PATH)

from polydim_v764_monolito import PMTPSlabChannel

DLL_PATH = os.path.join(DIR_PATH, "build", "libpolydim.dll")
if not os.path.exists(DLL_PATH):
    DLL_PATH = os.path.join(DIR_PATH, "build", "libpolydim.so")

D_STRESS = 1000000  # 1 Million Dimensions (8 MB)
CYCLES = 5000

def brutal_writer(tag, cycles, dll_path):
    """Brutal Writer: Pumps 8 MB tensors at maximum bandwidth with rotating patterns."""
    channel = PMTPSlabChannel(tag, D_STRESS, dll_path, create=True)
    buf = np.empty(D_STRESS, dtype=np.float64)
    
    t0 = time.perf_counter()
    for c in range(cycles):
        # Fill buffer with identifiable pattern (val = c + 1.0 everywhere)
        buf.fill(float(c + 1))
        channel.write_tensor(buf)
    
    dt = time.perf_counter() - t0
    rate = cycles / dt
    throughput_gb = (cycles * 8.0) / (dt * 1024.0)
    print(f"[WRITER] {cycles} Cycles finished in {dt:.2f}s | Rate: {rate:.1f} writes/s | Bandwidth: {throughput_gb:.2f} GB/s")
    channel.close()

def adversarial_reader(tag, reader_id, duration_sec, dll_path, result_queue):
    """Adversarial Reader: Hammers the shared slab, checking for any partial / torn read."""
    channel = PMTPSlabChannel(tag, D_STRESS, dll_path, create=False)
    
    reads_ok = 0
    torn_detected = 0
    
    t_end = time.time() + duration_sec
    while time.time() < t_end:
        tensor = channel.read_tensor()
        if tensor is not None:
            # The tensor MUST be uniform: first element == last element == all elements
            val0 = tensor[0]
            if val0 > 0.0:
                # Fast check: all elements equal to val0
                if tensor[-1] != val0 or tensor[D_STRESS // 2] != val0 or not np.all(tensor == val0):
                    torn_detected += 1
                else:
                    reads_ok += 1
                    
    channel.close()
    result_queue.put((reader_id, reads_ok, torn_detected))

if __name__ == "__main__":
    print(f"\n============================================================================")
    print(f"POLYDIM V765 — TEST RING 3: HIGH-FREQUENCY STRESS TEST (D={D_STRESS:,} / 8 MB)")
    print(f"============================================================================")
    
    tag_stress = "ring3_asymptotic_stress"
    
    # Pre-create master channel
    master = PMTPSlabChannel(tag_stress, D_STRESS, DLL_PATH, create=True)
    
    queue = multiprocessing.Queue()
    duration = 5.0 # 5 seconds of maximum saturation
    
    num_readers = 4
    readers = [
        multiprocessing.Process(target=adversarial_reader, args=(tag_stress, i, duration, DLL_PATH, queue))
        for i in range(num_readers)
    ]
    
    writer = multiprocessing.Process(target=brutal_writer, args=(tag_stress, CYCLES, DLL_PATH))
    
    for r in readers:
        r.start()
    writer.start()
    
    writer.join()
    for r in readers:
        r.join()
        
    total_reads = 0
    total_torn = 0
    while not queue.empty():
        rid, rok, rtorn = queue.get()
        total_reads += rok
        total_torn += rtorn
        print(f"-> Reader {rid}: {rok:,} atomic reads verified | {rtorn} torn reads")
        
    print(f"\n=== RESULTADOS ANILLO 3 ===")
    print(f"Total Lecturas Atómicas Exitosas: {total_reads:,}")
    print(f"Total Desgarros de Memoria (Torn Reads): {total_torn}")
    
    if total_torn == 0 and total_reads > 0:
        print("-> TEST RING 3 PASSED: Zero-Copy PMTP Triple-Buffer Air Tight Under Saturation (Exit Code 0).")
    else:
        print("-> TEST RING 3 FAILED: Memory Tear Detected!")
        sys.exit(1)
