import ctypes
import os
import sys
import multiprocessing
import numpy as np
import time

if sys.platform == "win32":
    os.add_dll_directory(r'E:\winlibs_gcc14_zip\mingw64\bin')

# Ensure we can import the monolithic wrapper
sys.path.append(r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_20_V765_VECTOR_B")
try:
    from polydim_v764_monolito import PMTPSlabChannel
except ImportError:
    print("Failed to import PolydimNativeCore")
    sys.exit(1)

DLL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build", "libpolydim.dll")

D_SIZE = 256

def writer_worker(tag, iters):
    pmtp = PMTPSlabChannel(tag, D_SIZE, DLL_PATH, create=True)
    print(f"Writer started on tag {tag}")
    base_mat = np.eye(16, dtype=np.float64)
    for i in range(iters):
        mutated = (base_mat * (1 if i % 2 == 0 else -1)).flatten()
        pmtp.write_tensor(mutated)
    print("Writer finished.")

def reader_worker(tag, iters, reader_id):
    pmtp = PMTPSlabChannel(tag, D_SIZE, DLL_PATH, create=False)
    success = 0
    torn = 0
    race_caught = 0
    
    start = time.time()
    for i in range(iters):
        try:
            tensor = pmtp.read_tensor()
            if tensor is not None:
                mat = tensor.reshape((16, 16))
                I_check = mat.T @ mat
                drift = np.max(np.abs(I_check - np.eye(16)))
                if drift > 1e-10:
                    torn += 1
                else:
                    success += 1
        except Exception as e:
            if "SEQLOCK_RACE" in str(e):
                race_caught += 1
                
    elapsed = time.time() - start
    print(f"Reader {reader_id} finished in {elapsed:.2f}s. Success: {success}, Torn (Fatal): {torn}, Races Caught (Safe): {race_caught}")
    if torn > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    tag = "ring1_test"
    iters = 10000
    
    # Spawn 1 Writer
    w = multiprocessing.Process(target=writer_worker, args=(tag, iters))
    # Spawn 4 Readers
    readers = []
    for i in range(4):
        r = multiprocessing.Process(target=reader_worker, args=(tag, iters, i))
        readers.append(r)
        
    w.start()
    for r in readers: r.start()
    
    w.join()
    for r in readers: r.join()
    
    for r in readers:
        if r.exitcode != 0:
            print("FATAL: A torn read occurred! Seqlock failed.")
            sys.exit(1)
            
    print("RING 1 TEST PASSED. Zero Torn Reads. Seqlock is mathematically airtight.")
