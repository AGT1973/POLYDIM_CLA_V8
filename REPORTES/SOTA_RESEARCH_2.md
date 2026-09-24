# POLYDIM SOTA RESEARCH 2: Extreme Hardware Limits & UB Triggers

## 1. Float64/Float32 Subnormals & Mantissa Collapse (FMA Depth > 10,000,000)

**Catastrophic Latency Spikes (Hardware UB):**
At sequential FMA tree depths of $10^7$, unbounded sequences frequently decay into subnormal ranges ($< 1.18 \times 10^{-38}$ for FP32, $< 2.22 \times 10^{-308}$ for FP64).
Modern microarchitectures (Intel Golden Cove, AMD Zen 4) natively trap subnormal arithmetic into microcode assists. This triggers latency penalties of ~100x to ~150x per instruction. In a $10^7$ pipeline, encountering scattered subnormal operands causes chaotic, non-deterministic execution spikes (Timing UB).
*Mandate:* You must unconditionally force hardware FTZ (Flush-To-Zero) and DAZ (Denormals-Are-Zero) flags by writing to MXCSR: `_mm_setcsr(_mm_getcsr() | 0x8040)`. In high-dimensional tensors ($D \ge 10^4$), subnormal tracking is useless entropy and an asymptotic bottleneck.

**Mantissa Collapse in Deep FMA:**
While a single FMA (`a * b + c`) retains infinite intermediate precision before the final round, at depth $10^7$, the accumulation of the "Sticky Bit" during hierarchical summations leads to deterministic mantissa collapse. The condition number explodes exponentially. Sequential FMA accumulation without pairwise or block reduction is numerically suicidal.

## 2. OpenMP Concurrency, KBN Summation, & AVX-512 Prefix Sums

**L3 Cache MESI Protocol Thrashing (False Sharing):**
Deploying Kahan-Babuska-Neumaier (KBN) across 4096-sized blocks requires state tracking (a `sum` and a compensation `c`). 
If OpenMP threads write their local block states to contiguous memory (e.g., an array of structs), threads $i$ and $i+1$ will map to the exact same 64-byte L1/L2 cache line (which holds 16 FP32s).
*Result:* Catastrophic false sharing. The MESI protocol will endlessly invalidate the cache line across the ring bus/mesh, forcing serial L3 cache stalls and neutralizing the parallelism.
*Mandate:* KBN struct states MUST be explicitly padded: `alignas(64) struct KBNState { float sum; float c; };` to isolate each thread's state boundary.

**AVX-512 / AVX-10 Intrinsic Prefix Sums:**
There is NO native hardware floating-point prefix sum (scan) instruction in AVX-512 or AVX-10. Hardware conflict/scan logic (e.g., `_mm512_mask_scan_epi32` / `VPCONFLICT`) exists strictly for integer vectors, not FP additions.
*Is ReproBLAS the only way?*
No. ReproBLAS relies on Kulisch accumulators (wide fixed-point integer conversions) which guarantee bit-wise reproducible summation but impose severe pipeline penalties and ruin throughput.
*SOTA Alternative (Hardware KBN):*
Synthesize the prefix sum completely in registers using a Blelloch or Hillis-Steele network mapped to `_mm512_shuffle_ps` (or `_mm512_permutexvar_ps`) and `_mm512_add_ps`. Vectorize the KBN error tracking inside the 16 parallel ZMM lanes, and perform horizontal log(N) reductions strictly at the 4096-block boundaries to avoid pipeline stalls.

**Final Verdict:**
Do not assume standard FP behaviors scale to $10^7$. Force FTZ/DAZ via MXCSR. Pad KBN accumulators to 64 bytes to survive OpenMP scale. Build vector-level prefix sums via AVX-512 shuffles; reject ReproBLAS for high-throughput $S^{D-1}$ tensor geometry.
