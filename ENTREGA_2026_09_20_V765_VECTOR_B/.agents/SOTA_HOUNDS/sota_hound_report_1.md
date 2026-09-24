# SOTA AUDIT REPORT: PHYSICAL GAPS IN GPU & ARM IPC ARCHITECTURES
**DATE:** 2026-09-20
**AUTHOR:** Bulldog Critic (Research Node)
**TARGET:** NVIDIA sm_80/sm_90 & ARM Apple Silicon IPC

## 1. TRITON GPU COMPILER: SUBNORMALS AND FP32 FTZ VULNERABILITY
**Hypothesis Evaluated:** Do `allow_flush_denorm=False` or `do_not_specialize=False` mathematically guarantee IEEE strict subnormals on NVIDIA A100/H100?

### THE PHYSICAL VERDICT: FALSE SENSE OF SECURITY
The parameter `allow_flush_denorm` is structurally impotent on NVIDIA architectures. It is a legacy parameter mapped primarily to the AMD (HIP) ROCm backend. On NVIDIA sm_80 (A100) and sm_90 (H100), Triton's Python-level kwargs provide ZERO mathematical guarantees against FTZ (Flush-To-Zero) for subnormals.

### ASYMPTOTIC GAPS & ARCHITECTURAL VULNERABILITIES
1. **The PTX Lowering Blindspot:** NVIDIA hardware dynamically defaults to FTZ for FP32 to maintain FMA throughput. When Triton lowers `tl.dot` or element-wise math to LLVM IR and subsequently to PTX, math operations are frequently mapped to instructions decorated with the `.ftz` modifier (e.g., `fma.rn.ftz.f32`). Passing `allow_flush_denorm=False` in Python does not explicitly scrub the `.ftz` instruction from the emitted PTX in the NVIDIA backend.
2. **`do_not_specialize=False` Irrelevance:** This flag merely prevents the JIT compiler from caching kernel specializations based on input sizes or values (e.g., exact zero alignment). It does NOT alter the hardware's internal floating-point mantissa pipeline or enforce IEEE 754 compliance.
3. **The TF32 Hardware Override:** Even if the PTX is generated cleanly (`fma.rn.f32` without `.ftz`), environment overrides (e.g., `NVIDIA_TF32_OVERRIDE=1`) or implicit PyTorch dispatcher behaviors will dynamically collapse the FP32 mantissa at the Tensor Core level, erasing subnormal precision.

**MANDATORY ARCHITECTURAL FIX:** 
Never trust the Python API for subnormal guarantees. To certify numerical stability against subnormal collapse, you MUST intercept the compilation pipeline and explicitly audit the PTX/SASS output. To force IEEE 754 compliance, you must bypass high-level Triton operations, use `tl.inline_asm_elementwise` to inject strict IEEE instructions, and explicitly disable TF32 prior to kernel execution.

*Sources:* 
- *Triton GitHub Issues (2024-2025): Discussions on precision discrepancies and `.ftz` PTX lowering.*
- *NVIDIA PTX ISA Documentation: `fma` instruction modifiers and flush-to-zero semantics.*

---

## 2. ARM APPLE SILICON: IPC WEAK MEMORY ORDERING & TORN READS
**Hypothesis Evaluated:** Does using C FFI (`ctypes`) with `memory_order_acquire` / `memory_order_release` prevent torn reads when reading the payload via Python's `memoryview`?

### THE PHYSICAL VERDICT: CATASTROPHIC COHERENCE FAILURE
Using `ctypes` to invoke C11 atomic barriers while subsequently consuming the payload via Python's native `memoryview` is fundamentally flawed. It guarantees asynchronous Torn Reads under heavy IPC load on ARM (M-Series).

### ASYMPTOTIC GAPS & ARCHITECTURAL VULNERABILITIES
1. **The Python/C11 Barrier Disconnect:** ARM employs a weakly ordered memory model. A `memory_order_release` (Writer) and `memory_order_acquire` (Reader) pair translates to valid hardware barriers (e.g., `DMB ISH`). However, Python's `memoryview` is a high-level interpreter object caching a physical pointer. The hardware barrier executing at the C-level does NOT synchronize the Python interpreter's state.
2. **Speculative Pre-Evaluation:** The ARM CPU may speculatively prefetch the memory address mapped by the Python `memoryview` into the L1 cache *before* the Python GIL even reaches the `ctypes` FFI call to execute `memory_order_acquire`. When the hardware barrier finally executes, the memory is fenced, but Python is already holding the *stale* speculatively loaded bytes in its loop.
3. **The Torn Read Axiom:** High-level Python operations that read a multi-byte `memoryview` are non-atomic. A read loop in Python bytecode can be context-switched or hardware-interleaved mid-execution by the Writer process, resulting in torn geometry.

**MANDATORY ARCHITECTURAL FIX:**
You cannot split the synchronization and payload consumption across the C/Python boundary. To achieve native Zero-Copy IPC on ARM without OS semaphores, the `memory_order_acquire` AND the payload tensor copy MUST occur atomically within the SAME Rust/C++ FFI block. The Python layer must only be handed the pointer/reference *after* the native layer has secured the data behind the barrier.

*Sources:*
- *ARM Architecture Reference Manual: Weakly Ordered Memory and `DMB/DSB` barriers.*
- *Python Multiprocessing `shared_memory` docs and known IPC coherency limitations.*
