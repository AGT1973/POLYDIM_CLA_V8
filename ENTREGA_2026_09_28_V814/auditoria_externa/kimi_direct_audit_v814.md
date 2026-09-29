# MOONSHOT KIMI K3 REASONING ANALYSIS

This is a Red Team audit request. The user wants a line-by-line audit of a multi-language codebase (C++ header, C++ kernel, Rust kernel, C++ RCU/futex IPC, Dart FFI). They explicitly ask me to act as a destroyer of code, find bugs, and be rigorous. The system prompt injection says "do not explain basic concepts, assume PhD level, mathematically rigorous, no tutorials."

I should comply with the audit — this is legitimate security/correctness review work. Let me actually do a careful, real audit. I need to be careful to find real bugs, not hallucinate. Let me go through each file methodically.

Let me analyze each file carefully.

## FILE 1: polydim_solver_abi_v808_1.h

Struct layouts:

```c
typedef struct {
    uint32_t state;                  /* 0 */
    uint32_t pid;                    /* 4 */
    uint64_t process_start_time_ns;  /* 8 */
    uint64_t generation;             /* 16 */
    uint32_t epoch;                  /* 24 */
    uint32_t pad;                    /* 28 */
} PmtpReaderLease;  /* 32 bytes OK */
```

```c
typedef struct {
    uint32_t global_epoch;           /* 0 */
    uint32_t active_bank;            /* 4 */
    uint32_t writer_active;          /* 8 */
    uint32_t owner_pid;              /* 12 */
    uint64_t sequence;               /* 16 */
    uint64_t owner_start_time_ns;    /* 24 */
    uint32_t num_reclaimed_orphans;  /* 32 */
    uint32_t prev_bank;              /* 36 */
    uint64_t writer_heartbeat_ns;    /* 40 */
    uint8_t  header_padding[80];     /* 48..128 */
    PmtpReaderLease leases_bank0[32];  /* 128 */
    PmtpReaderLease leases_bank1[32];  /* 128 + 1024 = 1152 */
    PmtpReaderLease leases_bank2[32];  /* 2176 */
} PmtpBankedSlotHeader;  /* total 3200 bytes */
```

Check static_asserts: sizeof(PmtpReaderLease)==32 ✓. offsetof leases_bank0 == 128: 48 + 80 = 128 ✓.

**KEY ABI BUG**: `writer_active` is at offset 8, `owner_pid` at offset 12. The pmtp_rcu_v813.cpp does a 64-bit CAS on `&header->writer_active` — this requires 8-byte alignment of offset 8. offset 8 is 8-aligned ✓. The packed value: `desired = ((uint64_t)pid << 32) | 1`. On little-endian, a 64-bit value stored at offset 8: low 32 bits at offset 8 (writer_active), high 32 bits at offset 12 (owner_pid). So writer_active = 1, owner_pid = pid on little-endian. On big-endian this reverses: the high 32 bits land at offset 8. So the CAS packing is endianness-dependent — but on big-endian the writer_active field would read as pid and owner_pid as 1. That's a portability bug (MEDIUM/LOW given x86/ARM-LE dominance). Also reading `expected >> 32` gives pid only on LE.

Also potential issue: `#pragma pack(push, 8)` — with pack 8, alignment of uint64 is 8, fine. Struct sizes fine.

PolydimSolverOptions:
```c
uint64_t max_iterations;   /* 0 */
double gradient_tolerance; /* 8 */
double step_tolerance;     /* 16 */
double ortho_tolerance;    /* 24 */
double learning_rate;      /* 32 */
uint32_t sampling_period;  /* 40 */
uint32_t num_threads;      /* 44 */
int32_t retraction_type;   /* 48 */
double shift_regularization; /* 56 (needs 8-align, so padding 52..56) */
```
Total: 64 bytes ✓ (with 4 bytes implicit padding at 52). static_assert(sizeof==64) OK.

PolydimSolverResult: int32 status (0), uint64 iterations (8), doubles... char[256]. size = 4 + 4pad + 8 + 8+8+8 + 8 + 256 = 296. No static assert here — fine but noted.

PolydimTelemetryPoint: 8+8*4+8 = 48 bytes.

PolydimTelemetryEvent: uint64 timestamp (0), uint32 event_type (8), uint32 thread_id (12), double metrics[14] (16..128). 16 + 112 = 128 ✓.

PolydimSpscRing:
```c
uint64_t write_index;      /* 0 */
uint8_t pad_write[120];    /* 8..128 */
uint64_t read_index;       /* 128 */
uint8_t pad_read[120];     /* 136..256 */
size_t capacity;           /* 256 */
size_t capacity_mask;      /* 264 */
PolydimTelemetryEvent* ring_buffer; /* 272 */
```
Total 280 bytes. write_index and read_index are on separate 128-byte cache lines — good (assuming the struct itself is aligned to 128; if the struct is allocated at a non-128-aligned address, the padding doesn't guarantee cache-line separation. Alignment requirement: the struct must be 128-aligned for the padding scheme to isolate cache lines. There's no `alignas(128)`/declspec on the struct. That's a real false-sharing bug if the caller allocates the ring on stack or via malloc (16-aligned). MEDIUM.)

Note reinterpret_cast<std::atomic<uint64_t>*>(&ring->write_index) in the .cpp — this is fine alignment-wise (8-aligned guaranteed by pack).

PolydimHandle:
```c
void* data;     /* 0 */
size_t bytes;   /* 8 */
int32_t refcount; /* 16 */
uint32_t flags;   /* 20 */
uint64_t allocation_id; /* 24 */
```
32 bytes. refcount accessed via reinterpret_cast to atomic — alignment 4 fine.

One more: the comment says "Evento de Telemetría para el Anillo SPSC (128 bytes, espejo exacto C++/Python)" — but there's no Python code included in the audit; skip.

Header overall: minor issues:
1. Endianness dependence of the 64-bit writer CAS (documented nowwhere).
2. PolydimSpscRing lacks alignment enforcement (alignas(128)) for cache-line isolation guarantee.
3. Missing static_assert for offsetof(writer_active)==8 % 8 alignment requirement and for the LE packing assumption.
4. No include guard issue... it's fine.
5. Status code ranges: positive statuses 0..3, negative errors. OK.
6. Note the header file name says v808_1 but files include it as "polydim_solver_abi_v808_1.h" — consistent.

## FILE 2: kernel_cpp_v813.cpp

### polydim_abi_probe
Returns sizeof(PolydimSolverOptions) = 64. try/catch pointless but harmless. NO BUGS (trivial).

### FP mode getters/setters: fine.

### knuth_two_sum
```c
volatile double sum = a + b;
double b_virtual = sum - a;
double a_virtual = sum - b_virtual;
*s = sum;
*t = (a - a_virtual) + (b - b_virtual);
```
Standard Knuth TwoSum (branchless version). The `volatile` forces rounding of the sum. But the subsequent operations are not volatile; with -fno-fast-math they're IEEE. However: under x87 (32-bit x86) extended precision this breaks; on x86-64 SSE2 it's fine. The standard formulation requires 6 operations; correct. One subtlety: compiler with contraction (FMA) could fuse `(a - a_virtual) + (b - b_virtual)`? FMA contraction fuses a*b+c, not additions. OK. This is fine on modern compilers with -ffp-contract=off/on since no multiplies. NO BUG.

### twosum_tree_reduce_inplace
Iterative pairwise TwoSum reduction, accumulating errors into err_acc with another TwoSum and err_comp as plain sum. Final: s_final + (t_final + err_comp). This is a reasonable compensated reduction. Potential issue: modifying `current` in place destroys caller data — documented ("inplace"). Edge: N==0 → 0, N==1 → current[0]. Looks OK. One subtle numerical note: `return s_final + (t_final + err_comp);` — adding t_final + err_comp first is fine. Not a bug.

Actually wait — there's a subtle issue: when `t != 0.0` check. If t == 0 we skip compensation — that's fine because error is exactly zero. OK.

But is this function even used? Searching... it's not called anywhere in the kernel (gram uses Neumaier inline). Dead code, LOW. Not a correctness bug.

### polydim_stream_copy_nt
```c
if (dest < src + count && src < dest + count) overlap...
```
Pointer comparison between unrelated objects is UB technically (relational comparison), but common practice. Better: cast to uintptr_t. LOW/MEDIUM.

Then: NT store path only when dest 16-aligned. Uses `#pragma omp parallel for` over sse_blocks — each thread writes disjoint 2-element blocks, fine. `_mm_loadu_pd` on src (unaligned OK). Tail loop scalar. `_mm_sfence()` after — but sfence is executed only by the thread running that line... Actually after the parallel for, there's an implicit barrier at the end of the parallel for region (OpenMP barrier has memory synchronization semantics), then the tail loop, then sfence on the master thread. But NT stores from OTHER threads: OpenMP barrier implies flush, which orders memory operations — but does the OpenMP flush fence NT stores? OpenMP flush is a memory fence conceptually; on x86, the barrier implementation uses locked instructions / mfence-equivalent? Actually OpenMP barriers typically use atomic ops (lock-prefixed) which do NOT order NT stores (only MFENCE/SFence orders them). Hmm — lock-prefixed instructions do drain the store buffer including WC buffers? Intel SDM: locked instructions have a total order and behave as full fences for WB memory... For WC (write-combining) buffers used by MOVNT, locked operations do NOT necessarily flush WC buffers; only SFENCE/MFENCE/serializing instructions guarantee that. So other threads' NT stores may still be in WC buffers when the master executes sfence — sfence on master only orders master's stores. So the final fence doesn't guarantee visibility of other threads' NT stores. In practice, on return the caller might read dest from another thread and get stale data. This is a REAL concurrency bug (MEDIUM/HIGH in theory; in practice WC buffers drain quickly, but architecturally not guaranteed). Fix: sfence inside the parallel region per thread before barrier, or execute sfence in each thread at loop end (e.g., put `_mm_sfence()` at end of each parallel iteration or a `#pragma omp parallel` wrapping with per-thread sfence).

Also: `_mm_stream_pd` requires 16-byte alignment of dest — checked `dest % 16 == 0` — yes. But wait: check is done once outside; dest + idx stays 16-aligned since idx is even (2 doubles = 16 bytes) ✓.

Another subtlety: `if ((reinterpret_cast<uintptr_t>(dest) % 16 == 0) && count >= 2)`. If dest not aligned, falls to scalar loop for ALL elements — fine.

Also possible NULL+UB: src + count when src is valid — fine.

Error return POLYDIM_STATUS_ERR_NUMERICAL_NAN in catch — weird code for a copy, cosmetic.

Race: if caller invokes concurrently with same dest — caller's problem.

So: MEDIUM bug — missing per-thread sfence before the OpenMP barrier (the single trailing sfence doesn't order other threads' NT stores). Severity HIGH-ish but practically MEDIUM. I'll rate HIGH? Let me think: theoretical correctness guarantees for IPC zero-copy (they advertise mmap zero-copy). If the copy is used to publish into shared memory, another process could read torn/stale data. Combined with seq_cst fence after sfence on master... still doesn't flush other threads' WC. I'll call it HIGH with note.

### Allocator
polydim_alloc_aligned: checks power-of-two alignment, min sizeof(void*). posix_memalign requires alignment be multiple of sizeof(void*) and power of two — OK. bytes==0 returns nullptr. Note: overflow — none (no additions). OK.

BUG (LOW): On MSVC, `_aligned_malloc` with alignment < sizeof(void*)? handled. Fine.

polydim_handle_create: casts &h->refcount to atomic<int32_t>* — refcount is int32_t, 4-aligned (offset 16 in struct, aligned 8 actually). Fine. Uses `std::malloc` for handle, aligned to 16, fine.

**BUG**: `h->flags = 0;` etc fine. `g_allocation_seq.fetch_add` fine.

polydim_handle_release: fetch_sub → if was 1, frees. Classic. But: potential use-after-free if retain races release with refcount reaching 0 — caller discipline; standard.

**BUG (LOW/MEDIUM)**: refcount overflow — int32_t refcount; 2^31 retains overflow to negative → premature free or double free. Typical, LOW.

**BUG**: `polydim_handle_retain` on a handle whose refcount is 0 (already released) resurrects — caller error, skip.

Also reinterpret_cast of &h->refcount to atomic: OK since C++17-ish practice, technically UB but standard practice.

One real issue: polydim_handle_create stores into refcount via atomic store with memory_order_release — fine.

### SPSC ring

init: capacity power of two ≥2; checks `capacity > SIZE_MAX / sizeof(Event)` overflow — good. Allocates, memsets, stores indices, fence. Fine.

**BUG**: In init, if a previous buffer existed (re-init), it leaks — documented? Not checked. LOW.

push: 
```c
uint64_t wi = w->load(relaxed);
uint64_t ri = r->load(acquire);
if (wi - ri >= capacity) return FULL;
ring_buffer[wi & mask] = *event;
atomic_thread_fence(release);
w->store(wi + 1, release);
```
SPSC: single producer so relaxed load of w fine. ri acquire load — fine. The release fence before the release store is redundant but fine. OK.

pop: similar. `*event = ring_buffer[ri & mask];` then release store of ri+1. The acquire fence after load of wi — ordering ok: they do wi load acquire, then fence acquire, then read buffer. Fine.

**BUG**: capacity vs mask: full condition `wi - ri >= capacity` — allows capacity entries? Standard SPSC with full capacity using monotonic indices — yes since indices wrap at 2^64, wi-ri in [0, capacity]. OK. uint64 wrap: takes 10^9 yrs. Fine.

destroy: frees buffer, sets null. If called while producer/consumer active → UAF, caller responsibility. LOW.

### polydim_gram_dsyrk

Signature (double* X, D, K, K_out, num_threads).

Issues:
1. `omp_set_num_threads(threads)` — mutates global OMP state; thread-unsafe side effect; also if another concurrent call sets differently → races. MEDIUM (global state pollution). Also #pragma omp parallel for in deterministic branch uses dynamic scheduling — "deterministic" mode with dynamic schedule: each (i,j) dot product is computed by a single thread serially in d — the sum order within the dot product is fixed, so result is deterministic per (i,j) regardless of which thread computes it. Yes, deterministic. OK.

2. Neumaier inner loop:
```c
double t = sum + term;
if (fabs(sum) >= fabs(term)) comp += (sum - t) + term;
else comp += (term - t) + sum;
sum = t;
```
Correct Neumaier.

3. X layout: X is D×K row-major (`X[d*K + i]`). Access pattern strided by K — cache-hostile but correct.

4. **BUG (overflow)**: `K * K * sizeof(double)` memset — if K huge could overflow; K ≤ D, D≥10000... K*K*8 for K=10000 = 8e8, fine on 64-bit. size_t overflow only if K ~ 2^61. Not realistic. Also D*K for X indexing: d*K + i with D,K from user; X buffer assumed D*K doubles. No validation possible. Fine.

5. In throughput mode: tiled_dsyrk_fixed(CblasTrans, K, D, ...) computes upper triangle, then mirrors. OK.

### tiled_dsyrk_fixed

```c
#pragma omp parallel for schedule(static)
for (int64_t i0 = 0; i0 < n; i0 += TN)
  for (int64_t j0 = i0; j0 < n; j0 += TN)
```
Each thread gets a chunk of i0 values; for each i0, j0 ranges from i0 — disjoint (i0,j0) tiles across threads? Two different i0 values handled by different threads, each computing j0 from its own i0 — no overlap since tiles (i0,j0) with i0 different are distinct and write to distinct blocks: writes to rows i in [i0,i0+TN), cols j≥i — thread A with i0=0 writes rows 0..31 (cols 0..n), thread B with i0=32 writes rows 32..63. Disjoint rows → no data race. OK.

`size_t j_start = (i0 == j0) ? std::max(i, (size_t)j0) : (size_t)j0;` — i0,j0 are int64_t; comparing i0==j0 fine. max(i, j0): i ≥ i0 = j0 always in this branch, so j_start = i. OK.

Inner simd reduction over k. alpha*acc + beta*c. beta=0 in caller. Note: beta*c reads uninitialized? Caller memsets K_out to 0 first. OK.

TILE_D/TILE_K macros defined but unused — cosmetic.

**BUG (LOW)**: `#pragma omp simd reduction(+:acc)` on a loop with `a[p * lda + i] * a[p * lda + j]` — p*lda + i with p size_t, lda size_t — fine.

### solve_linear_system_general

Gauss-Jordan with partial pivoting:
- scale = max |A|. pivot_thresh = scale*1e-12 + 1e-15.
- If A is all zeros: scale = 0, thresh = 1e-15, max_val = 0 < thresh → return false. Good.
- **BUG (MEDIUM)**: If scale == 0 exactly but... handled. If scale is subnormal ~1e-310, thresh = 1e-15 → returns false. fine.
- Row swaps: swaps full rows of A (N columns) and B rows. Partial pivoting only row swaps — fine.
- Normalizes pivot row then eliminates all other rows — Gauss-Jordan. For cc from i (not 0): columns before i are already zero in other rows; in pivot row they're... A[i][0..i-1] may be nonzero after row swap! Gauss-Jordan normalizing from column i only: since we never need columns < i again, fine. Elimination uses f = A[r*N+i] and subtracts from cc≥i — entries in columns < i become garbage but unused. OK.
- **BUG**: division `A[i*N+cc] /= diag` — diag could be... |diag| = max_val ≥ thresh > 0. OK.
- Numerical: pivoting threshold relative to global scale, not column — acceptable.
- No iterative refinement. Acceptable.

Edge: N=0? Called with K2 = 2K ≥ 2. fine.

### frobenius_diff — fine (simd reduction).

### compute_VtZ
- num_threads = omp_get_max_threads(); scratch sized num_threads*K*K.
- `#pragma omp parallel` — the actual number of threads in the region may be LESS than omp_get_max_threads() (e.g., OMP dynamic). tid < actual threads ≤ max? Actual threads can exceed max_threads? No — omp_get_max_threads returns the max that CAN be used for the next parallel region; the region uses at most that. With nested or dynamic adjustments, actual ≤ max. So tid ∈ [0, actual-1] ⊂ [0, max-1]. Scratch indexing safe. 
- BUT: second loop sums over th in [0, num_threads): includes scratch of threads that didn't participate — but scratch was zero-initialized, so safe (just wasted). OK.
- **BUG (MEDIUM perf/memory)**: scratch alloc num_threads*K*K*8 bytes; K=... fine.
- `#pragma omp for schedule(static)` on d loop: each thread accumulates its local copy — fine.
- vector<double> allocation inside hot path each call — M3 claims O(1) dynamic memory for Gram but compute_VtZ allocates 2 vectors per call. perf, not correctness. LOW.

Wait — one real issue: `omp_get_max_threads()` could be huge (e.g., 256); scratch = 256*K*K*8 bytes. For K=100: 256*10000*8 = 20 MB. Fine. For K=1000: 2 GB — OOM risk. Exception caught by FFI barrier → returns NaN error. Eh, MEDIUM resource bug. Also note: called inside retract after projection; each call allocates. OK.

### project_to_tangent_space
- VtZ computed, sym = (VtZ + VtZ^T)/2, then Z -= V*sym. Standard tangential projection on Stiefel: Z - V sym(V^T Z). ✓
- Uses std::fma in inner loop. Note: acc = fma(V[d*K+j], sym[j*K+k], acc) — correct order.
- Allocates two K*K vectors per call. fine.

### polar_newton_refinement
- Iteration: V ← V(3I - S)/2 where S = V^T V. Newton for polar orthonormalization. Converges quadratically if ||I - S|| < 1 (spectral). 
- **BUG (MEDIUM)**: If V is far from orthonormal (e.g., after big step, ||I−S|| ≥ 1, singular values > sqrt(3)?) iteration diverges. No convergence check, no damping, fixed 8 passes, breaks only if err < tol. If it diverges, result could be worse — and caller doesn't verify. The outer solver checks ortho error after retraction, so divergence is caught and returns ORTHO_VIOLATION. Acceptable but fragile; note as MEDIUM robustness.
- Per-d std::vector<double> tmp(K) allocated INSIDE the parallel loop per row — D allocations of K doubles → D allocations total (for D=10^4+, 10k allocations/iter). Perf disaster but correct. Actually declared inside the d loop body — allocated per iteration of the loop → D allocations per pass, 8 passes. Perf LOW/MEDIUM.
- err accumulation: plain sum of e*e over K*K — could overflow if S huge (diverged) → err inf → sqrt(inf) = inf, not < tol, loop continues 8 passes. fine.

Also `1.5 * (j == k ? 1.0 : 0.0) - 0.5 * S[j*K+k]` — computes (1.5I - 0.5S). ✓

### apply_shifted_cholqr2

- G = X^T X (K×K) via gram.
- frob_norm of G.
- sigma = max(λ·||G||_F, 1e-14). G += σI.
- Cholesky of G (lower L): standard loop. val <= 0 or non-finite → RANK_DEFICIENT. ✓ good.
- **BUG (MEDIUM numerical)**: The pivot check `val <= 0.0` — but val could be tiny positive (e.g., 1e-300·σ?) — after σ shift, diag ≥ σ ≥ 1e-14 in exact arithmetic; Cholesky residual could make val small but positive; sqrt fine. Also note dividing by L[j*K+j] which could be tiny if val small → overflow to inf → subsequent NaN. The check only triggers on ≤ 0 or non-finite. A tiny-but-positive pivot yields huge Linv and the algorithm proceeds with garbage, then polar refinement may not fix it; final ortho check catches. Fragility, MEDIUM.
- Linv computation: forward substitution for inverse of lower triangular L:
```
Linv[i][i] = 1/L[i][i];
for j < i: sum = -Σ_{k=j}^{i-1} L[i][k]*Linv[k][j]; Linv[i][j] = sum / L[i][i];
```
Check: L·Linv = I. Row i, col j (j<i): Σ_k L[i][k] Linv[k][j] = 0. L[i][i]Linv[i][j] + Σ_{k=j}^{i-1} L[i][k]Linv[k][j] = 0 → Linv[i][j] = -(Σ_{k=j}^{i-1}...)/L[i][i]. Code: sum -= L[i*K+k]*Linv[k*K+j] for k in [j, i). ✓ correct.
- X ← X·Linv^T: Q = X L^{-T}. Row d: row[k] = Σ_j X[d][j] * Linv[k][j]. (X·Linv^T)[d][k] = Σ_j X[d][j]·(Linv^T)[j][k] = Σ_j X[d][j]·Linv[k][j]. ✓.
- Then polar refinement with tol 1e-14. 

- **BUG (perf, noted)**: std::vector<double> row(K) inside parallel loop per d — allocation per row.

- CholQR2 usually does two CholQR passes; here one CholQR + polar refinement. Fine.

- **BUG (MEDIUM)**: Gram computed on X AFTER caller may have huge norms: if ||X|| columns ~1e12, G ~1e24, fine; frob ok. sigma relative. OK.

- What if X has a zero column (rank deficient)? G diag zero, σ shift makes it σ; Cholesky succeeds (σ>0); Q column becomes 0/sqrt(σ) ~ garbage direction; polar refinement amplifies noise — silent garbage column instead of RANK_DEFICIENT error. The σ=1e-14 floor means zero column → L diag = 1e-7, Linv = 1e7, X col (zeros) × ... = 0 → Q has zero column → polar Newton: S = Q^TQ has zero diag → iteration V(1.5I - 0.5S): zero column stays zero? If a column is exactly zero, S column zeros, update = V*1.5 → zero. So Q keeps a zero column; ortho check afterwards: Gram has zero diagonal entry → ortho_err ≈ sqrt(1+...) ≥ 1 → ORTHO_VIOLATION eventually. OK, caught downstream. But during solver, this appears as ortho violation not rank deficiency — acceptable semantics. Note as LOW.

### retract_cayley_smw_mixed

Cayley retraction on Stiefel: standard formula (Wen–Yin): 
Y(τ) = V - (τ/2)[V, Z] (I + (τ/2) Q^T P)^{-1} ... hmm let me recall.

Cayley: Y = V + τ M (I - τ/2 M)^{-1}? Wen-Yin: with skew-symmetric W = ZV^T - VZ^T (for gradient direction Z tangent), Y(τ) = V - (τ/2) W (V + Y(τ))? The SMW form: Y = V - τ U (I_{2K} + (τ/2) V^T U ... ) hmm.

Wen-Yin feasible method: Y(τ) = X - τ U (I_{2k} + (τ/2) V^T U)^{-1} V^T X, where U = [G, X], V = [X, -G] (n×2k each). Then W = U V^T = G X^T - X G^T skew.

Here code: P, Q such that... They define QtP (K2×K2) = Q^T P where presumably P = [Z, V]? Let's decode: QtP blocks:
- top-left: VtZ
- top-right: VtV
- bottom-left: -ZtZ
- bottom-right: -VtZ^T

If Q = [V, Z] (D×2K) and P = [Z, V]... Q^T P = [[V^T Z, V^T V], [Z^T Z, Z^T V]]. Code bottom-left is -ZtZ, bottom-right -VtZ^T. So with Q = [V, -Z], P = [Z, V]: Q^T P = [[V^T Z, V^T V], [-Z^T Z, -Z^T V]] ✓ matches (Z^T V = (V^T Z)^T = VtZ^T ✓).

So the skew matrix W = P Q^T = [Z, V][V, -Z]^T = Z V^T - V Z^T. ✓ skew-symmetric.

C = I + (τ/2)·(−Q^T P)... code: C[i][j] = -0.5τ QtP[i][j] + δ. So C = I - (τ/2) Q^T P.

Standard SMW: (I - (τ/2) P Q^T)^{-1} = I + (τ/2) P (I - (τ/2) Q^T P)^{-1} Q^T.

Retraction: Y = (I - (τ/2) W)^{-1} (I + (τ/2) W) V? That's the Cayley transform applied to V with skew W. Y = V + τ W (I - τ/2 W)^{-1} V (another equivalent form: Y = V + 2·(τ/2)(I - (τ/2)W)^{-1}... let me just verify code's update):

RHS (K2×K) = Q^T V? Q^T V = [[V^T V], [-Z^T V]] = top block VtV, bottom block -VtZ^T. Code: RHS[i][j] = VtV[i][j]; RHS[K+i][j] = -VtZ[j][i] = -(VtZ^T)[i][j] ✓. So RHS = Q^T V.

Solve C·X_sol = RHS → X_sol = (I - τ/2 Q^T P)^{-1} Q^T V.

Update: V[d][k] = V[d][k] + (τ/2)·acc where acc = Σ_j Z[d][j]·RHS_sol[j][k] + V[d][j]·RHS_sol[K+j][k] = (P·X_sol)[d][k] since P = [Z, V]. So V_new = V + (τ/2) P (I - τ/2 Q^T P)^{-1} Q^T V = (I + (τ/2) P Q^T (I - τ/2 P Q^T)^{-1})... wait SMW: (I - (τ/2)PQ^T)^{-1} = I + (τ/2)P(I - (τ/2)Q^TP)^{-1}Q^T. So V_new = (I - (τ/2)W)^{-1} V where W = P Q^T = ZV^T - VZ^T skew. 

Hmm, Cayley retraction is usually Y = (I - τ/2 W)^{-1}(I + τ/2 W)V, which is the Cayley transform (orthogonal) applied to V — preserves Stiefel exactly. But code computes only (I - τ/2 W)^{-1} V, which is NOT exactly orthogonal (it's one-sided). Indeed Wen-Yin's Y(τ) = X - τ U(I + τ/2 V^TU)^{-1}V^T X corresponds to solving (I + τ/2 W)Y = X — i.e., Y = (I + τ/2 W)^{-1} X — also one-sided! Wen-Yin's scheme is a retraction (not exactly feasible), with Y(τ)^T Y(τ) = I + O(τ^3)? Actually Wen-Yin: Y(τ) = X - τU(...)V^TX satisfies Y^T Y = I + (τ²/4)(...)? Known result: Wen-Yin Cayley update is NOT exactly orthonormal; it's a retraction with second-order... Let me recall: Y(τ) satisfies Y(τ) = X - (τ/2)W(X + Y(τ)) → implicit midpoint-like. Then X+Y = ... and X^TX = I ⇒ Y^TY = I exactly? Check: Y = X - (τ/2)W(X+Y). Then (X+Y) = 2X - (τ/2)W(X+Y) → (I + (τ/4)W·2)... Let S = X+Y. S = 2X - (τ/2)WS → (I + (τ/4)·2W/2)... S = (I + (τ/4)W)^{-1} 2X. Y = S - X = [2(I + (τ/4)W)^{-1} - I]X = (I + (τ/4)W)^{-1}(2I - (I + (τ/4)W))X = (I + (τ/4)W)^{-1}(I - (τ/4)W)X. Cayley transform! Exactly orthogonal. So Wen-Yin IS the Cayley transform and exactly feasible (in exact arithmetic).

Now compare with code: V_new = (I - (τ/2)W)^{-1}V. That's NOT the Cayley transform; it's a single inverse — a first-order retraction (like implicit Euler), not exactly orthogonal: ||V_new^T V_new - I|| = O(τ²). Since they follow with polar_newton_refinement, the orthonormality is restored by Newton iteration. So correctness is maintained via refinement; the retraction itself is only first-order accurate (affects convergence rate, not correctness). Hmm, but sign convention: Z = -G (descent). W = ZV^T - VZ^T. Update V ← (I - τ/2 W)^{-1} V. Equivalent to (I - τ/2 W) V_new = V → V_new = V + (τ/2) W V_new — implicit step along W V. Since W V = ZV^TV - VZ^TV = Z - V(Z^TV)... for tangent Z with V^TZ skew... Z tangent: V^T Z + Z^T V = 0 → Z^T V = -V^T Z. W V = Z - V Z^T V... hmm W V = (ZV^T - VZ^T)V = Z(V^TV) - V(Z^TV) = Z - V(Z^T V) (if V orthonormal). For tangent Z, projection (I - VV^T)Z = Z - V V^T Z = Z + V Z^T V (using tangency). So W V = Z - V Z^T V vs tangent component Z + VZ^TV... The update direction is W V_new evaluated at new point; as a first-order implicit step it's a valid retraction direction (derivative at τ=0 is W V = Z - V Z^T V which for tangent Z equals... W V = Z(V^TV) - V(Z^TV); with V^TV = I and Z^TV skew part: Z^TV = -V^TZ. So W V = Z + V V^T Z. For Z = (I - VV^T)G_tangent... if Z fully tangent (V^TZ = 0), then Z^T V = 0 → W V = Z. Good: projected Z is tangent so V^T Z = 0 ⇒ Z^T V = 0 ⇒ W V = Z. So the implicit Euler step has correct first-order behavior. Fine — it's a valid retraction, second-order accuracy loss vs Cayley, mitigated by polar refinement. Not a bug per se, but the name "Cayley-SMW" is a misnomer (it's implicit-Euler-SMW); I'll flag as MEDIUM mathematical accuracy note? The prompt says zero tolerance for unverified claims; I can prove: (I−τ/2 W)^{-1}V has V_new^T V_new = I + O(τ²) generally — actually since W skew, (I−aW)^{-1}... For skew W, eigenvalues pure imaginary ±iλ; map x → x/(1−a i

---

