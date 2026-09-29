"""
polydim_triton_kernel_v814.py
GPU Triton & Native Kernel Acceleration for POLYDIM V814
Hardware-Agnostic Silicon Dispatch (CUDA / ROCm / OpenMP Fallback)
"""

import os
import sys
import numpy as np

try:
    import torch
    import triton
    import triton.language as tl
    HAS_TRITON = True
except ImportError:
    HAS_TRITON = False

if HAS_TRITON:
    @triton.jit
    def dsyrk_triton_kernel(
        X_ptr, K_out_ptr,
        D: tl.constexpr, K: tl.constexpr,
        BLOCK_SIZE_D: tl.constexpr, BLOCK_SIZE_K: tl.constexpr
    ):
        """
        Streaming DSYRK Kernel in Triton: K_out = X^T @ X
        """
        pid_k1 = tl.program_id(0)
        pid_k2 = tl.program_id(1)

        offs_k1 = pid_k1 * BLOCK_SIZE_K + tl.arange(0, BLOCK_SIZE_K)
        offs_k2 = pid_k2 * BLOCK_SIZE_K + tl.arange(0, BLOCK_SIZE_K)

        acc = tl.zeros((BLOCK_SIZE_K, BLOCK_SIZE_K), dtype=tl.float64)

        for d_start in range(0, D, BLOCK_SIZE_D):
            offs_d = d_start + tl.arange(0, BLOCK_SIZE_D)
            mask_d = offs_d < D

            # Load tile X[offs_d, offs_k1]
            x1_ptrs = X_ptr + offs_d[:, None] * K + offs_k1[None, :]
            x1 = tl.load(x1_ptrs, mask=(mask_d[:, None] & (offs_k1[None, :] < K)), other=0.0)

            # Load tile X[offs_d, offs_k2]
            x2_ptrs = X_ptr + offs_d[:, None] * K + offs_k2[None, :]
            x2 = tl.load(x2_ptrs, mask=(mask_d[:, None] & (offs_k2[None, :] < K)), other=0.0)

            # Accumulate X1^T @ X2
            acc += tl.dot(tl.trans(x1), x2)

        out_ptrs = K_out_ptr + offs_k1[:, None] * K + offs_k2[None, :]
        mask_out = (offs_k1[:, None] < K) & (offs_k2[None, :] < K)
        tl.store(out_ptrs, acc, mask=mask_out)

def compute_gramian_gpu(X_tensor: "torch.Tensor") -> "torch.Tensor":
    """
    Computes K = X^T @ X via Triton if CUDA is available, or PyTorch standard op.
    """
    if not HAS_TRITON or not X_tensor.is_cuda:
        return torch.matmul(X_tensor.T, X_tensor)
    
    D, K = X_tensor.shape
    K_out = torch.empty((K, K), device=X_tensor.device, dtype=X_tensor.dtype)
    BLOCK_SIZE_K = 16
    BLOCK_SIZE_D = 128
    grid = ((K + BLOCK_SIZE_K - 1) // BLOCK_SIZE_K, (K + BLOCK_SIZE_K - 1) // BLOCK_SIZE_K)
    
    dsyrk_triton_kernel[grid](
        X_tensor, K_out,
        D=D, K=K,
        BLOCK_SIZE_D=BLOCK_SIZE_D, BLOCK_SIZE_K=BLOCK_SIZE_K
    )
    return K_out

if __name__ == "__main__":
    print(f"Triton available: {HAS_TRITON}")
