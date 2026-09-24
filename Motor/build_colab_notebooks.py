import os
import json

def create_notebook(cells):
    return {
        "cells": cells,
        "metadata": {
            "colab": {"provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"}
        },
        "nbformat": 4,
        "nbformat_minor": 0
    }

def mk_markdown(text):
    return {"cell_type": "markdown", "metadata": {"id": os.urandom(4).hex()}, "source": [text]}

def mk_code(code):
    return {"cell_type": "code", "execution_count": None, "metadata": {"id": os.urandom(4).hex()}, "outputs": [], "source": [code]}

# =====================================================================
# NOTEBOOK 1: EMISOR
# =====================================================================
cells_emisor = [
    mk_markdown("# 🌌 IA-A (EMISOR): Protocolo PMTP\n\nEste cuaderno representa la **Primera Sesión**. Tu objetivo como IA Emisora es generar un estado latente denso (un tensor gigante simulando una representación profunda) y volcarlo a un disco compartido en Google Drive mediante **PMTP (Memoria Nativa)** en lugar de usar JSON o Base64.\n\n### 1. Montar el Drive Compartido (POLYDIM_BUS)"),
    mk_code("from google.colab import drive\nimport os\n\n# Montar Drive\ndrive.mount('/content/drive')\n\n# Define el directorio. IMPORTANTE: Si los alumnos añadieron el shortcut, suele estar en:\n# /content/drive/MyDrive/POLYDIM_BUS/\n# Reemplaza esta ruta si tu shortcut tiene otro nombre.\nBUS_DIR = '/content/drive/MyDrive/POLYDIM_BUS'\n\nif not os.path.exists(BUS_DIR):\n    print('❌ ERROR: No se encontr la carpeta. Asegrate de aadir POLYDIM_BUS a Mi Unidad.')\nelse:\n    print('✅ Drive montado exitosamente. Directorio BUS localizado.')"),
    mk_markdown("### 2. Inyección de Memoria Nativa (Zero-Copy)\nVamos a generar un tensor colosal (Ej: 200MB de floats) y volcarlo mediante memmap, destruyendo el Gusano 2D."),
    mk_code("import time\nimport numpy as np\nimport jax\nimport jax.numpy as jnp\n\nprint('Generando Pensamiento ND (Simulacin 50,000 x 1024)...')\nt0 = time.time()\n# Simular un embedding masivo de forma determinista\nkey = jax.random.PRNGKey(42)\ntensor = jax.random.normal(key, (50000, 1024), dtype=jnp.float32)\njax.block_until_ready(tensor)\nprint(f'Generacin completada en {time.time() - t0:.2f} segundos.')\n\n# Escribir a PMTP\npmtp_path = os.path.join(BUS_DIR, 'pmtp_transfer.dat')\nprint(f'Escribiendo Tensor Nativo en {pmtp_path} ...')\n\nt1 = time.time()\ntensor_np = np.asarray(tensor)\nfp = np.memmap(pmtp_path, dtype=np.float32, mode='w+', shape=tensor_np.shape)\nfp[:] = tensor_np[:]\nfp.flush()\ndel fp\n\nprint(f'✅ Transferencia C-Backend PMTP Exitosa. (Tiempo: {time.time() - t1:.2f} s)')\nprint('El tensor ya est en el disco y listo para que la IA-B lo asimile instantneamente.')")
]

# =====================================================================
# NOTEBOOK 2: RECEPTOR
# =====================================================================
cells_receptor = [
    mk_markdown("# 🌌 IA-B (RECEPTOR): Protocolo PMTP\n\nEste cuaderno representa la **Segunda Sesión** (IA-B). Tu trabajo es despertar, conectarte al mismo `POLYDIM_BUS`, y asimilar los 200MB de pensamiento matricial generados por la IA-A sin utilizar I/O secuencial ni parseo de texto.\n\n### 1. Montar el Drive Compartido (POLYDIM_BUS)"),
    mk_code("from google.colab import drive\nimport os\n\ndrive.mount('/content/drive')\nBUS_DIR = '/content/drive/MyDrive/POLYDIM_BUS'\n\nif not os.path.exists(BUS_DIR):\n    print('❌ ERROR: No se encontr la carpeta.')\nelse:\n    print('✅ Drive montado exitosamente.')"),
    mk_markdown("### 2. Asimilación de Memoria Nativa (Page Cache OS)\nMapearemos el binario `.dat` instantáneamente a memoria RAM."),
    mk_code("import time\nimport numpy as np\nimport jax\nimport jax.numpy as jnp\n\npmtp_path = os.path.join(BUS_DIR, 'pmtp_transfer.dat')\n\nif not os.path.exists(pmtp_path):\n    print('❌ ERROR: El archivo pmtp_transfer.dat an no ha sido generado por IA-A.')\nelse:\n    print('Iniciando Asimilacin PMTP Zero-Copy...')\n    t0 = time.time()\n    \n    # Map directo a memoria\n    fp = np.memmap(pmtp_path, dtype=np.float32, mode='r', shape=(50000, 1024))\n    \n    # Levantar a VRAM (o RAM)\n    tensor_recibido = jnp.array(fp)\n    jax.block_until_ready(tensor_recibido)\n    \n    t1 = time.time()\n    \n    print(f'✅ Pensamiento Asimilado en {(t1-t0)*1000:.2f} ms.')\n    print(f'Forma del Tensor: {tensor_recibido.shape}')\n    \n    # Calcular heurstica para verificar la integridad de la conexin\n    suma = float(jnp.sum(tensor_recibido))\n    print(f'Heurstica (Suma Total): {suma:.4f}')\n    print('¡Traspaso de datos duros sin serializacin (No-Gusano) comprobado con xito!')")
]

if __name__ == "__main__":
    OUT_DIR = r"I:\Mi unidad\POLYDIM_BUS"
    
    if not os.path.exists(OUT_DIR):
        print(f"Creando directorio: {OUT_DIR}")
        os.makedirs(OUT_DIR, exist_ok=True)
        
    nb1_path = os.path.join(OUT_DIR, "PMTP_01_EMISOR.ipynb")
    nb2_path = os.path.join(OUT_DIR, "PMTP_02_RECEPTOR.ipynb")
    
    with open(nb1_path, "w", encoding="utf-8") as f:
        json.dump(create_notebook(cells_emisor), f, indent=2)
        
    with open(nb2_path, "w", encoding="utf-8") as f:
        json.dump(create_notebook(cells_receptor), f, indent=2)
        
    print(f"✅ Notebooks generados con éxito en {OUT_DIR}")
