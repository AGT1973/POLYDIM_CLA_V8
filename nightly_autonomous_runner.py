import os, sys, time, json, urllib.request, subprocess

print("================================================================================")
print("     POLYDIM V753 - RUNNER NOCTURNO AUTONOMO (100 RONDAS ADVERSARIALES)         ")
print("================================================================================")

log_path = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_18_V753\nightly_rounds.log"
pool_file = r"C:\Users\eluithi\.gemini\config\api_keys_pool.json"

with open(pool_file, "r") as f:
    pool = json.load(f)

groq_keys = pool.get("groq_keys", [])
key_idx = 0

def get_groq_response(prompt):
    global key_idx
    for attempt in range(len(groq_keys)):
        k = groq_keys[(key_idx + attempt) % len(groq_keys)]
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = json.dumps({
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are the Chief Red Team Critic for high-dimensional mathematics and low-level C++/CUDA/Rust systems. Seek failure modes, asymptotic traps, and FFI bugs."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 2048
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={
            "Authorization": f"Bearer {k}",
            "Content-Type": "application/json"
        })
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                key_idx = (key_idx + attempt + 1) % len(groq_keys)
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            time.sleep(1)
            continue
    return None

prompt_base = """[POLYDIM V753 - ADVERSARIAL DRILL ROUND]
Target: High-dimensional unit sphere S^{D-1} (D=10^7), Fused 2-Pass Rodrigues Geodesic, Higham Thm 4.3 calibrated Rust Guard, SEQLock with epoch parity validation, and Riemannian Adam with Parallel Transport.

Identify any unaddressed mathematical bug, subnormal flush anomaly, or FFI race condition. If none remain, explicitly state 'ZERO CRITICAL DEFECTS'."""

with open(log_path, "a", encoding="utf-8") as log:
    log.write(f"\n=== INICIO BUCLE NOCTURNO 100 RONDAS: {time.ctime()} ===\n")

print("[NIGHT MODE] Iniciando bucle continuo de 100 rondas...")

for round_num in range(1, 101):
    t0 = time.perf_counter()
    # 1. Ejecutar prueba física en silicio nativo
    test_proc = subprocess.run([sys.executable, r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_18_V753\raw_silicon_benchmark_v753.py"], capture_output=True, text=True)
    silicon_ok = (test_proc.returncode == 0) and ("PASS" in test_proc.stdout)
    
    # 2. Consultar al Tribunal Adversarial (Groq LPU LLaMA 3.3 70B / DeepSeek)
    response = get_groq_response(prompt_base)
    t_elapsed = time.perf_counter() - t0
    
    with open(log_path, "a", encoding="utf-8") as log:
        log.write(f"--- RONDA {round_num:03d} [{time.strftime('%H:%M:%S')}] (Silicon: {'OK' if silicon_ok else 'FAIL'}) (Time: {t_elapsed:.2f}s) ---\n")
        if response:
            summary_line = response.strip().split("\n")[0][:120]
            log.write(f"Verdict: {summary_line}\n\n")
        else:
            log.write("Verdict: Rate-limit or network timeout on key pool\n\n")
            
    print(f"Ronda {round_num:03d}/100 completada | Silicon: {'OK' if silicon_ok else 'FAIL'} | Tiempo: {t_elapsed:.2f}s")
    time.sleep(2)

with open(log_path, "a", encoding="utf-8") as log:
    log.write(f"=== CIERRE BUCLE NOCTURNO: {time.ctime()} ===\n")

print("[NIGHT MODE] 100 Rondas concluidas exitosamente.")
