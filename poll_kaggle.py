import subprocess
import time
import sys

slug = "tradingnewtech/polydim-hardware-benchmark-gpu"

def check_status():
    res = subprocess.run(["python", "-m", "kaggle", "kernels", "status", slug], capture_output=True, text=True)
    return res.stdout.strip()

print("Polling Kaggle kernel...")
while True:
    status = check_status()
    print(status)
    if "KernelWorkerStatus.COMPLETE" in status:
        print("Kernel completed! Fetching output...")
        subprocess.run(["python", "-m", "kaggle", "kernels", "output", slug, "-p", r"E:\POLYDIM_EINSOF\kaggle_kernel\kaggle_export"])
        print("Results fetched.")
        break
    elif "KernelWorkerStatus.ERROR" in status or "error" in status.lower():
        print("Kernel failed!")
        break
    time.sleep(10)
