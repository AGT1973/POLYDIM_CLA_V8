"""
POLYDIM — MODO NOCTURNO 2AM
Ejecutar: python e:\POLYDIM_EINSOF\nightly_2am.py
Horario: 02:00 AM todos los dias con trabajo pendiente
"""

import subprocess, sys, os, datetime, time

LOG = f"e:\\POLYDIM_EINSOF\\nightly_{datetime.date.today()}_02-00.log"

def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def run(cmd, cwd="e:\\POLYDIM_EINSOF"):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if r.stdout.strip(): log(r.stdout.strip()[:500])
    if r.stderr.strip(): log("STDERR: " + r.stderr.strip()[:300])
    return r.returncode

log("="*50)
log("POLYDIM MODO NOCTURNO — INICIO")
log("="*50)

# ── 1. GIT: COMMIT Y PUSH DE TODO ────────────────────────────
log("\n[GIT] Verificando estado...")
run("git status --short")

log("[GIT] Inspeccionando diff antes de commit (Regla 14 anti-leak)...")
rc = run("git diff --cached --name-only")

log("[GIT] Agregando entregas V741 con -f (ignoradas en .gitignore)...")
run("git add -f ENTREGA_2026_09_17_V741/")
run("git add -f REPORTES/SOTA_FlashAttention_vs_POLYDIM_2026_09_17.md")
run("git add POLYDIM_MEMORIA_PERMANENTE.md")

# Verificar que no hay API keys en el diff
diff_check = subprocess.run(
    "git diff --cached", shell=True, capture_output=True, text=True,
    cwd="e:\\POLYDIM_EINSOF"
)
for bad_word in ["ghp_", "sk-", "api_key", "password", "secret"]:
    if bad_word in diff_check.stdout.lower():
        log(f"[ALERTA REGLA 14] POSIBLE API KEY DETECTADA: {bad_word} — ABORTANDO PUSH")
        sys.exit(1)

log("[GIT] Commit V741...")
run('git commit -m "V741: Rodrigues Rank-2 + silicon tests 5/5 PASS + y_comp budget + E0 fix + cross-platform pragma"')

log("[GIT] Push a origin (POLYDIM_CLA_V5)...")
rc_push = run("git push origin master")
if rc_push == 0:
    log("[GIT] Push exitoso a GitHub ✓")
else:
    log("[GIT] Push fallido — verificar conectividad o token")

# ── 2. KAGGLE BENCHMARK ───────────────────────────────────────
log("\n[KAGGLE] Subiendo benchmark_linux_v741.py a Kaggle...")
# El MCP kaggle no puede llamarse desde Python directamente en modo nocturno
# Se deja instruccion para que el agente lo ejecute via MCP al despertar
log("[KAGGLE] PENDIENTE: ejecutar via MCP kaggle_run_benchmark al amanecer")
log("[KAGGLE] Script: e:\\POLYDIM_EINSOF\\ENTREGA_2026_09_17_V741\\benchmark_linux_v741.py")
log("[KAGGLE] Accelerator: GPU T4")

# ── 3. CONTEXTO HISTORICO V741 ────────────────────────────────
log("\n[CONTEXTO] Escribiendo contexto_historico_v741.md...")
ctx = f"""# CHECKPOINT HANDOFF — POLYDIM V741
Generado: {datetime.datetime.now().isoformat()}

## Estado
- V741 compilado y verificado en silicio (5/5 PASS)
- C++ DLL: kernel_cpp_v741.dll (MSVC /fp:precise)
- Rust DLL: kernel_rust_v741.dll (rustc 1.98.1)
- Nuevo: verify_ycomp_budget_f64 — budget ||y_comp||_inf <= 50*D*eps
- Nuevo: POLYDIM_MAX_D = 2^32 guard en todas las funciones
- Pragma: cross-platform (float_control MSVC / FP_CONTRACT OFF GCC)

## Pendiente URGENTE
1. Ejecutar benchmark GPU en Kaggle (benchmark_linux_v741.py) — Chart 1
2. Completar README honesto con entorno + log real
3. Agregar LICENSE (MIT)
4. Actualizar PERMANENT_MEMORY.md global

## Aprendizajes clave
- IAs sin contexto de entorno asumen Linux/GCC — siempre incluir entorno en README
- GPU solo en Colab/Kaggle — con 50+4 cuentas no hay excusa para no benchmarkear
- Modo nocturno nunca fue realmente usado — este script es el primer paso real
"""
with open("e:\\POLYDIM_EINSOF\\REPORTES\\contexto_historico_v741.md", "w", encoding="utf-8") as f:
    f.write(ctx)
log("[CONTEXTO] contexto_historico_v741.md escrito")

# ── 4. RESUMEN FINAL ──────────────────────────────────────────
log("\n" + "="*50)
log("MODO NOCTURNO COMPLETADO")
log(f"LOG: {LOG}")
log("PENDIENTE MANANA: kaggle_run_benchmark via MCP")
log("="*50)
