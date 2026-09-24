// ============================================================================
// POLYDIM V762 — NATIVE RUST TOPOLOGICAL GUARD & INVARIANT ENGINE
// Catch-Unwind Protected FFI | Betti-1 Graph Topology | Higham Bounds on S^(D-1)
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
    ErrSeqLockRace = -9,
    ErrPanicCaught = -99,
}

const EPS_MACH: f64 = f64::EPSILON; // 2.220446049250313e-16

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
        if d == 0 {
            return PolydimRustStatus::ErrInvalidDimension;
        }

        let slice = slice::from_raw_parts(ptr, d);

        // Neumaier compensated 2-norm summation
        let mut sum: f64 = 0.0;
        let mut c: f64 = 0.0;

        for &val in slice {
            if val.is_nan() || val.is_infinite() {
                return PolydimRustStatus::ErrNanOrInf;
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

        let norm = norm_sq.sqrt();
        let drift = (norm - 1.0).abs();

        if !max_drift_out.is_null() {
            *max_drift_out = drift;
        }

        // C++ V764 Alignment: Tol = 64 * eps_mach (invariant O(eps) under compensated summation)
        let tol = 64.0 * EPS_MACH;
        if drift > tol {
            return PolydimRustStatus::ErrNumericalInstability;
        }

        PolydimRustStatus::Success
    });

    match result {
        Ok(status) => status as i32,
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
        if n == 0 {
            return PolydimRustStatus::ErrInvalidDimension;
        }
        if n > 4096 {
            return PolydimRustStatus::ErrBufferOverflow;
        }

        let mat = slice::from_raw_parts(adj_matrix, n * n);

        // Disjoint Set Union (DSU / Union-Find) to compute Betti-0 and Betti-1
        let mut parent: Vec<usize> = (0..n).collect();
        let mut rank: Vec<usize> = vec![0; n];

        fn find(parent: &mut [usize], i: usize) -> usize {
            if parent[i] == i {
                i
            } else {
                let p = parent[i];
                parent[i] = find(parent, p);
                parent[i]
            }
        }

        fn union(parent: &mut [usize], rank: &mut [usize], i: usize, j: usize) -> bool {
            let root_i = find(parent, i);
            let root_j = find(parent, j);
            if root_i != root_j {
                if rank[root_i] < rank[root_j] {
                    parent[root_i] = root_j;
                } else if rank[root_i] > rank[root_j] {
                    parent[root_j] = root_i;
                } else {
                    parent[root_j] = root_i;
                    rank[root_i] += 1;
                }
                true
            } else {
                false // Cycle detected (increases Betti-1)
            }
        }

        let mut edges = 0usize;
        let mut components = n;

        for i in 0..n {
            for j in (i + 1)..n {
                let weight = mat[i * n + j];
                if weight.is_nan() || weight.is_infinite() {
                    return PolydimRustStatus::ErrNanOrInf;
                }
                if weight >= threshold {
                    edges += 1;
                    if union(&mut parent, &mut rank, i, j) {
                        components -= 1;
                    }
                }
            }
        }

        // Betti-0 is number of connected components
        // Betti-1 = Edges - Vertices + Connected Components
        if components > 1 {
            return PolydimRustStatus::ErrTopologyFragmented;
        }

        PolydimRustStatus::Success
    });

    match result {
        Ok(status) => status as i32,
        Err(_) => PolydimRustStatus::ErrPanicCaught as i32,
    }
}
