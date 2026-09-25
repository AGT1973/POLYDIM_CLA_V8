# Peer Review: POLYDIM Concurrency & Systems Fixes

Context assumed: D≈10⁷, K=512, shared-memory NUMA host, OpenMP + C++20 + Python FFI. I'll be blunt — several of these are correct in spirit but wrong or under-specified in the details that matter at this scale.

---

## B. Data Races & Concurrency

### B1. Atomic UB — A vs B

**Opción A (`std::atomic<uint64_t>` fields)** is the safe default. **Opción B (`std::atomic_ref`)** is SOTA *only* if the storage is `alignas(8)` **and** the lifetime/aliasing rules hold: `atomic_ref` requires that no other non-atomic access to the same object occurs during the ref's lifetime, and that you never take two `atomic_ref`s with different memory orders over overlapping regions. At D=10⁷ with readers iterating, you will trip this unless you enforce a strict phase (publish barrier → ref covers a sealed struct). Don't use `atomic_ref` opportunistically.

Gaps:
- Missing `alignas(64)` is *not* just perf: `atomic_ref<uint64_t>` on unaligned storage is **UB** (C++20 [atomics.ref.operations]/p1).
- `is_lock_free()` must be asserted at startup; on some older ARM64 it silently falls back to locks → priority inversion in the reader path.
- ABI: putting `std::atomic` in a `struct` shared with Python ctypes changes layout only if the underlying size differs (it doesn't on mainstream ABIs), but the *non-trivially-copyable* trait breaks `memcpy`-style FFI. Audit `PolydimEdge` — if you ever `memcpy` or `from_buffer` it, you're already UB.

**Recommendation:** Keep `std::atomic<uint64_t>` in the header, but isolate it in a `head` struct that Python never touches; expose sequence via a separate `uint64_t` mirror written under `release` after the atomic.

### B2. PMTP Banked Race (LMAX Disruptor pattern)

The `FREE → ACQUIRING` CAS is right, but the **writer-aborts-if-readers-active** rule is the bug generator:
- LMAX's ring works because *single writer*. Here you imply multiple bankers. If two threads CAS to ACQUIRING and both see "readers active" and both abort, you've livelocked under load. If one succeeds, no readers should be active — but your transition is `ACQUIRING → ACTIVE`, not `FREE → ACQUIRING → ACTIVE` atomically. A reader that observed `FREE` just before the CAS and is *about to* increment its reader count can arrive between CAS and the reader-active check → **use-after-free-style recycle**. This is the classic "StoreLoad on reader ingress" hole.
- Real fix: readers must enter via a `load(acquire)` of the state and a **seqlock-style** handshake — reader publishes intent, then re-reads state; if `ACQUIRING`, back off. Otherwise you need RCU-style grace periods, not a CAS on the bank header.

**Recommendation:** Replace with an explicit epoch/RCU scheme (`liburcu`-style): writer increments epoch, waits for all readers' snapshotted epochs (bounded by `synchronize_rcu`), then recycles. Or use a **single-writer MPSC ring per bank** and shard the readers.

### B3. Memory Ordering

`sequence.release` on write, `acquire` on read is correct **for the publication itself**, but insufficient for the reader's re-check loop:
```cpp
do { s1 = seq.load(acquire); ...read...; s2 = seq.load(acquire); } while (s1 != s2 || s1 & 1);
```
The second load must be `acquire` *or* you need a `std::atomic_thread_fence(acquire)` after the data read. On ARM64 this often "works" but is not guaranteed by the model. Also: the writer's `store(seq+1, release)` must be preceded by a `release` fence if writes to the payload used relaxed stores — at D=10⁷ you will use vectorized stores, which are not ordered.

**Recommendation:** Make it a proper **seqlock** with a documented invariant, and unit-test under `-fsanitize=thread` *and* herd7 litmus tests. TSO-only reasoning will bite on AArch64.

---

## C. Bottlenecks

### C1. OpenMP scratchpad

Correct, but `omp_get_max_threads()` is an upper bound, not the *bound of the parallel region's team*. If you oversubscribe or nested-parallelize, indexing `ThreadScratchpad[omp_get_thread_num()]` inside the outer region is safe; inside nested regions it is **not** (different team). Use `omp_get_thread_num()` within the *same* region that sized the array, or use `omp_get_max_threads()` for the allocation and `omp_get_thread_num()` only in non-nested contexts. Also: TLS alternative (`thread_local`) is often better on NUMA (first-touch), but requires per-thread init hooks.

Alignment: `alignas(64)` on a `struct` array is fine, but if the element size isn't a multiple of 64 you'll get false sharing on the *last* cacheline of each entry. Pad elements to `align_up(sizeof(T), 64)`.

### C2. Gram Matrix Parallelism — **this is wrong at your scale**

> "Cada hilo acumula en G_local[K×K] privado en L1."

K=512 → G is 512×512×8B = **2 MiB**. That does **not** fit in L1 (32–64 KiB) or even L2 (1–2 MiB) on most cores. Your "private in L1" claim is off by two orders of magnitude.

Consequences:
- Per-thread G spill to L3/DRAM; final reduction reads N_threads × 2 MiB. At 64 threads that's 128 MiB of DRAM traffic per reduction — likely dominates the compute.
- Parallelizing over D (10⁷) with per-thread K×K accumulation is fine **only if** the reduction cost is amortized. At outer-symmetric K=512, better: **block over K** (e.g., 64×64 tiles), accumulate into a per-thread tile block, and use a **hierarchical reduction over a tree of NUMA-local aggregates**.

**Recommendation:** Split-GEMM via cache-resident blocks; reduce in a NUMA-aware tree (pairs across sockets, then across dies). Measure reduction as a fraction of total time; if >15%, re-partition.

### C3. Dense Matrix OOM — Cayley-SMW Matrix-Free

Fine conceptually, but:
- "Tiling L2 (B≈8192)" — L2 is per-core and typically 512 KiB–2 MiB. B=8192 doubles ≈ 64 KiB per row → a tile is 64 KiB * B_row; you must specify **both** dimensions from L2 size at runtime (`sysconf`/`cpuid`), not hardcode.
- The **SMW (Sherman–Morrison–Woodbury)** update for rank-r modifications has O(K²r + Kr²) cost per step. At K=512 and r small, per-step is fine, but you must guarantee the base inverse stays **well-conditioned** across updates — re-factorize when `cond(A) * prod_i |1 + vᵀA⁻¹u|` exceeds 1/√eps. Add a Schmidt–recompute trigger.

### C4. Weiszfeld next_median

`std::swap` on pre-allocated buffers is right. Missing: **live-lock detection** and **zero-gradient-at-vertex** case (Weiszfeld's iteration has a well-known degenerate when the iterate coincides with a data point). You need the Vardi–Zhang modification (eps-insensitive weight at coincident points). Without it you'll NaN at exactly the configuration a robust library is expected to handle.

---

## D. Portability

### D1. ARM64 / NEON fallback

> Guard `#if defined(__x86_64__)` … fallback to NEON STNP.

STNP is a **non-temporal store hint**, not an intrinsic family. You want `<arm_neon.h>` / SVE. More importantly:
- `__x86_64__` misses `_M_X64` (MSVC) and `__amd64__`. Use `#if defined(__x86_64__) || defined(_M_X64)`.
- Runtime dispatch (AVX-512 vs AVX2 vs NEON vs SVE) beats compile-time guards for portability; `google/highway` or `xsimd` are the 2024–2026 baseline. Maintainability cost of hand-rolled NEON ≠ x86 duplication is real at this size.

### D2. Win32 APIs

Correct, but:
- `GetModuleHandleA` couples you to ANSI; use `GetModuleHandleW` + `utf8 → utf16` conversion for path correctness (rare but real bugs on non-ASCII paths).
- POSIX `<sys/types.h>` is needed for `ssize_t`; also `<unistd.h>`, `<dlfcn.h>`. Link `-ldl` on glibc < 2.34, omit on ≥ 2.34 (dl functions moved to libc) — otherwise you get either double-def or unresolved depending on toolchain. Guard with `__GLIBC_PREREQ`.

### D3. OpenMP index

> Replace `size_t` with `int64_t`.

Necessary but not sufficient. Correct OpenMP 4.5+ canonical loop form requires **signed** loop variable if you want `omp for` to accept it (unsigned integral *is* allowed since 3.0 with `<` but not with `!=`, and some compilers are picky with `size_t` on MSVC). The right rule:
- Loop counter: `std::ptrdiff_t` or `int64_t`.
- Indices used to address: keep `size_t`, but compute inside the loop with an explicit cast and **prove** the range fits.
- `#pragma omp parallel for` requires the trip count to fit in the loop variable type; at D=10⁷ that's fine, but if any caller passes a huge D from Python without checking, you'll overflow.

### D4. Power-of-2

Removing `(D & (D-1)) == 0` is right, but the padding strategy matters:
- FWHT wants power-of-2 *per axis*; zero-padding inflates D → memory and time blow up superlinearly. **Prefer Friedman–Tukey / zero-padded decomposition per axis with reconstruction** (drop padded coefficients) — this is O(D log D) with constant ~log of next-pow2(D)/D overhead, and is what e.g. `fastfood`/`Ailon–Chazelle` structured transforms do.
- Do not silently pad: expose a `PolydimPrecision{PAD, FRIEDMAN}` option so callers can trade memory for exactness.

---

## E. Numerics

### E1. NaN Propagation

> Replace `.max(1e-12)` with `safe_dist_clamp()` returning `ERR_NUMERICAL_NAN`.

Two problems:
1. `.max(1e-12)` silently destroys gradient information near zero; replacing it with an error may **break existing pipelines** that relied on the floor. This needs a feature flag and a migration note.
2. Propagating a sentinel `ERR_NUMERICAL_NAN` through SIMD is not free — you'll branch per lane or use a mask. Decide: do you want **poisoned propagation** (all downstream ops keep the sentinel, checked at reduction boundaries) or **immediate abort** (calls `std::terminate`/exception)? For HPC inner loops, poisoned propagation with a single check at the reduction boundary is the only performance-viable option. Document the contract.

### E2. Tolerances / Neumaier

`tol = c · D · eps_mach` is the **forward-error** heuristic for a dot product of D terms. Fine for iterative stopping, but:
- For *backward-stable* guarantees, use `tol = c · D · eps / (1 - D·eps)` (Higham 2nd ed., §3.5).
- `neumaier_sum` is **scalar** compensated summation; don't call it in a SIMD loop and expect vectorization. Use **vector compensated** (Ogita–Rump–Oishi `TwoProd`/`TwoSum` with FMA) — otherwise your "fix" regresses throughput 4–8×.
- At D=10⁷, scalar Neumaier is ~10⁷ fp ops *just for the compensation*, ~4× the cost of naive. Profile before merging.

---

## F. Python FFI

### F1. ctypes zero-copy

`(PolydimEdge * N).from_buffer(arr)` requires the buffer to be **writable** and **aligned**; if `arr` is read-only or backed by a non-contiguous view, you get `ValueError` or silent misreads. Also `from_buffer` gives you a Python object that mutates the NumPy array in place — fine, but you must match the C `struct` layout exactly, including padding. `np.ctypeslib.ndpointer(..., flags='C_CONTIGUOUS,ALIGNED,WRITEABLE')` is stricter and better; prefer it.

**The real SOTA answer in 2024–2026 is nanobind / pybind11 + DLPack**, not ctypes. ctypes at D=10⁷ will not be the bottleneck only if you're doing a *single* FFI call per kernel; if you're doing per-block calls, the Python call overhead kills you. Verify call frequency.

### F2. `np.require(...)`

Correct but note: `['C','A','W']` will **copy** if any requirement fails. If X is already C-contiguous and float64, zero copy; otherwise two copies (one in `require`, one implicit in the ctypes cast). Chain them so `require`'s output is the one passed to ctypes, not a re-derived view.

### F3. Stiefel VJP

Sylvester adjoint in SVD eigenbasis is correct **only when** the Stiefel point has well-separated singular values. Near-degenerate singular values (which happen with clustered data at K=512) the Sylvester system becomes ill-conditioned → VJP noise. Standard remedy: **block perturbation / Tikhonov damping with adaptive ridge = f(gap)**. Also: you're differentiating through SVD — sign/phase ambiguity in singular vectors must be fixed (per-vector gauge) or gradients will be wrong at the level of machine epsilon on symmetric inputs.

---

## G. FPU FTZ/DAZ

Correct pattern, but:
- **FTZ/DAZ must be set identically in every thread and every FFI host thread.** Python's main thread, NumPy's internal threads, and any `threading.Thread` will each need the guard. A global `pthread_atfork`-style init hook + an `atexit` restore is required; RAII alone leaves the first-call race open.
- Setting FTZ/DAZ changes **results** vs. denormal-honoring code. Library users computing subnormal-sensitive quantities (e.g., tail probabilities, log-domain softmax) will see silently different answers. Expose the policy explicitly (`PolydimFpuMode::FAST_DENORMAL` vs `IEEE`) and record it in kernel metadata for reproducibility.
- On AArch64, `FPCR` controls FZ (flush-to-zero) but there is **no DAZ equivalent** — denormals are always flushed if FZ is set. Your "salva/restaura MXCSR/FPCR" comment is fine, but the semantics differ; document that DAZ unification is x86-only.
- Restoring MXCSR from non-main threads: use `std::atomic` to publish a per-thread saved value if you also permit async cancellation (OpenMP `cancel`), otherwise restoration is skipped on cancellation.

---

## Cross-cutting gaps

1. **Reproducibility contract.** None of these fixes specifies determinism guarantees vs. thread count. For a numerical library at this scale, bitwise-reproducibility-across-`OMP_NUM_THREADS` is often a customer requirement; if so, the reduction orders in C2 and E2 must be **fixed** (e.g., pairwise over a canonical tree), not "whatever OpenMP does."
2. **NUMA.** D=10⁷ means the data doesn't fit in a socket's DRAM partition; all the "local" claims (C1, C2) are wrong without `numactl`-aware first-touch and allocation policy. Add `libnuma` allocation or `mmap` + `MPOL_BIND` in the initialization path.
3. **Testing.** Nothing here mentions TSan, `-fsanitize=address` with `detect_stack_use_after_return`, herd7 for the seqlock, or a fuzz target for the FFI boundary. At this concurrency level those are non-negotiable, not nice-to-haves.
4. **ABI/versioning.** Adding `std::atomic` fields and changing OpenMP index types changes layout/ABI; version the serialized form and the FFI struct with an explicit `uint32_t abi_version` at the head.
5. **Cancellation safety.** OpenMP `cancel` + RAII FPU guards + pre-allocated scratchpads interact badly; define a `TASK_ABORT` protocol or disable cancellation in these regions.

## Suggested SOTA refinements (tight list)

- Replace the disruptor-style PMTP with **RCU + epoch** or **seqlock with explicit acquire-fence tail**; prove with herd7 litmus tests.
- **Split-GEMM Gram** with NUMA-tree reduction; measure reduction fraction, target <15%.
- Runtime ISA dispatch via **highway**; drop hand-rolled NEON/AVX duplication.
- **Vector compensated summation** (Ogita–Rump–Oishi with FMA), not scalar Neumaier in hot loops.
- **nanobind/pybind11 + DLPack** instead of ctypes for anything called more than a few times per kernel.
- **FWHT over non-pow2 via Friedman–Tukey per axis**, not zero-pad.
- **FTZ/DAZ policy as explicit, thread- and host-initialized configuration**, not silent RAII.

Net: the direction of every fix is right. The failure modes are in the details — cache-size arithmetic (C2), reader/writer handshake (B2), non-pow2 strategy (D4), and the FFI call-frequency assumption (F1). Those are the ones I'd gate a merge on.