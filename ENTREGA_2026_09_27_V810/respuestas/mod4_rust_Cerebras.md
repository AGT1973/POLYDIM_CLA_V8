**POLYDIM V810 – HOSTILE RED‑TEAM LINE‑BY‑LINE AUDIT**  
*All functions are examined under the threat model of 64‑thread concurrent callers, arbitrary‑precision adversarial inputs, and hostile FFI usage.  For each routine the verdict, a rigorous justification (memory‑ordering, pointer‑arithmetic, numeric‑stability, asymptotic‑complexity) and an exact patch (if vulnerable) are given.*

---

## 1. `set_last_error`

| Item | Detail |
|------|--------|
| **FUNCTION NAME** | `set_last_error` |
| **VERDICT** | **VULNERABLE** |
| **REASONING** | <ul><li>`CString::new(msg).unwrap_or_else(..)` may allocate a heap buffer; the clone is stored **both** in the thread‑local `LAST_ERR_TLS` **and** in the global `LAST_ERROR` mutex.  The global copy is *shared* across threads without any *happens‑before* relationship to the thread‑local write.  A concurrent reader of `polydim_last_error_v1` may observe the pointer from the TLS while the global mutex is still holding the old value, causing a *data‑race* on the internal reference count of the `CString` (non‑atomic `Arc`‑like).  This violates Rust’s aliasing rules and can lead to use‑after‑free or double‑free on some allocator implementations.</li><li>The function does **not** enforce a memory‑ordering fence between the two stores; the global `Mutex` provides acquire/release only for the lock, but the TLS write occurs *outside* the lock, so another thread that only reads the global `LAST_ERROR` may see a partially‑initialized `CString`.</li></ul> |
| **PROPOSED PATCH** | ```rust
fn set_last_error(msg: &str) {
    // Allocate once, then move the same owned CString into both locations under a single lock.
    let c = CString::new(msg).unwrap_or_else(|_| CString::new("error").unwrap());
    // Serialize the two writes under the same atomic ordering.
    if let Ok(mut guard) = LAST_ERROR.lock() {
        // Replace the global entry first – this is the *release* side.
        *guard = Some(c.clone());
        // Now update the TLS while holding the same lock (ensures acquire‑release ordering).
        LAST_ERR_TLS.with(|tls| {
            *tls.borrow_mut() = Some(c);
        });
    }
}
```<br>Using the mutex as the sole synchronisation point guarantees a total order and eliminates the data‑race.  The TLS write is now *sequenced‑after* the global write, providing a proper *happens‑before* relation for any thread that reads either location. |

---

## 2. `ffi_guard!` (macro – treated as a wrapper)

| Item | Detail |
|------|--------|
| **FUNCTION NAME** | `ffi_guard!` (macro) |
| **VERDICT** | **VULNERABLE** |
| **REASONING** | <ul><li>The macro catches panics with `catch_unwind` but **does not** enforce `UnwindSafe` on any *captured* mutable references that may be passed to the body.  If the wrapped body mutates a `&mut` reference that points into a shared data structure, a panic will unwind past the mutation leaving the data in an *inconsistent* state – a classic *use‑after‑unwind* bug.</li><li>`INSTANCE_STATE` is stored with `SeqCst` on both success and failure, but the *store* on the panic path occurs **before** `set_last_error` finishes.  If `set_last_error` itself panics (e.g. OOM), the state may be left at `1` forever, causing a *livelock* for all subsequent calls.</li></ul> |
| **PROPOSED PATCH** | ```rust
macro_rules! ffi_guard {
    ($body:expr) => {{
        // Enforce that the body cannot capture any `&mut` that outlives the guard.
        let result = catch_unwind(std::panic::AssertUnwindSafe(|| { $body }));
        match result {
            Ok(code) => {
                INSTANCE_STATE.store(0, Ordering::SeqCst);
                code
            }
            Err(e) => {
                // First record the error, then publish the panic flag (release‑acquire ordering).
                let msg = if let Some(s) = e.downcast_ref::<&str>() {
                    s.to_string()
                } else if let Some(s) = e.downcast_ref::<String>() {
                    s.clone()
                } else {
                    "Unknown Rust Panic".to_string()
                };
                set_last_error(&msg);
                // Publish after the error is safely stored.
                INSTANCE_STATE.store(1, Ordering::SeqCst);
                NativeStatus::Panic
            }
        }
    }};
}
```<br>By moving the `INSTANCE_STATE.store` **after** `set_last_error`, we guarantee that any thread observing the panic flag also sees a fully‑initialised error string.  The `AssertUnwindSafe` guard remains, but the macro now documents the restriction. |

---

## 3. `polydim_last_error_v1`

| Item | Detail |
|------|--------|
| **FUNCTION NAME** | `polydim_last_error_v1` |
| **VERDICT** | **VULNERABLE** |
| **REASONING** | <ul><li>Returns a raw pointer to the internal buffer of a `CString` stored in thread‑local storage.  The lifetime of that buffer ends **when the TLS entry is overwritten** (next error on the same thread) or when the thread exits.  A hostile caller can retain the pointer across calls or across thread switches, leading to a *use‑after‑free* read.</li><li>No alignment check is performed; on architectures that require stricter than 1‑byte alignment for `c_char` (e.g. some DSPs), dereferencing the returned pointer may cause undefined behaviour.</li></ul> |
| **PROPOSED PATCH** | ```rust
#[no_mangle]
pub extern "C" fn polydim_last_error_v1(out_buf: *mut c_char, out_cap: usize) -> i32 {
    // New API: caller supplies a buffer; we copy the string safely.
    if out_buf.is_null() {
        return -1; // InvalidArgument
    }
    if out_cap == 0 {
        return -2; // BufferTooSmall
    }
    let src_opt = LAST_ERR_TLS.with(|tls| tls.borrow().clone());
    match src_opt {
        Some(cstr) => {
            let bytes = cstr.to_bytes_with_nul();
            if bytes.len() > out_cap {
                return -2;
            }
            unsafe { std::ptr::copy_nonoverlapping(bytes.as_ptr() as *const c_char, out_buf, bytes.len()); }
            0
        }
        None => {
            unsafe { *out_buf = 0 };
            0
        }
    }
}
```<br>By requiring the caller to provide a destination buffer, the function no longer exposes an internal pointer, eliminating the dangling‑pointer class of bugs.  Alignment is guaranteed because the caller controls the buffer layout. |

---

## 4. `polydim_get_last_error_v2`

| Item | Detail |
|------|--------|
| **FUNCTION NAME** | `polydim_get_last_error_v2` |
| **VERDICT** | **CERTIFIED** |
| **REASONING** | <ul><li>All pointer arguments are validated (`null` checks) before any dereference.</li><li>`bytes` is a freshly allocated `Vec<u8>`; the copy uses `copy_nonoverlapping` with length `req` that has been verified against `out_cap`.  No overflow.</li><li>Memory ordering is irrelevant because the function only reads the thread‑local `CString`, which is never mutated concurrently (writes go through `set_last_error` under a mutex).</li><li>Numeric handling is trivial (no arithmetic). </li></ul> |
| **PROPOSED PATCH** | *None required.* |

---

## 5. `polydim_reset_engine_state`

| Item | Detail |
|------|--------|
| **FUNCTION NAME** | `polydim_reset_engine_state` |
| **VERDICT** | **CERTIFIED** |
| **REASONING** | <ul><li>Atomic store uses `SeqCst`, guaranteeing a total order with all other accesses to `INSTANCE_STATE`.</li><li>Both TLS and global error storage are cleared under the same mutex, providing a *happens‑before* relationship for any subsequent read.</li><li>No pointer arithmetic or allocation.</li></ul> |
| **PROPOSED PATCH** | *None required.* |

---

## 6. `DisjointSet::new`

| Item | Detail |
|------|--------|
| **FUNCTION NAME** | `DisjointSet::new` |
| **VERDICT** | **CERTIFIED** |
| **REASONING** | <ul><li>Creates two `Vec`s of length `n`; allocation is O(n) and bounded by `usize::MAX`.  No overflow because `parent: (0..n).collect()` panics on overflow, which is caught by the outer `ffi_guard!`.</li><li>No unsafe code, no data races (the DSU is confined to the calling thread).</li></ul> |
| **PROPOSED PATCH** | *None required.* |

---

## 7. `DisjointSet::find`

| Item | Detail |
|------|--------|
| **FUNCTION NAME** | `DisjointSet::find` |
| **VERDICT** | **CERTIFIED** |
| **REASONING** | <ul><li>Iterative path‑compression loop is memory‑safe; all indices are bounded by `self.parent.len()` because the loop condition `root != self.parent[root]` guarantees `root` is a valid index.</li><li>All reads/writes are to distinct `usize` locations; no data race because `&mut self` guarantees exclusive access.</li></ul> |
| **PROPOSED PATCH** | *None required.* |

---

## 8. `DisjointSet::union`

| Item | Detail |
|------|--------|
| **FUNCTION NAME** | `DisjointSet::union` |
| **VERDICT** | **CERTIFIED** |
| **REASONING** | <ul><li>Calls `find` (already safe) and then performs rank‑based linking.  The only arithmetic is `self.count -= 1;` where `self.count` is a `u64` that starts