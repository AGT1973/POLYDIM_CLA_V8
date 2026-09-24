import os
import time
import numpy as np
import jax.numpy as jnp
import jax

def compile_md_to_pmtp(md_path, pmtp_path, D=1024):
    """
    Compila un archivo 1D (Markdown) a un Tensor ND (PMTP).
    Representa el colapso inverso: de la interfaz humana a la memoria nativa.
    """
    if not os.path.exists(md_path):
        print(f"Error: {md_path} no encontrado.")
        return
        
    print(f"[{time.strftime('%H:%M:%S')}] Iniciando Compilación de Skill MD -> PMTP...")
    
    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()
    
    # 1. Transformación Estructural (Texto -> Flujo de Bytes)
    b_data = text.encode("utf-8")
    num_bytes = len(b_data)
    
    # 2. Asignación a Espacio Euclidiano Discreto
    N = int(np.ceil(num_bytes / D))
    padded_size = N * D
    padded_b = bytearray(padded_size)
    padded_b[:num_bytes] = b_data
    
    # 3. Elevación al Espacio Latente
    print(f"[{time.strftime('%H:%M:%S')}] Elevando {num_bytes} bytes a una variedad R^({N}x{D})...")
    arr_int8 = np.frombuffer(padded_b, dtype=np.int8).reshape(N, D)
    arr_f32 = arr_int8.astype(np.float32)
    
    # Simulación de un Feature Extractor (Ortogonalización aleatoria vía Cayley/Hodge)
    key = jax.random.PRNGKey(0)
    W = jax.random.normal(key, (D, D), dtype=jnp.float32)
    Q, _ = jnp.linalg.qr(W) # Matriz Ortogonal Unitaria
    
    # 4. Proyección Tensorial y Flush a Memmap C-backend (Directo a IO)
    Z = jnp.dot(jnp.array(arr_f32), Q)
    Z_np = np.asarray(Z)
    
    print(f"[{time.strftime('%H:%M:%S')}] Flusheando Tensor Latente (Size: {Z_np.nbytes / 1024:.2f} KB) a: {pmtp_path}")
    fp = np.memmap(pmtp_path, dtype=np.float32, mode='w+', shape=Z_np.shape)
    fp[:] = Z_np[:]
    fp.flush()
    del fp
    
    print(f"[{time.strftime('%H:%M:%S')}] [OK] PMTP SKILL CREADA CON EXITO.")

if __name__ == "__main__":
    HERE = os.path.dirname(os.path.abspath(__file__))
    # Simulamos compilar la propia Constitución de POLYDIM (la que creé en V15)
    md_skill = r"e:\.agents\skills\polydim_transferencia_multidimensional\SKILL.md"
    pmtp_skill = os.path.join(HERE, "pmtp_multidimensional_skill.dat")
    compile_md_to_pmtp(md_skill, pmtp_skill, D=1024)
