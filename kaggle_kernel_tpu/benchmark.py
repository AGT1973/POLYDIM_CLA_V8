# ============================================================================
# POLYDIM V765 — KAGGLE CLOUD TPU BENCHMARK (GOOGLE TPU v3-8 / XLA)
# High-Dimensional Manifold S^(D-1) on TPU Systolic Array (D = 10,000,000)
# ============================================================================

import os
import sys
import time
import json
import numpy as np

def run_tpu_benchmark():
    print("=" * 78)
    print("POLYDIM V765 — KAGGLE TPU v3-8 BENCHMARK (GOOGLE XLA SYSTOLIC CORES)")
    print("=" * 78)

    # Detect TPU environment (PyTorch XLA or JAX or TensorFlow)
    tpu_backend = "none"
    try:
        import torch_xla
        import torch_xla.core.xla_model as xm
        device = xm.xla_device()
        tpu_backend = f"torch_xla ({xm.xla_device_hw(device)})"
        print(f"[OK] TPU Device Detected: {device} | HW: {tpu_backend}")
    except Exception as e:
        print(f"[INFO] PyTorch XLA not found, attempting JAX TPU backend... ({e})")
        try:
            import jax
            import jax.numpy as jnp
            devices = jax.devices()
            tpu_backend = f"JAX TPU ({devices})"
            print(f"[OK] JAX TPU Detected: {devices}")
        except Exception as e2:
            print(f"[INFO] Running in fallback CPU/GPU mode for testing: {e2}")
            import torch
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            tpu_backend = f"Fallback ({device})"

    results = {
        "backend": tpu_backend,
        "benchmarks": []
    }

    # 1. Asymptotic Rodrigues on TPU up to D = 10,000,000 (80 MB Vector)
    dims = [100000, 1000000, 10000000]
    print("\n[TPU BENCHMARK 1] Asymptotic Rodrigues Geodesic on S^(D-1)")
    
    if "torch_xla" in tpu_backend:
        import torch
        for D in dims:
            try:
                y = torch.randn(D, dtype=torch.float32, device=device)
                y = y / torch.norm(y)
                u = torch.randn(D, dtype=torch.float32, device=device)
                u = u / torch.norm(u)
                v = torch.randn(D, dtype=torch.float32, device=device)
                v = v - torch.dot(u, v) * u
                v = v / torch.norm(v)

                xm.mark_step()
                t0 = time.perf_counter()

                theta = 0.5
                vers = 2.0 * torch.sin(torch.tensor(0.5 * theta, device=device)) ** 2
                sn = torch.sin(torch.tensor(theta, device=device))

                yu = torch.dot(y, u)
                yv = torch.dot(y, v)
                alpha = -vers * yu - sn * yv
                beta = -vers * yv + sn * yu
                y_out = y + alpha * u + beta * v

                xm.mark_step()
                t1 = time.perf_counter()

                dt_ms = (t1 - t0) * 1000.0
                norm_err = abs(torch.norm(y_out).item() - 1.0)
                print(f"  -> D = {D:>10,}: TPU Latency = {dt_ms:>8.3f} ms | Norm Error = {norm_err:>.3e}")
                results["benchmarks"].append({"D": D, "latency_ms": dt_ms, "norm_err": norm_err})
            except Exception as ex:
                print(f"  -> D = {D:,} FAILED: {ex}")
    else:
        # JAX or PyTorch standard runner
        import torch
        for D in dims:
            try:
                y = torch.randn(D, dtype=torch.float32)
                y = y / torch.norm(y)
                u = torch.randn(D, dtype=torch.float32)
                u = u / torch.norm(u)
                v = torch.randn(D, dtype=torch.float32)
                v = v - torch.dot(u, v) * u
                v = v / torch.norm(v)

                t0 = time.perf_counter()
                theta = 0.5
                vers = 2.0 * np.sin(0.5 * theta) ** 2
                sn = np.sin(theta)

                yu = torch.dot(y, u)
                yv = torch.dot(y, v)
                alpha = -vers * yu - sn * yv
                beta = -vers * yv + sn * yu
                y_out = y + alpha * u + beta * v
                t1 = time.perf_counter()

                dt_ms = (t1 - t0) * 1000.0
                norm_err = abs(torch.norm(y_out).item() - 1.0)
                print(f"  -> D = {D:>10,}: Latency = {dt_ms:>8.3f} ms | Norm Error = {norm_err:>.3e}")
                results["benchmarks"].append({"D": D, "latency_ms": dt_ms, "norm_err": norm_err})
            except Exception as ex:
                print(f"  -> D = {D:,} FAILED: {ex}")

    os.makedirs("kaggle_output", exist_ok=True)
    with open("kaggle_output/tpu_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] TPU Benchmark finished. Telemetry written to kaggle_output/tpu_results.json")

if __name__ == "__main__":
    run_tpu_benchmark()
