# ADVERSARIAL AUDIT — kernel_rust_v810.rs

**Auditor posture:** Hostile. Assume every comment is a lie until proven otherwise. Assume every "fix" introduced a new bug. Assume the author is a competent adversary who knows the standard attack surface and has hidden the real defects in the *interaction* between functions.

**Global preconditions established before per-function analysis:**

- `catch_unwind` does **not** catch `abort()` (double-panic, alloc failure, `panic = "abort"` profile). Any `Vec` allocation inside `ffi_guard!` can abort the process. This is a **process-wide DoS** vector, not a recoverable panic. The macro's comment "el latch ya NO es permanente" is only true for *unwinding* panics.
- `LAST_ERROR: Mutex<Option<CString>>` is written on every panic path but **never read by any exported function**. `polydim_last_error_v1` and `polydim_get_last_error_v2` read `LAST_ERR_TLS`, not `LAST_ERROR`. The global mutex is dead weight that still serializes all panic paths across 64 threads. This is a **false-sharing / contention** defect masquerading as a fix (G10).
- `INSTANCE_STATE` is written with `SeqCst` but **never read** by any function in this module. Dead store on every call. Not a correctness bug, but it is a lie in the header comment.

---

## 1. `set_last_error`

**FUNCTION NAME:** `set_last_error`

**VERDICT:** [VULNERABLE]

**REASONING:**
- `CString::new(msg)` returns `Err` if `msg` contains an interior NUL. The fallback `CString::new("error")` is fine, but the *original* message is silently discarded. A panic message containing `\0` (possible via `panic!("{}", user_string)`) loses forensic data. Minor.
- **Real defect:** `LAST_ERR_TLS.with(|tls| { *tls.borrow_mut() = Some(c.clone()); })`. If `set_last_error` is called *while* `LAST_ERR_TLS` is already mutably borrowed (re-entrant panic during TLS access, or a panic inside a `with` closure that itself calls `set_last_error`), `borrow_mut()` panics. That panic occurs **inside** the `catch_unwind` handler of `ffi_guard!`, i.e. **during unwinding**. A panic during unwinding = `abort()`. This is a **process-kill vector** reachable from any FFI caller that can trigger a panic whose message formatting re-enters TLS.
- `LAST_ERROR.lock()` uses `if let Ok(...)`. If the mutex is poisoned (a previous panic occurred while holding it — impossible here since the critical section is a single store, but still), the error is silently dropped. Acceptable but undocumented.

**PROPOSED EXACT PATCH:**
```rust
fn set_last_error(msg: &str) {
    // Sanitize interior NULs instead of discarding the message.
    let sanitized: String = msg.chars().map(|c| if c == '\0' { '?' } else { c }).collect();
    let c = CString::new(sanitized).unwrap_or_else(|_| CString::new("error").unwrap());
    // try_borrow_mut: never panic during unwinding.
    let _ = LAST_ERR_TLS.try_with(|tls| {
        if let Ok(mut slot) = tls.try_borrow_mut() { *slot = Some(c.clone()); }
    });
    if let Ok(mut guard) = LAST_ERROR.lock() { *guard = Some(c); }
}
```

---

## 2. `polydim_last_error_v1`

**FUNCTION NAME:** `polydim_last_error_v1`

**VERDICT:** [VULNERABLE]

**REASONING:**
- Returns `c.as_ptr()` where `c: &CString` is borrowed from the TLS `RefCell`. The pointer is valid **only until the next `set_last_error` on the same thread**, which drops the old `CString` and frees the buffer. The C caller has no way to know this. Classic **use-after-free** across the FFI boundary if the caller stores the pointer and calls any other POLYDIM function that panics.
- Worse: `LAST_ERR_TLS.with(...)` returns the pointer, then the closure ends, releasing the `RefCell` borrow. The `CString` itself lives in the TLS slot, so the pointer remains valid *until mutation* — but the API contract is undocumented and the header comment (G10) explicitly claims the global is the source of truth. It is not.
- Thread affinity: if the caller invokes this from a different thread than the one that panicked, it returns `NULL`. The header comment for G10 says "el caller puede estar en otro hilo" — yet this function reads TLS. **The stated fix is not implemented in this function.**

**PROPOSED EXACT PATCH:**
```rust
#[no_mangle]
pub extern "C" fn polydim_last_error_v1() -> *const c_char {
    // Return a pointer into the GLOBAL, not TLS, so cross-thread callers work.
    // Lifetime: valid until next set_last_error. Document this.
    match LAST_ERROR.lock() {
        Ok(guard) => match &*guard {
            Some(c) => c.as_ptr(),
            None => std::ptr::null(),
        },
        Err(_) => std::ptr::null(),
    }
}
```
(Note: this still has a lifetime hazard — the returned pointer is invalidated by the next panic. The only correct fix is a caller-provided buffer, which is what `_v2` does. `_v1` should be deprecated.)

---

## 3. `polydim_get_last_error_v2`

**FUNCTION NAME:** `polydim_get_last_error_v2`

**VERDICT:** [VULNERABLE]

**REASONING:**
- Reads from `LAST_ERR_TLS`, not `LAST_ERROR`. Same cross-thread defect as `_v1`. The G10 comment claims the global exists precisely so cross-thread callers work; this function ignores it.
- `out_cap < req` returns `-2` **after** writing `*out_required = req`. Correct. But if `out_buf` is non-null and `out_cap == 0`, we return `-2` without writing anything — fine.
- **Buffer overrun check is correct** (`out_cap < req` before `copy_nonoverlapping`). No overflow.
- **Missing:** no check that `out_buf` is writable for `req` bytes. That's the caller's contract; acceptable.
- **Real defect:** the `None` branch writes `*out_buf = 0` when `out_cap > 0`. If `out_buf` is a `*mut c_char` pointing to a 1-byte buffer, fine. But if `out_buf` is non-null and `out_cap == 0`, we skip — correct. No bug here, but the asymmetry (write NUL on empty, return `-2` on too-small) is confusing.

**PROPOSED EXACT PATCH:**
```rust
#[no_mangle]
pub extern "C" fn polydim_get_last_error_v2(out_buf: *mut c_char, out_cap: usize, out_required: *mut usize) -> i32 {
    let bytes_opt = match LAST_ERROR.lock() {
        Ok(guard) => guard.as_ref().map(|c| c.to_bytes_with_nul().to_vec()),
        Err(_) => None,
    };
    // ... rest unchanged
}
```

---

## 4. `polydim_reset_engine_state`

**FUNCTION NAME:** `polydim_reset_engine_state`

**VERDICT:** [CERTIFIED] (with caveat)

**REASONING:**
- Clears both TLS and global. `SeqCst` store on `INSTANCE_STATE` is overkill but correct.
- **Caveat:** does not reset `INSTANCE_STATE` on *other* threads' TLS. If thread A panicked and thread B calls reset, thread A's `polydim_last_error_v1` still returns the stale message. This is a semantic inconsistency, not a memory-safety bug. Documented behavior is ambiguous.

**PROPOSED EXACT PATCH:** None required for memory safety. Document that reset is per-thread for TLS.

---

## 5. `DisjointSet::new`

**FUNCTION NAME:** `DisjointSet::new`

**VERDICT:** [VULNERABLE]

**REASONING:**
- `(0..n).collect()` and `vec![0; n]` allocate `n` usizes each. For `n = num_vertices as usize` where `num_vertices: u32`, max `n = 2^32 - 1`. On 64-bit, `parent` alone is `2^32 * 8 = 32 GiB`. **Unbounded allocation from an FFI-supplied `u32`.** No `try_reserve`. A malicious caller passing `num_vertices = 0xFFFFFFFF` triggers an allocation failure → `abort()` (not catchable by `catch_unwind`). **Process-kill DoS.**
- `count: n as u64` — fine.

**PROPOSED EXACT PATCH:**
```rust
impl DisjointSet {
    pub fn try_new(n: usize) -> Option<Self> {
        let mut parent = Vec::new();
        parent.try_reserve_exact(n).ok()?;
        parent.extend(0..n);
        let mut rank = Vec::new();
        rank.try_reserve_exact(n).ok()?;
        rank.resize(n, 0);
        Some(DisjointSet { parent, rank, count: n as u64 })
    }
}
```
And in callers, map `None` → `NativeStatus::CapacityExceeded`.

---

## 6. `DisjointSet::find`

**FUNCTION NAME:** `DisjointSet::find`

**VERDICT:** [CERTIFIED]

**REASONING:**
- Path compression is correct: two-pass, first finds root, then rewrites. No recursion (no stack overflow). `#[inline]` is fine.
- **Invariant:** `i < parent.len()` must hold. Callers must guarantee this. In `betti_dual_guard`, `u, v < num_vertices` is checked before `union`. In `frechet_betti_filter`, indices are `0..n`. Safe.
- No UB. No aliasing issue (single `&mut self`).

---

## 7. `DisjointSet::union`

**FUNCTION NAME:** `DisjointSet::union`

**VERDICT:** [CERTIFIED]

**REASONING:**
- Union by rank is correct. `count -= 1` only on successful merge. No underflow because `count` starts at `n` and decrements at most `n-1` times.
- `find` is called twice; both borrow `&mut self` sequentially — no aliasing.

---

## 8. `polydim_rust_betti_dual_guard`

**FUNCTION NAME:** `polydim_rust_betti_dual_guard`

**VERDICT:** [VULNERABLE]

**REASONING:**

**(a) Alignment check is wrong for the NULL case.**
```rust
if (edges_ptr as usize) % mem::align_of::<PolydimEdge>() != 0 { return NativeStatus::InvalidArgument; }
```
When `edges_ptr` is NULL and `num_edges == 0`, `0 % 4 == 0`, so it passes. OK. But when `edges_ptr` is NULL and `num_edges > 0`, the earlier check returns `NullPointer`. OK. **However:** the alignment check runs *after* the NULL check, so a NULL pointer with `num_edges == 0` is fine. No bug here, but the ordering is fragile.

**(b) `num_vertices == 0` returns `InvalidArgument`.** But `DisjointSet::new(0)` would be valid (empty). The rejection is a policy choice, not a bug.

**(c) `betti1 = valid_edges - num_vertices + betti0`.** For a graph with `V` vertices, `E` edges, `C` components: `β₁ = E - V + C`. Correct. But `valid_edges` counts **only non-self-loop edges** (`if u == v { continue; }`). Self-loops contribute to `β₁` in standard homology (each self-loop adds 1 to `β₁`). **The function silently drops self-loops from the cycle count.** This is a **mathematical defect**: a graph with one vertex and one self-loop has `β₁ = 1`, but this function returns `β₁ = 0 - 1 + 1 = 0`. The header claims "Guardián Topológico" — it is not computing Betti numbers correctly.

**(d) `num_edges` is stored in the output as the *input* `num_edges`, not `valid_edges`.** Inconsistent with `cycles_betti1` which uses `valid_edges`. A caller reading `num_edges` and `cycles_betti1` will compute the wrong Euler characteristic.

**(e) `is_critically_healthy` is set to 1 iff `betti0 == 1`.** But `betti0 == 1` with `num_vertices > 0` and disconnected edges is impossible if all edges are valid. Actually `betti0 == 1` means connected. Fine. But `is_optimally_healthy` requires `betti1 <= max_tau_betti1` — if `max_tau_betti1` is negative (caller-supplied `i64`), this is always false. No validation. Minor.

**(f) `ffi_guard!` wraps the body, but `DisjointSet::new` can abort on OOM.** See §5. The guard does not protect against `abort()`.

**PROPOSED EXACT PATCH:**
```rust
// Count self-loops separately; they contribute to β₁.
let mut self_loops: u64 = 0;
for e in edges_slice {
    let (u, v) = (e.u as usize, e.v as usize);
    if u >= num_vertices as usize || v >= num_vertices as usize { return NativeStatus::InvalidArgument; }
    if u == v { self_loops += 1; continue; }
    dsu.union(u, v);
    valid_edges += 1;
}
let betti0 = dsu.count as u32;
let betti1 = (valid_edges + self_loops) as i64 - num_vertices as i64 + betti0 as i64;
// ...
*out_result = PolydimBettiResult {
    // ...
    num_edges: (valid_edges + self_loops) as u32,  // report what was actually counted
    // ...
};
```
And use `DisjointSet::try_new` with `CapacityExceeded` on failure.

---

## 9. `polydim_rust_frechet_betti_filter`

**FUNCTION NAME:** `polydim_rust_frechet_betti_filter`

**VERDICT:** [VULNERABLE] — multiple independent defects

**REASONING:**

**(a) O(n²·d) graph construction with no cap.** `n = num_candidates as usize` up to `2^32 - 1`. The double loop `for i in 0..n { for j in (i+1)..n { ... } }` is `O(n²)`. For `n = 10^5`, that's `5·10^9` distance computations. **Unbounded CPU DoS.** No `max_candidates` parameter. The `checked_mul` on `n*d` protects against integer overflow of the slice length, but not against the quadratic blowup.

**(b) `DisjointSet::new(n)` can abort on OOM.** Same as §5.

**(c) `sizes` allocation:** `vec![0usize; n]` — another `O(n)` allocation, same abort risk.

**(d) Median-of-medians is not used.** The "discrete geometric median" is computed by brute force: `O(|honest|² · d)`. For `|honest| = n`, this is another `O(n²·d)`. Combined with (a), the function is `O(n²·d)` twice. **Asymptotic bottleneck.**

**(e) Weiszfeld iteration:**
```rust
if dsq < 1e-16 { continue; }
```
This skips the candidate at the current median. But if **all** candidates coincide with the median (e.g., all points identical), `wsum == 0`, and the `if wsum > 0.0` guard skips the update. The loop runs 10 times doing nothing. Fine, but wasteful. More importantly: **the `continue` skips the point entirely, which biases the weighted average.** The correct Weiszfeld update uses `w = 1/max(‖x_j - m‖, ε)` with a small ε, not a hard skip. The hard skip means the median is not a fixed point of the iteration when a candidate coincides with it. **Numerical defect.**

**(f) Damping `median[k] = 0.5*median[k] + 0.5*upd`.** This is a fixed 0.5 damping factor. It slows convergence but does not break correctness. However, the convergence criterion `max_delta < 1e-12` is checked on the *damped* update, not the raw Weiszfeld step. With damping 0.5, `max_delta` is halved, so the criterion triggers at `2e-12` raw. Minor.

**(g) `refined_resid` is computed as the mean of Euclidean distances from the median to each honest candidate.** This is the *mean* absolute deviation, not the Fréchet variance (which is the *sum* of squared distances, or the sum of distances for the geometric median objective). The header calls it "residual" — ambiguous. If the caller expects the Fréchet *variance* (sum of squared distances), this is wrong by a factor and by the square. **Semantic defect.**

**(h) Normalization:**
```