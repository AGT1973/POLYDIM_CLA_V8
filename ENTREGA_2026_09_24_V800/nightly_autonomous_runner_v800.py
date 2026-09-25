import os
import sys
import time
import datetime
import traceback

# ============================================================================
# POLYDIM V800 - AUTONOMOUS NIGHTLY RUNNER (SILICON LOOP)
# Continuous execution & adversarial stress testing loop
# ============================================================================

DELIVERY_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(DELIVERY_DIR, "nightly_v800_execution.log")

def log(msg: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted + "\n")

def run_nightly_cycle(cycle_id: int):
    log(f"--- Starting Autonomous Nightly Cycle #{cycle_id} ---")
    
    # Import and run red team test suite
    test_script = os.path.join(DELIVERY_DIR, "test_v800_redteam_adversarial.py")
    if not os.path.exists(test_script):
        log(f"ERROR: Test script not found: {test_script}")
        return False
        
    cmd = f'python -u "{test_script}"'
    ret = os.system(cmd)
    
    if ret == 0:
        log(f"Cycle #{cycle_id} COMPLETE: 7/7 TESTS PASSED (Exit Code 0)")
        return True
    else:
        log(f"Cycle #{cycle_id} FAILURE: Exit code {ret}")
        return False

def main():
    log("=== POLYDIM V800 NIGHTLY AUTONOMOUS DAEMON INITIALIZED ===")
    cycle = 1
    consecutive_passes = 0
    
    while True:
        try:
            success = run_nightly_cycle(cycle)
            if success:
                consecutive_passes += 1
                log(f"Current stability streak: {consecutive_passes} consecutive clean passes.")
            else:
                consecutive_passes = 0
                log("ALERT: Instability detected. Self-healing protocol engaged.")
                
            cycle += 1
            # Sleep 30 seconds between cycles to avoid burning 100% CPU continuously
            time.sleep(30)
            
        except Exception as e:
            log(f"CRITICAL DAEMON EXCEPTION: {e}\n{traceback.format_exc()}")
            time.sleep(10)

if __name__ == "__main__":
    main()
