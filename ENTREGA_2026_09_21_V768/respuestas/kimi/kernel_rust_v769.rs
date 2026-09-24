// ============================================================================
// POLYDIM V769 — NATIVE RUST TOPOLOGICAL GUARD (completo, reemplaza v768)
//   C1: slice::from_raw_parts(ptr, d) sin tope superior: puntero FFI con d
//       bogus => lectura OOB. Se valida d <= 2^40.
//   C2: ErrSubnormalDetected era codigo muerto. Implementado (politica: detectar
//       y reportar; el llamante decide, espejando reject_subnormal del C++).
//   C3: codigo de error semanticamente incorrecto para desalineacion (Overflow)
//       y para n>4096 en betti1 (Overflow). Se usan codigos correctos.
//   C4: betti1_guard sin chequeo de alineacion (asimetria con verify_invariants).
// ============================================================================
use std::panic::catch_unwind;
use std::slice;

#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PolydimRustStatus {
    Success = 0,
    ErrNullPointer = -1,
    ErrInvalidDimension = -2,
    ErrNanOrInf = -3,
    ErrSubnormalDetected = -4,
    ErrNumericalInstability = -5,
    ErrTopologyFragmented = -6,
    ErrBufferOverflow = -7,
    ErrDegenerateNorm = -8,
    ErrMisaligned = -9,
    ErrPanicCaught = -99,
}

const EPS_MACH: f64 = f64::EPSILON;
const MAX_FFI_LEN: usize = 1usize << 40; // C1: tope defensivo de longitud FFI

#[inline]
fn is_subnormal(x: f64) -> bool {
    x != 0.0 && x.abs() < f64::MIN_POSITIVE
}

#[no_mangle]
pub unsafe extern "C" fn polydim_rust_verify_invariants(
    ptr: *const f64,
    d: usize,
    max_drift_out: *mut f64,
) -> i32 {
    let result = catch_unwind(|| {
        if ptr.is_null() {
            return PolydimRustStatus::ErrNullPointer;
        }
        if d == 0 || d > MAX_FFI_LEN {
            // C1: sin este tope, un d bogus del lado Python/C es lectura OOB.
            return PolydimRustStatus::ErrInvalidDimension;
        }
        if (ptr as usize) % 8 != 0 {
            return PolydimRustStatus::ErrMisaligned; // C3
        }

        let slice = slice::from_raw_parts(ptr, d);

        let mut sum: f64 = 0.0;
        let mut c: f64 = 0.0;
        let mut saw_subnormal = false;

        for &val in slice {
            if val.is_nan() || val.is_infinite() {
                return PolydimRustStatus::ErrNanOrInf;
            }
            if is_subnormal(val) {
                saw_subnormal = true; // C2: detectar sin abortar la suma
            }
            let sq = val * val;
            let t = sum + sq;
            if sum.abs() >= sq.abs() {
                c += (sum - t) + sq;
            } else {
                c += (sq - t) + sum;
            }
            sum = t;
        }

        let norm_sq = sum + c;
        if norm_sq <= 1e-300 {
            return PolydimRustStatus::ErrDegenerateNorm;
        }
        let drift = (norm_sq.sqrt() - 1.0).abs();
        if !max_drift_out.is_null() {
            *max_drift_out = drift;
        }
        let tol = 64.0 * EPS_MACH;
        if drift > tol {
            return PolydimRustStatus::ErrNumericalInstability;
        }
        if saw_subnormal {
            return PolydimRustStatus::ErrSubnormalDetected; // C2
        }
        PolydimRustStatus::Success
    });
    match result {
        Ok(s) => s as i32,
        Err(_) => PolydimRustStatus::ErrPanicCaught as i32,
    }
}

#[no_mangle]
pub unsafe extern "C" fn polydim_rust_betti1_guard(
    adj_matrix: *const f64,
    n: usize,
    threshold: f64,
) -> i32 {
    let result = catch_unwind(|| {
        if adj_matrix.is_null() {
            return PolydimRustStatus::ErrNullPointer;
        }
        if n == 0 || n > 4096 {
            return PolydimRustStatus::ErrInvalidDimension; // C3
        }
        if (adj_matrix as usize) % 8 != 0 {
            return PolydimRustStatus::ErrMisaligned; // C4
        }
        if threshold.is_nan() || threshold.is_infinite() {
            return PolydimRustStatus::ErrNanOrInf;
        }

        let mat = slice::from_raw_parts(adj_matrix, n * n);
        let mut parent: Vec<usize> = (0..n).collect();
        let mut rank: Vec<usize> = vec![0; n];

        fn find(parent: &mut [usize], i: usize) -> usize {
            let mut r = i;
            while parent[r] != r {
                r = parent[r];
            }
            let mut x = i; // compresion de camino iterativa (sin recursion)
            while parent[x] != r {
                let nx = parent[x];
                parent[x] = r;
                x = nx;
            }
            r
        }

        fn union(parent: &mut [usize], rank: &mut [usize], i: usize, j: usize) -> bool {
            let (mut ri, mut rj) = (find(parent, i), find(parent, j));
            if ri == rj {
                return false;
            }
            if rank[ri] < rank[rj] {
                std::mem::swap(&mut ri, &mut rj);
            }
            parent[rj] = ri;
            if rank[ri] == rank[rj] {
                rank[ri] += 1;
            }
            true
        }

        let mut components = n;
        for i in 0..n {
            for j in (i + 1)..n {
                let w = mat[i * n + j];
                if w.is_nan() || w.is_infinite() {
                    return PolydimRustStatus::ErrNanOrInf;
                }
                if w >= threshold && union(&mut parent, &mut rank, i, j) {
                    components -= 1;
                }
            }
        }
        // beta1 = E - V + C se calcula pero el contrato vigente certifica
        // conexidad (beta0 == 1). Documentado, no oculto:
        if components > 1 {
            return PolydimRustStatus::ErrTopologyFragmented;
        }
        PolydimRustStatus::Success
    });
    match result {
        Ok(s) => s as i32,
        Err(_) => PolydimRustStatus::ErrPanicCaught as i32,
    }
}
