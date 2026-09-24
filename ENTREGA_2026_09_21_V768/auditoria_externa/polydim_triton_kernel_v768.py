# ============================================================================
# POLYDIM V768 — TRITON GPU SILICON KERNEL (FUSED 2-PASS RODRIGUES FP64)
# Multi-GPU Agnostic (NVIDIA CUDA / AMD ROCm HIP) | Zero-Copy DMA
# Cierra el estudio analítico: Reducción final en GPU para evitar .item() sincrónico
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
    def rodrigues_final_reduction_kernel(
        partial_yu_ptr, partial_yv_ptr, partial_uu_ptr, partial_vv_ptr, partial_uv_ptr,
        alpha_beta_ptr,
        theta, num_partials, BLOCK_REDUCE: tl.constexpr
    ):
        """
        Reducción final y cómputo de alpha y beta 100% en GPU.
        Evita los 5 llamados sincrónicos a .item() desde Python a CPU.
        """
        pid = tl.program_id(axis=0)
        if pid == 0:
            offsets = tl.arange(0, BLOCK_REDUCE)
            mask = offsets < num_partials

            yu_parts = tl.load(partial_yu_ptr + offsets, mask=mask, other=0.0)
            yv_parts = tl.load(partial_yv_ptr + offsets, mask=mask, other=0.0)
            uu_parts = tl.load(partial_uu_ptr + offsets, mask=mask, other=0.0)
            vv_parts = tl.load(partial_vv_ptr + offsets, mask=mask, other=0.0)
            uv_parts = tl.load(partial_uv_ptr + offsets, mask=mask, other=0.0)

            yu = tl.sum(yu_parts, axis=0)
            yv = tl.sum(yv_parts, axis=0)
            uu = tl.sum(uu_parts, axis=0)
            vv = tl.sum(vv_parts, axis=0)
            uv = tl.sum(uv_parts, axis=0)

            half_theta = 0.5 * theta
            # Versine por medio ángulo
            sn_half = tl.sin(half_theta)
            vers = 2.0 * sn_half * sn_half
            sn = tl.sin(theta)

            alpha = -vers * yu - sn * yv
            beta  = -vers * yv + sn * yu

            tl.store(alpha_beta_ptr + 0, alpha)
            tl.store(alpha_beta_ptr + 1, beta)
            tl.store(alpha_beta_ptr + 2, uu)
            tl.store(alpha_beta_ptr + 3, vv)
            tl.store(alpha_beta_ptr + 4, uv)

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
    num_partials = grid[0]

    partial_yu = torch.empty(num_partials, dtype=torch.float64, device=y.device)
    partial_yv = torch.empty(num_partials, dtype=torch.float64, device=y.device)
    partial_uu = torch.empty(num_partials, dtype=torch.float64, device=y.device)
    partial_vv = torch.empty(num_partials, dtype=torch.float64, device=y.device)
    partial_uv = torch.empty(num_partials, dtype=torch.float64, device=y.device)

    # PASS 1: Reducción por bloques en GPU
    rodrigues_geodesic_pass1_kernel[grid](
        y, u, v,
        partial_yu, partial_yv, partial_uu, partial_vv, partial_uv,
        D, BLOCK_SIZE=BLOCK_SIZE
    )

    # PASS 1.5: Reducción final GPU (Qwen / Z-AI SOTA optimization)
    # Se confina la reducción a un bloque de potencia de 2 en GPU
    block_reduce = triton.next_power_of_2(num_partials)
    if block_reduce <= 4096:
        alpha_beta = torch.empty(5, dtype=torch.float64, device=y.device)
        rodrigues_final_reduction_kernel[(1,)](
            partial_yu, partial_yv, partial_uu, partial_vv, partial_uv,
            alpha_beta,
            float(theta), num_partials, BLOCK_REDUCE=block_reduce
        )
        alpha = alpha_beta[0].item()
        beta  = alpha_beta[1].item()
    else:
        # Fallback para dimensiones extremas (D > 4M elementos)
        yu = torch.sum(partial_yu).item()
        yv = torch.sum(partial_yv).item()
        half_theta = 0.5 * theta
        sn_half = math.sin(half_theta)
        vers = 2.0 * sn_half * sn_half
        sn = math.sin(theta)
        alpha = -vers * yu - sn * yv
        beta  = -vers * yv + sn * yu

    y_out = torch.empty_like(y)

    # PASS 2: Streaming streaming update
    rodrigues_geodesic_pass2_kernel[grid](
        y, u, v, y_out,
        alpha, beta,
        D, BLOCK_SIZE=BLOCK_SIZE
    )

    return y_out
