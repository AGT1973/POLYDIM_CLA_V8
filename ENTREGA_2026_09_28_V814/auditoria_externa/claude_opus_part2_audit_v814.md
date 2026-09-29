

# POLYDIM V813 PART 2 AUDIT — LINE-BY-LINE

---

## FILE: `kernel_rust_v813.rs`

---

### `set_last_error` L28-L33

**[BUG 1] MEDIUM — Poisoned Mutex silently swallowed**

L32: `if let Ok(mut guard) = LAST_ERROR.lock()` — if the mutex is poisoned (prior panic while holding it), the global error is silently dropped. Since `ffi_guard!` catches panics, a panic inside any FFI call that happens to hold `LAST_ERROR` will poison it permanently. All subsequent global error writes are lost.

**Lines:** 32

**Root cause:** `Mutex::lock()` returns `Err` on poison; code ignores it.

**Fix:**
```rust
if let Ok(mut guard) = LAST_ERROR.lock().or_else(|e| Ok::<_, ()>(e.into_inner())) {
    // This is wrong — need to clear poison
}
// Correct:
match LAST_ERROR.lock() {
    Ok(mut guard) => { *guard = Some(c); }
    Err(poisoned) => { *poisoned.into_inner() = Some(c); } // recover from poison
}
```

**Severity:** MEDIUM — error reporting degrades after any panic that races with `set_last_error`.

---

### `ffi_guard!` macro L35-L49

**[BUG 2] MEDIUM — `INSTANCE_STATE` set to 0 on success masks concurrent panic state**

L42: On `Ok(code)`, the macro unconditionally stores `0` into `INSTANCE_STATE`. If two FFI calls execute concurrently and one panics, the successful one will overwrite the panic state `1` with `0`, erasing the panic signal for the caller polling `INSTANCE_STATE`.

**Lines:** 42

**Root cause:** Non-atomic read-modify-write; store(0) is unconditional.

**Fix:**
```rust
Ok(code) => {
    // Only clear if WE set it (or don't clear at all — let reset_engine_state handle it)
    // Simplest correct fix: don't touch INSTANCE_STATE on success
    code
}
```

**Severity:** MEDIUM — race condition in multi-threaded FFI usage.

---

### `polydim_last_error_v1` L52-L59

**[BUG 3] HIGH — Dangling pointer returned from TLS**

L54-L58: The function returns `c.as_ptr()` from inside a `with` closure over `RefCell<Option<CString>>`. The returned `*const c_char` points into the TLS `CString`. If the caller (potentially from another thread per G10 comment) calls any other FFI function that triggers `set_last_error`, the TLS `CString` is replaced, deallocating the old one. The previously returned pointer is now dangling.

Even within the same thread: the pointer is valid only until the next `set_last_error` call. There is no lifetime guarantee communicated to the C caller.

**Lines:** 56-57

**Root cause:** Returning a raw pointer to interior of a mutable TLS cell.

**Fix:** This is inherently unsafe with the current design. The `_v2` API is the correct one. Document `_v1` as "pointer valid only until next FFI call on same thread" or deprecate it. Alternatively, use a double-buffered TLS approach.

**Severity:** HIGH — UAF if caller doesn't immediately copy.

---

### `polydim_get_last_error_v2` L62-L86

**[BUG 4] LOW — Missing alignment check on `out_buf`**

Not a correctness bug per se (byte copy doesn't require alignment), but `out_required` is written via raw pointer without null-safety on the write path when `bytes_opt` is `Some`. Actually, L70 does check `!out_required.is_null()`. Fine.

**`polydim_get_last_error_v2` L62-L86: NO BUGS FOUND after 3-pass review** (beyond the inherent unsafety of raw pointer APIs, which is expected for FFI).

---

### `polydim_reset_engine_state` L88-L93

`[polydim_reset_engine_state] L88-L93: NO BUGS FOUND after 3-pass review`

Same poisoned-mutex issue as `set_last_error` (L91), but consistent with the pattern. Already reported above.

---

### `DisjointSet` L108-L127

`[DisjointSet] L108-L127: NO BUGS FOUND after 3-pass review`

Standard iterative DSU with path compression and union by rank. Correct.

---

### `polydim_rust_betti_dual_guard` L133-L175

**[BUG 5] MEDIUM — Betti₁ computation incorrect for multigraphs**

L157: `valid_edges` counts every non-self-loop edge, including **parallel edges** (duplicate (u,v) pairs). The Euler characteristic formula β₁ = E - V + β₀ requires the number of edges in the simplicial complex (unique edges), not the multigraph. If the input contains duplicate edges, `valid_edges` overcounts and β₁ is inflated.

Meanwhile, `dsu.union(u, v)` correctly handles duplicates (returns `false` for already-connected), but `valid_edges` increments regardless of whether the union was effective or the edge was a duplicate.

**Lines:** 155-156

**Root cause:** `valid_edges` counts all non-self-loop edges, not unique edges.

**Fix:**
```rust
// Option A: Only count edges that are new to the DSU
if u == v { continue; }
if dsu.union(u, v) {
    valid_edges += 1; // tree edge
} else {
    valid_edges += 1; // cycle edge — BUT only if not a duplicate
}
```
Actually, for β₁ = E - V + C, E must be the number of *distinct* edges in the 1-skeleton. The DSU doesn't track this. Need a HashSet:
```rust
use std::collections::HashSet;
let mut seen = HashSet::new();
for e in edges_slice {
    let (u, v) = (e.u as usize, e.v as usize);
    if u >= num_vertices as usize || v >= num_vertices as usize { return NativeStatus::InvalidArgument; }
    if u == v { continue; }
    let key = if u < v { (u, v) } else { (v, u) };
    if !seen.insert(key) { continue; }
    dsu.union(u, v);
    valid_edges += 1;
}
```

**Severity:** MEDIUM — silent topological miscomputation on duplicate edges.

---

**[BUG 6] LOW — `out_result` alignment not checked**

L136: `out_result` is checked for null but not for alignment. `PolydimBettiResult` has `align(8)`. Writing to a misaligned pointer is UB.

**Lines:** 136

**Fix:**
```rust
if (out_result as usize) % mem::align_of::<PolydimBettiResult>() != 0 {
    return NativeStatus::InvalidArgument;
}
```

---

### `polydim_rust_frechet_betti_filter` L181-L310

**[BUG 7] LETHAL — Random Projection Tree does NOT guarantee all neighbor pairs are found**

L199-L248: The RP-tree partitioning with `margin = thresh` is supposed to ensure that all pairs within distance `thresh` end up in the same leaf at least once. However:

1. **The pivot selection is deterministic** (`p1 = indices[0]`, `p2 = indices[indices.len()-1]`), not random. This means the "Random Projection Tree" is actually a deterministic projection tree with a single pass. For adversarial inputs, this can systematically miss neighbor pairs.

2. **Single tree, no repetition.** Standard RP-tree nearest-neighbor requires O(log n) independent trees to achieve high recall. With one deterministic tree, recall can be arbitrarily bad.

3. **The margin overlap `thresh`** helps but doesn't fix the fundamental issue: if two points are close in Euclidean distance but their projections onto the chosen direction differ by more than `thresh` (possible when the direction is nearly orthogonal to their displacement), they'll be split into different leaves and never compared.

**Lines:** 199-248

**Root cause:** Single deterministic projection tree cannot guarantee all ε-neighbors are found. The comment says "O(N log N)" but correctness requires O(N²) worst case or multiple trees.

**Impact:** The geometric graph is incomplete → β₀ is overestimated, β₁ is wrong, the giant component is smaller than it should be, honest nodes are misclassified as outliers, consensus fails on valid inputs.

**Fix:** Either:
- Use multiple (≥ log n) independent random projection trees with actual randomness
- Fall back to brute-force O(N²) for N ≤ some threshold (the original code likely did this)
- Use a proper spatial data structure (ball tree, cover tree)

**Severity:** LETHAL — consensus filter silently rejects valid swarm members.

---

**[BUG 8] HIGH — `projs.sort_unstable_by` panics on NaN despite earlier finite check**

L228: The finite check at L195 validates `candidates`, but `v[k]` is computed from differences and normalized. If `norm_sq` is extremely small (but ≥ 1e-16), `inv_norm` can be very large, and the dot product `p` can overflow to `Inf`. The `partial_cmp(...).unwrap_or(Ordering::Equal)` handles NaN but treats NaN as equal, which corrupts the sort's total order invariant. `sort_unstable_by` requires a total order; violating this is UB in practice (can cause out-of-bounds access in the sort implementation).

**Lines:** 228

**Root cause:** `unwrap_or(Ordering::Equal)` does not establish a total order when NaN values exist.

**Fix:**
```rust
projs.sort_unstable_by(|a, b| a.1.total_cmp(&b.1));
```
(`f64::total_cmp` is stable since Rust 1.62 and provides IEEE 754 total ordering.)

**Severity:** HIGH — potential panic or memory corruption in sort.

---

**[BUG 9] MEDIUM — Weiszfeld median with 0.5 damping converges to wrong point**

L270-L283: The update `median[k] = 0.5*median[k] + 0.5*upd` is a damped Weiszfeld iteration. While damping aids convergence, the fixed 0.5 factor means the iteration converges to a point that is NOT the geometric median — it converges to the midpoint between the initial discrete medoid and the Weiszfeld fixed point. The geometric median minimizes Σ‖x - pᵢ‖, but the damped iteration minimizes a different objective.

**Lines:** 278-279

**Root cause:** Constant damping factor doesn't decrease; the fixed point of `x ← 0.5x + 0.5*W(x)` is not the fixed point of `x ← W(x)`.

**Fix:** Use adaptive damping that decreases toward 0 (i.e., weight → 1.0 as iterations progress), or use Vardi-Zhang's modified Weiszfeld which handles the non-smooth case:
```rust
let alpha = 1.0; // or use line search
median[k] = (1.0 - alpha) * median[k] + alpha * (next[k] / wsum);
```
With `alpha = 1.0`, this is standard Weiszfeld. If convergence issues arise, use backtracking.

**Severity:** MEDIUM — consensus vector is biased toward the initial medoid.

---

**[BUG 10] MEDIUM — `dist_threshold == 0.0` silently replaced with 1.0**

L190: `let thresh = if dist_threshold > 0.0 { dist_threshold } else { 1.0 };`

A threshold of exactly 0.0 is valid (passed the `>= 0.0` check at L188) but is silently replaced with 1.0. This completely changes the geometric graph. A caller passing `dist_threshold = 0.0` expects no edges (only self-connections), but gets edges within distance 1.0.

**Lines:** 190

**Fix:**
```rust
if dist_threshold == 0.0 {
    // No edges possible; each node is its own component
    // Handle specially or return early
}
let thresh = dist_threshold; // already validated > 0 or == 0
```
Or change the validation:
```rust
if dist_threshold <= 0.0 || dist_threshold.is_nan() { return NativeStatus::InvalidArgument; }
```

**Severity:** MEDIUM — silent semantic change for edge-case input.

---

**[BUG 11] LOW — `n.checked_mul(d)` overflow check but `honest` loop is O(|honest|² · d)**

L261-L268: The discrete medoid search is O(|honest|² · d). For large swarms (e.g., n=10000, d=10000), this is 10¹² FLOPs. No timeout, no early termination. This is a DoS vector.

**Lines:** 261-268

**Severity:** LOW (performance, not correctness) — but can hang the process.

---

**[BUG 12] MEDIUM — BFT quorum check uses wrong formula**

L299: `(active as u64) * 3 >= (2 * n as u64)` checks `3a ≥ 2n`, i.e., `a ≥ 2n/3`. The comment says "3a > 2n" (strict), but the code uses `>=` (non-strict). For `n = 3`, `a = 2`: `3*2 = 6 ≥ 2*3 = 6` → passes. But BFT with `n = 3, f = 1` requires `a > 2n/3 = 2`, i.e., `a ≥ 3`. With `a = 2`, only 2 of 3 nodes agree, which is insufficient for BFT (tolerates f = 0 only).

The comment C4 says "3a > 2n (antes >=, que para n=3f admite 2f)" — but the code still uses `>=`, not `>`.

**Lines:** 299

**Root cause:** Comment says strict inequality was the fix, but code implements non-strict.

**Fix:**
```rust
let quorum_ok = (active as u64) * 3 > (2 * n as u64);
```

**Severity:** MEDIUM — BFT quorum is weaker than intended; accepts f Byzantine faults when it shouldn't.

---

### `polydim_rust_quantum_synthesize_discrete` L319-L381

**[BUG 13] HIGH — Solovay-Kitaev "primitive" does not approximate the residual rotation**

L354-L363: The residual approximation pushes `[H, T, H, T†]` (or its inverse) repeated `reps` times. The unitary `H·T·H·T†` is a fixed rotation; repeating it `reps` times gives `(H·T·H·T†)^reps`, which rotates by `reps × α` for some fixed angle `α`. But `α` is NOT `residual / reps` — it's a fixed angle determined by the Clifford+T algebra (~π/4 related). The number of repetitions `reps = ceil(|residual| / (π/16))` has no mathematical relationship to the actual rotation angle produced.

This is not Solovay-Kitaev; it's an ad-hoc sequence that does not converge to the target rotation. The certified error bound is meaningless.

**Lines:** 354-363

**Root cause:** Solovay-Kitaev requires recursive group commutator decomposition, not repetition of a fixed sequence.

**Fix:** Either implement actual Solovay-Kitaev (recursive, O(log^c(1/ε)) depth) or use the Ross-Selinger / gridsynth algorithm. If neither is feasible, document that this function only provides Clifford