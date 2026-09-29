import sys
import multiprocessing.shared_memory as shm

def create_slab(name, file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    size = len(data)
    try:
        shared = shm.SharedMemory(name=name, create=True, size=size)
    except FileExistsError:
        shared = shm.SharedMemory(name=name)
        if shared.size < size:
            shared.close()
            shared.unlink()
            shared = shm.SharedMemory(name=name, create=True, size=size)
    shared.buf[:size] = data
    print(f"SLAB_ID: {name}, TENSOR_READY (Size: {size})")
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def read_slab(name, size, output_path):
    shared = shm.SharedMemory(name=name)
    data = bytes(shared.buf[:int(size)])
    with open(output_path, 'wb') as f:
        f.write(data)
    print(f"SLAB_ID: {name} read and saved to {output_path}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python pmtp_slab_tool.py [create|read] ...")
        sys.exit(1)
    
    cmd = sys.argv[1]
    if cmd == 'create':
        create_slab(sys.argv[2], sys.argv[3])
    elif cmd == 'read':
        read_slab(sys.argv[2], int(sys.argv[3]), sys.argv[4])
