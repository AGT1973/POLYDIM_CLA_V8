# RED TEAM AUDIT 5: Arena Alignment & False Sharing
**Target:** `polydim_stiefel_cayley_smw_f64` (Arena padding logic)
**Date:** 2026-09-20
**Status:** **CRITICAL VULNERABILITY DETECTED**

## 1. Asymptotic & Hardware Failure Analysis
The current implementation attempts to pad thread-local memory blocks to 64-byte (cache line) boundaries to prevent false sharing and enable SIMD (AVX-512) auto-vectorization:
```cpp
const size_t stride_doubles = (static_cast<size_t>(KK2) + 7) & ~7ULL;
std::vector<double> arena;
// ...
double* L = arena.data() + static_cast<size_t>(tid) * stride_doubles;
```
**The FATAL flaw:** `std::vector<double>` relies on the default C++ allocator, which only guarantees `alignof(std::max_align_t)`. On x86_64 systems, this is 16 bytes (or at most 32 bytes on some AVX compilers), **NEVER 64 bytes**.

## 2. The False Sharing Trap
If `arena.data()` starts at a 16-byte aligned address (e.g., `0x...010`), adding a multiple of 64 bytes (`stride_doubles * 8`) guarantees that **every thread's base pointer is equally misaligned**.
- **Thread 0 writes up to:** `0x...04F`
- **Thread 1 starts at:** `0x...050`

Both threads share the cache line starting at `0x...040` (which spans `0x...040` to `0x...07F`). Thread 0 writes to the end of its block, and Thread 1 writes to the beginning of its block in the EXACT SAME cache line. 
**Result:** Textbook False Sharing. Cache line bouncing between L1/L2 caches across cores, destroying OpenMP scaling performance.

## 3. Root Cause of Previous SIMD Segfaults
The code contains comments stating:
`// #pragma omp simd (Removed due to SIMD alignment segfaults on odd K)`
The segfault was **NOT** just caused by odd K. It was caused by attempting aligned vector operations (e.g., AVX-512 which strictly requires 64-byte alignment) on a 16-byte aligned base pointer. The hardware emitted a General Protection Fault because `arena.data()` was inherently unaligned for AVX-512 from the start.

## 4. Remediation
1. **ABANDON `std::vector` for shared memory arenas.**
2. Allocate the arena using `std::aligned_alloc(64, total_bytes)` (C++17) or `_aligned_malloc` / `posix_memalign`.
3. Ensure `total_bytes` is a multiple of 64 bytes.
4. Manage memory lifetime with a custom RAII wrapper or `std::unique_ptr<double[], void(*)(void*)>`.
5. Restore the `#pragma omp simd aligned(L: 64)` pragmas once the base pointer is genuinely aligned.
