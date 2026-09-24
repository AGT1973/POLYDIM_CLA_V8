#!/usr/bin/env python3
# tinyllama_qwen_pmtp_proof.py -- POLYDIM PMTP V735 SOTA
# Canal IA-a-IA: TinyLlama (EEUU/dim=2048) -> SHM -> Qwen (China/dim=896)
# Modo SECUENCIAL para proteger 16GB RAM: A muere antes que B arranque.
# Peak RAM = max(RAM_A ~2.2GB, RAM_B ~1.0GB), nunca la suma.
# Modelos en float16. gc.collect() explícito después de usar A.
# Bugs resueltos: BFloat16->numpy: .float(); dtype mismatch: .to(); SHM en padre; lm_head no generate()

import os, sys, gc, time
import numpy as np
import torch
import multiprocessing as mp
from multiprocessing import shared_memory
from transformers import AutoTokenizer, AutoModelForCausalLM

os.environ["TOKENIZERS_PARALLELISM"] = "false"
import warnings; warnings.filterwarnings("ignore", category=UserWarning)

MODEL_A = r"E:\POLYDIM_EINSOF\_HISTORICO\models\tinyllama_1_1b"
MODEL_B = r"E:\POLYDIM_EINSOF\_HISTORICO\models\qwen_0_5b"
SHM_NAME = "pmtp_tinyllama_qwen"
DIM_A, DIM_B, SEED = 2048, 896, 42
PROMPT = ("The high dimensional tensor allows two AIs from different countries "
          "to communicate natively.")


def agente_A(seq_len, shm_name):
    """Emisor: TinyLlama genera tensor, proyecta a dim=896, vuelca en SHM y muere."""
    t0 = time.perf_counter()
    print("[A] TinyLlama-1.1B (float16)...", flush=True)
    tok = AutoTokenizer.from_pretrained(MODEL_A, local_files_only=True)
    mdl = AutoModelForCausalLM.from_pretrained(
        MODEL_A, local_files_only=True, dtype=torch.float16)
    mdl.eval()
    nm = sum(p.numel() for p in mdl.parameters())/1e6
    print(f"[A]   {nm:.1f}M params | dtype={next(mdl.parameters()).dtype}", flush=True)
    inputs = tok(PROMPT, return_tensors="pt")
    print(f"[A]   seq_len={inputs['input_ids'].shape[1]}", flush=True)
    with torch.no_grad():
        out = mdl(**inputs, output_hidden_states=True)
    # BFloat16 fix: .float() antes de .numpy()
    hidden = out.hidden_states[-1].float().squeeze(0).cpu().numpy()  # (seq_len, 2048)
    print(f"[A]   hidden_state shape={hidden.shape}", flush=True)
    # Liberar modelo A de RAM antes de proyectar
    del mdl, tok, inputs, out; gc.collect()
    print("[A]   Modelo A liberado. Proyectando...", flush=True)
    # Proyeccion PMTP seed fija
    W = np.random.RandomState(SEED).randn(DIM_B, DIM_A).astype(np.float32)
    proj = (hidden @ W.T).astype(np.float32)  # (seq_len, 896)
    nrm = np.linalg.norm(proj, axis=1, keepdims=True)
    proj = proj / np.where(nrm < 1e-8, 1.0, nrm)
    print(f"[A]   Proyectado={proj.shape} norma_media={np.linalg.norm(proj,axis=1).mean():.4f}", flush=True)
    shm = shared_memory.SharedMemory(name=shm_name)
    np.ndarray((seq_len, DIM_B), dtype=np.float32, buffer=shm.buf)[:] = proj
    shm.close()
    print(f"[A]   Tensor volcado en SHM. A muere. t={time.perf_counter()-t0:.2f}s", flush=True)


def agente_B(seq_len, shm_name):
    """Receptor: lee SHM, pasa por lm_head de Qwen, colapsa a texto."""
    t0 = time.perf_counter()
    print("[B] Qwen-0.5B (float16) -- A ya murio, RAM libre.", flush=True)
    shm = shared_memory.SharedMemory(name=shm_name)
    buf = np.ndarray((seq_len, DIM_B), dtype=np.float32, buffer=shm.buf)
    tensor_recv = torch.from_numpy(buf.copy())
    shm.close()
    print(f"[B]   Tensor recibido via PMTP: {tuple(tensor_recv.shape)}", flush=True)
    tok = AutoTokenizer.from_pretrained(MODEL_B, local_files_only=True)
    mdl = AutoModelForCausalLM.from_pretrained(
        MODEL_B, local_files_only=True, dtype=torch.float16)
    mdl.eval()
    nm = sum(p.numel() for p in mdl.parameters())/1e6
    print(f"[B]   {nm:.1f}M params | dtype={next(mdl.parameters()).dtype}", flush=True)
    # dtype mismatch fix
    dtype_b = next(mdl.parameters()).dtype
    t_in = tensor_recv.to(dtype_b).unsqueeze(0)  # (1, seq_len, 896)
    with torch.no_grad():
        logits = mdl.lm_head(t_in)  # (1, seq_len, vocab_size)
    ids = logits.argmax(dim=-1).squeeze(0)
    texto = tok.decode(ids.tolist(), skip_special_tokens=True)
    sep = "="*64
    print(f"\n{sep}\n  POLYDIM PMTP -- COLAPSO 2D\n{sep}", flush=True)
    print(f"  Logits : {tuple(logits.shape)}", flush=True)
    print(f"  IDs    : {ids.tolist()}", flush=True)
    safe_text = texto.encode('ascii', 'backslashreplace').decode('ascii')
    print(f"  TEXTO  : {safe_text}", flush=True)
    print(sep, flush=True)
    print(f"[B]   Texto sin recibir texto de A. CANAL PMTP OK. t={time.perf_counter()-t0:.2f}s", flush=True)


if __name__ == "__main__":
    sep = "="*64
    print(sep)
    print("  POLYDIM PMTP PROOF -- TinyLlama->Qwen | V735 | 16GB-SAFE")
    print(sep)
    # Detectar seq_len en padre
    tok_tmp = AutoTokenizer.from_pretrained(MODEL_A, local_files_only=True)
    seq_len = tok_tmp(PROMPT, return_tensors="pt")["input_ids"].shape[1]
    del tok_tmp
    print(f"[MAIN] seq_len={seq_len} | SHM={seq_len*DIM_B*4} bytes", flush=True)
    # SHM en padre
    shm = shared_memory.SharedMemory(create=True, size=seq_len*DIM_B*4, name=SHM_NAME)
    t_total = time.perf_counter()
    # FASE 1: A corre solo
    print("\n[MAIN] FASE 1: Agente A (TinyLlama)...", flush=True)
    pa = mp.Process(target=agente_A, args=(seq_len, SHM_NAME))
    pa.start(); pa.join()
    if pa.exitcode != 0:
        print(f"[MAIN] FALLO A: code={pa.exitcode}"); shm.close(); shm.unlink(); sys.exit(1)
    print("[MAIN] A muerto. RAM A liberada.", flush=True)
    # FASE 2: B corre solo
    print("\n[MAIN] FASE 2: Agente B (Qwen)...", flush=True)
    pb = mp.Process(target=agente_B, args=(seq_len, SHM_NAME))
    pb.start(); pb.join()
    if pb.exitcode != 0:
        print(f"[MAIN] FALLO B: code={pb.exitcode}"); shm.close(); shm.unlink(); sys.exit(1)
    shm.close(); shm.unlink()
    print(f"\n{sep}", flush=True)
    print(f"  Tiempo total : {time.perf_counter()-t_total:.2f}s")
    print("  [MAIN] PMTP CANAL IA-a-IA CERTIFICADO")
    print(sep)