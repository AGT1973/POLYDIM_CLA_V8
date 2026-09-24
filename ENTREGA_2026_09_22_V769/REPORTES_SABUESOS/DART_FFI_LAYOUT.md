# DART FFI MEMORY LAYOUT CONSTRAINTS (PMTPControl ABI)
**Date:** 2026-09-21
**Target Context:** POLYDIM Native Tensor Telepathy (PMTP Protocol)
**Agent Persona:** Bulldog Critic / Red Team

## 1. Executive Summary: The Asymptotic ABI Mismatch

Mapping a high-performance C++ struct like `PMTPControl` to Dart 3.0+ FFI is fraught with critical ABI misalignment risks. Dart's FFI assumes standard C-ABI (natural padding based on the largest scalar), lacks native alignment overriding constraints like `alignas(64)`, and has zero visibility into C++ template abstractions like `std::atomic`. 

If `PMTPControl` is blindly mapped, pointer arithmetic across arrays (the Swarm Vector Bus) will immediately corrupt memory, cross cache lines, and trigger hard segfaults.

## 2. The 64-Byte Alignment & Stride Corruption

In C++, appending `alignas(64)` to a struct forces its total size to be a multiple of 64 bytes (typically exactly 64 bytes to fill a CPU cache line and prevent false sharing).

**The Vulnerability:** 
Dart's `sizeOf<Struct>()` calculates size based solely on the fields present. If your struct contains two 32-bit integers, Dart computes a size of 8 bytes (or 16 depending on natural padding). 
If C++ returns an array of `PMTPControl`, C++ steps by `64` bytes per index. Dart will step by `8` bytes. `pointer[1]` in Dart will read garbage data from the middle of `pointer[0]`'s cache line.

**The Solution (Strict Manual Padding):**
You MUST manually inject trailing byte arrays in the Dart definition to force the struct size to exactly 64 bytes.

```dart
// DART LAYER
import 'dart:ffi';

final class PMTPControl extends Struct {
  @Int32()
  external int flag; // 4 bytes

  @Int32()
  external int count; // 4 bytes

  // MANDATORY PADDING to enforce 64-byte struct size and stride ABI.
  // 64 - 4 - 4 = 56 bytes.
  @Array(56)
  external Array<Uint8> _padding; 
}
```

*Note on Base Allocation:* Dart's internal `calloc`/`malloc` only guarantees 8-byte or 16-byte alignment. You MUST NOT allocate `PMTPControl` in Dart. It must be allocated in C++ via `aligned_alloc(64, size)` or provided via a 64-byte aligned `mmap` pointer (which PMTP already does), then cast in Dart using `pointer.cast<PMTPControl>()`.

## 3. The `std::atomic` Mapping Constraint

**The Vulnerability:**
`std::atomic<T>` is a C++ template, not a Plain Old Data (POD) struct. While standard implementations for integers map identically to the underlying integer type, this is not guaranteed by the ISO C++ standard unless the type is lock-free. 

**The C++ Veto:**
You must violently enforce the ABI contract in C++ at compile time.
```cpp
// C++ LAYER
struct alignas(64) PMTPControl {
    std::atomic<int32_t> flag;
    std::atomic<int32_t> count;
};

// MANDATORY ABI VERIFICATIONS
static_assert(std::atomic<int32_t>::is_always_lock_free, "Atomic requires hidden locks, ABI broken!");
static_assert(sizeof(PMTPControl) == 64, "PMTPControl is not strictly 64 bytes!");
static_assert(offsetof(PMTPControl, flag) == 0, "Flag offset mismatch");
static_assert(offsetof(PMTPControl, count) == 4, "Count offset mismatch");
```

**Dart Synchronization Veto:**
Dart FFI `Pointer` lacks native atomic Read-Modify-Write (RMW) operations (like Compare-And-Swap or Fetch-Add). 
- If Dart only *reads* the flag, a standard FFI read (`pmtp.ref.flag`) is safe provided hardware cache coherence is assumed, but risks instruction reordering on ARM.
- If Dart must *mutate* the atomic state, doing so directly (`pmtp.ref.flag = 1`) breaks atomic guarantees and risks data races. You MUST expose a C-FFI wrapper: `void pmtp_cas(PMTPControl* ptr, int32_t exp, int32_t des);` for Dart to call.

## 4. The `@Packed` Annotation Danger

Dart provides `@Packed(1)` to mirror C's `#pragma pack(1)`. 
**DO NOT USE `@Packed` FOR PMTPControl.** 
Packing a struct collapses natural padding. Unaligned atomic operations cross cache-line boundaries, resulting in massive latency penalties on x86 (cache line splits) and catastrophic `SIGBUS` alignment faults on ARM/Apple Silicon. 
Instead, manually order your fields from largest (e.g., 64-bit) to smallest (e.g., 8-bit) to ensure zero natural padding gaps, and let standard C-ABI alignment govern the internals.
