# ============================================================================
# POLYDIM V765 — KAGGLE CLOUD GPU BENCHMARK (2x NVIDIA TESLA T4)
# High-Dimensional Manifold S^(D-1) & Orthogonalization on GPU
# ============================================================================

import os
import sys
import time
import json
import torch
import numpy as np

def run_gpu_benchmark():
    print("=" * 78)
    print("POLYDIM V765 — KAGGLE GPU BENCHMARK (NVIDIA TESLA T4 FP64 & FP32)")
    print("=" * 78)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 0
    print(f"Device: {device} | GPU: {gpu_name} (Count: {gpu_count})")

    results = {
        "device": str(device),
        "gpu_name": gpu_name,
        "gpu_count": gpu_count,
        "benchmarks": []
    }

    # 1. Rodrigues Geodesic on S^(D-1) in FP64 across dimensions
    dims = [10000, 100000, 1000000, 10000000]
    print("\n[BENCHMARK 1] Rodrigues Geodesic on S^(D-1) (FP64 GPU Tensor)")
    for D in dims:
        try:
            y = torch.randn(D, dtype=torch.float64, device=device)
            y = y / torch.norm(y)
            u = torch.randn(D, dtype=torch.float64, device=device)
            u = u / torch.norm(u)
            v = torch.randn(D, dtype=torch.float64, device=device)
            v = v - torch.dot(u, v) * u
            v = v / torch.norm(v)

            theta = 0.5
            vers = 2.0 * torch.sin(torch.tensor(0.5 * theta, dtype=torch.float64, device=device)) ** 2
            sn = torch.sin(torch.tensor(theta, dtype=torch.float64, device=device))

            torch.cuda.synchronize() if torch.cuda.is_available() else None
            t0 = time.perf_counter()

            # Rodrigues: y_out = y + (-vers * (y.u) - sn * (y.v)) * u + (-vers * (y.v) + sn * (y.u)) * v
            yu = torch.dot(y, u)
            yv = torch.dot(y, v)
            alpha = -vers * yu - sn * yv
            beta = -vers * yv + sn * yu
            y_out = y + alpha * u + beta * v

            torch.cuda.synchronize() if torch.cuda.is_available() else None
            t1 = time.perf_counter()

            dt_ms = (t1 - t0) * 1000.0
            norm_err = abs(torch.norm(y_out).item() - 1.0)
            bandwidth_gbs = (D * 8 * 4) / (dt_ms * 1e-3 * 1e9) # read y,u,v, write y_out

            print(f"  -> D = {D:>10,}: Latency = {dt_ms:>8.3f} ms | Drift = {norm_err:>.3e} | Bandwidth = {bandwidth_gbs:>6.2f} GB/s")
            results["benchmarks"].append({
                "name": "Rodrigues_GPU_FP64",
                "D": D,
                "latency_ms": dt_ms,
                "norm_drift": norm_err,
                "bandwidth_gbs": bandwidth_gbs
            })
        except Exception as e:
            print(f"  -> D = {D:,} FAILED: {e}")

    # 2. CholQR2 Matrix Orthogonalization on GPU
    print("\n[BENCHMARK 2] CholQR2 Tiling on GPU (D=65536, K=32 & K=64)")
    for K in [16, 32, 64]:
        D_chol = 65536
        try:
            X = torch.randn(D_chol, K, dtype=torch.float64, device=device)
            torch.cuda.synchronize() if torch.cuda.is_available() else None
            t0 = time.perf_counter()

            # Step 1: Cholesky of X^T X
            A1 = torch.mm(X.t(), X)
            L1 = torch.linalg.cholesky(A1)
            Q1 = torch.linalg.solve_triangular(L1, X.t(), upper=False).t()

            # Step 2: Second pass
            A2 = torch.mm(Q1.t(), Q1)
            L2 = torch.linalg.cholesky(A2)
            Q2 = torch.linalg.solve_triangular(L2, Q1.t(), upper=False).t()

            torch.cuda.synchronize() if torch.cuda.is_available() else None
            t1 = time.perf_counter()

            dt_ms = (t1 - t0) * 1000.0
            ortho_err = torch.max(torch.abs(torch.mm(Q2.t(), Q2) - torch.eye(K, dtype=torch.float64, device=device))).item()
            print(f"  -> D = {D_chol:,}, K = {K}: Latency = {dt_ms:>8.3f} ms | Ortho Error = {ortho_err:>.3e}")
            results["benchmarks"].append({
                "name": "CholQR2_GPU_FP64",
                "D": D_chol,
                "K": K,
                "latency_ms": dt_ms,
                "ortho_error": ortho_err
            })
        except Exception as e:
            print(f"  -> CholQR2 K={K} FAILED: {e}")

    # 3. Subnormal Float Preservation Canary
    print("\n[BENCHMARK 3] GPU Subnormal Float Preservation (IEEE-754 FTZ Canary)")
    v1 = torch.tensor([1.0e-20], dtype=torch.float32, device=device)
    v2 = torch.tensor([1.0e-22], dtype=torch.float32, device=device)
    v_sub = v1 * v2
    val = v_sub.item()
    print(f"  -> Subnormal (1e-20 * 1e-22) = {val:e}")
    if val == 0.0:
        print("  -> WARNING: GPU backend has FTZ active (Flush-To-Zero).")
    else:
        print("  -> PASS: GPU preserves IEEE-754 subnormals.")
    results["subnormal_val"] = val

    # Save output
    os.makedirs("kaggle_output", exist_ok=True)
    with open("kaggle_output/results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] Results saved to kaggle_output/results.json (Exit Code 0)")

if __name__ == "__main__":
    run_gpu_benchmark()
