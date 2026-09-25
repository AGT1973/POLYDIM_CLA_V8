import torch
import triton
import triton.language as tl

# ============================================================================
# POLYDIM V801 - LATENT OS (GHOST PROTOCOL)
# GPU TRITON KERNEL
#
# CHANGELOG vs V800:
#   [FIX-11] D and K were tl.constexpr in V800. Triton specializes/recompiles
#            a distinct kernel binary per unique combination of constexpr
#            arguments; marking *runtime-varying* tensor dimensions as
#            constexpr means every new (D, K) shape seen in production
#            triggers a fresh JIT compile. They are now ordinary runtime
#            arguments; only the tuning constants (BLOCK_SIZE_D/K) stay
#            constexpr, which is what constexpr is for.
#   [FIX-12] V800's GPU path had ZERO parity with the CPU path's numerical
#            safety: no NaN/Inf poison detection (the CPU kernel returns
#            -99 and now marks poisoned cells with quiet_NaN; the GPU
#            kernel silently propagated NaN/Inf with no signal at all).
#            Added a poison_flag output tensor set via atomic_max so the
#            launcher can raise the same PolydimError the CPU path raises.
#            NOTE (still true, and worth stating plainly rather than
#            hiding it): full Ogita-Rump-Oishi double-double compensation
#            like the CPU's two_sum/two_prod is NOT implemented here.
#            Triton's float64 support does not give you an error-free
#            transform for free, and porting one correctly is nontrivial
#            enough that shipping a fake version would be worse than
#            documenting the gap honestly. CPU and GPU results should be
#            expected to differ in the last 1-2 ulps until that lands.
#   [NOTE]   This file could not be executed end-to-end in this delivery's
#            sandbox (no CUDA GPU available) -- see CHANGELOG_V801.md. It
#            was however import- and trace-checked against a live Triton
#            3.x install to catch syntax/API-level regressions.
# ============================================================================

@triton.jit
def polydim_cayley_smw_triton_v801(
    X_ptr, U_ptr, V_ptr, Y_out_ptr, Poison_ptr,
    D, K,
    BLOCK_SIZE_D: tl.constexpr, BLOCK_SIZE_K: tl.constexpr
):
    pid_d = tl.program_id(axis=0)
    pid_k = tl.program_id(axis=1)

    offsets_d = pid_d * BLOCK_SIZE_D + tl.arange(0, BLOCK_SIZE_D)
    offsets_k = pid_k * BLOCK_SIZE_K + tl.arange(0, BLOCK_SIZE_K)

    mask_d = offsets_d < D
    mask_k = offsets_k < K
    mask = mask_d[:, None] & mask_k[None, :]

    ptrs_offset = offsets_d[:, None] * K + offsets_k[None, :]

    x_vals = tl.load(X_ptr + ptrs_offset, mask=mask, other=0.0)
    u_vals = tl.load(U_ptr + ptrs_offset, mask=mask, other=0.0)
    v_vals = tl.load(V_ptr + ptrs_offset, mask=mask, other=0.0)

    # [FIX-12] poison detection, parity with the CPU kernel's guard.
    is_poisoned = (
        (x_vals != x_vals) | (u_vals != u_vals) | (v_vals != v_vals) |
        (tl.abs(x_vals) == float("inf")) |
        (tl.abs(u_vals) == float("inf")) |
        (tl.abs(v_vals) == float("inf"))
    )
    block_poisoned = tl.max(tl.where(mask & is_poisoned, 1, 0))
    tl.atomic_max(Poison_ptr, block_poisoned)

    y_vals = x_vals + u_vals * v_vals
    tl.store(Y_out_ptr + ptrs_offset, y_vals, mask=mask)


def launch_polydim_triton_kernel(X: torch.Tensor, U: torch.Tensor, V: torch.Tensor, Y: torch.Tensor) -> int:
    """Returns 0 on success, -99 if any NaN/Inf was detected in X, U or V
    (mirrors the C++ kernel's return contract). Y still gets a value written
    for poisoned cells on the GPU path (no per-cell quiet_NaN marking yet --
    tracked as follow-up, see CHANGELOG_V801.md FIX-12 note)."""
    assert X.is_contiguous(), "Tensor X debe ser C-contiguous"
    assert U.is_contiguous(), "Tensor U debe ser C-contiguous"
    assert V.is_contiguous(), "Tensor V debe ser C-contiguous"
    assert Y.is_contiguous(), "Tensor Y debe ser C-contiguous"

    D, K = X.shape
    BLOCK_SIZE_D = 128
    BLOCK_SIZE_K = 32

    poison_flag = torch.zeros(1, dtype=torch.int32, device=X.device)

    grid = (triton.cdiv(D, BLOCK_SIZE_D), triton.cdiv(K, BLOCK_SIZE_K))

    polydim_cayley_smw_triton_v801[grid](
        X, U, V, Y, poison_flag,
        D, K,
        BLOCK_SIZE_D=BLOCK_SIZE_D,
        BLOCK_SIZE_K=BLOCK_SIZE_K
    )

    return -99 if int(poison_flag.item()) != 0 else 0
