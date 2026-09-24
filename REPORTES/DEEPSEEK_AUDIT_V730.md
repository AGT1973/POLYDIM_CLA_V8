# AUDITORÍA ADVERSARIAL DEEPSEEK V730 (2026-09-15)
# Adversarial Audit: POLYDIM V730

## 1. Threshold `sum >= 0 → +1` — Catastrophic Drift

**Yes, and it's worse than you think.** This is a *biased* random walk on the hypercube, not a symmetric one.

Under MAP binding with random i.i.d. bipolar vectors, the sum of two coordinates is `{-2, 0, +2}` with probabilities `{1/4, 1/2, 1/4}`. Your rule maps `0 → +1`. So:

- P(+1) = 1/4 + 1/2 = **3/4**
- P(-1) = 1/4

Per-coordinate drift is `E[Δ] = +0.5` per superposition step. Over `n` iterations of repeated bundling, the marginal probability of a coordinate being +1 follows a Markov chain with stationary distribution **not** uniform — it's absorbing toward all-+1. The expected Hamming weight after `n` steps is `D·(1 - (1/2)^n)`-ish under naive analysis, but the *variance* collapses too: you're not doing a random walk, you're doing a **contraction toward the all-ones vector**.

Concretely: after ~30 superpositions, >99.99% of coordinates are +1. Your "superposition" is a **constant vector generator**. Any retrieval by cosine similarity against this is meaningless — every bundle converges to the same point.

**Fix:** threshold at `> 0` (ties broken by a per-coordinate random sign, or by a stored tie-break mask). Or use odd superposition counts. Or use `{0,1}` with XOR binding (which is what VSA literature actually does for binary — Kanerva's BSC uses XOR, not multiply).

The fact that you chose `>=0` suggests you copied the real-valued MAP rule (`sign(Σ)`) without noticing that `sign(0)` is a measure-zero event in ℝ but a **50% event** in the bipolar lattice. This is a category error.

---

## 2. `i8 * i8` under AVX-512 — Saturation vs. Wrapping

**The question is malformed, and that's the tell.**

`i8 * i8` in Rust is *defined* to wrap (two's complement, `wrapping_mul` semantics in release, panic in debug). LLVM will not silently substitute saturating multiply — there is no `pmullb` saturating instruction for 8-bit signed on AVX-512 that LLVM would auto-select. So the "saturating vs wrapping" framing is a red herring.

**The real attack:** your inputs are `{-1, +1}`. The product is `{-1, +1}`. **You are not doing arithmetic — you are doing XOR.** `i8 * i8` on `{-1,+1}` is isomorphic to `XOR` on `{0,1}` via `x ↦ (1-x)/2`. You are burning 8 bits per element and a full multiply pipeline to compute a 1-bit XOR.

AVX-512 has `vpternlogd` which does arbitrary 3-input boolean functions at 32 bits/cycle. You could bind **32× more data per instruction** by packing to bits and using `vpternlogd` with the XOR truth table. Your "Int8 bipolar" representation is a **32× throughput tax** for zero semantic benefit.

Worse: if you ever *do* feed non-`{-1,+1}` values (e.g., after a buggy superposition), `i8*i8` overflows silently in release. `127 * 127 = 16129 mod 256 = 1`. You've built a system whose correctness depends on an invariant that the type system does not enforce and the release build does not check.

---

## 3. 10MB memcpy per binding — Von Neumann Reincarnated

**Yes, and you've made it worse than the original.**

D = 10^7, i8 = 10 MB per vector. A cyclic permutation is a memcpy with a rotation offset. On a modern CPU:

- L1: 48 KB, L2: 1–2 MB, L3: 32–64 MB (shared).
- 10 MB does **not** fit in L2. It may or may not fit in L3 depending on your SKU and what else is running.

So every binding operation:
1. Reads 10 MB from L3/DRAM.
2. Writes 10 MB to L3/DRAM.
3. Then reads 10 MB again for the multiply.

That's ~30 MB of memory traffic per bind. At ~50 GB/s effective bandwidth, that's **~600 µs per binding**. You cannot do real-time VSA at this scale.

**The permutation is the killer.** A cyclic shift by `k` is `memcpy(dst, src+k, D-k); memcpy(dst+D-k, src, k)`. This is O(D) *data movement* for an O(1) *logical* operation. The permutation is a **relabeling of indices** — it should be free.

**Fix:** Don't materialize permutations. Store a permutation as an offset (for cyclic) or a permutation index (for general). Apply it lazily during the dot product / similarity computation. Or use a **block-cyclic** permutation with block size = cache line, so the "permuted" vector is just a reordered list of cache-line pointers. You've turned a pointer-chase into a memcpy.

This is the Von Neumann bottleneck *amplified*: you're not just moving data, you're moving it *redundantly* to perform an operation that has no data dependence on the values.

---

## 4. Geometric information lost: Float64 S^(D-1) → {-1,+1}^D

**You lose everything that makes VSA work.**

The unit sphere S^(D-1) has:
- **Continuous angular structure.** Cosine similarity is a continuous function of angle. Near-orthogonality is a *measure-zero* concept — random vectors are orthogonal in expectation but with O(1/√D) fluctuations.
- **Superposition as vector addition.** Bundling `a + b` gives a vector whose angle with `a` is `arccos(1/√2) ≈ 45°`. This is a *geometric* fact.
- **Binding as rotation.** In the Fourier/Hadamard domain, circular convolution (the real-valued binding) is a rotation. This is what makes unbinding work.

Collapsing to `{-1,+1}^D`:
- **Quantizes angles to a discrete set.** The minimum angle between distinct vectors is `arccos(1 - 2/D)`, which for D=10^7 is ~0.0006 rad. Fine in principle, but...
- **Destroys the algebra.** `sign(a) * sign(b) ≠ sign(a * b)` in general. Your binding is no longer a homomorphism from the real-valued VSA. You've built a *different* algebra and are hoping it has the same properties. It doesn't.
- **Kills the noise model.** In real VSA, bundling `n` vectors gives a result whose similarity to each input is `1/√n`. In bipolar with your biased threshold, it's `→ 1` (see #1). The capacity scaling law is gone.
- **Loses magnitude.** A vector that is "almost" another vector (small angular difference) becomes *identical* after quantization. You've destroyed the metric.

The specific loss: **the inner product structure.** `⟨a,b⟩` in ℝ^D is a continuous random variable with variance O(D). In `{-1,+1}^D`, it's `2·(agreements) - D`, which is a *discrete* random variable with the same variance but **no small-deviation structure**. You cannot represent "a is 0.99 similar to b" — only "a agrees with b on 99% of coordinates," which is a different statement.

---

## 5. Householder reflections on a Boolean hypercube

**No. And the question reveals a deeper confusion.**

A Householder reflection is `H = I - 2vv^T/(v^Tv)`. It is:
- **Linear** over ℝ.
- **Orthogonal**: `H^T H = I`.
- **Involutive**: `H^2 = I`.
- **Determinant -1** (it's a reflection).

The Boolean hypercube `{-1,+1}^D` is:
- **Not a vector space** over ℝ (it's not closed under addition: `(+1) + (+1) = +2 ∉ {-1,+1}`).
- **Not closed under linear maps** in general.
- **A group under coordinate-wise multiplication** (isomorphic to `(ℤ/2)^D`).

A Householder reflection maps `{-1,+1}^D` to a set of vectors with **arbitrary real coordinates**. `H·x` for `x ∈ {-1,+1}^D` is generically in `ℝ^D \ {-1,+1}^D`. So Householder reflections are **not endomorphisms of the hypercube**.

What *is* the hypercube's symmetry group? The **hyperoctahedral group** `B_D = (ℤ/2)^D ⋊ S_D` — coordinate-wise sign flips and coordinate permutations. This is a group of order `2^D · D!`. It is **finite**, whereas the orthogonal group `O(D)` is a Lie group of dimension `D(D-1)/2`. The hypercube's symmetry group is a **measure-zero subgroup** of `O(D)` — specifically, the subgroup of signed permutation matrices.

**Consequence:** You cannot do continuous rotations on the hypercube. You cannot do Householder reflections. You cannot do Givens rotations. You cannot do SVD. The only "geometric" operations available are:
- Coordinate-wise XOR (binding).
- Majority/threshold (bundling).
- Permutation (protection against crosstalk).

This is exactly the **Kanerva Binary Spatter Code** (BSC) / **Binary Holographic Reduced Representation** (BHRR) model. It works, but it is a *different* algebra from real-valued VSA, with different capacity laws, different noise models, and different failure modes. You cannot import theorems from the real-valued setting.

**If you need Householder reflections, you need to stay in ℝ^D.** If you need the hypercube, you need to accept that your "geometry" is the hyperoctahedral group, not the orthogonal group.

---

## Summary of Fatal Issues

| # | Issue | Severity |
|---|-------|----------|
| 1 | `>=0` threshold → all-ones collapse in ~30 steps | **Fatal** |
| 2 | i8 multiply is a 32× throughput tax for a 1-bit XOR | **Severe** |
| 3 | 10 MB memcpy per bind → ~600 µs/bind, cache-hostile | **Fatal for real-time** |
| 4 | Quantization destroys inner-product structure and capacity laws | **Fatal for VSA semantics** |
| 5 | Householder reflections undefined on hypercube | **Category error** |

**The deepest problem:** you've built a system that *looks* like VSA (bipolar vectors, binding, bundling) but is not VSA. The algebra is different, the geometry is different, the noise model is different, and the performance characteristics are different. You cannot reason about it using VSA theorems, and you cannot reason about it using Boolean algebra theorems either — it's an ad-hoc hybrid that inherits the weaknesses of both and the strengths of neither.

**Recommendation:** Pick one. Either real-valued VSA (Float32, Hadamard/Fourier binding, no memcpy — use FFT) or binary VSA (BSC, XOR binding, bit-packed, popcount similarity). The hybrid is not a synthesis; it's a category error with a performance bug on top.
