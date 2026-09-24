# Red Team Audit: `polydim_stiefel_cayley_smw_f64` (BLAS & LU Paths)

## Asymptotic & Algorithmic Breaches Found

### 1. BLAS Path: Algebraically Invalid Tikhonov Regularization (Post-Factorization)
- **Location**: Line 740-745 in `polydim_kernel.cpp` (inside `#ifdef POLYDIM_USE_BLAS`).
- **Breach**: When `rcond < tol.pivot_rel` or `pmin < pivot_thr`, the code attempts Tikhonov regularization by modifying the diagonal of `Mc`:
  ```cpp
  Mc[i * n + i] += lambda * (Mc[i * n + i] >= 0 ? 1.0 : -1.0);
  ```
- **Why it's fatal**: At this point, `Mc` contains the $R$ factor (upper triangle) and Householder reflectors (lower triangle) from the `dgeqp3` (QR factorization) call. Adding a scalar to the diagonal of $R$ directly alters the operator to $Q(R + \Lambda)P^T$. This is **not** equivalent to $(M + \lambda I)$. Applying `dormqr` and `dtrtrs` on this corrupted factorization will yield an entirely incorrect solution vector, completely breaking the Cayley transform and causing the output to violently leave the Stiefel manifold.
- **Attack Vector**: Feed a nearly singular $M$ (e.g., from highly linearly dependent tangent vectors). The condition threshold will trip, the R-factor will be patched, and the returned point will have an orthonormal error wildly exceeding `tol.point_norm`, leading to silent manifold drift.

### 2. Native LU Path: Schur Complement Diagonal Patching
- **Location**: Line 780-784 in `polydim_kernel.cpp` (inside `#else` block).
- **Breach**: During Gaussian elimination, if the pivot at step `k` is too small, the code attempts to apply Tikhonov regularization by adding `lambda` to the diagonal of the unreduced submatrix:
  ```cpp
  for (uint32_t i = k; i < K2; ++i) { M[i * K2 + i] += lambda * ... }
  ```
- **Why it's fatal**: By step `k`, the matrix `M` has been partially reduced into an LU form. The remaining submatrix is the Schur complement. Modifying the diagonal of the Schur complement mid-factorization does **not** equal Tikhonov regularization on the original matrix $M$. It creates a mathematically meaningless frankenstein operator.
- **Attack Vector**: Trigger a small pivot exactly at $k > 0$ (e.g., by making the first few basis vectors well-conditioned but the later ones degenerate). The partial patch will mathematically invalidate the LU solver, producing garbage outputs for the SMW update.

### 3. Absolute Scale Floor in `lambda` Violates Silicon Contract
- **Location**: `double lambda = std::max(1e-12, tol.pivot_rel * m_inf);`
- **Breach**: The `std::max(1e-12, ...)` imposes a hardcoded absolute floor. If the entire system operates at a scale where `m_inf` is on the order of $10^{-15}$ (which is legitimate in some deep convergence regimes of SU(2) deformations), `lambda = 1e-12` becomes a massive relative perturbation (factor of 1000x).
- **Why it's fatal**: The fundamental premise of POLYDIM is scale invariance (no magic constants). Hardcoding `1e-12` violates the anti-hardcoding rule and destroys micro-scale gradients.
- **Attack Vector**: Provide a valid, well-conditioned system where all entries are globally scaled down by $10^{-16}$. If regularization is somehow forced, `1e-12` will completely override the signal, erasing the tangent step.

## Corrective Mandate
1. **BLAS Path**: If Tikhonov is required, `M` must be patched *before* calling `dgeqp3`, or a fresh copy of `M + \lambda I` must be refactorized. You cannot patch the $R$ factor post-factorization.
2. **Native LU Path**: If a pivot fails, the entire factorization must be aborted, `M` must be re-initialized as `M + \lambda I`, and the LU decomposition must restart from $k=0$.
3. **Lambda Scale**: Remove the `1e-12` hardcoded floor. It should strictly be a function of the matrix norm (e.g., `lambda = std::max(kEps, tol.pivot_rel) * m_inf`).
