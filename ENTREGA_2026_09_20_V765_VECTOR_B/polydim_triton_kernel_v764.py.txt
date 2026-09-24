# ============================================================================
# POLYDIM V762 — TRITON GPU SILICON KERNEL (2-PASS RODRIGUES FP64)
# Multi-GPU Agnostic (NVIDIA CUDA / AMD ROCm HIP) | Zero-Copy DMA
# ============================================================================

import torch

try:
    import triton
    import triton.language as tl
    HAS_TRITON = True
except ImportError:
    HAS_TRITON = False

if HAS_TRITON:
    @triton.jit(do_not_specialize=False)
    def rodrigues_geodesic_pass1_kernel(
        y_ptr, u_ptr, v_ptr,
        partial_yu_ptr, partial_yv_ptr, partial_uu_ptr, partial_vv_ptr, partial_uv_ptr,
        D, BLOCK_SIZE: tl.constexpr
    ):
        pid = tl.program_id(axis=0)
        offsets = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
        mask = offsets < D

        yi = tl.load(y_ptr + offsets, mask=mask, other=0.0)
        ui = tl.load(u_ptr + offsets, mask=mask, other=0.0)
        vi = tl.load(v_ptr + offsets, mask=mask, other=0.0)

        # Dot product reductions per block
        yu = tl.sum(yi * ui, axis=0)
        yv = tl.sum(yi * vi, axis=0)
        uu = tl.sum(ui * ui, axis=0)
        vv = tl.sum(vi * vi, axis=0)
        uv = tl.sum(ui * vi, axis=0)

        tl.store(partial_yu_ptr + pid, yu)
        tl.store(partial_yv_ptr + pid, yv)
        tl.store(partial_uu_ptr + pid, uu)
        tl.store(partial_vv_ptr + pid, vv)
        tl.store(partial_uv_ptr + pid, uv)

    @triton.jit(do_not_specialize=False)
    def rodrigues_geodesic_pass2_kernel(
        y_ptr, u_ptr, v_ptr, y_out_ptr,
        alpha, beta,
        D, BLOCK_SIZE: tl.constexpr
    ):
        pid = tl.program_id(axis=0)
        offsets = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
        mask = offsets < D

        yi = tl.load(y_ptr + offsets, mask=mask, other=0.0)
        ui = tl.load(u_ptr + offsets, mask=mask, other=0.0)
        vi = tl.load(v_ptr + offsets, mask=mask, other=0.0)

        # Exact streaming update
        y_out = yi + alpha * ui + beta * vi
        tl.store(y_out_ptr + offsets, y_out, mask=mask)

def apply_triton_rodrigues_geodesic(
    y: torch.Tensor,
    u: torch.Tensor,
    v: torch.Tensor,
    theta: float,
    stream: torch.cuda.Stream = None
) -> torch.Tensor:
    if not HAS_TRITON:
        raise RuntimeError("Triton is not available on this system.")
    
    assert y.is_cuda and u.is_cuda and v.is_cuda, "Tensors must be on GPU device."
    assert y.dtype == torch.float64, "Strict FP64 manifold representation required."

    D = y.numel()
    BLOCK_SIZE = 1024
    grid = (triton.cdiv(D, BLOCK_SIZE),)

    partial_yu = torch.empty(grid[0], dtype=torch.float64, device=y.device)
    partial_yv = torch.empty(grid[0], dtype=torch.float64, device=y.device)
    partial_uu = torch.empty(grid[0], dtype=torch.float64, device=y.device)
    partial_vv = torch.empty(grid[0], dtype=torch.float64, device=y.device)
    partial_uv = torch.empty(grid[0], dtype=torch.float64, device=y.device)

    # PASS 1
    rodrigues_geodesic_pass1_kernel[grid](
        y, u, v,
        partial_yu, partial_yv, partial_uu, partial_vv, partial_uv,
        D, BLOCK_SIZE=BLOCK_SIZE
    )

    yu = torch.sum(partial_yu).item()
    yv = torch.sum(partial_yv).item()
    uu = torch.sum(partial_uu).item()
    vv = torch.sum(partial_vv).item()
    uv = torch.sum(partial_uv).item()

    # Factibility & Orthonormality Gates (64 * eps_mach)
    tol = 64.0 * torch.finfo(torch.float64).eps
    if abs(uu - 1.0) > tol or abs(vv - 1.0) > tol or abs(uv) > tol:
        raise ValueError("Basis {u, v} is not orthonormal within tolerance.")

    half_theta = 0.5 * theta
    sn_half = torch.sin(torch.tensor(half_theta, dtype=torch.float64)).item()
    vers = 2.0 * sn_half * sn_half
    sn = torch.sin(torch.tensor(theta, dtype=torch.float64)).item()

    # Exact orientation fix
    alpha = -vers * yu - sn * yv
    beta = -vers * yv + sn * yu

    y_out = torch.empty_like(y)

    # PASS 2
    rodrigues_geodesic_pass2_kernel[grid](
        y, u, v, y_out,
        alpha, beta,
        D, BLOCK_SIZE=BLOCK_SIZE
    )

    return y_out
