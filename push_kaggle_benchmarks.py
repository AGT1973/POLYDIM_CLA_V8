import os
import sys
import json
import subprocess

def push_benchmark(accelerator: str = "gpu"):
    username = "tradingnewtech"
    kernel_slug = f"polydim-v765-{accelerator.lower()}-benchmark"
    work_dir = os.path.join(r"E:\POLYDIM_EINSOF", f"kaggle_kernel_{accelerator.lower()}")
    os.makedirs(work_dir, exist_ok=True)

    script_src = r"E:\POLYDIM_EINSOF\benchmark_polydim_hardware.py" if accelerator == "gpu" else r"E:\POLYDIM_EINSOF\benchmark_polydim_tpu.py"
    with open(script_src, "r", encoding="utf-8") as f:
        code = f.read()

    script_dst = os.path.join(work_dir, "benchmark.py")
    with open(script_dst, "w", encoding="utf-8") as f:
        f.write(code)

    metadata = {
        "id": f"{username}/{kernel_slug}",
        "title": f"POLYDIM V765 {accelerator.upper()} Benchmark",
        "code_file": "benchmark.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": "true",
        "enable_gpu": "true" if accelerator.lower() == "gpu" else "false",
        "enable_tpu": "true" if accelerator.lower() == "tpu" else "false",
        "enable_internet": "true"
    }

    with open(os.path.join(work_dir, "kernel-metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"[*] Empujando {kernel_slug} ({accelerator.upper()}) a Kaggle...")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, "-m", "kaggle", "kernels", "push", "-p", work_dir]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        print(f"[OK] {accelerator.upper()}: {res.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {accelerator.upper()}: {e.stderr.strip() or e.stdout.strip()}")
        return False

if __name__ == "__main__":
    print("=== PUSHING KAGGLE GPU (2x T4) & TPU (v3-8) BENCHMARKS ===")
    push_benchmark("gpu")
    push_benchmark("tpu")
