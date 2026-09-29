

# POLYDIM V813 — FULL LINE-BY-LINE AUDIT

## Pass 1–5 Consolidated Report

---

## FILE: `polydim_solver_abi_v808_1.h` (Lines 1–139)

### `PmtpBankedSlotHeader` struct, L60–79

**BUG 1 — MEDIUM: `header_padding` size computation is fragile and non-portable across compilers**

Lines affected: L75 (`uint8_t header_padding[80]`)

The padding is hand-computed: fields at offsets 0–47 occupy 48 bytes, padding is 80 bytes to reach offset 128. This is correct *only* under `#pragma pack(push, 8)`. The `static_assert` at L133 catches drift, but the struct mixes `uint32_t`, `uint64_t`, and `uint8_t` fields. Under `pack(8)`, the layout is:

- `global_epoch` (4) + `active_bank` (4) = 8
- `writer_active` (4) + `owner_pid` (4) = 16
- `sequence` (8) = 24
- `owner_start_time_ns` (8) = 32
- `num_reclaimed_orphans` (4) + `prev_bank` (4) = 40
- `writer_heartbeat_ns` (8) = 48
- `header_padding[80]` = 128 ✓

The `static_assert` is the real guard. **No bug, but fragility noted.**

### `PolydimSpscRing` struct, L108–115

**BUG 2 — HIGH: False sharing between `write_index` and `pad_write` is not guaranteed by `#pragma pack(push, 8)`**

Lines affected: L109–114

The struct uses `uint8_t pad_write[120]` to isolate `write_index` from `read_index` to separate cache lines (128 bytes total per side). Under `pack(8)`, `write_index` (8 bytes) + `pad_write[120]` = 128 bytes. Then `read_index` (8) + `pad_read[120]` = 128 bytes. This is correct for layout, but **there is no `alignas(128)` or `__attribute__((aligned(128)))` on the struct itself**. If the struct is heap-allocated or embedded in another struct, the base address may not be 128-byte aligned, so `write_index` and `read_index` could share a cache line with external data, or the 128-byte boundary between them could be misaligned.

**Severity: HIGH** — False sharing on the SPSC ring hot path degrades throughput.

**Fix:**
```c
typedef struct __attribute__((aligned(128))) {
    uint64_t write_index;
    uint8_t  pad_write[120];
    uint64_t read_index;
    uint8_t  pad_read[120];
    size_t   capacity;
    size_t   capacity_mask;
    PolydimTelemetryEvent* ring_buffer;
} PolydimSpscRing;
```
Note: This changes `sizeof(PolydimSpscRing)` and may require ABI version bump. Alternatively, ensure all allocations of this struct use 128-byte aligned allocation.

### `PolydimSolverOptions` struct, L82–92

**BUG 3 — MEDIUM: `static_assert(sizeof(PolydimSolverOptions) == 64)` may fail on some ABIs**

Lines affected: L82–92, L131

Layout under `pack(8)`:
- `max_iterations` (8) = 8
- `gradient_tolerance` (8) = 16
- `step_tolerance` (8) = 24
- `ortho_tolerance` (8) = 32
- `learning_rate` (8) = 40
- `sampling_period` (4) + `num_threads` (4) = 48
- `retraction_type` (4) + 4 bytes padding to align `shift_regularization` = 56
- `shift_regularization` (8) = 64 ✓

Under `pack(8)`, `retraction_type` (int32_t at offset 52) is followed by `shift_regularization` (double at offset 56, needs 8-byte alignment → offset 56 is 8-aligned ✓). Wait: offset 48 + 4 (`sampling_period`) + 4 (`num_threads`) = 56. Then `retraction_type` at 56 (4 bytes) → offset 60. `shift_regularization` needs 8-byte alignment → padded to 64. Total = 64 + 8 = 72. **This breaks the static_assert.**

Let me recount under `pack(8)`:
- `uint64_t max_iterations`: offset 0, size 8
- `double gradient_tolerance`: offset 8, size 8
- `double step_tolerance`: offset 16, size 8
- `double ortho_tolerance`: offset 24, size 8
- `double learning_rate`: offset 32, size 8
- `uint32_t sampling_period`: offset 40, size 4
- `uint32_t num_threads`: offset 44, size 4
- `int32_t retraction_type`: offset 48, size 4
- **4 bytes implicit padding** (to align double to 8)
- `double shift_regularization`: offset 56, size 8
- Total: 64 ✓

Offset 48 + 4 = 52 for end of `retraction_type`. Next field is `double` needing 8-byte alignment. 52 rounded up to 8 = 56. So 4 bytes padding. 56 + 8 = 64. ✓

**No bug.** The implicit padding makes it exactly 64. The `static_assert` will catch any platform where this differs.

### `PolydimTelemetryEvent` struct, L104–108

Lines affected: L104–108, L132

Layout: `uint64_t` (8) + `uint32_t` (4) + `uint32_t` (4) + `double[14]` (112) = 128. ✓

### `PolydimHandle` struct, L118–124

**BUG 4 — HIGH: `refcount` is accessed atomically in C++ but declared as plain `int32_t` in the ABI header**

Lines affected: L121 (`int32_t refcount`), and kernel_cpp L~230–250

The C++ code does `reinterpret_cast<std::atomic<int32_t>*>(&h->refcount)` which is technically **undefined behavior** per C++17 §6.9.2. `std::atomic<int32_t>` is not layout-compatible with `int32_t` in the standard, even though it works on all major platforms. The `#pragma pack(push, 8)` makes this worse because it could affect padding around the atomic.

**Severity: HIGH** — UB that works today but is not guaranteed.

**Fix:** Use `_Atomic int32_t` in C or `std::atomic<int32_t>` in C++, or use explicit atomic intrinsics (`__atomic_fetch_add`, etc.) on the raw `int32_t`. Since this is an ABI header shared across C/C++/Python/Dart, the safest fix:
```c
#ifdef __cplusplus
#include <atomic>
static_assert(sizeof(std::atomic<int32_t>) == sizeof(int32_t), "atomic<int32_t> size mismatch");
#endif
```
This at least validates the assumption. Alternatively, use `__atomic_*` builtins directly.

### `PmtpReaderLease` struct, L55–62

`static_assert(sizeof(PmtpReaderLease) == 32)` at L130. Layout under `pack(8)`:
- `state` (4) + `pid` (4) = 8
- `process_start_time_ns` (8) = 16
- `generation` (8) = 24
- `epoch` (4) + `pad` (4) = 32 ✓

**No bug.**

---

## FILE: `kernel_cpp_v813.cpp` (Lines 1–~580)

### `polydim_abi_probe` L~155–160

`[polydim_abi_probe] L155-L160: NO BUGS FOUND after 3-pass review`

### `knuth_two_sum` L~175–181

**BUG 5 — MEDIUM: `volatile` on `sum` is insufficient to prevent reordering of the error computation**

Lines affected: L176–180

The `volatile` keyword prevents the compiler from optimizing away the store/reload of `sum`, but the subsequent lines `b_virtual = sum - a` and `a_virtual = sum - b_virtual` are computed from the volatile read. The comment says compile with `-fno-fast-math`, which is the real protection. The `volatile` is a belt-and-suspenders approach that is correct but may introduce unnecessary store-to-load latency on every call.

**Not a bug per se** — the `-fno-fast-math` flag is the actual guard. The `volatile` is defensive and correct.

`[knuth_two_sum] L175-L181: NO BUGS FOUND after 3-pass review`

### `twosum_tree_reduce_inplace` L~183–210

**BUG 6 — LOW: Potential issue with `current` array being modified in-place when caller doesn't expect it**

Lines affected: L183–210

The function name says `_inplace` so this is by contract. However, the caller must ensure the array is writable and expendable.

`[twosum_tree_reduce_inplace] L183-L210: NO BUGS FOUND after 3-pass review`

### `polydim_stream_copy_nt` L~216–245

**BUG 7 — MEDIUM: Overlap check is incorrect for non-overlapping case**

Lines affected: L222

```cpp
if (dest < src + count && src < dest + count) {
```

This checks if the ranges `[dest, dest+count)` and `[src, src+count)` overlap. If they do, it falls back to `memmove`. This is correct. However, comparing pointers from potentially different allocations is **undefined behavior** in C/C++ per §6.8.9. In practice, this works on flat address space architectures.

**Severity: LOW** — UB that works universally on target platforms (x86_64, ARM64).

**BUG 8 — MEDIUM: `_mm_loadu_pd` from `src` but `_mm_stream_pd` requires 16-byte aligned `dest`**

Lines affected: L228–232

The code checks `reinterpret_cast<uintptr_t>(dest) % 16 == 0` before using `_mm_stream_pd`, which requires 16-byte alignment. This is correct. However, `src` uses `_mm_loadu_pd` (unaligned load), which is fine.

But: the `#pragma omp parallel for` on the streaming stores means **multiple threads issue non-temporal stores**. NT stores bypass the cache and go directly to the write-combining buffer. If two threads' stores hit the same cache line (which they won't since each `b` maps to a distinct `idx = b*2`), there'd be a problem. Since each thread writes to a disjoint 16-byte region, this is safe **as long as the regions don't share a cache line boundary in a way that causes WC buffer conflicts**. For 16-byte aligned `dest`, consecutive 16-byte blocks are fine.

`[polydim_stream_copy_nt] L216-L245: NO BUGS FOUND after 3-pass review`

### `polydim_alloc_aligned` / `polydim_free_aligned` L~251–280

`[polydim_alloc_aligned] L251-L268: NO BUGS FOUND after 3-pass review`
`[polydim_free_aligned] L270-L280: NO BUGS FOUND after 3-pass review`

### `polydim_handle_create` L~282–296

**BUG 9 — HIGH: `reinterpret_cast<std::atomic<int32_t>*>(&h->refcount)` on a `malloc`'d struct — the `int32_t` was never constructed as `std::atomic`**

Lines affected: L289

Same issue as BUG 4. The `PolydimHandle` is allocated with `std::malloc`, so no constructor runs. Then the code reinterpret_casts the `int32_t` field to `std::atomic<int32_t>*` and calls `.store()`. This is UB: the `std::atomic` was never constructed.

**Severity: HIGH** — UB. On all major compilers/platforms, `std::atomic<int32_t>` is trivially constructible and has the same representation as `int32_t`, so this works. But it's formally UB.

**Fix:** Use `__atomic_store_n(&h->refcount, 1, __ATOMIC_RELEASE)` instead, which operates on plain integers.

### `polydim_handle_retain` / `polydim_handle_release` L~298–312

Same UB as BUG 9. Additionally:

**BUG 10 — MEDIUM: `polydim_handle_release` has a use-after-free window in multi-threaded scenarios**

Lines affected: L305–310

```cpp
if (reinterpret_cast<std::atomic<int32_t>*>(&h->refcount)->fetch_sub(1, ...) == 1) {
    if (h->data) { polydim_free_aligned(h->data); h->data = nullptr; }
    std::free(h);
}
```

If two threads both hold a reference and both call `release` simultaneously:
- Thread A: `fetch_sub(1)` returns 2 → doesn't free
- Thread B: `fetch_sub(1)` returns 1 → frees

This is correct. The `fetch_sub` is atomic, so only one thread sees the return value of 1. **No bug here.**

But: if a thread calls `release` and then another thread calls `retain` on the same handle *after* the refcount hit 0 but *before* `std::free(h)` executes — that's a use-after-free. This is a caller contract violation (don't retain a handle you've fully released), not a library bug.

`[polydim_handle_retain] L298-L302: NO BUGS FOUND after 3-pass review`
`[polydim_handle_release] L304-L312: NO BUGS FOUND after 3-pass review` (with UB caveat from BUG 9)

### `polydim_spsc_init` L~318–338

**BUG 11 — LOW: Missing overflow check for `capacity * sizeof(PolydimTelemetryEvent)` before the explicit check**

Lines affected: L323–325

The code checks `capacity > SIZE_MAX / sizeof(PolydimTelemetryEvent)` which correctly prevents overflow. ✓

`[polydim_spsc_init] L318-L338: NO BUGS FOUND after 3-pass review`

### `polydim_spsc_push` L~340–355

**BUG 12 — MEDIUM: Redundant fence before store-release**

Lines affected: L350–351

```cpp
std::atomic_thread_fence(std::memory_order_release);
w->store(wi + 1, std::memory_order_release);
```

The `store` with `memory_order_release` already provides the release semantics. The preceding fence is redundant but not incorrect. It's a performance pessimization, not a bug.

`[polydim_spsc_push] L340-L355: NO BUGS FOUND after 3-pass review`

### `polydim_spsc_pop` L~357–372

`[polydim_spsc_pop] L357-L372: NO BUGS FOUND after 3-pass review`

### `polydim_spsc_destroy` L~374–380

**BUG 13 — LOW: No fence after zeroing `write_index`/`read_index`**

The destroy function doesn't reset `write_index` or `read_index`. If the ring is reused (re-initialized), the old indices could be visible