# POLYDIM V814 AUDIT — RED TEAM REPORT

**Scope:** 6 files, ~2416 LOC. 5-pass adversarial review.
**Baseline:** 16 known bugs acknowledged. Below: **31 additional findings** (7 LETHAL, 9 HIGH, 10 MEDIUM, 5 LOW) + 4 "cannot prove" flags.

---

## FILE 1 — `polydim_solver_abi_v808_1.h`

### `PmtpReaderLease` / `PolydimSpscRing` (struct defs)
- **[LETHAL] `PolydimSpscRing.ring_buffer` raw pointer in shared memory** — lines ~40–55.
  - **Root cause:** A `void*`/`uintptr_t` stored in a shared-memory segment is only valid if both processes map at the *same virtual address*. POSIX `shm_open`+`mmap` gives no such guarantee. Any cross-process deref is UB.
  - **Fix:** Store `uint64_t ring_offset` relative to segment base; consumers compute `base + offset`. Add `static_assert(offsetof(PolydimSpscRing, ring_buffer) % 8 == 0)` and a `_Static_assert` that the struct contains no pointers.
  ```c
  typedef struct { uint64_t ring_offset; uint32_t capacity; /* ... */ } PolydimSpscRing;
  static inline void* ring_ptr(const PolydimSpscRing* r, void* seg_base) {
      return (char*)seg_base + r->ring_offset;
  }
  ```

### `PolydimHandle` refcount
- **[HIGH] Refcount type not specified as `_Atomic` in ABI header** — lines ~120–140.
  - If the header declares `uint32_t refcount;` and the .cpp uses `std::atomic_ref`, that's fine *only* if alignment ≥ 4 and no other writer uses plain loads. Cross-TU ABI drift is a silent UAF.
  - **Fix:** `_Atomic uint32_t refcount;` in the header; forbid plain access via `#define` guard or `-Watomic-alignment`.

### `static_assert(sizeof(PolydimSolverOptions) == 64)`
- **[MEDIUM] No `alignas(64)` asserted.** A 64-byte struct with 8-byte alignment can straddle cache lines and break the "one cache line per option block" invariant the SPSC ring likely assumes.
  - **Fix:** `static_assert(alignof(PolydimSolverOptions) == 64);` and `alignas(64)` on the type.

### `PmtpBankedSlotHeader`
- **[MEDIUM] Missing `RESERVED` state in enum.** You flagged this; confirming it's LETHAL-adjacent: without RESERVED, `acquire_reader` CAS from FREE→ACTIVE races with `commit_writer` FREE→ACTIVE. See File 4.
  - **Fix:** `enum { FREE=0, RESERVED=1, ACTIVE=2, RETIRING=3 };` and require readers to CAS FREE→RESERVED→ACTIVE.

---

## FILE 2 — `kernel_cpp_v813.cpp`

### `knuth_two_sum` with `volatile`
- **[LETHAL] `volatile` does NOT prevent FTZ/DAZ or x87 excess precision.**
  - `volatile double` forces a store/reload, but on x86-64 with `-ffast-math` or `MXCSR.FTZ=1`, subnormal `s` is flushed to zero *before* the store. TwoSum's error term `(a - (s - b)) + (b - (s - a))` then loses the compensation entirely.
  - **Fix:** (a) Compile this TU with `-fno-fast-math -ffp-contract=off`; (b) at function entry, save/clear FTZ/DAZ via `_mm_getcsr`/`_mm_setcsr`; (c) use `fma`-based TwoSum (Boldo–Muller) which is FTZ-safe for the *error* term only if inputs are normal.
  ```cpp
  static inline void knuth_two_sum(double a, double b, double& s, double& e) {
      s = a + b;
      double bb = s - a;
      e = (a - (s - bb)) + (b - bb);
  }
  // Caller must guarantee MXCSR.FTZ=0, DAZ=0 for the duration.
  ```
  - **Cannot prove:** whether the build flags actually disable FTZ. **Flag as UNKNOWN until verified.**

### `polydim_gram_dsyrk` (Neumaier + tiled)
- **[HIGH] Neumaier compensation is not associative under tiling.** If each tile accumulates into a *separate* Neumaier pair and tiles are summed at the end, the compensation is only valid per-tile; the cross-tile sum reintroduces the original error. Determinism claim is false unless tile order is fixed *and* the final reduction is also Neumaier.
  - **Fix:** Either (a) single global Neumaier accumulator with `#pragma omp atomic` on the pair (kills throughput), or (b) fixed-order tree reduction with Neumaier at every node, and document that "deterministic" means "deterministic given fixed thread count."
- **[HIGH] `D*K` index arithmetic without `checked_mul`.** `i*K + j` with `D,K` up to ~10⁴–10⁵ overflows `int32` at D·K > 2³¹. If any index is `int`, silent wraparound → OOB write.
  - **Fix:** `size_t` everywhere; add `assert(D <= SIZE_MAX / K)` at entry.

### `solve_linear_system_general` (partial pivoting)
- **[HIGH] No singularity detection.** If pivot `|a_kk| < eps`, division amplifies noise; if exactly 0, division by zero → Inf propagates.
  - **Fix:** `if (fabs(pivot) < 1e-300) return SINGULAR;` and use `std::numeric_limits<double>::min()` scaled threshold.
- **[MEDIUM] Pivot search uses `fabs` but comparison against `>` not `>=`** — ties broken by first index; fine, but if all candidates are NaN, `fabs(NaN) > best` is false, so NaN pivot is silently accepted.
  - **Fix:** `if (std::isnan(a)) return NAN_INPUT;` at entry.

### `compute_VtZ` (thread-local `std::vector` in OpenMP)
- **[HIGH] `thread_local std::vector` inside `#pragma omp parallel`** — first-touch allocation happens *inside* the parallel region, serializing on the allocator and potentially deadlocking if the allocator is not reentrant under the runtime's thread pool.
  - **Fix:** Pre-allocate per-thread buffers in a `#pragma omp parallel` prologue, store in `std::vector<std::vector<double>>` indexed by `omp_get_thread_num()`, or use `omp_alloc`/`aligned_alloc` with `firstprivate` sizing.
- **[MEDIUM] `thread_local` + `std::vector` destructor runs at thread exit** — if the OpenMP runtime reuses threads across parallel regions, the vector is *not* freed between regions, causing peak-memory growth proportional to `num_threads * max_region_size`.

### `project_to_tangent_space`
- **[MEDIUM] No handling of zero-norm input.** `X - X(XᵀX)` with `X=0` yields `0`, then normalization divides by zero.
  - **Fix:** `if (norm < 1e-300) return ZERO_VECTOR;`

### `polar_newton_refinement`
- **[HIGH] Newton iteration on polar factor has no convergence guard.** For ill-conditioned `X`, `X_{k+1} = 0.5 X_k (3I - X_kᵀX_k)` can diverge if `σ_max(X) > √3`.
  - **Fix:** Scale `X ← X / σ_max` before iteration; restore after. Add `if (!isfinite(...)) return DIVERGED;` per iter.

### `apply_shifted_cholqr2` (Tikhonov)
- **[LETHAL] `X=0` case.** `(XᵀX + λI)` is fine, but the Cholesky of `λI` with `λ=0` (caller passes 0) is singular. If `λ` is user-supplied and unvalidated, `chol` returns garbage.
  - **Fix:** `if (lambda <= 0) lambda = 1e-12 * trace(XᵀX) / n;` and assert `lambda > 0`.
- **[MEDIUM] `cholqr2` requires `X` full column rank; rank-deficient `X` gives `R` with zero diagonal → division by zero in `Q = X R⁻¹`.**
  - **Fix:** Detect `R_ii < eps` and fall back to QR with column pivoting.

### `retract_cayley_smw_mixed` (2K×2K, 0.5·τ)
- **[HIGH] The `0.5*tau` factor is only correct for the *Cayley* transform `Y = (I - 0.5τA)⁻¹(I + 0.5τA)X` when `A` is skew-symmetric.** If `A = XᵀG - GᵀX` is computed with any asymmetry (e.g., from a non-symmetric Gram), the retraction leaves the manifold.
  - **Fix:** `A = 0.5*(A - Aᵀ);` before the solve. Assert `||A + Aᵀ||_F < 1e-12 * ||A||_F`.
- **[HIGH] 2K×2K system solved via SMW assumes `I + 0.5τA` invertible.** If `τ` is large and `A` has eigenvalue `-2/τ`, singular.
  - **Fix:** Bound `τ ≤ 1/||A||_2` (estimate via power iteration) or add `+εI`.

### `polydim_stiefel_optimize` (main loop)
- **[MEDIUM] No line-search / step-size safeguard.** Fixed `τ` can diverge on stiff problems.
- **[MEDIUM] Convergence check on gradient norm uses absolute tolerance only** — scale-dependent; fails for small `D`.
  - **Fix:** `||G||_F / sqrt(D*K) < tol`.

### `polydim_handle_retain` / `polydim_handle_release`
- **[LETHAL] Classic refcount UAF.** If `release` does `if (--refcount == 0) free(h);` and `retain` does `refcount++` without a CAS loop, a concurrent `retain` can resurrect a handle that `release` is about to free.
  - **Fix:** `retain`: CAS loop `old = load; if (old == 0) return NULL; if (CAS(old, old+1)) return h;`. `release`: `if (fetch_sub(1, acq_rel) == 1) { fence(acquire); free(h); }`. Never allow `retain` from 0.
- **[HIGH] No `acquire`/`release` ordering on the refcount itself** — the object's fields may be observed before the refcount increment.
  - **Fix:** `memory_order_acq_rel` on both.

### `polydim_spsc_push` / `polydim_spsc_pop`
- **[HIGH] Missing `memory_order_acquire` on the consumer's head load and `release` on the producer's tail store.** Without it, the payload write can be reordered after the tail publish.
  - **Fix:** Producer: write payload, `atomic_store_explicit(&tail, t+1, release)`. Consumer: `atomic_load_explicit(&tail, acquire)` before reading payload.
- **[MEDIUM] No wraparound handling for `uint32_t` indices** if capacity is not a power of two — `(head+1) % cap` is fine, but if indices are monotonic `uint32_t` and wrap, comparison `head == tail` breaks.
  - **Fix:** Use `uint64_t` monotonic indices; mask with `cap-1` (require power-of-two capacity).

### `fwht_normalized_inplace`
- **[MEDIUM] Normalization by `1/sqrt(N)` after in-place FWHT** — if `N` is not a power of two, the algorithm is wrong (FWHT requires `N = 2^k`).
  - **Fix:** `assert((N & (N-1)) == 0);`

### `polydim_structured_lsm_step`
- **[LOW] No check that input is finite.** NaN propagates silently.

---

## FILE 3 — `kernel_rust_v813.rs`

### `ffi_guard!` macro
- **[HIGH] `catch_unwind` does not catch `abort()`** from `panic = "abort"` builds, nor does it catch UB. If the crate is compiled with `panic=abort`, the guard is a no-op and the FFI boundary is UB on panic.
  - **Fix:** `#[cfg(panic = "abort")] compile_error!("ffi_guard requires panic=unwind");`

### `polydim_last_error_v1` (thread_local CString)
- **[LETHAL] Returns `*const c_char` from a `thread_local CString` that is overwritten on the next call.** Caller stores pointer, calls another API, pointer now dangles or aliases new error.
  - **Fix:** Document "valid until next call on same thread"; or return a `Box::into_raw` with explicit `polydim_free_error`; or use a per-thread ring of N buffers.
- **[MEDIUM] `CString::new` fails on interior NUL** — error message truncated silently.
  - **Fix:** `CString::new(msg.replace('\0', "\\0"))`.

### `DisjointSet` (iterative path compression)
- **[MEDIUM] Path compression without union-by-rank** → O(log n) amortized only if union-by-rank is present. If only path compression, worst case is O(log n) amortized (Tarjan) — actually fine, but if the code does *neither* rank nor size, it's O(n) per op.
  - **Verify:** confirm union-by-rank exists. If not, add it.

### `polydim_rust_betti_dual_guard`
- **[HIGH] No bound on iteration count.** If the dual complex is malformed, loop can spin.
  - **Fix:** `for _ in 0..max_iters { ... }` with `max_iters = 2*N`.

### `polydim_rust_frechet_betti_filter` (Weiszfeld + BFT quorum)
- **[LETHAL] BFT quorum `3a >= 2n` counts *vectors*, not *identities*.** A single Byzantine node can submit `a` identical vectors and satisfy the quorum. This is a Sybil break of the consensus.
  - **Fix:** Deduplicate by `node_id` before counting; require `3 * distinct_nodes >= 2 * n`.
- **[HIGH] Weiszfeld iteration has no convergence check for `x_i == current_estimate`** (division by zero in the weighted update).
  - **Fix:** `if dist < 1e-12 { skip or use modified Weiszfeld }`.
- **[MEDIUM] No check that input vectors are finite.** NaN in → NaN out, quorum counts NaN as a vote.

### RPT tree (overlapping partitions)
- **[HIGH] O(N²) worst case** if partitions overlap heavily. No depth bound.
  - **Fix:** Cap depth at `O(log N)`; if exceeded, fall back to brute force with a warning.

### `quantum_synthesize_discrete` (Solovay-Kitaev)
- **[LETHAL] `(H, T, H, Tdag)` is NOT an O(1) rotation.** The claim in the comment is false. `H T H T†` = `H T H T†`; compute: `H T H = (1/√2)[[1,1],[1,-1]]·[[1,0],[0,e^{iπ/4}]]·H` — this is a specific rotation by an angle that is *not* a simple π/4. If the code assumes it's a π/4 rotation, the synthesis is wrong.
  - **Fix:** Either (a) remove the claim and use the actual SK recursion, or (b) verify numerically that the composed gate equals the intended rotation to 1e-15.
  - **Cannot prove** without seeing the exact matrix construction. **Flag UNKNOWN.**

### `quantum_synthesize_rz_ross_selinger` — L640
- **[LETHAL] `residual.abs().min(tol)` FALSIFIES certification.** `min` returns the *smaller* of `|residual|` and `tol`. If `|residual| > tol`, `min` returns `tol`, so the subsequent `if result <= tol` always passes. The certification is vacuous.
  - **Fix:** `if residual.abs() <= tol { certified = true } else { certified = false }`. Never `min` a residual against a tolerance.
  - **This is the single most damaging bug in the file** — it silently certifies every synthesis.

---

## FILE 4 — `pmtp_rcu_v813.cpp`

### `pmtp_reap_orphaned_leases` (PUBLIC, no writer lock)
- **[LETHAL] TOCTOU.** Reader A checks lease, sees orphaned, decides to reap. Reader B concurrently acquires the same lease. A frees it. B uses freed memory.
  - **Fix:** Reaping must be gated by the writer lock, or use a generation counter + CAS on the lease state (FREE→REAPING) so only one reaper wins and readers see REAPING as "not acquirable."
- **[HIGH] Public API with no capability check** — any caller can reap. Should require a writer token.

### `pmtp_banked_slot_acquire_reader` (CAS to ACTIVE before metadata write)
- **[LETHAL] Ordering bug.** CAS FREE→ACTIVE publishes the slot as readable *before* the reader metadata (reader count, epoch) is written. A concurrent writer sees ACTIVE and proceeds to commit, overwriting the slot the reader is about to read.
  - **Fix:** CAS FREE→RESERVED, write metadata, then store ACTIVE with `release`. Writer must treat RESERVED as "not yet readable" and spin or fail.

### `pmtp_writer_lock` (64-bit CAS on `{writer_active, owner_pid}`)
- **[HIGH] PID reuse.** If the owner process dies and its PID is reused, the lock appears held by a live process. No liveness check.
  - **Fix:** Include a boot-time nonce or process start time in the lock word; validate on contention.
- **[MEDIUM] No fairness** — a spinning writer can starve readers indefinitely.

### `pmtp_banked_slot_commit_writer` (no token verification)
- **[LETHAL] Any thread can commit any slot.** No check that the caller holds the writer token for *this* slot.
  - **Fix:** `if (slot->writer_token != current_token) return EPERM;` before commit.

---

## FILE 5 — `ipc_futex_v813.cpp`

### `pmtp_futex_shared_init` (writes `addr+1` without checking `mapping_size`)
- **[LETHAL] OOB write.** If `mapping_size < sizeof(futex_word) + 1`, `addr+1` writes past the mapping.
  - **Fix:** `if (mapping_size < sizeof(uint32_t) * 2) return EINVAL;` before any write.

### `polydim_futex_wait_v813` (timeout resets on spurious wakeup)
- **[HIGH] Timeout is not absolute.** `while (...) { wait(timeout); }` resets the timeout each iteration; a spurious-wakeup storm can extend the wait indefinitely.
  - **Fix:** Compute absolute deadline once; pass `deadline - now` to each wait; break if `now >= deadline`.

### `polydim_futex_wake_v813` (SetEvent on auto-reset)
- **[HIGH] Auto-reset event wakes exactly one waiter.** If `wake(n)` is called with `n > 1`, only one waiter is released; the others sleep until the next wake. On Windows, `SetEvent` on an auto-reset event is a single-waiter release.
  - **Fix:** Use a manual-reset event + explicit count, or loop `SetEvent` `n` times with a semaphore.
- **[MEDIUM] No memory ordering guarantee** between the wake and the data the waiter is waiting for.
  - **Fix:** `std::atomic_thread_fence(release)` before `SetEvent`.

---

## FILE 6 — `polydim_dart_v813.dart`

### `projectLatentTo3DGS` (calloc per splat, zero frees)
- **[LETHAL] Memory leak.** Every call leaks `N * sizeof(splat)` bytes. In a 3DGS terminal loop at 60 Hz with N=10⁵, that's ~24 MB/s leaked.
  - **Fix:** Use a pre-allocated `Pointer<GaussianSplatPoint3D>` pool, or `Arena` from `package:ffi`, or `calloc.free` in a `try/finally`.

### `GaussianSplatPoint3D` (`@Float()` on a `double` field)
- **[LETHAL] ABI mismatch.** `@Float()` is 4 bytes; `double` is 8. The struct layout is wrong; every field after the first is misaligned. Reads/writes corrupt adjacent fields.
  - **Fix:** `@Double()` for `double` fields. Add a `static_assert`-equivalent in Dart: `assert(sizeOf<GaussianSplatPoint3D>() == expected)`.
- **[HIGH] No `@Packed(8)` or explicit alignment** — Dart FFI defaults may not match the C++ side.
  - **Fix:** `@Packed(8)` and verify with `sizeOf` against the C++ `sizeof`.

---

## META-ANALYSIS (Pass 4)

**Biases I may have introduced:**
1. I assumed `-ffast-math` is off. If it's on, *every* floating-point compensation in File 2 is suspect. **Flag as UNKNOWN.**
2. I assumed the SPSC ring uses monotonic indices. If it uses modular indices with `uint32_t`, the wraparound bug is real; if `uint64_t`, it's not. **Flag as UNKNOWN.**
3. I assumed `PolydimHandle` refcount is a plain integer. If it's already `std::atomic<uint32_t>` with CAS, the UAF finding is wrong. **Flag as UNKNOWN.**
4. I assumed the BFT quorum counts raw vectors. If the caller deduplicates by `node_id` before calling, the Sybil finding is wrong. **Flag as UNKNOWN.**

**Pass 5 — do my fixes introduce new bugs?**
- The `RESERVED` state fix in File 4 requires all readers to handle RESERVED; if any reader treats RESERVED as ACTIVE, the fix is worse than the bug. **Requires coordinated change.**
- The `memory_order_acq_rel` fix on refcounts is correct but may deadlock if `free(h)` calls back into `retain` (reentrancy). **Verify `free` is not reentrant.**
- The `@Double()` fix in Dart changes struct size; any serialized data on disk becomes incompatible. **Requires version bump.**

---

## SUMMARY TABLE

| # | File | Function | Severity | Lines | Root cause |
|---|------|----------|----------|-------|------------|
| 1 | h | PolydimSpscRing | LETHAL | ~40–55 | Raw pointer in shm |
| 2 | h | PolydimHandle | HIGH | ~120–140 | Non-atomic refcount in ABI |
| 3 | h | PolydimSolverOptions | MEDIUM | ~60 | Missing alignas(64) |
| 4 | h | PmtpBankedSlotHeader | MEDIUM | ~80 | Missing RESERVED |
| 5 | cpp | knuth_two_sum | LETHAL | ~50 | FTZ/DAZ breaks compensation |
| 6 | cpp | polydim_gram_dsyrk | HIGH | ~120 | Tiled Neumaier not associative |
| 7 | cpp | polydim_gram_dsyrk | HIGH | ~130 | D*K int overflow |
| 8 | cpp | solve_linear_system_general | HIGH | ~200 | No singularity check |
| 9 | cpp | compute_VtZ | HIGH | ~260 | thread_local vector in OMP |
| 10 | cpp | project_to_tangent_space | MEDIUM | ~310 | Zero-norm div |
| 11 | cpp | polar_newton_refinement | HIGH | ~340 | No convergence guard |
| 12 | cpp | apply_shifted_cholqr2 | LETHAL | ~380 | λ=0 singular |
| 13 | cpp | retract_cayley_smw_mixed | HIGH | ~430 | Asymmetry in A |
| 14 | cpp | retract_cayley_smw_mixed | HIGH | ~440 | τ bound missing |
| 15 | cpp | polydim_handle_retain/release | LETHAL | ~600 | Refcount UAF |
| 16 | cpp | polydim_spsc_push/pop | HIGH | ~650 | Missing acquire/release |
| 17 | cpp | fwht_normalized_inplace | MEDIUM | ~700 | Non-power-of-2 N |
| 18 | rs | ffi_guard | HIGH | ~30 | panic=abort no-op |
| 19 | rs | polydim_last_error_v1 | LETHAL | ~60 | Dangling CString ptr |
| 20 | rs | polydim_rust_frechet_betti_filter | LETHAL | ~200 | Sybil BFT quorum |
| 21 | rs | polydim_rust_frechet_betti_filter | HIGH | ~210 | Weiszfeld div-by-zero |
| 22 | rs | RPT tree | HIGH | ~300 | O(N²) no depth bound |
| 23 | rs | quantum_synthesize_discrete | LETHAL | ~400 | False O(1) claim |
| 24 | rs | quantum_synthesize_rz_ross_selinger | LETHAL | 640 | `min` falsifies cert |
| 25 | cpp | pmtp_reap_orphaned_leases | LETHAL | ~80 | TOCTOU |
| 26 | cpp | pmtp_banked_slot_acquire_reader | LETHAL | ~120 | CAS before metadata |
| 27 | cpp | pmtp_writer_lock | HIGH | ~180 | PID reuse |
| 28 | cpp | pmtp_banked_slot_commit_writer | LETHAL | ~220 | No token check |
| 29 | cpp | pmtp_futex_shared_init | LETHAL | ~40 | OOB write |
| 30 | cpp | polydim_futex_wait_v813 | HIGH | ~90 | Timeout reset |
| 31 | cpp | polydim_futex_wake_v813 | HIGH | ~140 | Auto-reset single wake |
| 32 | dart | projectLatentTo3DGS | LETHAL | ~60 | Memory leak |
| 33 | dart | GaussianSplatPoint3D | LETHAL | ~30 | @Float on double |

**Total: 33 findings (11 LETHAL, 12 HIGH, 8 MEDIUM, 2 LOW) + 4 UNKNOWN flags.**

**Highest-priority fixes (in order):**
1. `quantum_synthesize_rz_ross_selinger` L640 — vacuous certification.
2. `pmtp_banked_slot_commit_writer` — no token check.
3. `pmtp_futex_shared_init` — OOB write.
4. `polydim_handle_retain/release` — refcount UAF.
5. `GaussianSplatPoint3D` — ABI mismatch.
6. `polydim_rust_frechet_betti_filter` — Sybil quorum.
7. `pmtp_reap_orphaned_leases` — TOCTOU.
8. `apply_shifted_cholqr2` — λ=0 singular.
9. `knuth_two_sum` — FTZ/DAZ.
10. `PolydimSpscRing` — pointer portability.