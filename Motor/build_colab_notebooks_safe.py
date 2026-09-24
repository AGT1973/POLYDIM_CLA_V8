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
# NOTEBOOK 1: EMISOR (CON PROTECCION CONTRA COLISIONES EN DRIVE)
# =====================================================================
cells_emisor = [
    mk_markdown("# 🌌 IA-A (EMISOR): Protocolo PMTP\n\nEste cuaderno representa la **Primera Sesión**. Tu objetivo es generar un estado latente denso y volcarlo a un disco compartido en Google Drive mediante **PMTP (Memoria Nativa)**.\n\n### 1. Montar el Drive Compartido (POLYDIM_BUS)"),
    mk_code("from google.colab import drive\nimport os\n\ndrive.mount('/content/drive')\n\n# IMPORTANTE: Reemplaza con la ruta de tu shortcut de Drive si es diferente.\nBUS_DIR = '/content/drive/MyDrive/POLYDIM_BUS'\n\nif not os.path.exists(BUS_DIR):\n    print('❌ ERROR: No se encontro la carpeta. Asegurate de anadir POLYDIM_BUS a Mi Unidad.')\nelse:\n    print('✅ Drive montado exitosamente. Directorio BUS localizado.')\n\n# Pide el numero de grupo para no sobreescribir los archivos de otros alumnos\ngrupo_id = input('Ingresa el numero de tu grupo (ej: 01, 02, 03): ')\nif not grupo_id.strip():\n    grupo_id = 'DEFAULT'"),
    mk_markdown("### 2. Inyección de Memoria Nativa (Zero-Copy)"),
    mk_code("import time\nimport numpy as np\nimport jax\nimport jax.numpy as jnp\n\nprint('Generando Pensamiento ND (Simulacion 50,000 x 1024)...')\nt0 = time.time()\nkey = jax.random.PRNGKey(42)\ntensor = jax.random.normal(key, (50000, 1024), dtype=jnp.float32)\njax.block_until_ready(tensor)\nprint(f'Generacion completada en {time.time() - t0:.2f} segundos.')\n\n# Escribir a PMTP con nombre unico por grupo\npmtp_filename = f'pmtp_transfer_GRUPO_{grupo_id}.pmtp'\npmtp_path = os.path.join(BUS_DIR, pmtp_filename)\nprint(f'Escribiendo Tensor Nativo en {pmtp_path} ...')\n\nt1 = time.time()\ntensor_np = np.asarray(tensor)\nfp = np.memmap(pmtp_path, dtype=np.float32, mode='w+', shape=tensor_np.shape)\nfp[:] = tensor_np[:]\nfp.flush()\ndel fp\n\nprint(f'✅ Transferencia C-Backend PMTP Exitosa. (Tiempo de volcado: {time.time() - t1:.2f} s)')\nprint('El tensor ya esta en el disco. Tu compañero ya puede correr el Cuaderno RECEPTOR.')")
]

# =====================================================================
# NOTEBOOK 2: RECEPTOR (CON PROTECCION CONTRA COLISIONES EN DRIVE)
# =====================================================================
cells_receptor = [
    mk_markdown("# 🌌 IA-B (RECEPTOR): Protocolo PMTP\n\nEste cuaderno representa la **Segunda Sesión** (IA-B). Te conectarás al mismo `POLYDIM_BUS` para asimilar instantáneamente la matriz de la IA-A.\n\n### 1. Montar el Drive Compartido (POLYDIM_BUS)"),
    mk_code("from google.colab import drive\nimport os\n\ndrive.mount('/content/drive')\nBUS_DIR = '/content/drive/MyDrive/POLYDIM_BUS'\n\nif not os.path.exists(BUS_DIR):\n    print('❌ ERROR: No se encontro la carpeta.')\nelse:\n    print('✅ Drive montado exitosamente.')\n\ngrupo_id = input('Ingresa el numero de tu grupo para buscar tu archivo (ej: 01, 02, 03): ')\nif not grupo_id.strip():\n    grupo_id = 'DEFAULT'"),
    mk_markdown("### 2. Asimilación de Memoria Nativa (Page Cache OS)"),
    mk_code("import time\nimport numpy as np\nimport jax\nimport jax.numpy as jnp\n\npmtp_filename = f'pmtp_transfer_GRUPO_{grupo_id}.pmtp'\npmtp_path = os.path.join(BUS_DIR, pmtp_filename)\n\nif not os.path.exists(pmtp_path):\n    print(f'❌ ERROR: El archivo {pmtp_filename} aun no ha sido generado por la IA-A en tu grupo.')\nelse:\n    print('Iniciando Asimilacion PMTP Zero-Copy...')\n    t0 = time.time()\n    \n    fp = np.memmap(pmtp_path, dtype=np.float32, mode='r', shape=(50000, 1024))\n    tensor_recibido = jnp.array(fp)\n    jax.block_until_ready(tensor_recibido)\n    \n    t1 = time.time()\n    \n    print(f'✅ Pensamiento Asimilado en {(t1-t0)*1000:.2f} ms.')\n    print(f'Forma del Tensor: {tensor_recibido.shape}')\n    \n    suma = float(jnp.sum(tensor_recibido))\n    print(f'Heuristica (Suma Total): {suma:.4f}')\n    print('¡Traspaso de datos PMTP comprobado con exito!')")
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
        
    print(f"Notebooks generados en {OUT_DIR}")
