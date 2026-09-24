#!/usr/bin/env python3
# tinyllama_qwen_pmtp_parallel.py -- POLYDIM PMTP V735
# Ejecucion PARALELA (float16) - 16GB SAFE.
# Ambos agentes vivos simultaneamente sincronizados por Barrier.
# Toda la salida es capturada a pmtp_parallel.log

import os, sys, time
import numpy as np
import torch
import multiprocessing as mp
from multiprocessing import shared_memory
from transformers import AutoTokenizer, AutoModelForCausalLM

os.environ["TOKENIZERS_PARALLELISM"] = "false"
import warnings; warnings.filterwarnings("ignore", category=UserWarning)

MODEL_A = r"E:\POLYDIM_EINSOF\_HISTORICO\models\tinyllama_1_1b"
MODEL_B = r"E:\POLYDIM_EINSOF\_HISTORICO\models\qwen_0_5b"
SHM_NAME = "pmtp_parallel_shm"
LOG_FILE = "pmtp_parallel.log"
DIM_A, DIM_B, SEED = 2048, 896, 42
PROMPT = "The high dimensional tensor allows two AIs from different countries to communicate natively."

def log_msg(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

def agente_A(seq_len, barrier):
    log_msg("[A] Iniciando TinyLlama-1.1B en paralelo (float16)...")
    tok = AutoTokenizer.from_pretrained(MODEL_A, local_files_only=True)
    mdl = AutoModelForCausalLM.from_pretrained(
        MODEL_A, local_files_only=True, dtype=torch.float16)
    mdl.eval()
    
    log_msg("[A] TinyLlama listo. Esperando a Qwen en la barrera...")
    barrier.wait()  # Sincroniza inicio exacto con B
    
    t0 = time.perf_counter()
    inputs = tok(PROMPT, return_tensors="pt")
    with torch.no_grad():
        out = mdl(**inputs, output_hidden_states=True)
    
    hidden = out.hidden_states[-1].float().squeeze(0).cpu().numpy()
    # Cargar W semantica entrenada por Procrustes/Ridge
    try:
        W = np.load("W_aligned.npy").astype(np.float32)  # (2048, 896)
        proj = (hidden @ W).astype(np.float32)          # (seq_len, 2048) @ (2048, 896) -> (seq_len, 896)
        log_msg("[A] Matriz W_aligned.npy cargada con éxito. Aplicando traducción topológica.")
    except Exception as e:
        log_msg(f"[A] WARNING: No se encontro W_aligned.npy, usando RANDOM. Error: {e}")
        W = np.random.RandomState(SEED).randn(DIM_B, DIM_A).astype(np.float32)
        proj = (hidden @ W.T).astype(np.float32)
    nrm = np.linalg.norm(proj, axis=1, keepdims=True)
    proj = proj / np.where(nrm < 1e-8, 1.0, nrm)
    
    shm = shared_memory.SharedMemory(name=SHM_NAME)
    np.ndarray((seq_len, DIM_B), dtype=np.float32, buffer=shm.buf)[:] = proj
    shm.close()
    
    log_msg(f"[A] Tensor PMTP volcado en SHM. Avisando a B... (t={time.perf_counter()-t0:.2f}s)")
    barrier.wait()  # Libera a B para que lea
    log_msg("[A] Mision cumplida. A sale.")

def agente_B(seq_len, barrier):
    log_msg("[B] Iniciando Qwen-0.5B en paralelo (float16)...")
    tok = AutoTokenizer.from_pretrained(MODEL_B, local_files_only=True)
    mdl = AutoModelForCausalLM.from_pretrained(
        MODEL_B, local_files_only=True, dtype=torch.float16)
    mdl.eval()
    
    log_msg("[B] Qwen listo. Esperando a TinyLlama en la barrera...")
    barrier.wait()  # Sincroniza inicio con A
    
    log_msg("[B] Esperando a que A procese y envíe el tensor...")
    t0 = time.perf_counter()
    barrier.wait()  # Espera a que A termine de escribir
    
    shm = shared_memory.SharedMemory(name=SHM_NAME)
    buf = np.ndarray((seq_len, DIM_B), dtype=np.float32, buffer=shm.buf)
    tensor_recv = torch.from_numpy(buf.copy())
    shm.close()
    
    log_msg(f"[B] Tensor atrapado via PMTP en vivo: {tuple(tensor_recv.shape)}")
    
    dtype_b = next(mdl.parameters()).dtype
    t_in = tensor_recv.to(dtype_b).unsqueeze(0)
    with torch.no_grad():
        logits = mdl.lm_head(t_in)
    
    ids = logits.argmax(dim=-1).squeeze(0)
    texto = tok.decode(ids.tolist(), skip_special_tokens=True)
    safe_text = texto.encode("ascii", "backslashreplace").decode("ascii")
    
    out = []
    out.append("="*64)
    out.append("  POLYDIM PMTP -- PARALELO EN VIVO (COLAPSO 2D)")
    out.append("="*64)
    out.append(f"  Logits : {tuple(logits.shape)}")
    out.append(f"  TEXTO  : {safe_text}")
    out.append("="*64)
    out.append(f"[B] Colapso certificado SIN texto intermedio. (t={time.perf_counter()-t0:.2f}s)")
    log_msg(chr(10).join(out))

if __name__ == "__main__":
    if os.path.exists(LOG_FILE): os.remove(LOG_FILE)
    log_msg("================================================================")
    log_msg("  ARRANCANDO SWARM POLYDIM -- 2 IAS PARALELAS (FLOAT16)")
    log_msg("================================================================")
    
    tok_tmp = AutoTokenizer.from_pretrained(MODEL_A, local_files_only=True)
    seq_len = tok_tmp(PROMPT, return_tensors="pt")["input_ids"].shape[1]
    del tok_tmp
    
    shm = shared_memory.SharedMemory(create=True, size=seq_len*DIM_B*4, name=SHM_NAME)
    barrier = mp.Barrier(2)
    
    pa = mp.Process(target=agente_A, args=(seq_len, barrier))
    pb = mp.Process(target=agente_B, args=(seq_len, barrier))
    
    pa.start(); pb.start()
    pa.join(); pb.join()
    
    shm.close(); shm.unlink()
    log_msg("[MAIN] Memoria compartida limpia. SWARM TERMINADO.")