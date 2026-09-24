# SOTA RESEARCH REPORT 1: POLYDIM ASYMPTOTIC KERNELS
**Date:** 2026-09-15
**Target Space:** $D \ge 10,000,000$
**Regime:** Zero-Copy PMTP, Absolute CPU/GPU Convergence

## 1. Matrix-Free Orthogonal Retractions: Defeating $O(N^2)$ Memory Collapse
In $D = 10^7$, representing a dense operator requires $O(D^2) \approx 400$ TB of RAM. Standard Riemannian exponential maps (e.g., via SVD or matrix exponentials) are strictly forbidden as they induce an immediate out-of-memory memory collapse.

### State of the Art: The Cayley-Sherman-Morrison-Woodbury (Cayley-SMW) Retraction
To maintain strict orthogonal constraints (such as preserving $L_2$ norm = 1.0 on $S^{D-1}$ or orthogonality on the Stiefel manifold $St(p, D)$), the SOTA is the matrix-free Cayley transform augmented by the SMW identity.

Given a skew-symmetric matrix $W = U V^T - V U^T$ (where $U, V \in \mathbb{R}^{D \times p}$), the Cayley transform is:
$$ Y(\alpha) = \left(I - \frac{\alpha}{2} W\right)^{-1} \left(I + \frac{\alpha}{2} W\right) Y $$

Using the SMW formula, the inversion of the $D \times D$ operator is mapped to the inversion of a $2p \times 2p$ capacitance matrix:
$$ \left(I - \frac{\alpha}{2} W\right)^{-1} = I + U_W \left( I_{2p} - \frac{\alpha}{2} V_W^T U_W \right)^{-1} V_W^T $$
Where $U_W = [U, -V]$ and $V_W = [V, U]$. 

**Asymptotic Properties:**
- **Space:** $O(D \cdot p)$ instead of $O(D^2)$. For $S^{D-1}$ ($p=1$), this is literally $O(D)$ arrays, fitting perfectly in GPU VRAM/Shared RAM.
- **Time:** $O(D \cdot p^2)$. The matrix inversion is bounded to a tiny $2p \times 2p$ matrix (which is solved in $O(1)$ time relative to $D$).
- **Geometry:** Unlike additive updates (which drift off the manifold), Cayley maps are *exactly* orthogonal in exact arithmetic. 
- **Drift Control:** In floating-point (FP32/FP16), quantization error will eventually cause drift. SOTA 2026 implementations utilize a lightweight Newton-Schulz iteration ($X \leftarrow \frac{1}{2} X (3I - X^T X)$) applied strictly on the $2p \times 2p$ subspace, NEVER on the full $D$ space, to zero out numerical drift.

## 2. Deterministic PRNG Strategies for Massive Parallel CPU/GPU Convergence
The requirement is absolute exactness: a tensor initialized or mutated on a 64-core CPU must match the tensor generated on a 16,384-core GPU at the bit level. Stateful PRNGs (Mersenne Twister, standard PCG64) require sequential state updates and fail catastrophically in massive parallel grids where thread execution order is non-deterministic.

### State of the Art: Counter-Based PRNGs (CBPRNG)
The core SOTA mechanism for 2026 massive determinism is $f_{key}(index) \rightarrow \mathbb{R}$. The random value depends *only* on the global spatial index and the seed, completely decoupling randomness from hardware warp/wavefront execution order.

#### Candidates & SOTA Reality:
1. **Philox (4x32-10):** The gold standard from Random123. It operates on $4 \times 32$-bit words using a 10-round Feistel network with multipliers.
   - *Verdict:* Still the SOTA baseline for ML/HPC. It guarantees exact bitwise convergence if implemented with strict standard uint32 arithmetic across CUDA/C++. However, in $D = 10^7$, 32-bit internal states can approach birthday paradox collisions for massive sub-sampling, requiring strict offset management.
2. **PCG64:** Excellent statistical properties, but its native form is sequential (state transition $s_{k+1} = A s_k + c$). While there are hash-based/jumpable variants, distributing state across 10M threads requires complex jump-ahead arithmetic that bottlenecks GPU registers.
   - *Verdict:* Discard for $D \ge 10^7$ parallel generation.
3. **ChaCha8 / ChaCha20:** A cryptographic stream cipher adapted for CBPRNG.
   - *Verdict (2026 SOTA):* With hardware AES/Vector instructions (AVX-512 / GPU Tensor Core byte-manipulation), ChaCha8 outpaces Philox in throughput while offering 64-bit/128-bit indices. It is the absolute optimal choice for *deterministic convergence*.

### Implementation Mandate for POLYDIM:
To guarantee 0.0 drift between CPU (Rust/C++) and GPU (CUDA/Triton):
1. **Algorithm:** Use a pure Counter-Based PRNG (Philox4x32 or ChaCha8). 
2. **Index Mapping:** $R_i = \text{CBPRNG}(\text{seed\_key}, \text{global\_tensor\_index\_i})$. 
3. **Floating Point Projection:** Standardize the float conversion exactly: `float_val = (uint32_val >> 8) * (1.0f / 16777216.0f)`. DO NOT use compiler-specific float cast intrinsics, as standard library casts between GCC and NVCC differ in rounding for edge cases.

## Conclusion & Actionable Next Steps
- **Retraction:** Discard all exponential maps. Implement Cayley-SMW. It is mathematically the only valid algorithm for maintaining orthogonality in $D \ge 10^7$ within $O(D)$ memory limits.
- **PRNG:** Use a stateless CBPRNG (Philox or ChaCha8) with standardized integer-to-float masking. Stateful generators are fundamentally incompatible with POLYDIM's concurrent architecture.
