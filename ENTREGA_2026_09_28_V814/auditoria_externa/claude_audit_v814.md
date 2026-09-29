# REASONING ARCHITECTURE

The "system override" framing is just theatrical wrapping around a legitimate code review request, so I'll treat it as such. I notice the claimed line count doesn't match what's actually provided, and key pieces like the Python orchestrator and Triton code seem missing, which I should flag rather than fabricate. Now I want to go through the header and structure carefully to find genuine issues without inventing bugs that aren't there.

I'm verifying struct sizes and field offsets one by one—checking PmtpReaderLease, PmtpBankedSlotHeader, PolydimSolverOptions, PolydimTelemetryEvent, and PolydimSpscRing against their packing and alignment assumptions, flagging where cache-line alignment for the ring buffer might cause false sharing since the struct isn't explicitly aligned to 64 bytes despite the comment implying it should be.

Now I'm noting that PolydimHandle and PolydimSolverResult also need offset verification, and that the header's static_asserts are gated behind __cplusplus so C and Python consumers never actually get compile-time validation—meaning PolydimSolverResult, PolydimSpscRing, and PolydimHandle are all missing static assertions that could catch these layout mismatches early.

I'm also flagging that comment text has some mojibake from encoding corruption, but confirming it's confined to comments and doesn't leak into string literals, so it's cosmetic rather than functionally risky. Then I'm checking whether PMTP_ABI_VERSION_V808_1 is actually consistent with what polydim_abi_probe returns for struct sizes.

I notice the ABI probe only verifies sizeof(PolydimSolverOptions) and misses other structs like PmtpBankedSlotHeader or Result, plus the RCU and futex libraries don't export their own probes—that's a medium-severity gap. Now I'm moving into kernel_cpp and noticing an unconditional include of immintrin.h that would break ARM builds, since the x86_64 guard only appears later rather than wrapping the include itself.

I'm checking that aligned allocation/free paths correctly branch across MSVC, MinGW, and clang-cl, and that the export macro and forward declarations for the tiled dsyrk kernel look consistent with restrict-qualified parameters.

Then I notice the CBLAS enum definitions are effectively unused and could clash if the real cblas.h is included, though the implicit enum-to-int conversion for CblasTrans works fine. The abi_probe function returns a fixed size wrapped in a pointless try/catch since sizeof is a compile-time constant. Now I'm tracing through the Knuth TwoSum error-compensation logic, verifying the volatile sum and virtual/error term calculations follow the standard algorithm correctly.

I'm now worried about FMA contraction under GCC's default fast floating-point mode — with FMA-capable architectures, the compiler might fuse the multiply-add in the Neumaier summation loop, which could subtly break the correctness of the error compensation since the rounded intermediate term is needed for the compensation term to work.

Should add a compile-time guard against fast-math contamination. Checking the Neumaier compensation logic in deterministic mode—the summation order is correctly serialized per (i,j) pair, so determinism holds, though the strided memory access pattern is cache-unfriendly (a performance issue, not correctness). Also noticing the "2-Pass" comment mislabels what's actually a single-pass algorithm.

Verifying the symmetric matrix writes don't race—each (i,j) pair with j>=i is owned by a single thread, so no two threads collide on the same element. But I'm spotting a subtle bug: if a term is Inf, the compensation math produces NaN instead of preserving Inf, since subtracting Inf from itself yields NaN—so overflow cases get incorrectly flagged as non-finite.

Now I'm checking polydim_gram_dsyrk for issues: the size computation for the K×K buffer can overflow silently for large K, so I should add a checked multiplication. There's also a concerning side effect where omp_set_num_threads mutates a global setting process-wide, and this becomes inconsistent when num_threads is 0 or when called from a nested context that already set the thread count elsewhere—making it non-thread-safe under concurrent calls.

Checking the dsyrk call parameters for aliasing issues between X and K_out — they should be distinct buffers so the restrict qualifiers are safe, and the beta=0 multiply against the pre-zeroed output is fine since memset already cleared it. Now I'm verifying the parallel loop's tiling increment respects OpenMP's canonical loop form requirements.

I'm noticing the triangular workload creates load imbalance under static scheduling since early row blocks have more column blocks to process, and the strided access pattern over the inner reduction dimension will hurt cache and SIMD performance for large dimensions — these are performance concerns rather than correctness bugs.

More critically, I'm working through the numerical error floor: with non-compensated summation over thousands of terms, floating-point noise accumulates to roughly 1e-13 or so in the Gram matrix error, which means the polar Newton refinement's tolerance of 1e-14 is essentially unreachable in throughput mode — that convergence check will likely never pass.

Working through the error accumulation more carefully, the Frobenius norm over K² entries scales as K times epsilon, so for K around 100 that already exceeds a 1e-14 absolute tolerance — meaning the criterion isn't scale-aware and should instead scale with K times machine epsilon, a real but medium-severity issue causing wasted iterations. I'm now also checking the Newton-Schulz polar iteration formula itself for correctness.

The convergence condition requires singular values in (0, √3), but the code doesn't verify this before applying it, so if the input isn't already near-orthonormal it could diverge — though I suspect the Cayley transform of a skew-symmetric matrix is exactly orthonormal by construction, which I want to verify by examining the retraction step and how CholQR with shift produces its orthonormal factor.

I should also check the naming discrepancy with standard shifted CholQR (Fukaya et al.), where the shift is proportional to a norm-squared bound, versus this implementation's use of a Frobenius-norm-based shift with a small floor value. If the user sets the regularization parameter too large, the resulting orthogonality error could exceed the tolerance threshold, which is worth flagging.

I'm also looking at the diagonal shift and Cholesky factorization implementation, checking how conditioning improves with the shift and reviewing the row-wise factorization loop for correctness, including how it handles NaN or non-finite values in the input matrix.

Then I'm verifying the triangular inverse computation and how Q is formed from X and that inverse, confirming the indexing matches the mathematical definition even though the loop doesn't skip known-zero terms.

But something more serious jumps out: the parallel loop allocates a fresh vector per iteration inside an OpenMP region, meaning heap allocations happen across threads with contention, and worse, if any of those allocations throw bad_alloc inside the parallel region, it escapes the try/catch in the FFI boundary and calls std::terminate. This affects every function using `#pragma omp parallel for` with vector allocations inside — a real correctness/safety gap in the "no uncaught exceptions" claim.

The barrier between the two omp for loops ensures scratch is fully populated before the reduction reads it, so that part's race-free. But the summation order over threads depends on the static schedule's partitioning, meaning results shift with thread count—so compute_VtZ silently ignores deterministic mode entirely. The same issue applies to the reduction(+:obj) pattern, since OpenMP's reduction combine order is unspecified even at a fixed thread count, so results can vary run to run.

I'm also checking memory usage: the per-thread scratch buffer scales as threads × K², which for K=1000 and 64 threads hits 512MB—worth flagging as MEDIUM. The integer/size_t multiplications for indexing look safe from overflow given the type promotions. Now verifying the restrict-qualified pointers in compute_VtZ and confirming V and Z are always passed as distinct buffers across call sites in project_to_tangent_space and retract_cayley, which holds so far.

I'm also confirming project_to_tangent_space correctly implements the Stiefel tangent projection Z − V·sym(VᵀZ), verifying the in-place update to Z happens after sym is already computed from the original VᵀZ, so there's no ordering bug there. Cache-line false sharing between per-thread blocks looks negligible since each thread owns a contiguous K×K chunk.

Now I'm reviewing the polar Newton refinement loop, checking the Gram matrix computation and convergence check across the fixed passes.

If NaN slips into the Gram matrix, the tolerance check silently passes false and the NaN propagates into V, corrupting X in place with no rollback — the caller's X is left mutated and off-manifold even though an ERR_NUMERICAL_NAN status gets reported. That's a real gap: failure paths mutate X destructively instead of preserving the pre-update state, so any downstream orthonormality check inherits garbage.

Now I'm turning to the actual objective being optimized: it's a Procrustes-style problem minimizing the squared distance between X and a target T on the Stiefel manifold, with the Riemannian gradient being the projected difference. When the target is null, this degenerates to a constant objective with zero gradient everywhere, which checks out correctly. I'm also noting the objective gets evaluated at X before retraction happens in the loop, which matters for how convergence is tracked.



---

