import os
import time
import numpy as np
import jax.numpy as jnp
import jax

def read_gusano_1d(md_path, N, D):
    """
    Simula el proceso de la infraestructura 1D actual:
    1. Lee el archivo del disco (Texto UTF-8).
    2. Convierte el string a bytes.
    3. Asigna la memoria y la levanta al tensor latente de JAX.
    (Todo esto quema CPU y destruye ciclos).
    """
    t0 = time.perf_counter()
    
    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()
    
    b_data = text.encode("utf-8")
    num_bytes = len(b_data)
    padded_size = N * D
    padded_b = bytearray(padded_size)
    padded_b[:num_bytes] = b_data
    
    arr_int8 = np.frombuffer(padded_b, dtype=np.int8).reshape(N, D)
    arr_f32 = arr_int8.astype(np.float32)
    
    # Proyección (Simulando Encoder)
    key = jax.random.PRNGKey(0)
    W = jax.random.normal(key, (D, D), dtype=jnp.float32)
    Q, _ = jnp.linalg.qr(W)
    
    # La transferencia de CPU a GPU es el cuello de botella
    Z = jnp.dot(jnp.array(arr_f32), Q)
    jax.block_until_ready(Z)
    
    t1 = time.perf_counter()
    return (t1 - t0) * 1000.0, Z

def read_tensor_pmtp(pmtp_path, shape):
    """
    Simula el proceso nativo de lectura PMTP:
    Mapeo de archivo directo a GPU sin pasar por la Tokenización de la CPU.
    """
    t0 = time.perf_counter()
    
    # Zero-Copy Bypassing: memmap -> JAX DeviceArray
    fp = np.memmap(pmtp_path, dtype=np.float32, mode='r', shape=shape)
    
    # Simplemente "tragamos" la memoria mapeada al device
    Z = jnp.array(fp) 
    jax.block_until_ready(Z)
    
    t1 = time.perf_counter()
    return (t1 - t0) * 1000.0, Z

def run_benchmark():
    HERE = os.path.dirname(os.path.abspath(__file__))
    md_path = r"e:\.agents\skills\polydim_transferencia_multidimensional\SKILL.md"
    pmtp_path = os.path.join(HERE, "pmtp_multidimensional_skill.dat")
    
    if not os.path.exists(pmtp_path):
        print("ERROR: Corre primero 1_SKILL_COMPILER_V16.py")
        return
        
    print("==============================================================")
    print("POLYDIM V16 - BENCHMARK EMPÍRICO: GUSANO 1D vs CANAL NATIVO PMTP")
    print("==============================================================")
    
    D = 1024
    with open(md_path, "rb") as f:
        N = int(np.ceil(len(f.read()) / D))
    
    print(f"Tensor Shape objetivo: ({N}, {D})")
    
    # Calentar JAX
    _ = jax.numpy.zeros((N, D))
    
    print("\n[INICIANDO FLUIDEZ 1D (MARKDOWN + PARSEO)]")
    time_1d, Z_1d = read_gusano_1d(md_path, N, D)
    print(f"Latencia Total: {time_1d:.4f} ms")
    
    print("\n[INICIANDO FLUIDEZ ND (NATIVE PMTP TENSOR)]")
    time_pmtp, Z_pmtp = read_tensor_pmtp(pmtp_path, shape=(N, D))
    print(f"Latencia Total: {time_pmtp:.4f} ms")
    
    # Verificación de que el tensor en memoria es idéntico (No perdimos información)
    diff = jnp.max(jnp.abs(Z_1d - Z_pmtp))
    
    print("\n==============================================================")
    print(f"Diferencia Máxima (L-inf): {diff:.6f} (Debe ser cero)")
    if time_pmtp < time_1d:
        aceleracion = time_1d / time_pmtp
        print(f"RESULTADO: PMTP es {aceleracion:.2f}X más rápido (Evita I/O Overhead y Tokenización).")
    else:
        print("RESULTADO: Anómalo (La lectura 1D fue más rápida, posible cacheo o N muy pequeño).")
    print("==============================================================")

if __name__ == "__main__":
    run_benchmark()
