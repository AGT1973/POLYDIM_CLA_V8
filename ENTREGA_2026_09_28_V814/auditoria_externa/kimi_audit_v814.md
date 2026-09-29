# moonshotai/kimi-k3 REASONING

Let me carefully audit this code. The user wants a line-by-line audit of all files. Let me go through each file systematically.

**FILE 1: polydim_solver_abi_v808_1.h**

Let me check the struct layouts.

`PmtpReaderLease`:
- uint32_t state (0-4)
- uint32_t pid (4-8)
- uint64_t process_start_time_ns (8-16)
- uint64_t generation (16-24)
- uint32_t epoch (24-28)
- uint32_t pad (28-32)
Total: 32 bytes. OK with pack(8). static_assert confirms 32.

`PmtpBankedSlotHeader`:
- global_epoch: 0-4
- active_bank: 4-8
- writer_active: 8-12
- owner_pid: 12-16
- sequence: 16-24
- owner_start_time_ns: 24-32
- num_reclaimed_orphans: 32-36
- prev_bank: 36-40
- writer_heartbeat_ns: 40-48
- header_padding[80]: 48-128
- leases at 128. OK.

Note: writer_active at offset 8, owner_pid at offset 12. The writer lock CAS packs {writer_active:32, owner_pid:32} into a 64-bit atomic at offset 8. On little-endian, `((uint64_t)pid << 32) | 1` means writer_active (low 32 bits at offset 8) = 1, owner_pid (high 32 bits at offset 12) = pid. That's consistent on little-endian. On big-endian this breaks — but that's a portability concern, likely LOW.

`PolydimSolverOptions`:
- uint64_t max_iterations: 0-8
- double gradient_tolerance: 8-16
- double step_tolerance: 16-24
- double ortho_tolerance: 24-32
- double learning_rate: 32-40
- uint32_t sampling_period: 40-44
- uint32_t num_threads: 44-48
- int32_t retraction_type: 48-52
- padding 52-56 (implicit due to pack 8 and next double)
- double shift_regularization: 56-64
Total 64. OK.

`PolydimSolverResult`: int32 status (0-4), padding 4-8, uint64 iterations (8-16), doubles 16-40, uint64 total_time_ns 40-48, char[256] 48-304. Total 304. No static assert on this one. Fine.

`PolydimTelemetryPoint`: 8 + 4*8 + 8 = 48 bytes. OK.

`PolydimTelemetryEvent`: uint64 (0-8), uint32 event_type (8-12), uint32 thread_id (12-16), double metrics[14] (16-128). Total 128. OK.

`PolydimSpscRing`:
- write_index: 0-8
- pad_write[120]: 8-128
- read_index: 128-136
- pad_read[120]: 136-256
- capacity: 256-264
- capacity_mask: 264-272
- ring_buffer: 272-280
Total 280. OK.

`PolydimHandle`:
- void* data: 0-8
- size_t bytes: 8-16
- int32 refcount: 16-20
- uint32 flags: 20-24
- uint64 allocation_id: 24-32
Total 32. OK.

Dart side: PolydimHandle struct uses Pointer<Void> data, @Size() int bytes, @Int32 refcount, @Uint32 flags, @Uint64 allocationId. Matches.

Dart PolydimBettiResult: Int32 status, Uint32 componentsBetti0, Int64 cyclesBetti1, Uint32 numVertices, Uint32 numEdges, Uint8 isCriticallyHealthy, Uint8 isOptimallyHealthy, Array(102) pad.

Rust PolydimBettiResult: status i32 (0-4), components_betti0 u32 (4-8), cycles_betti1 i64 (8-16), num_vertices u32 (16-20), num_edges u32 (20-24), is_critically_healthy u8 (24), is_optimally_healthy u8 (25), pad [u8;102] (26-128). Total 128. Dart: 4+4+8+4+4+1+1+102 = 128. Dart FFI struct alignment: Int64 at offset 8 — fine. Matches.

Rust PolydimFrechetBettiResult: status i32 (0-4), num_candidates u32 (4-8), dimension u32 (8-12), connected_components_betti0 u32 (12-16), cycles_betti1 i64 (16-24), consensus_node_idx u32 (24-28), active_swarm_count u32 (28-32), rejected_outliers_count u32 (32-36), frechet_residual f64 (36-44)... 

Wait — f64 at offset 36? With align(8), the struct alignment is 8, so f64 must be at offset multiple of 8. Offset 36 is not a multiple of 8. Rust would insert padding: after rejected_outliers_count at 32-36, frechet_residual f64 needs 8-byte alignment → offset 40-48. Then is_consensus_certified u8 at 48, pad [u8;79] at 49-128. Total 128. OK that works: 40+8=48, +1=49, +79=128. 

Dart side: Int32 status (0-4), Uint32 numCandidates (4-8), Uint32 dimension (8-12), Uint32 connectedComponentsBetti0 (12-16), Int64 cyclesBetti1 (16-24), Uint32 consensusNodeIdx (24-28), Uint32 activeSwarmCount (28-32), Uint32 rejectedOutliersCount (32-36), Double frechetResidual — Dart FFI will align Double to 8 bytes → offset 40. Then Uint8 at 48, Array(79) at 49-128. Total 128. Matches. OK good.

But wait — the Rust struct has `#[repr(C, align(8))]`. The comment says "G5: sizeof sigue siendo 128 sin exigir align 128". OK.

Now the header comment says "PolydimSolverOptions (64 bytes, SIN objective_tolerance)". Fine.

**FILE 2: kernel_cpp_v813.cpp**

`polydim_abi_probe`: returns sizeof(PolydimSolverOptions) = 64. OK.

`knuth_two_sum`: uses `volatile double sum = a + b;` — volatile forces store/load but doesn't prevent the compiler from... actually with -fno-fast-math it's fine. The TwoSum algorithm: standard Knuth TwoSum requires 6 flops:
```
s = a + b
bp = s - a
ap = s - bp
t = (a - ap) + (b - bp)
```
Wait, standard TwoSum:
```
s = a + b
b' = s - a
a' = s - b'
δb = b - b'
δa = a - a'
t = δa + δb
```
Here: b_virtual = sum - a; a_virtual = sum - b_virtual; *t = (a - a_virtual) + (b - b_virtual). That matches. OK.

`twosum_tree_reduce_inplace`: pairwise reduction with error accumulation. Looks plausible. One issue: `err_comp += et;` — plain addition of error terms, fine for compensation. The final return `s_final + (t_final + err_comp)`. OK-ish. Not exported anyway. Actually it's unused? Let me check... `twosum_tree_reduce_inplace` is defined but never called in the file. Dead code — LOW.

`polydim_stream_copy_nt`: 
- Overlap check: `if (dest < src + count && src < dest + count)` — pointer arithmetic `src + count` where count is element count — fine for double*. But comparing pointers from different arrays is technically UB in C++, though practically fine. Also potential overflow: src + count could overflow if count is huge — but count*sizeof(double) overflow isn't checked. If count > SIZE_MAX/8, `count * sizeof(double)` overflows in memmove. HIGH-ish? Realistically count is bounded. MEDIUM.
- The SSE path: `#pragma omp parallel for` over sse_blocks, each thread does `_mm_stream_pd(&dest[idx], _mm_loadu_pd(&src[idx]))`. dest must be 16-byte aligned — checked. OK.
- After the parallel for, `i = sse_blocks * 2;` — set outside the parallel region, fine.
- Tail loop scalar. Then `_mm_sfence()`. OK.
- Note: `_mm_stream_pd` requires 16-byte alignment of dest — checked `dest % 16 == 0`. But if dest is not 16-aligned, the whole copy falls to scalar loop — correct but slow. Fine.
- Bug: if `count >= 2` but dest not aligned, sse_blocks path skipped, i=0, scalar loop handles all. OK.
- Return code in catch: POLYDIM_STATUS_ERR_NUMERICAL_NAN for a copy failure — semantically wrong but harmless. LOW.

`polydim_alloc_aligned`: checks power of two, min sizeof(void*). posix_memalign requires alignment to be multiple of sizeof(void*) and power of two — OK. But no overflow check on bytes — posix_memalign will fail if too big. OK.

`polydim_handle_create`: allocates data, then handle. Sets fields. Uses reinterpret_cast to atomic<int32_t> on h->refcount — this is a strict-aliasing violation technically; common practice in this codebase. The refcount is int32_t in a packed struct — alignment 4, fine for atomic<int32_t>. Note: `#pragma pack(push, 8)` — refcount at offset 16, 4-byte aligned. atomic<int32_t> needs 4-byte alignment. OK.

ABA on refcount? Standard refcount, retain/release. If release reaches 0, frees. If two threads release concurrently... fetch_sub is atomic; only the one seeing 1 frees. OK. But retain-after-release race (use-after-free) is caller's problem. Standard.

`polydim_spsc_init`: capacity power of two >= 2. Checks `capacity > SIZE_MAX / sizeof(PolydimTelemetryEvent)`. Allocates aligned 128. memset. Stores indices. OK.

`polydim_spsc_push`: 
- wi load relaxed, ri load acquire. `if (wi - ri >= ring->capacity)` — unsigned arithmetic; if ri > wi (corruption), wraps. Standard SPSC.
- Writes event, release fence, store wi+1 release. OK.
- One subtle issue: the ring is SPSC but nothing enforces single producer — caller's contract. Fine.
- `ring->capacity` read non-atomically while another thread could... in SPSC, capacity is set at init before use. OK.

`polydim_spsc_pop`: ri relaxed, wi acquire, acquire fence, copy, store ri+1 release. OK.

`polydim_spsc_destroy`: frees buffer. If called while producer/consumer active → UAF, but that's caller contract. LOW note.

`polydim_gram_dsyrk`:
- `std::memset(K_out, 0, K * K * sizeof(double));` — K*K overflow? K is size_t; K*K*8 could overflow for huge K. D>=10000, K presumably small. MEDIUM theoretical.
- Deterministic path: `#pragma omp parallel for schedule(dynamic)` over i (int64_t). Inner loop j from i to K. Neumaier/Kahan compensation per (i,j) pair. Writes K_out[i*K+j] and K_out[j*K+i]. Each i row unique per thread — no data race since j>=i and symmetric write only touches (i,j) and (j,i) — for different i values, pairs don't overlap. OK.
- The compensation: this is the "Neumaier" variant of Kahan:
```
t = sum + term
if |sum| >= |term|: comp += (sum - t) + term
else: comp += (term - t) + sum
sum = t
```
Correct Neumaier form. OK.
- Throughput path: tiled_dsyrk_fixed(CblasTrans, K, D, 1.0, X, K, 0.0, K_out, K). X is D×K row-major (X[d*K + i]). CblasTrans means A^T A with A being k×n... In their convention: trans==CblasTrans → acc += a[p*lda + i] * a[p*lda + j], p over k=D, lda=K. So a is D×K row-major, computing K_out[i,j] = sum_d X[d,i] X[d,j]. Correct.
- Then symmetrizes lower triangle from upper. tiled_dsyrk_fixed computes only j >= i (upper). Let me verify: loops i0 over n, j0 from i0, i from i0..i_max, j_start = (i0==j0) ? max(i, j0) : j0. For diagonal blocks j starts at i. For off-diagonal j0 > i0, j from j0. So computes upper triangle (j >= i). Then gram symmetrizes. OK.
- num_threads: `if (threads > 1) omp_set_num_threads(threads);` — this sets global OpenMP state, affecting subsequent calls — a side effect. Also calling omp_set_num_threads from multiple threads concurrently is a data race on OpenMP internal state. MEDIUM.
- BUG: In deterministic path with schedule(dynamic) and int64_t i loop — fine.
- Note: memset then deterministic path writes all entries — fine. Throughput path: tiled writes upper with beta=0.0 — `c[i*ldc+j] = alpha*acc + beta*c[i*ldc+j]` with beta=0 → 0*garbage = 0 unless garbage is NaN/Inf... but memset zeroed it, so 0*0=0. Fine. Actually beta=0.0 * 0.0 = 0. OK.

`tiled_dsyrk_fixed`: 
- `#pragma omp simd reduction(+:acc)` over p. OK.
- Potential issue: for trans==CblasTrans, a[p*lda+i] — lda=K. OK.
- No bugs apparent. The j_start for diagonal block: max(i, j0) = i since i >= i0 = j0. OK.

`solve_linear_system_general`:
- Gauss-Jordan with partial pivoting. scale = max |A[i]| over N*N. If scale == 0 (zero matrix), pivot_thresh = 1e-15, max_val = 0 < thresh → return false. OK.
- pivot_thresh = scale*1e-12 + 1e-15. OK.
- Normalizes pivot row, eliminates all other rows (Gauss-Jordan). Result in B. OK.
- No check that B is non-null — internal use only, always valid. OK.
- Note: it modifies A and B in place. Fine.

`frobenius_diff`: sqrt of sum of squares — could overflow if values huge, but Gram matrices near identity. OK. `#pragma omp simd reduction(+:s)` fine.

`compute_VtZ`:
- num_threads = omp_get_max_threads(). scratch vector of num_threads*K*K.
- `#pragma omp parallel` — inside, tid = omp_get_thread_num(). local = &scratch[tid*K*K].
- POTENTIAL BUG: If the parallel region runs with FEWER threads than omp_get_max_threads() (e.g., dynamic adjustment enabled, or nested parallelism limits), then scratch entries for unused threads remain zero — fine for reduction. If MORE threads... can't exceed max. Actually omp_get_max_threads returns the max nthreads-var; runtime may use fewer. Reduction over all num_threads entries includes zeros — correct. OK.
- But: nested parallel region — compute_VtZ is called from within... let me check callers. project_to_tangent_space calls compute_VtZ — not within a parallel region. retract_cayley_smw_mixed calls compute_VtZ directly — not in parallel region. OK.
- Memory: num_threads*K*K doubles — for K large and many threads, big allocation. Not a bug per se.
- The reduction loop: `#pragma omp for schedule(static)` over K*K, summing over threads. OK.

`project_to_tangent_space`:
- VtZ = V^T Z. sym = 0.5(VtZ + VtZ^T). Z -= V*sym. Standard Stiefel tangent projection: Z - V*sym(V^T Z). Correct.
- The update loop: for each d, for each k: acc = sum_j V[d,j]*sym[j,k]; Z[d,k] -= acc. Correct.

`polar_newton_refinement`:
- S = V^T V (via gram). err = ||S - I||_F. If < tol break.
- Update: V ← V(1.5I - 0.5S) — Newton-Schulz iteration for polar factor. Correct: V_{n+1} = 0.5 V (3I - V^T V).
- tmp vector allocated per row inside parallel loop — allocation in hot loop, perf issue not bug. LOW.
- 8 passes max. If V has a singular value exactly 0, Newton-Schulz can't recover — but that's mathematical, guarded by CholQR2 before.
- Note: convergence of Newton-Schulz requires ||V||_2 < sqrt(3) roughly; after CholQR2 V is near-orthonormal. OK.

`apply_shifted_cholqr2`:
- G = X^T X. frob_norm of G. sigma = max(lambda*frob_norm, 1e-14). G += sigma I.
- Cholesky of G (lower). If val <= 0 → RANK_DEFICIENT. OK.
- Linv: computes inverse of lower triangular L. Let me verify: L is lower, L[i,j] for j<=i. Linv lower. Linv[i,i] = 1/L[i,i]. For j<i: sum = -sum_{k=j}^{i-1} L[i,k]*Linv[k,j]; Linv[i,j] = sum / L[i,i]. Check: (L * Linv)[i,j] = sum_k L[i,k] Linv[k,j] = 0 for j<i. sum_{k=j}^{i} L[i,k]Linv[k,j] = 0 → L[i,i]Linv[i,j] = -sum_{k=j}^{i-1} L[i,k]Linv[k,j]. Yes correct.
- Q = X L^{-T}: row update: row[k] = sum_j X[d,j] * Linv[k,j]. (X * Linv^T)[d,k] = sum_j X[d,j] Linv[k,j]. Yes — Q = X L^{-T} means Q[d,k] = sum_j X[d,j] * (L^{-T})[j,k] = sum_j X[d,j] Linv[k,j]. Correct.
- Then polar refinement. OK.
- CholQR2 usually does two CholQR passes; here one CholQR + Newton refinement. Fine.
- Potential issue: if X is exactly rank-deficient, G + sigma I with sigma>=1e-14 makes Cholesky succeed but Q garbage... Actually with shift, Cholesky succeeds; the result Q = X L^{-T} may have huge norm; polar Newton may not converge (||V|| > sqrt(3) → Newton-Schulz diverges!). Hmm. If X is rank deficient, G = X^TX has tiny eigenvalues; sigma = max(lambda*frob, 1e-14). If frob is large but one direction is null, sigma relative to frob could be small vs needed... The shifted Cholesky succeeds, Linv has huge entries (1/sqrt(sigma)), Q rows huge, then Newton-Schulz on matrix with huge norm diverges → NaN. The NaN firewall in the caller catches non-finite ortho_err. So it degrades to error status. Acceptable but worth noting. MEDIUM.

`retract_cayley_smw_mixed`:
- Projects Z to tangent. Computes VtV, ZtZ, VtZ.
- Cayley-SMW for Stiefel: standard scheme (Wen-Yin / Jiang-Dai): 
  A = [V, Z] (D×2K), B = [Z, -V]... Let me recall the Cayley retraction on Stiefel:
  Y(tau) = V - (tau/2) [V, Z] (I + (tau/2) [Z,-V]^T [V, Z]... hmm.
  
  Standard: W = V^T Z (skew-symmetrized?). The Cayley transform: Y = V - (tau/2)(V Z^T - Z V^T)(V + Y)... The SMW form:
  Y(tau) = V - tau * U (I_{2K} + (tau/2) M)^{-1} ... let me derive from their code.

  They build QtP (2K×2K):
  QtP = [ VtZ,  VtV ]
        [ -ZtZ, -VtZ^T ]
  
  C = I - 0.5*tau*QtP... wait: C[i,j] = -0.5*tau*QtP[i,j], then C[i,i] += 1. So C = I - (tau/2) QtP.

  Hmm, standard Cayley-SMW (e.g., from "A feasible method for optimization with orthogonality constraints", Wen & Yin): 
  Y(τ) = V − τ U (I_{2k} + (τ/2) V^T U ... ) 
  
  Wen-Yin: Let W = (I - (τ/2) V V^T)... Actually the Crank-Nicolson-like scheme:
  Y = V - (τ/2) A (V + Y), A = Z V^T - V Z^T (skew-symmetric, assuming Z tangent... actually A = G V^T - V G^T).
  SMW: Y = V - (τ/2) [Z, V] (I + (τ/2) [V, -Z]^T [Z, V])^{-1} [V, -Z]^T (V + ... hmm let me be careful.

  A = U S U^T with U = [Z, V] (D×2K), S = [[0, I],[-I, 0]]... A = Z V^T - V Z^T = [Z, V] [[0, I], [-I, 0]] [Z, V]^T? [Z,V] [[0,I],[-I,0]] = [ -V, Z ]; times [Z,V]^T = -V Z^T + Z V^T. Yes.

  Y = V - (τ/2) A (V + Y) → (I + (τ/2) A) Y = (I - (τ/2) A) V → Y = (I + (τ/2)A)^{-1} (I - (τ/2)A) V — Cayley transform of (τ/2)A applied to V.

  SMW: (I + (τ/2) U S U^T)^{-1} = I - U ( (2/τ) I + S U^T U )^{-1} S U^T... 

  Y = V - (τ/2) A V - (τ/2) A Y. Implicit. The standard result (Wen-Yin eq. 13): Y(τ) = V - τ U (I_{2k} + (τ/2) S U^T U)^{-1} S U^T V? Let me just check their code's structure.

  Their QtP: with U = [V, Z] (order matters). QtP = U^T (something)? QtP = [[VtZ, VtV], [-ZtZ, -VtZ^T]]. Hmm: Let P = [Z, -V]? Then U^T P where U = [V, Z]: U^T P = [[V^T Z, -V^T V], [Z^T Z, -Z^T V]] = [[VtZ, -VtV], [ZtZ, -ZtV]]. Not matching.

  Their QtP = [[VtZ, VtV], [-ZtZ, -VtZ^T]]. Consider M = [V, Z]^T [Z, -V]... = [[V^T Z, -V^T V],[Z^T Z, -Z^T V]] no.

  Consider S U^T with S = [[0, I], [-I, 0]] and U = [Z, V]: S U^T = [[0,I],[-I,0]] [Z^T; V^T] = [V^T; -Z^T]. Then (S U^T) U = [V^T; -Z^T] [Z, V] = [[V^T Z, V^T V], [-Z^T Z, -Z^T V]] = [[VtZ, VtV], [-ZtZ, -VtZ^T]]. Yes! QtP = S U^T U with U = [Z, V], S = [[0,I],[-I,0]].

  C = I + (τ/2)... they have C = I - 0.5τ QtP. Hmm sign. Standard Wen-Yin: Y(τ) = V − τ U (I_{2k} + (τ/2) S U^T U)^{-1} S U^T V? Hmm, but their C = I − (τ/2) QtP. Sign discrepancy depends on convention of A (A = ZV^T − VZ^T vs VZ^T − ZV^T) and whether Z is ascent or descent direction. Since they pass Z = -G (descent), sign conventions may be consistent. I can't fully verify the sign without careful derivation; flag as "needs numerical verification" but not assert bug. Actually let me try to verify more carefully.

  Cayley: Y = (I + (τ/2) A)^{-1} (I − (τ/2) A) V where A = Z V^T − V Z^T (skew). Expand: Y = V − (τ/2) A (Y + V). 

  SMW: (I + (τ/2) A)^{-1} = I − (τ/2) U (I + (τ/2) S U^T U)^{-1} S U^T, with A = U S U^T, U = [Z, V], S = [[0,I],[-I,0]]: check U S U^T = [Z,V] [[0,I],[-I,0]] [Z;V]^T... U S = [Z,V][[0,I],[-I,0]] = [-V, Z]. U S U^T = -V Z^T + Z V^T = A. ✓.

  Y = (I − (τ/2)A)(V) − ... hmm, Y = (I + (τ/2)A)^{-1}(I − (τ/2)A)V.
  Let B = (τ/2)A. Y = (I+B)^{-1}(I−B)V = V − 2B(I+B)^{-1}V (using (I+B)^{-1}(I−B) = (I+B)^{-1}(I+B−2B) = I − 2(I+B)^{-1}B = I − 2B(I+B)^{-1} since B commutes with (I+B)^{-1}).
  So Y = V − τ A (I + (τ/2)A)^{-1} V.
  A (I + (τ/2)A)^{-1} = U S U^T [I − (τ/2) U (I + (τ/2) S U^T U)^{-1} S U^T] = U S [I − (τ/2)(I + (τ/2)QtP)^{-1} QtP] U^T where QtP = S U^T U... wait S U^T U: U^T U = [[Z^TZ, Z^TV],[V^TZ, V^TV]]; S U^T U = [[0,I],[-I,0]] [[ZtZ, ZtV],[VtZ, VtV]] = [[VtZ, VtV], [-ZtZ, -ZtV]]. And -ZtV = -(Z^T V) = -(VtZ)^T. So S U^T U = [[VtZ, VtV],[-ZtZ, -VtZ^T]] = their QtP. ✓ 

  So A(I+(τ/2)A)^{-1} = U S (I + (τ/2)QtP)^{-1} U^T (using the push-through identity S[I − (τ/2)(I+(τ/2)QtP)^{-1}QtP] = S(I+(τ/2)QtP)^{-1}).
  Y = V − τ U S (I + (τ/2)QtP)^{-1} U^T V.

  Their code: C = I − (τ/2)QtP. But derivation says I + (τ/2)QtP. Sign! Hmm. Unless their Z is negated: they call with Z = −G. In the derivation, A = ZV^T − VZ^T with Z the "direction". If the retraction is Y = Cayley(−(τ/2)A)... depends on convention. Wen-Yin: Y(τ) = V − (τ/2) W (V + Y) where W = G V^T − V G^T with G the gradient... and they move along −gradient. Here Z = −G, so A = ZV^T − VZ^T = −(GV^T − VG^T) = −W. So Y = Cayley((τ/2)A) = Cayley(−(τ/2)W). Wen-Yin: (I + (τ/2)W)Y = (I − (τ/2)W)V → Y = (I+(τ/2)W)^{-1}(I−(τ/2)W)V. With W = −A: Y = (I−(τ/2)A)^{-1}(I+(τ/2)A)V = V + τA(I−(τ/2)A)^{-1}V (by same manipulation: (I−B)^{-1}(I+B) = I + 2(I−B)^{-1}B = I + 2B(I−B)^{-1}).
  = V + τ U S (I − (τ/2)QtP)^{-1} U^T V.
  Their C = I − (τ/2)QtP ✓. And update: V_new = V + (τ/2) [Z, V] * RHS where RHS = S (I−(τ/2)QtP)^{-1} U^T V? They solve C * X = RHS0 where RHS0 = [[VtV],[-VtZ^T]] (2K×K). Note U^T V = [Z^T V; V^T V] = [VtZ^T; VtV]. And S U^T V = [[0,I],[-I,0]] [VtZ^T; VtV] = [VtV; −VtZ^T]. ✓ matches their RHS.
  So solution X* = (I − (τ/2)QtP)^{-1} S U^T V. Then Y = V + τ U S X*? Their update: row[k] = V[d,k] + 0.5τ acc where acc = sum_j Z[d,j] RHS[j,k] + V[d,j] RHS[K+j,k] = (U RHS)[d,k] with U = [Z, V]. So Y = V + (τ/2) U X*. But derivation says Y = V + τ U S X* where X* = C^{-1} S U^T V. Their RHS already includes S (RHS = S U^T V), so X* = C^{-1} S U^T V, and Y = V + τ U S X*? No wait: Y = V + τ U S (C^{-1} S U^T V) = V + τ U S X*. Their code: Y = V + (τ/2) U X* — missing the S and factor 2 discrepancy!

  Hmm wait, let me redo. Y = V + τ A (I − (τ/2)A)^{-1} V. A(I−(τ/2)A)^{-1} = U S U^T (I − (τ/2) U S U^T)^{-1}. Push-through: U S U^T (I − (τ/2) U S U^T)^{-1} = U S (I − (τ/2) U^T U S)^{-1} U^T. Note (I − (τ/2) U^T U S) vs their C = I − (τ/2) S U^T U. U^T U S ≠ S U^T U in general. Push-through: U^T (I − (τ/2) U S U^T)^{-1} = (I − (τ/2) U^T U S)^{-1} U^T. So A(I−(τ/2)A)^{-1} = U S (I − (τ/2) U^T U S)^{-1} U^T. Their C uses S U^T U, not U^T U S. Hmm, alternative: A(I − (τ/2)A)^{-1} = (I − (τ/2)A)^{-1} A (they commute). (I − (τ/2)A)^{-1} = I + (τ/2) U (I − (τ/2) S U^T U)^{-1} S U^T (SMW with B = −(τ/2)A: (I+B)^{-1} = I − U(B... let me just do SMW: (I + U M V^T)^{-1} = I − U (I + M V^T U)^{-1} M V^T. Here (I − (τ/2) U S U^T)^{-1}: M = −(τ/2) S, V^T = U^T. = I + (τ/2) U (I − (τ/2) S U^T U)^{-1} S U^T. So (I−(τ/2)A)^{-1} A = A + (τ/2) U (I − (τ/2)QtP)^{-1} S U^T A. And S U^T A = S U^T U S U^T = QtP S U^T. So A(I−(τ/2)A)^{-1} = U S U^T + (τ/2) U C^{-1} QtP S U^T = U [S + (τ/2) C^{-1} QtP S] U^T = U C^{-1} [C S + (τ/2) QtP S] U^T = U C^{-1} [(I − (τ/2)QtP) S + (τ/2) QtP S] U^T = U C^{-1} S U^T. 

  So Y = V + τ U C^{-1} S U^T V. Their code: X* = C^{-1} (S U^T V) [RHS = S U^T V ✓], Y = V + (τ/2) U X*. Factor: τ vs τ/2! The code has 0.5*tau*acc. Derivation gives τ. Hmm, but wait — maybe their convention: Y = (I − (τ/2)W)... Wen-Yin define Y(τ) satisfying Y = V − (τ/2) W (V + Y) where the curve Y(τ) ≈ V − τ G + O(τ²) for gradient G... Let me check first-order: Y = V + τ U C^{-1} S U^T V. To first order in τ: C^{-1} ≈ I, so Y ≈ V + τ U S U^T V = V + τ A V. A V = (Z V^T − V Z^T) V = Z (V^T V) − V (Z^T V) = Z VtV − V VtZ^T. With V orthonormal (VtV = I) and Z tangent (V^T Z skew part...): A V = Z − V (Z^T V). Hmm, Z tangent means sym(V^T Z) = 0, i.e., V^T Z = −

---

