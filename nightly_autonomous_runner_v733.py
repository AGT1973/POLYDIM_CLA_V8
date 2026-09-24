import os
import time
import json
import datetime
import traceback
import subprocess
from pathlib import Path

def run_stress_loop():
    log_file = Path("E:/POLYDIM_EINSOF/REPORTES/nightly_v733_stress.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # D starts at 1 million, scales up to 100 million
    D_VALUES = [1_000_000, 10_000_000, 50_000_000]
    ITERATIONS = 100
    
    with open(log_file, "a") as f:
        f.write(f"\n[{datetime.datetime.now()}] INICIANDO MODO NOCTURNO V733 (STRESS LOOP)\n")
        f.flush()
        
        script_path = Path("E:/POLYDIM_EINSOF/ENTREGA_2026_09_15_V733_INDUSTRIAL/polydim_v733_monolito.py")
        
        while True:
            for d in D_VALUES:
                try:
                    f.write(f"[{datetime.datetime.now()}] Lanzando benchmark D={d} ...\n")
                    f.flush()
                    
                    # We modify the monolith on the fly or just use env vars. 
                    # But monolith is hardcoded. So we run a sed/replace equivalent or just use a modified copy.
                    # For simplicity, we'll run a custom script if needed, but since we are just looping, 
                    # we can create a temporary runner that imports the monolith.
                    
                    cmd = f"python -c \"import sys; sys.path.append('E:/POLYDIM_EINSOF/ENTREGA_2026_09_15_V733_INDUSTRIAL'); import polydim_v733_monolito as mono; mono.D={d}; mono.ITERATIONS={ITERATIONS}; mono.main()\""
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        # Scan for drift
                        f.write(f"[{datetime.datetime.now()}] EXITOSO D={d}\n")
                        for line in result.stdout.split('\n'):
                            if "Median Drift" in line or "[RUST VALIDATION" in line:
                                f.write(f"    {line.strip()}\n")
                    else:
                        f.write(f"[{datetime.datetime.now()}] ERROR (Posible OOM o Segfault) D={d}\n")
                        f.write(f"STDERR: {result.stderr[:500]}\n")
                    
                    f.flush()
                except Exception as e:
                    f.write(f"[{datetime.datetime.now()}] EXCEPCION FATAL: {e}\n")
                    f.flush()
                
                # Sleep a bit to cool down CPU/GPU
                time.sleep(60)

if __name__ == "__main__":
    run_stress_loop()
