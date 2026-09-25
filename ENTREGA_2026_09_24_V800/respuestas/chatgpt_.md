# POLYDIM V803 — Bulldog Red-Team Status

Date: 2026-09-25

## What this delivery actually closes

The code shipped here removes the demonstrated V800 defects and the follow-on defects found while rebuilding the system:

1. The numerical kernel is an actual rank-2 Rodrigues rotation, not the former `X + U*V` placeholder.
2. The general operator is documented honestly as an orthogonal rank-2 rotation. The geodesic interpretation is exposed separately as the sphere exponential special case `u=x`, `v` unit tangent.
3. Python FFI rejects wrong dtype, ndim, strides/layout, read-only output, malformed descriptors, invalid aliases and size overflow.
4. Certified builds reject fast-math and use strict rounding flags; runtime checks cover MXCSR/FPCR.
5. CPU reductions are block-partitioned and combined in fixed block order, so changing worker count does not change the reduction order.
6. PMTP is real shared memory with generation handles, futex/WaitOnAddress, lifecycle accounting, local lease ownership and a true zero-copy producer path.
7. `publish()` is explicitly a copy convenience function; the zero-copy API is `begin_write → write_ptr → commit`.
8. PMTP close/open races, stale handles, double commit/release and local live leases are tested.
9. GPU/Triton code no longer uses the false elementwise placeholder and avoids six full `D×K` temporary reductions. It is still unverified on real CUDA/Triton hardware in this environment.
10. Hardware probing is fast/non-invasive by default; accelerator runtime initialization is opt-in.
11. CMake registers the native and Python suites in CTest; sanitizer and static-analyzer paths are provided.
12. Production core is 1,962 lines (`CMakeLists.txt` + `src/*`).

## Evidence executed locally

- CMake Release: 3/3 CTest tests passed.
- 16 Python integration checks passed.
- Normal C++ tests passed.
- ASan + UBSan passed.
- TSAN PMTP stress passed.
- GCC `-fanalyzer` passed for C++ kernel and PMTP.
- Clang static analyzer passed for C++ kernel and PMTP.
- Clang 17 strict shared-library build passed.
- Deterministic 70,000×3 CPU case matched GCC/Clang bitwise in the tested workload.
- Large-angle cases `1e6`, `1e12`, `1e16` matched an independent Python/libm construction within the tested tolerance.
- Certified build rejects `-ffast-math` at compilation.
- PMTP Linux cross-process test passed, including generation reuse and zero-copy shared-slab write path.
- High-dimensional capacity arithmetic test passed for `D=10,000,000`, `K=512`.

## Explicitly not certified here

- Windows runtime/build execution.
- Rust compiler/runtime: `rustc` is unavailable here.
- Triton/CUDA/ROCm runtime execution.
- Full physical `D=10^7,K=512` placement on target accelerator hardware.
- NUMA, HBM, PCIe and multi-GPU performance certification.
- Dead-process recovery for a crashed PMTP creator.
- Universal bitwise equivalence across all ISAs/libm implementations.

## Architecture boundaries that must not be misrepresented

- General V803 rotation is not automatically a geodesic integrator.
- PMTP zero-copy is CPU/shared-slab zero-copy. GPU-device IPC/VMM is a separate backend.
- The package contains no quantum compiler, LSM or SORM implementation. Optimizing nonexistent modules would be invented work.
- There is no completed Betti-1 topology engine in this delivery. A correct topological contract requires defining the simplicial/graph complex first.

## Red-team conclusion

No absolute claim of “bug free” is made. The claims marked as verified above are tied to source inspection and executed tests in the stated environment. Anything not executable here is left as a residual instead of being reported as PASS.
