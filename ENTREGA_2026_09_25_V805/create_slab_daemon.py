import time
import sys
from multiprocessing import shared_memory

def main():
    slab_name = sys.argv[1]
    filename = sys.argv[2]
    
    with open(filename, 'rb') as f:
        data = f.read()
        
    try:
        shm = shared_memory.SharedMemory(name=slab_name, create=True, size=len(data))
    except FileExistsError:
        shm = shared_memory.SharedMemory(name=slab_name)
        
    shm.buf[:len(data)] = data
    print(f"SLAB_READY: {slab_name}")
    sys.stdout.flush()
    
    # Hold the memory alive for 1 hour
    time.sleep(3600)

if __name__ == '__main__':
    main()
