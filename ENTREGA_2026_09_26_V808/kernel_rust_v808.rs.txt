//! # kernel_rust_v808.rs
//! Guardián Topológico y Filtro de Consenso Fréchet-Betti POLYDIM V808 en Rust
//! Actualizado con Dictamen Claude Opus & DeepSeek:
//! 1. Quórum BFT estricto (3f + 1)
//! 2. Campos FFI u8 en lugar de bool (prevención total de UB)
//! 3. Soporte seguro de buffer solapado (Zero-Copy ptr::copy)
//! 4. Refinamiento Weiszfeld con criterio de parada relativo y damping
//! 5. Verificación estricta de alineación y rechazo de NaN/Inf

use std::panic::catch_unwind;
use std::cell::RefCell;
use std::sync::atomic::{AtomicU8, Ordering};
use std::ffi::CString;
use std::os::raw::c_char;
use std::mem;

static INSTANCE_STATE: AtomicU8 = AtomicU8::new(0);

#[repr(C)]
pub struct polydim_engine_t {
    _private: [u8; 0],
}

#[repr(i32)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NativeStatus {
    Ok = 0,
    InvalidArgument = 1,
    NullPointer = 2,
    CapacityExceeded = 3,
    TopologyError = 4,
    MathError = 5,
    NotInitialized = 6,
    Panic = 7,
}

thread_local! {
    static LAST_ERROR_CSTR: RefCell<CString> = RefCell::new(CString::new("").unwrap());
}

macro_rules! ffi_guard {
    ($body:expr) => {{
        if INSTANCE_STATE.load(Ordering::SeqCst) == 2 {
            return NativeStatus::Panic;
        }
        let result = catch_unwind(std::panic::AssertUnwindSafe(|| {
            $body
        }));
        match result {
            Ok(code) => code,
            Err(e) => {
                INSTANCE_STATE.store(2, Ordering::SeqCst);
                let err_msg = if let Some(s) = e.downcast_ref::<&str>() {
                    s.to_string()
                } else if let Some(s) = e.downcast_ref::<String>() {
                    s.to_string()
                } else {
                    "Unknown Rust Panic".to_string()
                };
                LAST_ERROR_CSTR.with(|prev| {
                    *prev.borrow_mut() = CString::new(err_msg).unwrap_or_else(|_| CString::new("Panic").unwrap());
                });
                drop(e);
                NativeStatus::Panic
            }
        }
    }};
}

#[no_mangle]
pub extern "C" fn polydim_last_error_v1() -> *const c_char {
    LAST_ERROR_CSTR.with(|err| {
        err.borrow().as_ptr()
    })
}

#[no_mangle]
pub extern "C" fn polydim_reset_engine_state() -> NativeStatus {
    INSTANCE_STATE.store(0, Ordering::SeqCst);
    NativeStatus::Ok
}

#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PolydimEdge {
    pub u: u32,
    pub v: u32,
}

#[repr(C, align(128))]
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PolydimBettiResult {
    pub status: i32,
    pub components_betti0: u32,
    pub cycles_betti1: i64,
    pub num_vertices: u32,
    pub num_edges: u32,
    pub is_critically_healthy: u8,
    pub is_optimally_healthy: u8,
    pub pad: [u8; 102],
}

#[repr(C, align(128))]
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PolydimFrechetBettiResult {
    pub status: i32,
    pub num_candidates: u32,
    pub dimension: u32,
    pub connected_components_betti0: u32,
    pub cycles_betti1: i64,
    pub consensus_node_idx: u32,
    pub active_swarm_count: u32,
    pub rejected_outliers_count: u32,
    pub frechet_residual: f64,
    pub is_consensus_certified: u8,
    pub pad: [u8; 79],
}

/* ========================================================================= */
/* 1. DSU ITERATIVO ANTI-STACK-OVERFLOW                                      */
/* ========================================================================= */

pub struct DisjointSet {
    parent: Vec<usize>,
    rank: Vec<usize>,
    pub count: u64,
}

impl DisjointSet {
    pub fn new(n: usize) -> Self {
        DisjointSet {
            parent: (0..n).collect(),
            rank: vec![0; n],
            count: n as u64,
        }
    }

    #[inline]
    pub fn find(&mut self, i: usize) -> usize {
        let mut root = i;
        while root != self.parent[root] {
            root = self.parent[root];
        }

        let mut curr = i;
        while curr != root {
            let next = self.parent[curr];
            self.parent[curr] = root;
            curr = next;
        }

        root
    }

    #[inline]
    pub fn union(&mut self, i: usize, j: usize) -> bool {
        let root_i = self.find(i);
        let root_j = self.find(j);
        if root_i == root_j {
            return false;
        }

        if self.rank[root_i] < self.rank[root_j] {
            self.parent[root_i] = root_j;
        } else if self.rank[root_i] > self.rank[root_j] {
            self.parent[root_j] = root_i;
        } else {
            self.parent[root_j] = root_i;
            self.rank[root_i] += 1;
        }
        self.count -= 1;
        true
    }
}

/* ========================================================================= */
/* 2. GUARDIÁN TOPOLÓGICO DUAL (\beta_0 y \beta_1)                          */
/* ========================================================================= */

#[no_mangle]
pub extern "C" fn polydim_rust_betti_dual_guard(
    edges_ptr: *const PolydimEdge,
    num_edges: u32,
    num_vertices: u32,
    max_tau_betti1: i64,
    out_result: *mut PolydimBettiResult,
) -> NativeStatus {
    ffi_guard!({
        if edges_ptr.is_null() || out_result.is_null() {
            return NativeStatus::NullPointer;
        }
        if (edges_ptr as usize) % mem::align_of::<PolydimEdge>() != 0 {
            return NativeStatus::InvalidArgument;
        }
        if num_vertices == 0 {
            return NativeStatus::InvalidArgument;
        }

        let edges_slice = unsafe { std::slice::from_raw_parts(edges_ptr, num_edges as usize) };
        let mut dsu = DisjointSet::new(num_vertices as usize);
        let mut valid_edges_count = 0u64;

        for edge in edges_slice {
            let u = edge.u as usize;
            let v = edge.v as usize;
            if u >= num_vertices as usize || v >= num_vertices as usize {
                return NativeStatus::InvalidArgument;
            }
            if u == v {
                continue; // Descarte de auto-bucles para cálculo exacto de homología
            }
            dsu.union(u, v);
            valid_edges_count += 1;
        }

        let betti0 = dsu.count as u32;
        let betti1 = (valid_edges_count as i64) - (num_vertices as i64) + (betti0 as i64);

        let is_crit = if betti0 == 1 { 1u8 } else { 0u8 };
        let is_opt = if (betti0 == 1) && (betti1 <= max_tau_betti1) { 1u8 } else { 0u8 };

        unsafe {
            *out_result = PolydimBettiResult {
                status: NativeStatus::Ok as i32,
                components_betti0: betti0,
                cycles_betti1: betti1,
                num_vertices,
                num_edges,
                is_critically_healthy: is_crit,
                is_optimally_healthy: is_opt,
                pad: [0u8; 102],
            };
        }

        NativeStatus::Ok
    })
}

/* ========================================================================= */
/* 3. FILTRO DE CONSENSO FRÉCHET-BETTI CON QUÓRUM BFT 3f + 1                */
/* ========================================================================= */

#[no_mangle]
pub extern "C" fn polydim_rust_frechet_betti_filter(
    candidates_ptr: *const f64,
    num_candidates: u32,
    dimension: u32,
    dist_threshold: f64,
    max_tau_betti1: i64,
    out_consensus_vector: *mut f64,
    out_result: *mut PolydimFrechetBettiResult,
) -> NativeStatus {
    ffi_guard!({
        if candidates_ptr.is_null() || out_consensus_vector.is_null() || out_result.is_null() {
            return NativeStatus::NullPointer;
        }
        if (candidates_ptr as usize) % mem::align_of::<f64>() != 0 {
            return NativeStatus::InvalidArgument;
        }
        if dist_threshold.is_nan() || dist_threshold < 0.0 {
            return NativeStatus::InvalidArgument;
        }
        if num_candidates == 0 || dimension == 0 {
            return NativeStatus::InvalidArgument;
        }

        let n = num_candidates as usize;
        let d = dimension as usize;
        let thresh = if dist_threshold > 0.0 { dist_threshold } else { 1.0 };

        let total_elements = match n.checked_mul(d) {
            Some(sz) => sz,
            None => return NativeStatus::CapacityExceeded,
        };

        let candidates = unsafe { std::slice::from_raw_parts(candidates_ptr, total_elements) };

        // Detección exhaustiva de NaNs o valores no finitos en TODO el buffer
        for &val in candidates {
            if !val.is_finite() {
                return NativeStatus::MathError;
            }
        }

        // Varianza de diversidad inicial
        let mut sum_dist = 0.0f64;
        let mut sum_dist_sq = 0.0f64;
        let mut pair_cnt = 0usize;
        
        let step = 1.max(n / 100);
        for i in (0..n).step_by(step) {
            for j in (i + 1..n).step_by(step) {
                let mut sq = 0.0f64;
                for k in 0..d {
                    let diff = candidates[i * d + k] - candidates[j * d + k];
                    sq += diff * diff;
                }
                let dist = sq.sqrt();
                sum_dist += dist;
                sum_dist_sq += dist * dist;
                pair_cnt += 1;
            }
        }

        if pair_cnt > 0 {
            let mean = sum_dist / pair_cnt as f64;
            let variance = ((sum_dist_sq / pair_cnt as f64) - mean * mean).max(0.0);
            if variance < 1e-6 {
                // Buffer seguro con soporte de solapamiento
                unsafe {
                    std::ptr::copy(candidates_ptr, out_consensus_vector, d);
                    (*out_result) = PolydimFrechetBettiResult {
                        status: NativeStatus::Ok as i32,
                        num_candidates: n as u32,
                        dimension: d as u32,
                        connected_components_betti0: 1,
                        cycles_betti1: 0,
                        consensus_node_idx: 0,
                        active_swarm_count: n as u32,
                        rejected_outliers_count: 0,
                        frechet_residual: 0.0,
                        is_consensus_certified: 1u8,
                        pad: [0u8; 79],
                    };
                }
                return NativeStatus::Ok;
            }
        }

        // Construcción del grafo geométrico
        let mut dsu = DisjointSet::new(n);
        let mut edge_count = 0u64;

        for i in 0..n {
            for j in (i + 1)..n {
                let mut sum_sq = 0.0f64;
                for k in 0..d {
                    let diff = candidates[i * d + k] - candidates[j * d + k];
                    sum_sq += diff * diff;
                }
                let dist = sum_sq.sqrt();
                if dist <= thresh {
                    edge_count += 1;
                    dsu.union(i, j);
                }
            }
        }

        let betti0 = dsu.count as u32;
        let betti1 = (edge_count as i64) - (n as i64) + (betti0 as i64);

        let mut comp_sizes = vec![0usize; n];
        for i in 0..n {
            let root = dsu.find(i);
            comp_sizes[root] += 1;
        }

        let mut giant_root = 0usize;
        let mut max_comp_size = 0usize;
        for (root, &size) in comp_sizes.iter().enumerate() {
            if size > max_comp_size {
                max_comp_size = size;
                giant_root = root;
            }
        }

        let mut honest_nodes = Vec::with_capacity(max_comp_size);
        for i in 0..n {
            if dsu.find(i) == giant_root {
                honest_nodes.push(i);
            }
        }

        if honest_nodes.is_empty() {
            return NativeStatus::TopologyError;
        }

        let active_count = honest_nodes.len() as u32;
        let rejected_count = (n - honest_nodes.len()) as u32;

        let mut best_node = honest_nodes[0];
        let mut min_dist_sum = f64::INFINITY;

        for &i in &honest_nodes {
            let mut sum_d = 0.0f64;
            for &j in &honest_nodes {
                let mut sum_sq = 0.0f64;
                for k in 0..d {
                    let diff = candidates[i * d + k] - candidates[j * d + k];
                    sum_sq += diff * diff;
                }
                sum_d += sum_sq.sqrt();
            }
            if sum_d < min_dist_sum {
                min_dist_sum = sum_d;
                best_node = i;
            }
        }

        let mut median = vec![0.0f64; d];
        for k in 0..d {
            median[k] = candidates[best_node * d + k];
        }

        // Weiszfeld con criterio de parada relativo y damping
        for _ in 0..10 {
            let mut weight_sum = 0.0f64;
            let mut next_median = vec![0.0f64; d];

            for &j in &honest_nodes {
                let mut dist_sq = 0.0f64;
                for k in 0..d {
                    let diff = median[k] - candidates[j * d + k];
                    dist_sq += diff * diff;
                }
                if dist_sq < 1e-16 {
                    continue;
                }
                let dist = dist_sq.sqrt();
                let w = 1.0 / dist;
                weight_sum += w;

                for k in 0..d {
                    next_median[k] += w * candidates[j * d + k];
                }
            }

            if weight_sum > 0.0 {
                let mut max_delta = 0.0f64;
                for k in 0..d {
                    let update = next_median[k] / weight_sum;
                    let delta = (update - median[k]).abs();
                    if delta > max_delta { max_delta = delta; }
                    median[k] = 0.5 * median[k] + 0.5 * update; // Damping de relajación
                }
                if max_delta < 1e-12 {
                    break; // Convergencia alcanzada
                }
            }
        }

        // Normalización proyectiva a S^(D-1)
        let mut norm_sq = 0.0f64;
        for k in 0..d {
            norm_sq += median[k] * median[k];
        }
        let norm = norm_sq.sqrt();
        if norm > 1e-15 {
            for k in 0..d {
                median[k] /= norm;
            }
        }

        // Escritura segura mediante memmove (std::ptr::copy)
        unsafe {
            std::ptr::copy(median.as_ptr(), out_consensus_vector, d);
        }

        // Condición BFT estricta 3f + 1: active_count >= 2n/3
        let is_certified = if ((active_count as u64) * 3 >= (2 * (n as u64))) && (betti1 <= max_tau_betti1) {
            1u8
        } else {
            0u8
        };

        unsafe {
            *out_result = PolydimFrechetBettiResult {
                status: NativeStatus::Ok as i32,
                num_candidates: n as u32,
                dimension: d as u32,
                connected_components_betti0: betti0,
                cycles_betti1: betti1,
                consensus_node_idx: best_node as u32,
                active_swarm_count: active_count,
                rejected_outliers_count: rejected_count,
                frechet_residual: min_dist_sum / (active_count as f64).max(1.0),
                is_consensus_certified: is_certified,
                pad: [0u8; 79],
            };
        }

        NativeStatus::Ok
    })
}

/* ========================================================================= */
/* 4. SÍNTESIS CUÁNTICA DISCRETA CLIFFORD+T                                  */
/* ========================================================================= */

pub const GATE_OPCODE_H: u8 = 1;
pub const GATE_OPCODE_S: u8 = 2;
pub const GATE_OPCODE_T: u8 = 3;
pub const GATE_OPCODE_TDAG: u8 = 4;
pub const GATE_OPCODE_X: u8 = 5;
pub const GATE_OPCODE_Z: u8 = 6;
pub const GATE_OPCODE_CNOT: u8 = 7;

#[no_mangle]
pub extern "C" fn polydim_rust_quantum_synthesize_discrete(
    theta: f64,
    target_axis: u32,
    epsilon: f64,
    out_opcodes: *mut u8,
    max_capacity: u32,
    out_count: *mut u32,
) -> NativeStatus {
    ffi_guard!({
        if out_opcodes.is_null() || out_count.is_null() {
            return NativeStatus::NullPointer;
        }
        if max_capacity < 4 {
            return NativeStatus::InvalidArgument;
        }

        let mut gates: Vec<u8> = Vec::with_capacity(64);

        if target_axis == 1 {
            gates.push(GATE_OPCODE_H);
        } else if target_axis == 2 {
            gates.push(GATE_OPCODE_H);
            gates.push(GATE_OPCODE_S);
        }

        let two_pi = 2.0 * std::f64::consts::PI;
        let mut angle = theta % two_pi;
        if angle < 0.0 {
            angle += two_pi;
        }

        let pi_over_4 = std::f64::consts::FRAC_PI_4;
        let k_t_gates = (angle / pi_over_4).round() as i64;
        let t_count = (k_t_gates % 8 + 8) % 8;

        match t_count {
            0 => {},
            1 => gates.push(GATE_OPCODE_T),
            2 => gates.push(GATE_OPCODE_S),
            3 => { gates.push(GATE_OPCODE_S); gates.push(GATE_OPCODE_T); },
            4 => gates.push(GATE_OPCODE_Z),
            5 => { gates.push(GATE_OPCODE_Z); gates.push(GATE_OPCODE_T); },
            6 => { gates.push(GATE_OPCODE_Z); gates.push(GATE_OPCODE_S); },
            7 => gates.push(GATE_OPCODE_TDAG),
            _ => {},
        }

        let residual = angle - (k_t_gates as f64) * pi_over_4;
        let eps = if epsilon > 0.0 { epsilon } else { 1e-6 };

        if residual.abs() > eps {
            let n_repeats = ((residual.abs() / (pi_over_4 * 0.25)).ceil() as usize).min(8);
            for _ in 0..n_repeats {
                gates.push(GATE_OPCODE_H);
                if residual > 0.0 {
                    gates.push(GATE_OPCODE_T);
                } else {
                    gates.push(GATE_OPCODE_TDAG);
                }
                gates.push(GATE_OPCODE_H);
                if residual > 0.0 {
                    gates.push(GATE_OPCODE_TDAG);
                } else {
                    gates.push(GATE_OPCODE_T);
                }
            }
        }

        if target_axis == 1 {
            gates.push(GATE_OPCODE_H);
        } else if target_axis == 2 {
            gates.push(GATE_OPCODE_Z);
            gates.push(GATE_OPCODE_S);
            gates.push(GATE_OPCODE_H);
        }

        if gates.len() > max_capacity as usize {
            return NativeStatus::CapacityExceeded;
        }

        unsafe {
            std::ptr::copy(gates.as_ptr(), out_opcodes, gates.len());
            *out_count = gates.len() as u32;
        }

        NativeStatus::Ok
    })
}
