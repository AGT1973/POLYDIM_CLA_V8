**POLYDIM V810 – HOSTILE RED‑TEAM LINE‑BY‑LINE AUDIT**  
*Module 1 – kernel_cpp_v808_1.cpp*  

For every public‑or‑static function the following fields are reported:

| # | FUNCTION | VERDICT | REASONING (memory‑ordering / pointer‑arithmetic / numerical / asymptotic) | PATCH (if vulnerable) |
|---|----------|---------|-----------------------------------------------------------------------------|-----------------------|

---

### 1. ABI Probe  

| # | FUNCTION | VERDICT | REASONING | PATCH |
|---|----------|---------|-----------|-------|
|1|`polydim_abi_probe`|**CERTIFIED**|Purely returns `sizeof(PolydimSolverOptions)`. No pointer arithmetic, no concurrency, no allocation. | – |

---

### 2. Floating‑point utilities  

| # | FUNCTION | VERDICT | REASONING | PATCH |
|---|----------|---------|-----------|-------|
|2|`knuth_two_sum`|**CERTIFIED**|Deterministic IEEE‑754 two‑sum, no memory accesses, no branches that can cause UB. | – |
|3|`twosum_tree_reduce_inplace`|**CERTIFIED**|All accesses are within the `current` buffer (size = N). The reduction loop never reads past `current[len‑1]`. No atomics, no division by zero. | – |
|4|`twosum_tree_reduce`|**CERTIFIED**|Copies the input into a `std::vector<double>` of exact size `N`; then calls the in‑place version. No overflow. | – |

---

### 3. Non‑temporal streaming copy  

| # | FUNCTION | VERDICT | REASONING | PATCH |
|---|----------|---------|-----------|-------|
|5|`polydim_stream_copy_nt`|**CERTIFIED**|*Pointer arithmetic*: `&dest[idx]` and `&src[idx]` are safe because `idx < count`. Alignment test guarantees the `_mm_stream_pd` destination is 16‑byte aligned. *Memory ordering*: each thread writes its own 2‑element block, then a `std::atomic_thread_fence(seq_cst)` inside the parallel region guarantees that the non‑temporal stores are globally visible before the implicit barrier at the end of the `omp for`. The final `_mm_sfence()` (or the subsequent fence) orders the stores with respect to later loads. No data race, no overflow. | – |

---

### 4. Aligned allocator (G11)  

| # | FUNCTION | VERDICT | REASONING | PATCH |
|---|----------|---------|-----------|-------|
|6|`polydim_alloc_aligned`|**CERTIFIED**|*Alignment*: If `alignment` is not a power of two the code forces 64 B, which satisfies the POSIX requirement that the alignment be a power‑of‑two multiple of `sizeof(void*)`. The fallback to `sizeof(void*)` guarantees the minimum required alignment. No pointer arithmetic beyond the API call. | – |
|7|`polydim_free_aligned`|**CERTIFIED**|Corresponds to the allocation routine; no UB. | – |
|8|`polydim_handle_create`|**CERTIFIED**|Allocates the data buffer with the allocator above, then allocates the handle with `malloc`. The handle layout is *plain‑old‑data*; the only atomic operation is on `refcount`, which is stored after the allocation. No race at creation time. | – |
|9|`polydim_handle_retain`|**VULNERABLE**|**Race condition** – the retain uses `fetch_add(1, memory_order_relaxed)`. If a thread calls `retain` **concurrently** with another thread that is executing `polydim_handle_release`, the release may observe the reference count drop to 0 (previous value = 1) and free the handle **while the retaining thread still holds a reference**. The relaxed ordering does not synchronize with the acquire‑release pair used in `release`. This is a classic use‑after‑free / double‑free window. | ```cpp
POLYDIM_EXPORT void polydim_handle_retain(PolydimHandle* h) {
    if (!h) return;
    // Acquire‑release ensures the increment is visible to any concurrent release.
    reinterpret_cast<std::atomic<int32_t>*>(&h->refcount)
        ->fetch_add(1, std::memory_order_acq_rel);
}
``` |
|10|`polydim_handle_release`|**CERTIFIED (after patch)**|Uses `fetch_sub(1, memory_order_acq_rel)` and frees only when the previous value was 1, which is correct **provided** that all retains use at least acquire‑release semantics (see patch above). No pointer arithmetic errors. | – |

---

### 5. Single‑Producer‑Single‑Consumer ring (G12)  

| # | FUNCTION | VERDICT | REASONING | PATCH |
|---|----------|---------|-----------|-------|
|11|`polydim_spsc_init`|**CERTIFIED**|Capacity is forced to a power of two ≥ 2, overflow check `capacity > SIZE_MAX/sizeof(Event)` prevents `size_t` wrap‑around. Allocation is aligned, buffer is zero‑initialized. Write/read indices are stored with relaxed ordering followed by a global `seq_cst`