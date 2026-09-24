# RED TEAM AUDIT: OpenMP L2 Tiling in `polydim_stiefel_cayley_smw_f64`

**Target**: `polydim_kernel.cpp` -> `polydim_stiefel_cayley_smw_f64` (Lines 534-602)
**Mode**: Asymptotic Attack & Hardware-Aware Inspection (Bulldog Protocol Active)

## 1. Asymptotic False Sharing on Thread-Local Arena (Cache-Line Ping-Pong)
**Vulnerability**: Severe performance degradation (False Sharing) for small $K$.
**Location**:
`double* L = arena.data() + static_cast<size_t>(tid) * KK2;`
**Attack Vector**:
The buffer `arena` allocates exactly `KK2` doubles ($4K^2$ doubles) per thread consecutively. A standard L1/L2 cache line is 64 bytes (8 doubles).
If $K = 1$, $KK2 = 4$ (32 bytes). Thread 0 and Thread 1 will share the **exact same 64-byte cache line**.
When the OpenMP loop runs, Thread 0 and Thread 1 concurrently execute:
`L[i * K2 + j] += xi * xr[j];`
This triggers catastrophic cache invalidation (cache-line ping-pong) across CPU cores, destroying multi-threading performance.
**Patch**: Pad the arena allocation per thread to a multiple of 64 bytes (e.g., aligning strides to `std::hardware_destructive_interference_size`).

## 2. Invalid OpenMP Reduction Semantics (Data Race)
**Vulnerability**: Data Race / Undefined Behavior in OpenMP reduction.
**Location**:
```cpp
#pragma omp parallel num_threads(nthreads) reduction(|:bad_value)
// ...
if (!std::isfinite(xi) || !std::isfinite(gi)) {
    bad_value = 1; // <--- FATAL
}
```
**Attack Vector**:
According to the OpenMP specification, variables in a custom reduction clause must be updated using the matching reduction operator. Direct assignment (`bad_value = 1;`) is syntactically invalid for a bitwise reduction operation. Depending on the compiler, this will either be rejected, silently compiled as a non-reduction shared write (causing a classical Data Race), or optimized incorrectly.
**Patch**: Change to `bad_value |= 1;`.

## 3. SIMD Memory Alignment Violations (The "D not a multiple of K" trap)
**Vulnerability**: General Protection Fault (Segfault) due to unaligned SIMD loads.
**Location**:
```cpp
const double* __restrict__ xr = X + static_cast<size_t>(d) * K;
// ...
#pragma omp simd
for (uint32_t j = i; j < K; ++j) {
    L[i * K2 + j] += xi * xr[j];
}
```
**Attack Vector (Addressing the Hypothesis)**:
The hypothesis asked to look for violations "when D is not a multiple of K".
Mathematically, the matrix `X` is dimension $D \times K$. The row pointer `X + d * K` is algebraically correct and cannot go out of bounds regardless of $D \% K$.
**However**, the physical hardware reality is different. The critical failure is not when $D$ is not a multiple of $K$, but when **$K$ is not a multiple of the SIMD vector width** (e.g., 4 doubles / 32 bytes for AVX2).
If $K = 3$, row 0 starts at offset 0 (aligned). Row 1 starts at offset 3 (unaligned). Row 2 starts at offset 6 (unaligned).
By combining `__restrict__` with `#pragma omp simd` without explicitly handling unaligned loads, the compiler assumes the pointers are perfectly aligned for vectorization. It emits aligned instructions like `vmovapd`. When $d=1$, the CPU attempts an aligned load on an unaligned address, triggering an immediate Segfault.
**Patch**: Remove the assumption of alignment, or mandate that the matrix stride (pitch) is padded to a multiple of 64 bytes for safe SIMD L2 tiling.

## 4. False Sharing in Tree Reduction
**Vulnerability**: False sharing during the final symmetric matrix assembly.
**Location**:
```cpp
#pragma omp parallel for num_threads(nthreads) schedule(static)
for (int64_t r = 0; r < static_cast<int64_t>(K2); ++r) {
    // ...
    S[j] = s;
}
```
**Attack Vector**:
The static schedule assigns contiguous blocks of $r$ to threads. However, `S` is written to directly. If $K2$ is small, multiple threads will write to `S` at adjacent indices falling within the same cache line, causing unnecessary cache invalidations across cores.

---
**Verdict**: The L2 Tiling loop violates OpenMP reduction syntax and assumes physically aligned memory without stride padding. I strongly recommend rewriting the arena allocation to guarantee 64-byte aligned strides per thread, and fixing the reduction operator.
