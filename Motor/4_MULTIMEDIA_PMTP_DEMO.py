import os
import time
import struct
import numpy as np
import jax.numpy as jnp
import jax
import multiprocessing as mp
import glob

D_DIM = 1024
BUS_DIR = r"I:\Mi unidad\POLYDIM_BUS\DEMO_PMTP\bus"
SEND_DIR = r"I:\Mi unidad\POLYDIM_BUS\DEMO_PMTP\send"
RECEIVE_DIR = r"I:\Mi unidad\POLYDIM_BUS\DEMO_PMTP\receive"

def encode_and_send(file_path):
    filename = os.path.basename(file_path)
    print(f"[EMISOR] Asimilando {filename} a matriz ND...")
    
    with open(file_path, "rb") as f:
        file_bytes = f.read()
        
    file_size = len(file_bytes)
    
    # Header format: 256 bytes name (utf-8 padded), 8 bytes size (Q)
    name_bytes = filename.encode("utf-8")
    if len(name_bytes) > 256:
        raise ValueError("Filename too long")
    
    header = bytearray(264)
    header[:len(name_bytes)] = name_bytes
    header[256:264] = struct.pack('<Q', file_size)
    
    total_bytes = header + file_bytes
    total_len = len(total_bytes)
    
    N = int(np.ceil(total_len / D_DIM))
    padded_size = N * D_DIM
    
    padded_b = bytearray(padded_size)
    padded_b[:total_len] = total_bytes
    
    # Convert to 1D then reshape
    arr_int8 = np.frombuffer(padded_b, dtype=np.int8).reshape(N, D_DIM)
    arr_f32 = arr_int8.astype(np.float32)
    
    # We could do orthogonal projection here but for lossless demo we just send the normalized bytes
    # as float32 tensors (simulating latent features)
    Z = jnp.array(arr_f32)
    jax.block_until_ready(Z)
    Z_np = np.asarray(Z)
    
    pmtp_path = os.path.join(BUS_DIR, f"pmtp_{filename}.pmtp")
    fp = np.memmap(pmtp_path, dtype=np.float32, mode='w+', shape=Z_np.shape)
    fp[:] = Z_np[:]
    fp.flush()
    del fp
    
    print(f"[EMISOR] -> Tensor de {N}x{D_DIM} enviado por PMTP.")

def ia_a_emisor():
    os.makedirs(BUS_DIR, exist_ok=True)
    files = glob.glob(os.path.join(SEND_DIR, "*"))
    
    if not files:
        print("[EMISOR] Carpeta send vacia. Nada que enviar.")
        return
        
    for f in files[:10]: # max 10
        t0 = time.perf_counter()
        encode_and_send(f)
        t1 = time.perf_counter()
        print(f"[EMISOR] Envio completado en {(t1-t0)*1000:.2f} ms.\n")
        time.sleep(1.5) # Simulate processing gap
        
    print("[EMISOR] Todas las transferencias completadas.")

def ia_b_receptor():
    os.makedirs(BUS_DIR, exist_ok=True)
    os.makedirs(RECEIVE_DIR, exist_ok=True)
    print("[RECEPTOR] Bucle de Asimilación PMTP Iniciado. Esperando matrices en el BUS...")
    
    processed = set()
    timeout = 15 # Stop after 15 seconds of inactivity
    idle_time = 0
    
    while idle_time < timeout:
        dat_files = glob.glob(os.path.join(BUS_DIR, "*.pmtp"))
        found_new = False
        
        for pmtp_path in dat_files:
            if pmtp_path in processed:
                continue
                
            found_new = True
            idle_time = 0
            
            # Read shape (we can calculate N from filesize since we know dtype is float32 and D=1024)
            file_size_bytes = os.path.getsize(pmtp_path)
            N = file_size_bytes // (4 * D_DIM) # 4 bytes per float32
            
            t0 = time.perf_counter()
            fp = np.memmap(pmtp_path, dtype=np.float32, mode='r', shape=(N, D_DIM))
            Z = jnp.array(fp)
            jax.block_until_ready(Z)
            
            # Reconstruction
            Z_np = np.asarray(Z)
            arr_int8 = Z_np.astype(np.int8)
            raw_bytes = arr_int8.tobytes()
            
            # Parse header
            header = raw_bytes[:264]
            # Name is null terminated
            name_end = header[:256].find(b'\x00')
            if name_end == -1: name_end = 256
            original_name = header[:name_end].decode('utf-8')
            
            original_size = struct.unpack('<Q', header[256:264])[0]
            
            file_data = raw_bytes[264:264+original_size]
            
            out_path = os.path.join(RECEIVE_DIR, original_name)
            with open(out_path, "wb") as out_f:
                out_f.write(file_data)
                
            t1 = time.perf_counter()
            print(f"[RECEPTOR] Asimilado: {original_name} (Tam: {original_size} bytes)")
            print(f"[RECEPTOR] Reconstruido en {(t1-t0)*1000:.2f} ms.\n")
            
            processed.add(pmtp_path)
            
            # Delete tensor after receiving to keep bus clean
            try:
                del fp
                os.remove(pmtp_path)
            except:
                pass

        if not found_new:
            time.sleep(1)
            idle_time += 1
            
    print(f"[RECEPTOR] Bucle terminado tras {timeout}s de inactividad.")

if __name__ == "__main__":
    print("==============================================================")
    print("POLYDIM V16 - DEMO MULTIMEDIA PMTP (TRACK CORPORATIVO)")
    print("==============================================================")
    
    p2 = mp.Process(target=ia_b_receptor)
    p2.start()
    
    time.sleep(1) # Let receiver start listening
    
    p1 = mp.Process(target=ia_a_emisor)
    p1.start()
    
    p1.join()
    p2.join()
    print("Simulación concluida.")
