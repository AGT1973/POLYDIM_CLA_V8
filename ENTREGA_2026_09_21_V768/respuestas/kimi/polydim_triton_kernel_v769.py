# ============================================================================
# POLYDIM V769 — TRITON GPU SILICON KERNEL (FUSED 2-PASS RODRIGUES FP64)
# Correcciones Red Team:
#   C1: Fallback con 'math' sin importar -> NameError garantizado a D=10^7. ELIMINADO:
#       reduccion en 2 etapas 100% GPU (sin .item()).
#   C2: y,u,v no verificados (NaN/Inf pasaban silenciosos en GPU). Agregado flag.
#   C3: alpha/beta pasan a pass2 como puntero GPU: cero sincronizaciones host.
# ============================================================================
import torch

try:
    import triton
    import triton.language as tl
    HAS_TRITON = True
except ImportError:
    HAS_TRITON = False

if HAS_TRITON:

    @triton.jit
    def rodrigues_pass1_kernel(
        y_ptr, u_ptr, v_ptr,
        p_yu_ptr, p_yv_ptr, p_uu_ptr, p_vv_ptr, p_uv_ptr,
        nan_flag_ptr,
        D, BLOCK_SIZE: tl.constexpr
    ):
        pid = tl.program_id(axis=0)
        offsets = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
        mask = offsets < D

        yi = tl.load(y_ptr + offsets, mask=mask, other=0.0)
        ui = tl.load(u_ptr + offsets, mask=mask, other=0.0)
        vi = tl.load(v_ptr + offsets, mask=mask, other=0.0)

        bad = (~tl.math.isfinite(yi)) | (~tl.math.isfinite(ui)) | (~tl.math.isfinite(vi))
        if tl.sum(bad.to(tl.int32), axis=0) > 0:
            tl.atomic_max(nan_flag_ptr, 1)   # C2: NaN/Inf detectado en GPU

        tl.store(p_yu_ptr + pid, tl.sum(yi * ui, axis=0))
        tl.store(p_yv_ptr + pid, tl.sum(yi * vi, axis=0))
        tl.store(p_uu_ptr + pid, tl.sum(ui * ui, axis=0))
        tl.store(p_vv_ptr + pid, tl.sum(vi * vi, axis=0))
        tl.store(p_uv_ptr + pid, tl.sum(ui * vi, axis=0))

    @triton.jit
    def rodrigues_reduce_stage_kernel(
        src_ptr, dst_ptr, n_src, BLOCK: tl.constexpr
    ):
        # Reduce n_src parciales -> n_dst = cdiv(n_src, BLOCK) parciales (GPU pura)
        pid = tl.program_id(axis=0)
        offs = pid * BLOCK + tl.arange(0, BLOCK)
        vals = tl.load(src_ptr + offs, mask=offs < n_src, other=0.0)
        tl.store(dst_ptr + pid, tl.sum(vals, axis=0))

    @triton.jit
    def rodrigues_reduce_final_kernel(
        p_yu_ptr, p_yv_ptr, p_uu_ptr, p_vv_ptr, p_uv_ptr,
        ab_ptr, theta, num_partials, BLOCK: tl.constexpr
    ):
        offs = tl.arange(0, BLOCK)
        m = offs < num_partials
        yu = tl.sum(tl.load(p_yu_ptr + offs, mask=m, other=0.0), axis=0)
        yv = tl.sum(tl.load(p_yv_ptr + offs, mask=m, other=0.0), axis=0)
        uu = tl.sum(tl.load(p_uu_ptr + offs, mask=m, other=0.0), axis=0)
        vv = tl.sum(tl.load(p_vv_ptr + offs, mask=m, other=0.0), axis=0)
        uv = tl.sum(tl.load(p_uv_ptr + offs, mask=m, other=0.0), axis=0)

        sn_half = tl.sin(0.5 * theta)          # versine por medio angulo: estable en theta->0
        vers = 2.0 * sn_half * sn_half
        sn = tl.sin(theta)
        tl.store(ab_ptr + 0, -vers * yu - sn * yv)
        tl.store(ab_ptr + 1, -vers * yv + sn * yu)
        tl.store(ab_ptr + 2, uu)
        tl.store(ab_ptr + 3, vv)
        tl.store(ab_ptr + 4, uv)

    @triton.jit
    def rodrigues_pass2_kernel(
        y_ptr, u_ptr, v_ptr, y_out_ptr, ab_ptr,
        D, BLOCK_SIZE: tl.constexpr
    ):
        alpha = tl.load(ab_ptr + 0)            # C3: leido en GPU, sin sync host
        beta = tl.load(ab_ptr + 1)
        pid = tl.program_id(axis=0)
        offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
        mask = offs < D
        yi = tl.load(y_ptr + offs, mask=mask, other=0.0)
        ui = tl.load(u_ptr + offs, mask=mask, other=0.0)
        vi = tl.load(v_ptr + offs, mask=mask, other=0.0)
        tl.store(y_out_ptr + offs, yi + alpha * ui + beta * vi, mask=mask)

    @triton.jit
    def rodrigues_verify_kernel(
        y_out_ptr, p_norm_ptr, D, BLOCK_SIZE: tl.constexpr
    ):
        pid = tl.program_id(axis=0)
        offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
        mask = offs < D
        yo = tl.load(y_out_ptr + offs, mask=mask, other=0.0)
        tl.store(p_norm_ptr + pid, tl.sum(yo * yo, axis=0))


def apply_triton_rodrigues_geodesic(
    y: torch.Tensor, u: torch.Tensor, v: torch.Tensor, theta: float,
    tol: float = 64.0 * 2.220446049250313e-16
) -> tuple[torch.Tensor, dict]:
    """FP64 S^(D-1) Rodrigues en GPU. Cero sincronizaciones host hasta el retorno.
    Devuelve (y_out, report) con out_norm_err medido en GPU."""
    if not HAS_TRITON:
        raise RuntimeError("Triton no disponible en este sistema.")
    assert y.is_cuda and u.is_cuda and v.is_cuda, "Tensores en GPU requeridos."
    assert y.dtype == torch.float64, "FP64 estricto requerido para el manifold."

    D = y.numel()
    BLOCK = 1024
    grid = (triton.cdiv(D, BLOCK),)
    n_part = grid[0]
    dev = y.device

    nan_flag = torch.zeros(1, dtype=torch.int32, device=dev)
    partials = [torch.empty(n_part, dtype=torch.float64, device=dev) for _ in range(5)]

    rodrigues_pass1_kernel[grid](y, u, v, *partials, nan_flag, D, BLOCK_SIZE=BLOCK)

    # Reduccion en etapas, 100% GPU, valida para CUALQUIER D (C1)
    bufs = partials
    n = n_part
    while n > 4096:
        n_dst = triton.cdiv(n, 4096)
        nbufs = []
        for b in bufs:
            dst = torch.empty(n_dst, dtype=torch.float64, device=dev)
            rodrigues_reduce_stage_kernel[(n_dst,)](b, dst, n, BLOCK=4096)
            nbufs.append(dst)
        bufs, n = nbufs, n_dst

    ab = torch.empty(5, dtype=torch.float64, device=dev)
    blk = triton.next_power_of_2(n)
    rodrigues_reduce_final_kernel[(1,)](*bufs, ab, float(theta), n, BLOCK=blk)

    y_out = torch.empty_like(y)
    rodrigues_pass2_kernel[grid](y, u, v, y_out, ab, D, BLOCK_SIZE=BLOCK)

    # Verificacion a posteriori en GPU (1 sync al final, no 5 en medio)
    p_norm = torch.empty(n_part, dtype=torch.float64, device=dev)
    rodrigues_verify_kernel[grid](y_out, p_norm, D, BLOCK_SIZE=BLOCK)
    report = {
        "uu_err": float(abs(ab[2].item() - 1.0)),
        "vv_err": float(abs(ab[3].item() - 1.0)),
        "uv_err": float(abs(ab[4].item())),
        "out_norm_err": float(abs(torch.sum(p_norm).item() ** 0.5 - 1.0)),
        "nan_flag": int(nan_flag.item()),
    }
    assert report["nan_flag"] == 0, "NaN/Inf en entrada detectado por kernel GPU"
    if report["uu_err"] > tol or report["vv_err"] > tol or report["uv_err"] > tol:
        raise ArithmeticError(f"Base no ortonormal en GPU: {report}")
    return y_out, report
