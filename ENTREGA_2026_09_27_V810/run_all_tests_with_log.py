import os
import sys
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

test_scripts = [
    "test_v810_abi_and_ipc.py",
    "test_v810_quantum_and_honesty.py",
    "test_v810_adversarial_destructive.py",
    "test_graph_cuda.py",
    "test_v810_ipc_suite.py"
]

log_lines = []
log_lines.append("================================================================================")
log_lines.append(f"POLYDIM V810 PHYSICAL SILICON VALIDATION LOG — {time.strftime('%Y-%m-%d %H:%M:%S')}")
log_lines.append(f"Host: AMD APU x86_64, Windows, MinGW GCC 14.2.0, Rustc 1.98.1")
log_lines.append("================================================================================\n")

all_passed = True

for script in test_scripts:
    print(f"▶ Ejecutando {script}...")
    log_lines.append(f"--------------------------------------------------------------------------------")
    log_lines.append(f"EXEC: python {script}")
    log_lines.append(f"START: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_lines.append(f"--------------------------------------------------------------------------------")
    
    t0 = time.perf_counter()
    res = subprocess.run([sys.executable, script], capture_output=True, text=True)
    dt = time.perf_counter() - t0
    
    log_lines.append(res.stdout)
    if res.stderr:
        log_lines.append("[STDERR]:\n" + res.stderr)
    log_lines.append(f"EXIT CODE: {res.returncode} (Elapsed: {dt:.3f} s)\n")
    
    if res.returncode != 0:
        print(f"❌ {script} falló con Exit Code {res.returncode}")
        all_passed = False
    else:
        print(f"✅ {script} completado con Exit Code 0 ({dt:.3f} s)")

log_lines.append("================================================================================")
if all_passed:
    log_lines.append("CERTIFICACIÓN FINAL: 5/5 SUITES PASSED — EXIT CODE 0 — CERO ERRORES")
else:
    log_lines.append("CERTIFICACIÓN FINAL: FALLO DETECTADO")
log_lines.append("================================================================================")

log_content = "\n".join(log_lines)

out_path = os.path.join(BASE_DIR, "auditoria_externa", "05_LOG_RAW_TESTS.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(log_content)

print(f"\n📄 Log completo guardado en: {out_path}")
if not all_passed:
    sys.exit(1)
print("🎯 TODAS LAS PRUEBAS EN SILICIO REAL CERTIFICADAS CON EXIT CODE 0.")
