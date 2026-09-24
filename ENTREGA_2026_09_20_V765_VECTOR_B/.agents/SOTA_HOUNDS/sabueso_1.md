# RED TEAM HOUND REPORT: Triton/CUDA Subnormal Floats (FTZ) on Hopper (sm_90)
**Date:** 2026-09-20
**Target:** Evaluate `allow_flush_denorm=False` override behavior on LLVM NVPTX (sm_90).

## 1. EMPIRICAL VERDICT
There is **NO** specific LLVM bug overriding `allow_flush_denorm=False` on NVIDIA `sm_90` because the premise is fundamentally flawed. In the Triton compiler architecture, the `allow_flush_denorm` kwarg (often seen in `extra_kern_args`) is **hardcoded to the AMD (HIP) backend**. It specifically controls the `__HIP_FTZ` parameter via `triton/third_party/amd/backend/compiler.py`.

If Ariel is attempting to pass `allow_flush_denorm=False` to a Triton kernel targeting NVIDIA Hopper (`sm_90`) and expecting the NVPTX backend to respect it, it fails by design, not by a bug. Triton's NVIDIA backend does not pipe this Python-level argument to toggle FTZ (Flush-To-Zero) in NVPTX.

## 2. LLVM NVPTX & DENORMAL STATE (2024-2026)
While there is no "override bug" for `allow_flush_denorm` on Hopper, there *is* ongoing architectural work in LLVM (e.g., Issue #210392 mid-2026) to generalize denormal handling (like FTZ) across all backends. Historically:
- NVPTX denormal behavior relies on global flags (`-ftz=true` passed to `ptxas`) or PTX instruction modifiers.
- Triton abstracts this away. On `sm_90`, NVIDIA hardware efficiently processes subnormals in many paths without the severe penalties seen in older architectures, making manual forced FTZ less critical for performance.
- If precision degradation is observed, it's not due to LLVM "ignoring" `allow_flush_denorm`. It's because the NVPTX backend defaults to standard IEEE 754 handling (or `ptxas` defaults), and Triton simply does not expose a flag to override this for NVIDIA.

## 3. ARCHITECTURAL RECOMMENDATION (POLYDIM)
Do **NOT** rely on `allow_flush_denorm=False` for NVIDIA targets. 
- **For Debugging:** Use Triton's `fpsan` instrumentation (`triton.knobs.compilation.instrumentation_mode = "fpsan"`) to explicitly inspect float equivalence.
- **For Math Safety (Anti-Subnormal Sinkhole):** If subnormals are causing drift in $S^{D-1}$ high-dimensional topologies, implement algorithmic softening ($x + \epsilon$) directly in the Triton kernel math rather than expecting the compiler to toggle FTZ natively.

*End of Report. The architectural premise was flawed; adjust the pipeline accordingly.*
