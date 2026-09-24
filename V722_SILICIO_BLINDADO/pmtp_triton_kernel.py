# ============================================================================
# POLYDIM LATENTOS V722 SILICON — TRITON GPU KERNEL (DETERMINISTIC)
# ============================================================================
# Two-pass reduction (no atomic_add). Reject NaN/Inf (parity with native).
# FP64 accumulation throughout. Unified error semantics.
# ============================================================================

import torch

try:
    import triton
    import triton.language as tl
    HAS_TRITON = True
except ImportError:
    HAS_TRITON = False


# ── Pass 1: Partial sum of squares per block (FP64) ──────────────────────────
if HAS_TRITON:
    @triton.jit
    def _normalize_pass1(
        x_ptr,
        partial_ptr,
        status_ptr,       # per-block status: 0=ok, -1=nonfinite
        dim,
        BLOCK_SIZE: tl.constexpr,
    ):
        pid = tl.program_id(axis=0)
        offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
        mask = offs < dim

        x = tl.load(x_ptr + offs, mask=mask, other=0.0)

        # REJECT NaN/Inf (parity with C++/Rust: no silent zeroing)
        has_bad = tl.sum((tl.math.isnan(x) | tl.math.isinf(x)).to(tl.int32), axis=0)
        tl.store(status_ptr + pid, has_bad)

        x_fp64 = x.to(tl.float64)
        local_sum = tl.sum(x_fp64 * x_fp64, axis=0)
        tl.store(partial_ptr + pid, local_sum)


    # ── Pass 2: Final reduction + normalize (single-threaded per block) ───────
    @triton.jit
    def _normalize_pass2(
        x_ptr,
        out_ptr,
        partial_ptr,
        num_blocks,
        dim,
        BLOCK_SIZE: tl.constexpr,
    ):
        pid = tl.program_id(axis=0)

        # Each block reads ALL partial sums (deterministic serial reduction)
        global_sum = tl.zeros([], dtype=tl.float64)
        for j in range(num_blocks):
            global_sum += tl.load(partial_ptr + j)

        norm = tl.sqrt(global_sum)
        inv_norm = 1.0 / tl.where(norm > 1e-14, norm, tl.full([], 1e-14, dtype=tl.float64))

        offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
        mask = offs < dim
        x = tl.load(x_ptr + offs, mask=mask, other=0.0)

        # Normalize in FP64, store back in original dtype
        out = (x.to(tl.float64) * inv_norm).to(x.dtype)
        tl.store(out_ptr + offs, out, mask=mask)


def triton_normalize_s_d(tensor: torch.Tensor) -> torch.Tensor:
    """Normalize tensor to S^(D-1). Returns normalized tensor.
    Raises RuntimeError if NaN/Inf detected (parity with C++/Rust)."""

    if not tensor.is_cuda or not HAS_TRITON:
        # CPU fallback
        if not torch.isfinite(tensor).all():
            raise RuntimeError("PMTP_ERR_NONFINITE: NaN/Inf in input tensor")
        norm = torch.linalg.vector_norm(tensor.double(), dim=-1, keepdim=True)
        if (norm < 1e-14).any():
            raise RuntimeError("PMTP_ERR_COLLAPSE: degenerate vector")
        return (tensor.double() / norm).to(tensor.dtype)

    dim = tensor.numel()
    BLOCK_SIZE = 1024
    num_blocks = triton.cdiv(dim, BLOCK_SIZE)
    grid = (num_blocks,)

    partial_buf = torch.zeros(num_blocks, dtype=torch.float64, device=tensor.device)
    status_buf = torch.zeros(num_blocks, dtype=torch.int32, device=tensor.device)
    out = torch.empty_like(tensor)

    _normalize_pass1[grid](tensor, partial_buf, status_buf, dim, BLOCK_SIZE=BLOCK_SIZE)

    # Check for NaN/Inf (unified with C++/Rust rejection semantics)
    if status_buf.sum().item() > 0:
        raise RuntimeError("PMTP_ERR_NONFINITE: NaN/Inf detected in GPU tensor")

    _normalize_pass2[grid](tensor, out, partial_buf, num_blocks, dim, BLOCK_SIZE=BLOCK_SIZE)
    return out


def riemannian_exp_map_torch(
    s_t: torch.Tensor,
    velocity: torch.Tensor,
    v_tangent_buf: torch.Tensor,
    dt: float = 0.01,
) -> torch.Tensor:
    """GPU Riemannian Exp Map. All buffers caller-owned. In-place on v_tangent_buf."""

    if not torch.isfinite(s_t).all() or not torch.isfinite(velocity).all():
        raise RuntimeError("PMTP_ERR_NONFINITE in exp_map input")

    dot_sv = torch.vdot(s_t.double(), velocity.double()).item()

    # Tangent projection into pre-allocated buffer
    v_tangent_buf.copy_(velocity)
    v_tangent_buf.add_(s_t, alpha=-dot_sv)

    v_norm = torch.linalg.vector_norm(v_tangent_buf.double()).clamp_(min=1e-7).float().item()

    theta = (v_norm * dt) % (2.0 * 3.141592653589793)

    if theta < 1e-4:
        t2 = theta * theta
        scale_v = (1.0 - t2 / 6.0 + (t2 * t2) / 120.0) * dt
    else:
        import math
        scale_v = math.sin(theta) / v_norm

    cos_t = float(torch.cos(torch.tensor(theta)))

    # In-place computation on s_t
    s_t.mul_(cos_t)
    s_t.add_(v_tangent_buf, alpha=scale_v)

    return triton_normalize_s_d(s_t)
