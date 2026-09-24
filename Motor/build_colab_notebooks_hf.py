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

cells_emisor = [
    mk_markdown("# 🌌 IA-A (EMISOR): HuggingFace Libre + PMTP\n\nEste cuaderno descarga un modelo libre, realiza una inferencia y empaca la respuesta junto a un video/audio/texto en un solo Latent Tensor (.pmtp)."),
    mk_code("!pip install -q transformers torch jax jaxlib"),
    mk_code("from google.colab import drive\nimport os\ndrive.mount('/content/drive')\nBUS_DIR = '/content/drive/MyDrive/POLYDIM_BUS/DEMO_PMTP/bus'\nos.makedirs(BUS_DIR, exist_ok=True)"),
    mk_markdown("### Inferencia con Hugging Face (Modelo Libre)"),
    mk_code("from transformers import pipeline\nimport time\n\nprint('Descargando modelo ligero libre (GPT2)...')\nt0 = time.time()\ngenerator = pipeline('text-generation', model='gpt2')\nrespuesta_hf = generator('The future of AI communication is', max_length=30, num_return_sequences=1)[0]['generated_text']\nprint(f'\\n[Inferencia HF completada en {time.time()-t0:.2f}s]\\nGenerado: {respuesta_hf}')"),
    mk_markdown("### Empaquetado PMTP (Multimedia + HF Inference)"),
    mk_code("import numpy as np\nimport jax\nimport jax.numpy as jnp\nimport struct\n\n# Simulamos leer multimedia cruda (ej. Video/Audio/Texto)\n# En este demo, la 'multimedia' y la 'respuesta_hf' se empacan juntas.\ndata_payload = respuesta_hf.encode('utf-8')\n\nfile_size = len(data_payload)\nheader = bytearray(264)\nname = b'huggingface_inference.txt'\nheader[:len(name)] = name\nheader[256:264] = struct.pack('<Q', file_size)\n\ntotal_bytes = header + data_payload\nN = int(np.ceil(len(total_bytes) / 1024))\npadded_b = bytearray(N * 1024)\npadded_b[:len(total_bytes)] = total_bytes\n\narr_f32 = np.frombuffer(padded_b, dtype=np.int8).astype(np.float32).reshape(N, 1024)\ntensor = jnp.array(arr_f32)\njax.block_until_ready(tensor)\n\npmtp_path = os.path.join(BUS_DIR, 'pmtp_hf_transfer.pmtp')\nfp = np.memmap(pmtp_path, dtype=np.float32, mode='w+', shape=(N, 1024))\nfp[:] = np.asarray(tensor)[:]\nfp.flush()\ndel fp\n\nprint('✅ Tensor PMTP Multimodal y Libre inyectado en el BUS.')")
]

cells_receptor = [
    mk_markdown("# 🌌 IA-B (RECEPTOR): Asimilación de HuggingFace + Multimedia\n\nEste cuaderno asimila el archivo .pmtp generado por la IA-A."),
    mk_code("from google.colab import drive\nimport os\ndrive.mount('/content/drive')\nBUS_DIR = '/content/drive/MyDrive/POLYDIM_BUS/DEMO_PMTP/bus'\nRECEIVE_DIR = '/content/drive/MyDrive/POLYDIM_BUS/DEMO_PMTP/receive'\nos.makedirs(RECEIVE_DIR, exist_ok=True)"),
    mk_code("import time\nimport numpy as np\nimport jax\nimport jax.numpy as jnp\nimport struct\n\npmtp_path = os.path.join(BUS_DIR, 'pmtp_hf_transfer.pmtp')\nif not os.path.exists(pmtp_path):\n    print('❌ ERROR: Tensor no encontrado.')\nelse:\n    print('Asimilando PMTP...')\n    file_size_bytes = os.path.getsize(pmtp_path)\n    N = file_size_bytes // (4 * 1024)\n    \n    fp = np.memmap(pmtp_path, dtype=np.float32, mode='r', shape=(N, 1024))\n    Z = jnp.array(fp)\n    jax.block_until_ready(Z)\n    \n    raw_bytes = np.asarray(Z).astype(np.int8).tobytes()\n    header = raw_bytes[:264]\n    name_end = header[:256].find(b'\\x00')\n    if name_end == -1: name_end = 256\n    orig_name = header[:name_end].decode('utf-8')\n    orig_size = struct.unpack('<Q', header[256:264])[0]\n    \n    payload = raw_bytes[264:264+orig_size]\n    out_path = os.path.join(RECEIVE_DIR, orig_name)\n    with open(out_path, 'wb') as f:\n        f.write(payload)\n        \n    print(f'✅ Archivo {orig_name} ({orig_size} bytes) reconstruido.')\n    print(f'Contenido Asimilado:\\n{payload.decode(\"utf-8\")}')")
]

if __name__ == "__main__":
    OUT_DIR = r"e:\POLYDIM_FINAL_RELEASE_V17\Motor"
    os.makedirs(OUT_DIR, exist_ok=True)
    
    nb1_path = os.path.join(OUT_DIR, "HF_PMTP_01_EMISOR.ipynb")
    nb2_path = os.path.join(OUT_DIR, "HF_PMTP_02_RECEPTOR.ipynb")
    
    with open(nb1_path, "w", encoding="utf-8") as f:
        json.dump(create_notebook(cells_emisor), f, indent=2)
    with open(nb2_path, "w", encoding="utf-8") as f:
        json.dump(create_notebook(cells_receptor), f, indent=2)
        
    print(f"Notebooks HuggingFace generados en {OUT_DIR}")
