import subprocess, sys, os

cwd = r"E:\POLYDIM_EINSOF"

# Check git status
st_proc = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=cwd)
print("GIT STATUS SHORT:")
print(st_proc.stdout)

if not st_proc.stdout.strip():
    print("[GIT] Repositorio limpio, nada nuevo para commitear. Sincronizacion 2:00 AM al dia [OK].")
else:
    subprocess.run(["git", "add", "-f", "ENTREGA_2026_09_18_V753/"], cwd=cwd)
    subprocess.run(["git", "add", "-f", "contexto_historico_V753.md"], cwd=cwd)
    subprocess.run(["git", "add", "POLYDIM_STATE_LEDGER.json"], cwd=cwd)

    diff_proc = subprocess.run(["git", "diff", "--cached"], capture_output=True, cwd=cwd)
    diff_bytes = diff_proc.stdout.lower()

    leak_found = False
    for token in [b"ghp_", b"sk-ant", b"sk-proj", b"gsk_", b"hf_", b"aq.ab8", b"password", b"api_keys_pool"]:
        if token in diff_bytes:
            print(f"[ALERTA REGLA 14] Fuga detectada: '{token.decode()}' - Abortando")
            leak_found = True

    if not leak_found and diff_bytes.strip():
        subprocess.run(["git", "commit", "-m", "V753: Daily 2:00 AM Sync Iteration 2"], cwd=cwd)
        subprocess.run(["git", "push", "origin", "master"], cwd=cwd)
        print("[GIT] Push completado exitosamente.")
    else:
        print("[GIT] No hay cambios en staging o staging vacio.")
