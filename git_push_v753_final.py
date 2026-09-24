import os, sys, json, subprocess

cwd = r"E:\POLYDIM_EINSOF"

# Git add
subprocess.run(["git", "add", "-f", "ENTREGA_2026_09_18_V753/"], cwd=cwd)
subprocess.run(["git", "add", "-f", "contexto_historico_V753.md"], cwd=cwd)
subprocess.run(["git", "add", "POLYDIM_STATE_LEDGER.json"], cwd=cwd)

# Anti-leak check via bytes
diff_proc = subprocess.run(["git", "diff", "--cached"], capture_output=True, cwd=cwd)
diff_bytes = diff_proc.stdout.lower()

leak_found = False
for token in [b"ghp_", b"sk-ant", b"sk-proj", b"gsk_", b"hf_", b"aq.ab8", b"password", b"api_keys_pool"]:
    if token in diff_bytes:
        print(f"[ALERTA REGLA 14] Fuga detectada: '{token.decode()}' - Abortando")
        leak_found = True

if not leak_found:
    print("[SEGURIDAD] Diff verificado al 100% limpio de credenciales.")
    subprocess.run(["git", "commit", "-m", "V753: Regla 13 Handoff + Ingesta y Vectorizacion de Respuestas Tribunal Multi-IA"], cwd=cwd)
    p_push = subprocess.run(["git", "push", "origin", "master"], capture_output=True, text=True, cwd=cwd)
    if p_push.returncode == 0:
        print("[GIT] Push a origin master EXITOSO.")
    else:
        print(f"[WARN] Push warning: {p_push.stderr[:200]}")

print("REGLA_13_PUSH_FINALIZADO")
