import os
import sys
import json
import time
import subprocess

def push_linux_all():
    username = "agt1973gmailcom"
    ts = int(time.time())
    kernel_slug = f"polydim-v765-linux-cert-{ts}"
    work_dir = os.path.join(r"E:\POLYDIM_EINSOF", "kaggle_kernel_linux_all")
    os.makedirs(work_dir, exist_ok=True)

    script_src = r"E:\POLYDIM_EINSOF\benchmark_polydim_linux_all_milestones.py"
    with open(script_src, "r", encoding="utf-8") as f:
        code = f.read()

    script_dst = os.path.join(work_dir, "benchmark.py")
    with open(script_dst, "w", encoding="utf-8") as f:
        f.write(code)

    metadata = {
        "id": f"{username}/{kernel_slug}",
        "title": f"POLYDIM Linux 3 Milestones {ts}",
        "code_file": "benchmark.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": "true",
        "enable_gpu": "false",
        "enable_tpu": "false",
        "enable_internet": "true"
    }

    with open(os.path.join(work_dir, "kernel-metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"[*] Empujando {kernel_slug} a Kaggle (Ubuntu Linux)...")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, "-m", "kaggle", "kernels", "push", "-p", work_dir]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        print(f"[OK] {res.stdout.strip()}")
        return kernel_slug
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {e.stderr.strip() or e.stdout.strip()}")
        return None

if __name__ == "__main__":
    slug = push_linux_all()
    if slug:
        print(f"Target Kernel Slug: {slug}")
