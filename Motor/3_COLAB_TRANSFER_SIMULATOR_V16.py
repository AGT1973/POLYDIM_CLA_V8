import os
import time
import multiprocessing as mp
import numpy as np
import jax.numpy as jnp
import jax

def ia_a_generador(shared_path, N, D):
    """
    Sesión A (Emisor): Crea un Tensor Latente Gigante simulado y lo expone vía PMTP.
    """
    print(f"[IA-A] Despertando en PID: {os.getpid()}")
    print(f"[IA-A] Generando pensamiento latente (Size: {N}x{D}) en CUDA/CPU...")
    
    t0 = time.perf_counter()
    # Generar "pensamiento"
    key = jax.random.PRNGKey(99)
    tensor = jax.random.normal(key, (N, D), dtype=jnp.float32)
    jax.block_until_ready(tensor)
    
    # Exponer vía DLPack o Memmap
    print(f"[IA-A] Escribiendo PMTP sin colapsar a Base64...")
    tensor_np = np.asarray(tensor)
    fp = np.memmap(shared_path, dtype=np.float32, mode='w+', shape=(N, D))
    fp[:] = tensor_np[:]
    fp.flush()
    del fp
    
    t1 = time.perf_counter()
    print(f"[IA-A] Tensor Expuesto en {(t1-t0)*1000:.2f} ms. ¡Adios!")


def ia_b_receptor(shared_path, N, D):
    """
    Sesión B (Receptor): Despierta después, asimila el archivo binario sin parseo de JSON.
    """
    print(f"[IA-B] Despertando en PID: {os.getpid()}")
    
    if not os.path.exists(shared_path):
        print("[IA-B] ERROR: No encontré el pensamiento compartido.")
        return
        
    print(f"[IA-B] Asimilando pensamiento desde PMTP...")
    t0 = time.perf_counter()
    
    # Mapear sin lectura activa (Paging OS)
    fp = np.memmap(shared_path, dtype=np.float32, mode='r', shape=(N, D))
    tensor_recibido = jnp.array(fp)
    jax.block_until_ready(tensor_recibido)
    
    # Calcular alguna heurística para demostrar que el tensor es válido
    suma = float(jnp.sum(tensor_recibido))
    
    t1 = time.perf_counter()
    print(f"[IA-B] Pensamiento Asimilado en {(t1-t0)*1000:.2f} ms.")
    print(f"[IA-B] Forma: {tensor_recibido.shape} | Heurística Sum: {suma:.4f}")
    print("[IA-B] Transferencia multi-sesión exitosa. ¡El gusano 2D ha muerto!")

def run_simulation():
    print("==============================================================")
    print("POLYDIM V16 - SIMULACIÓN DE TRANSFERENCIA ENTRE SESIONES (COLAB)")
    print("==============================================================")
    
    HERE = os.path.dirname(os.path.abspath(__file__))
    shared_path = os.path.join(HERE, "colab_shared_memory.dat")
    
    N, D = 50000, 1024 # Matriz grande (~200 MB en f32)
    
    # 1. Spawn IA-A
    p1 = mp.Process(target=ia_a_generador, args=(shared_path, N, D))
    p1.start()
    p1.join() # Esperar a que la primera sesión termine (ej. termina celda en Colab)
    
    print("...")
    time.sleep(1)
    print("...")
    
    # 2. Spawn IA-B (Completamente aislada, nueva sesión)
    p2 = mp.Process(target=ia_b_receptor, args=(shared_path, N, D))
    p2.start()
    p2.join()
    
    # Limpiar
    if os.path.exists(shared_path):
        os.remove(shared_path)

if __name__ == "__main__":
    run_simulation()
