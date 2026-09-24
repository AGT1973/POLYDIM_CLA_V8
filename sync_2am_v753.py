import subprocess, sys, os, datetime

log_file = r"E:\POLYDIM_EINSOF\nightly_sync_2am.log"

def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")

log("="*60)
log("  POLYDIM V753 - SINCRONIZACION GITHUB 2:00 AM")
log("="*60)

cwd = r"E:\POLYDIM_EINSOF"

# 1. Agregar archivos de la Entrega V753
log("[GIT] Agregando archivos de entrega V753...")
subprocess.run(["git", "add", "-f", "ENTREGA_2026_09_18_V753/"], cwd=cwd)
subprocess.run(["git", "add", "-f", "POLYDIM_V751/"], cwd=cwd)
subprocess.run(["git", "add", "POLYDIM_STATE_LEDGER.json"], cwd=cwd)

# 2. Verificación Anti-Leak en Staging (Regla 14)
log("[GIT] Escaneando diff en staging contra fuga de credenciales...")
diff_proc = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True, cwd=cwd)
diff_text = diff_proc.stdout.lower()

leak_found = False
for token in ["ghp_", "sk-ant", "sk-proj", "gsk_", "hf_", "aq.ab8", "password", "api_keys_pool"]:
    if token in diff_text:
        log(f"[ALERTA FATAL - REGLA 14] Credencial o archivo prohibido detectado en diff: '{token}'")
        leak_found = True

if leak_found:
    log("[ABORTADO] Se cancela commit y push para proteger la seguridad.")
    sys.exit(1)
else:
    log("[SEGURIDAD] Diff limpio de credenciales y claves API [OK]")

# 3. Commit
commit_msg = "V753: Hardened 2-Pass Fused Geodesic + Higham calibrated Rust Guard + SOTA 10 compendium"
log(f"[GIT] Creando commit: '{commit_msg}'...")
subprocess.run(["git", "commit", "-m", commit_msg], cwd=cwd)

# 4. Push a remotes
log("[GIT] Empujando a origin (master)...")
p_push = subprocess.run(["git", "push", "origin", "master"], capture_output=True, text=True, cwd=cwd)
if p_push.returncode == 0:
    log("[GIT] Push a origin master EXITOSO [OK]")
else:
    log(f"[WARN] Error push origin: {p_push.stderr[:200]}")

log("\n[STATUS] Sincronizacion de las 2:00 AM completada exitosamente.")
