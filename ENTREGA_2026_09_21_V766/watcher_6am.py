import subprocess
import time
import datetime
import sys
import os

def run_until_6am():
    now = datetime.datetime.now()
    target = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now.hour >= 6:
        target += datetime.timedelta(days=1)
        
    print(f"HOUNDS WATCHDOG STARTED. TARGET STOP TIME: {target}")
    
    script = "nightly_autonomous_runner.py"
    
    while datetime.datetime.now() < target:
        print(f"[{datetime.datetime.now()}] Launching {script}...")
        process = subprocess.Popen([sys.executable, script])
        
        while process.poll() is None:
            time.sleep(10)
            if datetime.datetime.now() >= target:
                print("TARGET TIME REACHED. TERMINATING HOUNDS.")
                process.terminate()
                process.wait()
                return
                
        # If it crashed (segfault, exit code != 0), restart immediately
        exit_code = process.returncode
        print(f"[{datetime.datetime.now()}] {script} exited with code {exit_code}. Restarting...")
        time.sleep(1)

if __name__ == "__main__":
    run_until_6am()
