# POLYDIM V810 — MÓDULO 1: ADVERSARIAL AUDIT
## kernel_cpp_v810.cpp (self-identified as v808_1 — *version drift noted at line 3*)

**Audit baseline:** x86-64, IEEE-754 RN, LP64, OpenMP ≥ 4.0 assumed; MSVC OpenMP 2.0 flagged where relevant. Header `polydim_solver_abi_v808_1.h` is **not provided** — every `reinterpret_cast<std::atomic<...>*>` on struct fields is audited against the *assumption* that the underlying fields are trivially-copyable, naturally-aligned integers of matching width. That assumption is unverifiable from this TU alone and is itself a finding.

---

### FUNCTION NAME: `polydim_abi_probe`
**VERDICT: VULNERABLE** (severity: low — coverage gap)
**REASONING:** Returns `sizeof(PolydimSolverOptions)` only. The ABI surface includes `PolydimSolverResult`, `PolydimHandle`, `PolydimSpscRing`, `PolydimTelemetryBuffer`, `PolydimTelemetryPoint`, and the status/retraction enums. A Python-side struct packing mismatch in `PolydimSolverResult` (e.g., `uint64` vs `uint32` for `iterations_executed`) passes this probe silently and corrupts the stack on first call. A single `sizeof` is not an ABI barrier; it is an ABI *suggestion*. Also: filename/header say `v808_1`, audit target says V810 — if the header was rev'd without bumping the probe contract, the probe is checking the wrong thing.
**PROPOSED EXACT PATCH:**
```c
typedef struct { uint32_t abi_version; uint32_t sizeof_options; uint32_t sizeof_result;
                 uint32_t sizeof_handle; uint32_t sizeof_ring; uint32_t sizeof_tel_buf;
                 uint32_t sizeof_tel_point; uint32_t status_enum_max; } PolydimAbiDescriptor;
POLYDIM_EXPORT PolydimAbiDescriptor polydim_abi_probe(void) {
    return { 0x0810, (uint32_t)sizeof(PolydimSolverOptions), (uint32_t)sizeof(PolydimSolverResult),
             (uint32_t)sizeof(PolydimHandle), (uint32_t)sizeof(PolydimSpscRing),
             (uint32_t)sizeof(PolydimTelemetryBuffer), (uint32_t)sizeof(PolydimTelemetryPoint),
             (uint32_t)POLYDIM_STATUS_MAX_ENUM_SENTINEL };
}
```

---

### FUNCTION NAME: `polydim_set_fp_mode` / `polydim_get_fp_mode`
**VERDICT: CERTIFIED**
**REASONING:** `memory_order_relaxed` is correct: the flag is independent — no data publication is ordered through it. The mode is read at kernel-entry (`g_fp_mode.load` in `polydim_gram_dsyrk`); a concurrent flip mid-solve can mix deterministic/throughput Gram matrices across iterations, but this is semantically harmless (both paths compute the same mathematical object; only rounding differs). Unvalidated `mode` is benign: any value ≠ 0 collapses to `THROUGHPUT` at the comparison site. No torn read possible on aligned `int32_t`.

---

### FUNCTION NAME: `knuth_two_sum`
**VERDICT: CERTIFIED** (conditional on build flags)
**REASONING:** Branchless Knuth 2Sum; exact in round-to-nearest for all finite inputs, no operand-ordering precondition (unlike Fast2Sum, which requires |a| ≥ |b|). Pure add/sub — FMA contraction cannot apply. **Hard requirement:** TU must not be compiled with `-ffast-math`/`-ffinite-math-only`/`/fp:fast`; reassociation destroys the error-term identity. This constraint is **not encoded anywhere in the build system visible in this TU** — treat as a standing build-system dependency. NaN/Inf propagate (acceptable; callers firewall).

---

### FUNCTION NAME: `twosum_tree_reduce_inplace`
**VERDICT: CERTIFIED**
**REASONING:** Pairwise tree with TwoSum compensation. Error bound: naive sequential summation is O((N−1)u·Σ|xᵢ|); pairwise is O(⌈log₂N⌉·u·Σ|xᵢ|); the compensation recovers the first-order error of each tree level into `err_acc`, with only second-order terms (`et`) summed uncompensated into `err_comp`. Bound ≈ O(log₂N·u) + O(log²₂N·u²) — strictly better than plain pairwise, not a full Neumaier but asymptotically sound. Odd-length carry (`current[n_pairs] = current[len-1]`) is correct. Destroys input buffer — all call sites refill before