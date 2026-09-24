# SOTA HOUND REPORT: APPLE SILICON TORN READ VULNERABILITY IN HYBRID FFI SEQLOCKS

## 1. Topological Flaw Identification (The "One-Way Barrier" Illusion)
We have identified a **critical architectural vulnerability** leading to torn reads when mixing C-FFI atomics (`memory_order_acquire`) with Python non-atomic reads (`mmap` via `memoryview` or `struct.unpack`) on ARM64 weakly ordered memory (Apple Silicon).

## 2. The Asymptotic Failure Mechanism
When Python implements a seqlock reader, the logic traditionally flows as:
1. `seq0 = ffi.read_seq_begin()`
2. `payload = read_python_mmap()` (generates standard `LDR` or `LDP` ARM instructions)
3. `seq1 = ffi.read_seq_retry()`

If `ffi.read_seq_retry()` is implemented natively in C/Rust merely as `std::atomic_load_explicit(&seq, std::memory_order_acquire)`, the Clang/GCC compiler emits an **`LDAR` (Load-Acquire Register)** instruction on AArch64.

**The Fatal Topological Flaw:**
`LDAR` enforces *acquire* semantics, meaning NO memory accesses sequenced *after* the `LDAR` can be reordered *before* it. 
HOWEVER, `LDAR` does **NOT** prevent memory accesses sequenced *before* it from sinking *after* it. 
Because the Python `mmap` payload reads (standard `LDR`) are executed prior to the `LDAR`, the ARM CPU's out-of-order execution engine is physically permitted to:
1. Execute `LDAR` (validating `seq1` is consistent with `seq0`).
2. Delay the preceding Python `LDR` (payload reads) until *after* the `LDAR`.
3. Read the payload while the background writer is actively mutating it.

**Result:** A successfully validated sequence counter wrapped around a completely **Torn Read**.

## 3. The Required Fix (`DMB ISHLD`)
To prevent the prior `LDR` payload reads from sinking past the second sequence validation, a hardware read memory barrier is strictly mandatory *after* the Python payload read and *before* the second sequence load.

The C-FFI implementation must explicitly invoke an independent fence:
`std::atomic_thread_fence(std::memory_order_acquire);`

This instructs the compiler to emit a `DMB ISHLD` (Data Memory Barrier Inner Shareable Load-Load/Load-Store). Unlike the `LDAR` instruction, `DMB ISHLD` explicitly guarantees that all loads appearing in program order *before* the barrier (the Python `mmap` reads) are fully resolved and observed *before* any loads appearing *after* the barrier (the final sequence validation check).

## 4. Bulldog Verdict
The hybrid FFI/Python seqlock architecture is fundamentally compromised on Apple M-series chips unless the C-FFI layer explicitly implements a `DMB ISHLD` fence (or Linux `smp_rmb()` equivalent) between the Python payload read and the final sequence validation. Pure `memory_order_acquire` on the atomic load is a superficial trap and mathematically guarantees asynchronous data corruption under concurrent load. Code cannot be certified without this barrier.
