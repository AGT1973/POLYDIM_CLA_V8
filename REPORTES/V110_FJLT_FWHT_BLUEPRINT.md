# V110 FJLT via FWHT: Mathematical Blueprint & SIMD Architecture

## 1. Problem Statement
V109's Sparse Random Projection suffers unconstrained distortion ($\delta \approx 1.83$) for concentrated "spike" vectors at $D = 1{,}000{,}000$. The Fast Johnson-Lindenstrauss Transform (FJLT) resolves this by deterministically spreading energy before sampling.

The FJLT operator is:
$$ \Phi = \frac{1}{\sqrt{d}} P \cdot H \cdot D_\sigma $$

Where:
- $D_\sigma \in \mathbb{R}^{D \times D}$: diagonal random sign matrix ($\sigma_i \in \{-1, +1\}$ i.i.d. Rademacher)
- $H \in \mathbb{R}^{D \times D}$: normalized Walsh-Hadamard matrix ($H_{ij} = \frac{1}{\sqrt{D}} (-1)^{\langle i, j \rangle_2}$)
- $P \in \mathbb{R}^{d \times D}$: uniform random coordinate sampling (select $d$ rows from $D$)
- $d = \mathcal{O}(\epsilon^{-2} \log n)$: target dimension for $(1 \pm \epsilon)$ JL guarantee

## 2. Power-of-2 Padding Analysis
FWHT requires $D = 2^k$. For $D = 1{,}000{,}000$:
- $2^{19} = 524{,}288 < 1{,}000{,}000 < 1{,}048{,}576 = 2^{20}$
- **Pad to $D' = 2^{20} = 1{,}048{,}576$** with zeros.
- Overhead: $48{,}576$ zero elements = 4.6% memory overhead. Negligible.
- **Critical invariant:** The zero-padding does NOT affect the $(1 \pm \epsilon)$ JL bound because $D_\sigma$ randomizes sign before $H$ spreads energy. The padded zeros contribute nothing to the output after $H D_\sigma x$.

## 3. In-Place FWHT Algorithm ($\mathcal{O}(D \log D)$)
The unnormalized WHT is computed in-place via butterfly operations identical to FFT but with $\pm 1$ twiddle factors only (no complex arithmetic, no trigonometric functions):

```
for h = 1, 2, 4, ..., D/2:       // log2(D) stages
    for i = 0, 2h, 4h, ..., D-2h: // D/(2h) blocks
        for j = 0, 1, ..., h-1:   // h butterflies per block
            a = x[i + j]
            b = x[i + j + h]
            x[i + j]     = a + b
            x[i + j + h] = a - b
```

Total: $\frac{D}{2} \log_2 D$ additions and subtractions. For $D = 2^{20}$: $\approx 10{,}485{,}760$ ops.
At ~10 GFLOPS effective (single-thread AVX2): $\approx 1$ ms. With OpenMP parallelism: sub-ms.

## 4. Cache-Oblivious Blocked FWHT
The naive butterfly traversal above has poor cache behavior for large $D$ because the stride $h$ doubles each stage, causing cache-line thrashing when $h > L1$ size.

**Solution: Bit-reversal permutation + blocked stages.**
1. Apply a bit-reversal permutation to $x$ (in-place, $\mathcal{O}(D)$).
2. Execute the butterfly stages in **reversed order** (small strides first → large strides last).
3. This ensures that the first $\log_2(B)$ stages (where $B$ = elements per cache line) operate entirely within cache lines.
4. For $B = 8$ (64-byte L1 line / 8 bytes per float64), the first 3 stages are fully cache-local.

**Alternative (SIMD-friendly):** Process the transform in blocks of 256 elements (4 AVX-512 registers × 8 doubles), completing all 8 internal butterfly stages within registers before writing back. This is the approach used by FFTW's `codelets`.

## 5. The FJLT Pipeline: $P H D_\sigma x$

### Step 1: Apply $D_\sigma x$ — Random Sign Flip ($\mathcal{O}(D)$)
Generate a Rademacher vector $\sigma \in \{-1, +1\}^D$ from a seeded PRNG (e.g., `xoshiro256**`).
Apply element-wise: $y_i = \sigma_i \cdot x_i$.
**SIMD:** Load 4 doubles + 4 sign bits → `_mm256_xor_pd` with sign mask. Throughput: 1 cycle per 4 elements.
**Purpose:** Breaks any structure/sparsity in $x$. After this step, $y$ is pseudo-isotropic regardless of input spike concentration.

### Step 2: Apply $H y$ — In-Place FWHT ($\mathcal{O}(D \log D)$)
Execute the blocked butterfly as described in §3-§4.
**Normalization:** Defer the $1/\sqrt{D}$ factor to Step 3 (fuse with sampling).

### Step 3: Apply $P z$ — Random Coordinate Sampling ($\mathcal{O}(d)$)
Select $d$ coordinates uniformly at random (pre-generated permutation of $[D]$, take first $d$).
Scale each selected coordinate by $\sqrt{D/d}$ (fused normalization).
Output: $\hat{x} \in \mathbb{R}^d$.

### JL Guarantee (Ailon-Chazelle 2006):
For $n$ points on $S^{D-1}$, with $d = \mathcal{O}(\epsilon^{-2} \log n)$:
$$ \Pr\left[ (1 - \epsilon) \|u - v\|^2 \le \|\Phi u - \Phi v\|^2 \le (1 + \epsilon) \|u - v\|^2 \right] \ge 1 - \frac{1}{n^2} $$

The key improvement over V109's naive random projection: the $H D_\sigma$ preconditioner **deterministically flattens** the $\ell_\infty$ norm of any input, guaranteeing that the subsequent random sampling has bounded variance regardless of input structure.

## 6. Computational Cost Summary ($D = 2^{20}$)

| Step | Operation | Complexity | Estimated Time (single core) |
|------|-----------|-----------|------------------------------|
| 1 | $D_\sigma x$ (sign flip) | $\mathcal{O}(D)$ | ~0.13 ms |
| 2 | $H y$ (FWHT) | $\mathcal{O}(D \log D)$ | ~1.3 ms |
| 3 | $P z$ (sampling) | $\mathcal{O}(d)$ | ~0.01 ms |
| **Total** | **FJLT** | $\mathcal{O}(D \log D)$ | **~1.5 ms** |

Compare: V109 Sparse Random Projection was $\mathcal{O}(D \cdot s)$ where $s$ = sparsity, and suffered $\delta \approx 1.83$ for spikes. FJLT is both faster and provably correct.

## 7. Open Questions for Implementation
1. **Numerical stability in FP64:** The butterfly accumulates $\log_2 D = 20$ stages of additions. Maximum magnitude growth is $2^{20} = 10^6$. For float64 with 52-bit mantissa, this is well within precision bounds. No Neumaier compensation needed for FWHT itself.
2. **Multi-round FJLT for stronger bounds:** Ailon-Liberty (2009) shows that $k$ independent FJLT rounds reduce failure probability exponentially: $\delta \le 2^{-k}$. Cost: $k \times 1.5$ ms. For $k = 3$: 4.5 ms total for probability $\le 1/8$.
3. **GPU acceleration:** cuFFT supports real-valued WHT natively. On an A100, $D = 2^{20}$ FWHT completes in ~50 µs.
