# Red Team Audit Report: Singular Tikhonov Logic (polydim_kernel.cpp)

## 1. Vulnerability Summary
The NEW Tikhonov fallback logic introduced in `polydim_kernel.cpp` (V765) contains three severe asymptotic and architectural flaws when faced with highly singular or subnormal `M` matrices. Instead of safely aborting, it aggressively forces a factorization with insufficient regularization, leading to division by zero, `NaN` pollution, and ultimately a **silent certification of completely corrupted tensors** due to a flaw in C++'s `std::max` handling of `NaN`s.

## 2. Detailed Findings

### A. Insufficient Regularization ($10^{-15}$ is below the noise floor)
The Tikhonov parameter is computed as:
`double lambda = std::max(1e-15, tol.pivot_rel * m_inf);`
For a system where $K = 512$ ($2K = 1024$), and $M$ has an infinity norm of $\sim 1.0$, the parameter becomes clamped to $10^{-15}$.
In IEEE-754 `binary64`, the machine epsilon is $\approx 2.22 \times 10^{-16}$. The accumulation of rounding errors during an LU or QR factorization of a $1024 \times 1024$ matrix scales proportionally to $1024 \times \epsilon \approx 2.2 \times 10^{-13}$. 
Thus, a diagonal perturbation of $10^{-15}$ is strictly smaller than the numerical noise floor. It is mathematically obliterated by catastrophic cancellation during elimination.

### B. Division by Zero via Safety Bypass (Native LU Path)
At line 815, the kernel contains the following bypass:
```cpp
if (!(best > pivot_thr) && !needs_tikhonov) {
    // Abort logic bypassed if needs_tikhonov == true
}
```
If the first LU pass fails, `needs_tikhonov` becomes `true`. During the second LU pass, the safety check is intentionally disabled (`!needs_tikhonov` is false). 
Because the $10^{-15}$ regularization was consumed by numerical noise, the pivot (`best` / `diag`) can become exactly `0.0` or extremely subnormal. The loop proceeds directly to:
```cpp
const double f = M[...] / diag;
```
This triggers a `Division by Zero`, generating `Inf` or `NaN` which violently pollutes the $Z$ matrix, and subsequently the output $Y_{out}$.

### C. The `std::max` Hallucination Bug (CATASTROPHIC)
When the matrix $Y_{out}$ becomes polluted with `NaN`s, the terminal Ortho Error check is meant to catch it (line 905):
```cpp
if (err > tol.gram_ortho) return POLYDIM_ERR_DEGENERATE_NORM;
```
However, the error accumulator at line 902 reads:
```cpp
err = std::max(err, std::abs(s - (r == c ? 1.0 : 0.0)));
```
In C++, `std::max(a, b)` returns `a` if `a < b` is false. Because any comparison with `NaN` is false, `std::max(0.0, NaN)` evaluates to **`0.0`**. 
Consequently, `err` remains exactly `0.0` despite the matrix being filled with `NaN`s. The check `if (0.0 > 64 * eps)` evaluates to `false`, and the function returns `POLYDIM_SUCCESS`.
**This silently passes catastrophic failure and violates the most critical Anti-Hallucination constraint.**

### D. BLAS Path Impact (`dgeqp3`)
In the BLAS path, `dgeqp3` operates on the insufficiently regularized matrix. While QR pivoting handles the numerical singularity better, the condition number remains artificially massive ($\sim 10^{15}$). The back-substitution in `dtrtrs` will amplify the components by $10^{15}$, making the final tensor explode physically, completely losing the geometric properties of $S^{D-1}$.

## 3. Red Team Recommendations
1. **Dynamic Regularization Floor**: Remove the hardcoded $10^{-15}$. The floor must be dynamically scaled by the matrix dimension and $\epsilon$. `lambda = std::max(K2 * 2.22e-16 * m_inf, tol.pivot_rel * m_inf)`.
2. **Re-Enable the Pivot Safety Net**: Do not bypass `if (!(best > pivot_thr))` on the second pass. If the pivot collapses despite Tikhonov regularization, the code MUST abort with `POLYDIM_ERR_NUMERICAL_INSTABILITY`.
3. **Anti-NaN Geometry Check**: Replace `std::max` with a strict `std::isnan()` check inside the reduction loop. If any `NaN` is detected, immediately return `POLYDIM_ERR_NAN_OR_INF`.
