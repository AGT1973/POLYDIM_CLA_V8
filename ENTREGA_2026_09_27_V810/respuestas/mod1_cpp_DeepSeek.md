# ADVERSARIAL AUDIT — POLYDIM V810 (kernel_cpp_v810.cpp)

**Auditor stance:** Hostile. Assume every comment is a lie until proven otherwise. Every "fix" is a candidate regression. Every `#pragma omp` is a data race until the memory model says otherwise.

**Global preconditions assumed for the audit:**
- `PolydimSolverOptions`, `PolydimSolverResult`, `PolydimTelemetryBuffer`, `PolydimTelemetryPoint`, `PolydimTelemetryEvent`, `PolydimSpscRing`, `PolydimHandle` are PODs with the field names used below (I cannot see the header; I flag every place where the header's layout is load-bearing).
- `POLYDIM_STATUS_*` are distinct non-zero int32 codes; `POLYDIM_STATUS_OK == 0`.
- `POLYDIM_RETRACTION_CAYLEY_SMW` is a valid enum value.
- `omp_get_max_threads()` is available when `_OPENMP` is defined; the fallback stub in the file only defines `omp_get_num_threads`/`omp_get_thread_num`, **not** `omp_get_max_threads` — this is a compile-time landmine (see §8).

---

## §0. Cross-cutting defects (apply to multiple functions)

### 0.1 `omp_get_max_threads` is not stubbed in the non-OpenMP path
The file defines:
```cpp
static inline int omp_get_num_threads(void) { return 1; }
static inline int omp_get_thread_num(void)  { return 0; }
```
but `compute_VtZ` calls `omp_get_max_threads()`. **Non-OpenMP builds fail to compile.** This is a hard build break, not a runtime bug.

**Patch:**
```cpp
#if !defined(_OPENMP)
static inline int omp_get_max_threads(void) { return 1; }
#endif
```

### 0.2 `#include <immintrin.h>` duplicated
Line 1 and line 2 of the include block both include `<immintrin.h>`. Harmless (include guards) but signals copy-paste rot. Not a vulnerability.

### 0.3 `polydim_abi_probe` returns `sizeof(PolydimSolverOptions)` — ABI drift is *detected* but not *enforced*
The comment says "Python debe comparar esto en el arranque." That is a **contract, not a mechanism**. If Python forgets, silent ABI mismatch. Not a kernel bug per se, but the audit target claims "Barrera dura de deriva de ABI" — it is not hard. **Verdict: misleading comment, not a code defect.**

### 0.4 `g_fp_mode` is `std::atomic<int32_t>` but read with `memory_order_relaxed` in `polydim_gram_dsyrk`
`polydim_set_fp_mode` uses `relaxed` store; `polydim_gram_dsyrk` uses `relaxed` load. If a caller flips the mode mid-solve, the *next* `polydim_gram_dsyrk` call may see either value. That is fine for a mode flag, but the *deterministic* path allocates a `std::vector<double> products(D)` **inside** the parallel region — see §5.

---

## §1. `polydim_abi_probe`

1. **FUNCTION NAME:** `polydim_abi_probe`
2. **VERDICT:** CERTIFIED
3. **REASONING:** Pure `sizeof` on a POD. No memory access, no ordering, no arithmetic. The only failure mode is if `PolydimSolverOptions` is not a complete type at this TU — but it is included above. No UB.
4. **PATCH:** none.

---

## §2. FP mode accessors

### 2.1 `polydim_set_fp_mode`
1. **FUNCTION NAME:** `polydim_set_fp_mode`
2. **VERDICT:** CERTIFIED
3. **REASONING:** `relaxed` store to `int32_t` atomic. No ordering requirement — the mode is a hint, not a synchronization primitive. No torn writes on any platform where `int32_t` is lock-free (guaranteed by C++ for `int32_t` on all supported ABIs).
4. **PATCH:** none.

### 2.2 `polydim_get_fp_mode`
1. **FUNCTION NAME:** `polydim_get_fp_mode`
2. **VERDICT:** CERTIFIED
3. **REASONING:** Symmetric to 2.1.
4. **PATCH:** none.

---

## §3. `knuth_two_sum`

1. **FUNCTION NAME:** `knuth_two_sum`
2. **VERDICT:** CERTIFIED (with a caveat)
3. **REASONING:** The classic Knuth 2Sum requires round-to-nearest and no FMA contraction. **If the compiler contracts `(a - a_virtual) + (b - b_virtual)` into an FMA, the error term is wrong.** With `-ffast-math` or `-ffp-contract=fast` (default on some GCC/Clang configs for `-O2`), this is a silent correctness bug. The function is *mathematically* correct under IEEE-754 strict semantics; it is *not* robust to compiler contraction.
4. **PATCH:**
```cpp
static inline void knuth_two_sum(double a, double b, double* s, double* t) {
    double sum = a + b;
    double b_virtual = sum - a;
    double a_virtual = sum - b_virtual;
    *s = sum;
    *t = (a - a_virtual) + (b - b_virtual);
}
```
Add at file scope:
```cpp
#if defined(__GNUC__) || defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif
```
or compile with `-ffp-contract=off`. **Without this, the entire deterministic path is a lie.**

---

## §4. `twosum_tree_reduce_inplace`

1. **FUNCTION NAME:** `twosum_tree_reduce_inplace`
2. **VERDICT:** VULNERABLE
3. **REASONING:**
   - **Correctness of the tree:** The pairwise reduction is correct in structure. However, the error accumulation `err_acc`/`err_comp` is a **non-associative** accumulation of the error terms. The final `s_final + (t_final + err_comp)` is a *heuristic* compensated sum, not a rigorous bound. The function name promises "twosum tree reduce"; the implementation is a **tree reduce with a running compensated accumulator**, which is *not* the same as a full 2Sum tree. The error bound is not the classical `O(u log N)` of a true 2Sum tree; it is `O(u * N)` in the worst case because `err_comp` is a plain `double` accumulator.
   - **In-place aliasing:** `current` is both input and output. The loop writes `current[i]` for `i < n_pairs` while reading `current[2*i]`, `current[2*i+1]`. Since `i < n_pairs <= len/2`, and `2*i >= i` always, and `2*i+1 > i`, the write index is always strictly less than the read indices. **No aliasing hazard.** ✓
   - **Odd-length handling:** `current[n_pairs] = current[len-1]` — when `len` is odd, `n_pairs = (len-1)/2`, so `n_pairs < len-1` for `len >= 3`. For `len == 1` the loop doesn't execute. ✓
   - **`err_comp` overflow:** `err_comp` accumulates `et` terms which are `O(u^2 * |a|)`; for `N = 10^9` and `|a| ~ 1`, `err_comp` can reach `~10^-7`, well within `double` range. Not a practical overflow.
   - **The real bug:** the function is **not** a 2Sum tree. It is a tree-sum with a compensated *residual*. The asymptotic error is `O(u * N)` in the worst case, not `O(u log N)`. For the deterministic path in `polydim_gram_dsyrk`, this means the "deterministic" mode is deterministic but **not** more accurate than a naive sum in the worst case. The comment in the header claims otherwise.
4. **PATCH:** Replace with a true 2Sum tree that propagates the error term through the tree:
```cpp
static double twosum_tree_reduce_inplace(double* current, size_t N) {
    if (N == 0) return 0.0;
    if (N == 1) return current[0];
    size_t len = N;
    while (len > 1) {
        size_t n_pairs = len / 2;
        for (size_t i = 0; i < n_pairs; ++i) {
            double s, t;
            knuth_two_sum(current[2*i], current[2*i+1], &s, &t);
            current[i] = s;
            // propagate t into the next level by adding it to the *next* element
            // (this is the standard "distillation" trick; requires a second buffer)
        }
        // ... requires a scratch buffer to hold t terms
    }
}
```
The honest fix is to allocate a scratch buffer of size `N` and run a proper distillation. **The current implementation is a heuristic, not a certified compensated sum.**

---

## §5. `twosum_tree_reduce`

1. **FUNCTION NAME:** `twosum_tree_reduce`
2. **VERDICT:** VULNERABLE
3. **REASONING:** Allocates `std::vector<double> current(data, data + N)` on **every call**. In `polydim_gram_dsyrk`'s deterministic path, this is called `O(K^2)` times inside a parallel region. For `K = 256`, that is `~32k` heap allocations per Gram matrix. **This is the exact "memory allocation inside hot loops" attack vector.** The allocation is also inside an `#pragma omp parallel` region, so it is a per-thread allocation — but the vector is constructed *inside* the loop body, so it is per-`(i,j)` pair, not per-thread.
4. **PATCH:** Hoist the scratch buffer out of the loop. See §5.1 below.

### 5.1 `polydim_gram_dsyrk` — deterministic path
1. **FUNCTION NAME:** `polydim_gram_dsyrk` (deterministic branch)
2. **VERDICT:** VULNERABLE
3. **REASONING:**
   - **Allocation in hot loop:** `std::vector<double> products(D)` is declared *inside* the `#pragma omp parallel` region but *outside* the `#pragma omp for`. That is correct — one buffer per thread. ✓ **But** `twosum_tree_reduce_inplace` is called on `products.data()`, which is fine. The real issue is that `products` is `D` doubles per thread; for `D = 10^6` and 64 threads, that is 512 MB of scratch. Not a bug, but a scalability cliff.
   - **`schedule(dynamic)`:** The comment says "un solo buffer por hilo" — true. But `schedule(dynamic)` with default chunk size 1 causes `O(K^2)` atomic increments on the OpenMP runtime's internal counter. For `K = 256`, that is `~32k` atomic ops. **This is a throughput bug, not a correctness bug.** Use `schedule(static)` or `schedule(dynamic, 8)`.
   - **Symmetry write:** `K_out[i*K+j] = val; K_out[j*K+i] = val;` — for `i == j`, this writes the same location twice with the same value. Benign. ✓
   - **`memset(K_out, 0, K*K*sizeof(double))` before the parallel region:** correct, but the deterministic path overwrites every element anyway. The `memset` is redundant in the deterministic path and only needed for the `beta=0` case in the throughput path. Minor.
   - **`omp_set_num_threads(threads)` inside the function:** this is a **global** OpenMP setting. Calling `polydim_gram_dsyrk` from multiple threads concurrently will race on the OpenMP runtime's thread count. **This is a real concurrency bug** if the caller ever invokes this from a parallel region.
4. **PATCH:**
```cpp
POLYDIM_EXPORT int32_t polydim_gram_dsyrk(const double* X, size_t D, size_t K,
                                          double* K_out, uint32_t num_threads) {
    if (!X || !K_out) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (D == 0 || K == 0) return POLYDIM_STATUS_ERR_INVALID_DIM;
    // Do NOT call omp_set_num_threads here; use num_threads clause instead.
    std::memset(K_out, 0, K * K * sizeof(double));
    if (g_fp_mode.load(std::memory_order_relaxed) == POLYDIM_FP_DETERMINISTIC) {
        #pragma omp parallel num_threads(num_threads > 0 ? num_threads : 1)
        {
            std::vector<double> products(D);
            #pragma omp for schedule(static)
            for (int64_t i = 0; i < (int64_t)K; ++i) {
                for (size_t j = (size_t)i; j < K; ++j) {
                    for (size_t d = 0; d < D; ++d)
                        products[d] = X[d * K + i] * X[d * K + j];
                    double val = twosum_tree_reduce_inplace(products.data(), D);
                    K_out[i * K + j] = val;
                    K_out[j * K + i] = val;
                }
            }
        }
    } else {
        tiled_dsyrk_fixed(CblasTrans, K, D, 1.0, X, K, 0.0, K_out, K);
        for (size_t i = 0; i < K; ++i)
            for (size_t j = 0; j < i; ++j)
                K_out[i * K + j] = K_out[j * K + i];
    }
    return POLYDIM_STATUS_OK;
}
```

---

## §6. `polydim_stream_copy_nt`

1. **FUNCTION NAME:** `polydim_stream_copy_nt`
2. **VERDICT:** VULNERABLE
3. **REASONING:**
   - **`_mm_stream_pd` requires 16-byte alignment of `dest`.** The code checks `reinterpret_cast<uintptr_t>(dest) % 16 == 0`. ✓
   - **`_mm_loadu_pd` on `src`:** unaligned load is fine. ✓
   - **`std::atomic_thread_fence(std::memory_order_seq_cst)` inside the parallel region:** this is a **full fence per thread**, executed once per thread. It is *not* a barrier — it does not synchronize threads. The intent appears to be "flush the NT stores before returning." The correct primitive is `_mm_sfence()` (which is called after the parallel region). The `seq_cst` fence inside the parallel region is **redundant and misleading**. It does not order NT stores across threads.
   - **The tail loop `for (; i < count; ++i) dest[i] = src[i];`** runs on the master thread only. If `count` is odd, the last element is written by the master thread while other threads may still be in the parallel region. **This is a data race** if the parallel region has not been joined. Actually, `#pragma omp parallel` has an implicit barrier at the end, so the master thread waits. ✓ But the `seq_cst` fence inside the parallel region is still wrong.
   - **`_mm_sfence()` is called unconditionally after the parallel region**, even if the SSE path was not taken. Harmless.
   - **The `seq_cst` fence after `_mm_sfence()`** is redundant. `_mm_sfence()` already orders NT stores.
   - **Real bug:** if `dest` is 16-byte aligned but `count < 2`, the SSE path is skipped and the scalar loop runs. ✓
   - **Real bug:** if `dest` is 16-byte aligned and `count >= 2`, `sse_blocks = count / 2`, and the SSE loop writes `sse_blocks * 2` elements. The tail loop writes the remaining `count % 2` elements. ✓
   - **The `seq_cst` fence inside the parallel region is a performance bug** (full fence per thread) and a **semantic bug** (it does not do what the comment implies).
4. **PATCH:**
```cpp
POLYDIM_EXPORT int32_t polydim_stream_copy_nt(double* dest, const double* src, size_t count) {
    if (!dest || !src) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (count == 0)    return POLYDIM_STATUS_OK;
    size_t i = 0;
    if ((reinterpret_cast<uintptr_t>(dest) % 16 == 0) && count >= 2) {
        size_t sse_blocks = count / 2;
        #pragma omp parallel for schedule(static)
        for (size_t b = 0; b < sse_blocks; ++b) {
            size_t idx = b * 2;
            _mm_stream_pd(&dest[idx], _mm_loadu_pd(&src[idx]));
        }
        i = sse_blocks * 2;
    }
    for (; i < count; ++i) dest[i] = src[i];
#if defined(__x86_64__) || defined(_M_X64)
    _mm_sfence();
#endif
   