#![allow(non_camel_case_types)]
use std::panic::catch_unwind;

// ============================================================================
// POLYDIM V801 - LATENT OS (GHOST PROTOCOL)
// SOTA RUST GUARD - ASYMPTOTIC D=10^7, K<=512
//
// CHANGELOG vs V800:
//   [FIX-09] Removed PolydimPmtpHeaderV800: declared but never referenced
//            anywhere in the V800 dossier (confirmed by grep). Same
//            rationale as the C++ side's [FIX-01] -- dead IPC scaffolding
//            implies a guarantee this codebase does not provide.
//   [FIX-10] polydim_higham_bound_v801 now validates d > 0 and is wrapped in
//            catch_unwind like its two siblings. V800's version had neither:
//            d <= 0 silently produced NaN/-inf with no error signal, and it
//            was the only one of the three exported functions without a
//            panic firewall -- an inconsistency that becomes a real crash
//            risk the moment anyone adds a fallible operation to it later.
//   [NOTE]   polydim_validate_tensor_v801 and polydim_weiszfeld_swap_v801 are
//            unchanged in logic from V800 (both were already correct in
//            isolation: checked_mul avoids overflow, null/alignment checks
//            are sound). The V800 defect was NEVER wiring these into the
//            Python orchestrator's production call path -- that is fixed in
//            polydim_v801_monolito.py, not here. See CHANGELOG_V801.md.
// ============================================================================

#[no_mangle]
pub extern "C" fn polydim_validate_tensor_v801(
    d: i64,
    k: i64,
    bytes_len: usize,
) -> i32 {
    let result = catch_unwind(|| {
        if d <= 0 || k <= 0 {
            return -2; // Invalid dimensions
        }

        let expected_elements = (d as usize).checked_mul(k as usize);
        match expected_elements {
            Some(elements) => {
                let expected_bytes = elements.checked_mul(8); // float64
                match expected_bytes {
                    Some(eb) if eb == bytes_len => 0, // OK
                    _ => -3, // Mismatch size
                }
            },
            None => -1, // Integer Overflow
        }
    });

    result.unwrap_or(-999) // Anti-panic FFI firewall
}

// [FIX-10]
#[no_mangle]
pub extern "C" fn polydim_higham_bound_v801(d: i64) -> f64 {
    let result = catch_unwind(|| {
        if d <= 0 {
            return f64::NAN; // was: silently NaN/-inf with no consistent signal
        }
        let eps = f64::EPSILON / 2.0;
        let log_d = (d as f64).log2().ceil();
        50.0 * log_d * eps
    });
    result.unwrap_or(f64::NAN)
}

// SOTA FIX (carried from V800 P0-03): Strict Pointer Validation & Alignment Safeguard
#[no_mangle]
pub extern "C" fn polydim_weiszfeld_swap_v801(
    ptr_a: *mut *mut f64,
    ptr_b: *mut *mut f64,
) -> i32 {
    let result = catch_unwind(|| {
        if ptr_a.is_null() || ptr_b.is_null() {
            return -1; // Null pointer rejected
        }

        unsafe {
            let inner_a = *ptr_a;
            let inner_b = *ptr_b;

            if inner_a.is_null() || inner_b.is_null() {
                return -2; // Inner null pointer rejected
            }

            // Check 8-byte (double) alignment
            if (inner_a as usize) % 8 != 0 || (inner_b as usize) % 8 != 0 {
                return -3; // Misaligned pointer rejected
            }

            std::ptr::swap(ptr_a, ptr_b);
        }
        0
    });
    result.unwrap_or(-999)
}
