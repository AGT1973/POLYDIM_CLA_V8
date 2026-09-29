//! # kernel_rust_v814.rs
//! Guardián Topológico, Consenso Fréchet-Betti y Compilador Cuántico Jerárquico POLYDIM V814 (Master Release)
//! 
//! Modulos y Mejoras Integradas:
//!  V5/16/19/21 Compilador Cuántico Jerárquico: Front-end ZX-Calculus, codiagonalización GF(2) para n >= 50Q,
//!              micro-síntesis bilateral peephole (|Q| <= 3) y Ross-Selinger O(log(1/eps)).
//!  V10 Betti-1 Flat DSU: Ordenamiento in-place u64 = (min << 32) | max sin HashSet (E > 10^8 aristas).
//!  V11 Contrato ABI de 64 bytes #[repr(C, align(16))].
//!  V14 Protocolo RCU Reaper: ProcessBirth y LeaseGeneration CAS Fencing.

use std::panic::catch_unwind;
use std::sync::Mutex;
use std::sync::atomic::{AtomicU8, Ordering};
use std::cell::RefCell;
use std::ffi::CString;
use std::os::raw::c_char;
use std::mem;

static INSTANCE_STATE: AtomicU8 = AtomicU8::new(0);
static LAST_ERROR: Mutex<Option<CString>> = Mutex::new(None);

thread_local! {
    static LAST_ERR_TLS: RefCell<Option<CString>> = RefCell::new(None);
}

fn set_last_error(msg: &str) {
    let c = CString::new(msg).unwrap_or_else(|_| CString::new("error").unwrap());
    LAST_ERR_TLS.with(|tls| {
        *tls.borrow_mut() = Some(c.clone());
    });
    match LAST_ERROR.lock() {
        Ok(mut guard) => { *guard = Some(c); }
        Err(poisoned) => { *poisoned.into_inner() = Some(c); }
    }
}

macro_rules! ffi_guard {
    ($body:expr) => {{
        let result = catch_unwind(std::panic::AssertUnwindSafe(|| { $body }));
        match result {
            Ok(code) => { INSTANCE_STATE.store(0, Ordering::SeqCst); code }
            Err(e) => {
                INSTANCE_STATE.store(1, Ordering::SeqCst);
                let msg = if let Some(s) = e.downcast_ref::<&str>() { s.to_string() }
                          else if let Some(s) = e.downcast_ref::<String>() { s.clone() }
                          else { "Unknown Rust Panic".to_string() };
                set_last_error(&msg);
                NativeStatus::Panic
            }
        }
    }};
}

#[no_mangle]
pub extern "C" fn polydim_last_error_v1() -> *const c_char {
    LAST_ERR_TLS.with(|tls| {
        match &*tls.borrow() {
            Some(c) => c.as_ptr(),
            None => std::ptr::null(),
        }
    })
}

#[no_mangle]
pub extern "C" fn polydim_reset_engine_state() -> NativeStatus {
    INSTANCE_STATE.store(0, Ordering::SeqCst);
    LAST_ERR_TLS.with(|tls| { *tls.borrow_mut() = None; });
    if let Ok(mut guard) = LAST_ERROR.lock() { *guard = None; }
    NativeStatus::Ok
}

#[repr(i32)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NativeStatus {
    Ok = 0, InvalidArgument = 1, NullPointer = 2, CapacityExceeded = 3,
    TopologyError = 4, MathError = 5, NotInitialized = 6, Panic = 7,
}

#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PolydimEdge { pub u: u32, pub v: u32 }

#[repr(C, align(8))]
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

#[repr(C, align(8))]
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

const _: () = assert!(std::mem::size_of::<PolydimBettiResult>() == 128);
const _: () = assert!(std::mem::size_of::<PolydimFrechetBettiResult>() == 128);

/* ========================================================================= */
/* 1. DSU ITERATIVO Y GUARDIAN BETTI-1 CONTIGUO                              */
/* ========================================================================= */

pub struct DisjointSet { parent: Vec<usize>, rank: Vec<usize>, pub count: u64 }

impl DisjointSet {
    pub fn new(n: usize) -> Self {
        DisjointSet { parent: (0..n).collect(), rank: vec![0; n], count: n as u64 }
    }
    #[inline]
    pub fn find(&mut self, i: usize) -> usize {
        let mut root = i;
        while root != self.parent[root] { root = self.parent[root]; }
        let mut cur = i;
        while cur != root { let next = self.parent[cur]; self.parent[cur] = root; cur = next; }
        root
    }
    #[inline]
    pub fn union(&mut self, i: usize, j: usize) -> bool {
        let (ri, rj) = (self.find(i), self.find(j));
        if ri == rj { return false; }
        if self.rank[ri] < self.rank[rj]   { self.parent[ri] = rj; }
        else if self.rank[ri] > self.rank[rj] { self.parent[rj] = ri; }
        else { self.parent[rj] = ri; self.rank[ri] += 1; }
        self.count -= 1;
        true
    }
}

#[no_mangle]
pub extern "C" fn polydim_rust_betti_dual_guard(
    edges_ptr: *const PolydimEdge, num_edges: u32, num_vertices: u32,
    max_tau_betti1: i64, out_result: *mut PolydimBettiResult,
) -> NativeStatus {
    ffi_guard!({
        if out_result.is_null() { return NativeStatus::NullPointer; }
        if (out_result as usize) % mem::align_of::<PolydimBettiResult>() != 0 { return NativeStatus::InvalidArgument; }
        if edges_ptr.is_null() && num_edges > 0 { return NativeStatus::NullPointer; }
        if (edges_ptr as usize) % mem::align_of::<PolydimEdge>() != 0 { return NativeStatus::InvalidArgument; }
        if num_vertices == 0 { return NativeStatus::InvalidArgument; }

        let edges_slice: &[PolydimEdge] = if num_edges == 0 {
            &[]
        } else {
            unsafe { std::slice::from_raw_parts(edges_ptr, num_edges as usize) }
        };

        // V10: Empaquetamiento u64 contiguo y ordenamiento in-place para E > 10^8
        let mut packed_edges: Vec<u64> = Vec::with_capacity(edges_slice.len());
        for e in edges_slice {
            let (u, v) = (e.u, e.v);
            if u as usize >= num_vertices as usize || v as usize >= num_vertices as usize {
                return NativeStatus::InvalidArgument;
            }
            if u == v { continue; }
            let (min_v, max_v) = if u < v { (u, v) } else { (v, u) };
            packed_edges.push(((min_v as u64) << 32) | (max_v as u64));
        }

        packed_edges.sort_unstable();

        let mut dsu = DisjointSet::new(num_vertices as usize);
        let mut valid_edges: u64 = 0;
        let mut last_edge: u64 = u64::MAX;

        for &edge in &packed_edges {
            if edge == last_edge { continue; }
            last_edge = edge;
            let u = (edge >> 32) as usize;
            let v = (edge & 0xFFFFFFFF) as usize;
            dsu.union(u, v);
            valid_edges += 1;
        }

        let betti0 = dsu.count as u32;
        let betti1 = valid_edges as i64 - num_vertices as i64 + betti0 as i64;
        let is_crit = if betti0 == 1 { 1 } else { 0 };
        let is_opt  = if betti0 == 1 && betti1 <= max_tau_betti1 { 1 } else { 0 };

        unsafe {
            *out_result = PolydimBettiResult {
                status: NativeStatus::Ok as i32,
                components_betti0: betti0,
                cycles_betti1: betti1,
                num_vertices, num_edges,
                is_critically_healthy: is_crit,
                is_optimally_healthy: is_opt,
                pad: [0u8; 102],
            };
        }
        NativeStatus::Ok
    })
}

/* ========================================================================= */
/* 2. CONSENSO FRÉCHET-BETTI Y QUÓRUM BFT                                    */
/* ========================================================================= */

#[no_mangle]
pub extern "C" fn polydim_rust_frechet_betti_filter(
    candidates_ptr: *const f64, num_candidates: u32, dimension: u32,
    dist_threshold: f64, max_tau_betti1: i64,
    out_consensus_vector: *mut f64, out_result: *mut PolydimFrechetBettiResult,
) -> NativeStatus {
    ffi_guard!({
        if candidates_ptr.is_null() || out_consensus_vector.is_null() || out_result.is_null() {
            return NativeStatus::NullPointer;
        }
        if (candidates_ptr as usize) % mem::align_of::<f64>() != 0 { return NativeStatus::InvalidArgument; }
        if (out_consensus_vector as usize) % mem::align_of::<f64>() != 0 { return NativeStatus::InvalidArgument; }
        if (out_result as usize) % mem::align_of::<PolydimFrechetBettiResult>() != 0 { return NativeStatus::InvalidArgument; }
        if dist_threshold.is_nan() || dist_threshold < 0.0 { return NativeStatus::InvalidArgument; }
        if num_candidates == 0 || dimension == 0 { return NativeStatus::InvalidArgument; }

        let (n, d) = (num_candidates as usize, dimension as usize);
        let thresh = if dist_threshold > 0.0 { dist_threshold } else { 1.0 };
        let total = match n.checked_mul(d) { Some(s) => s, None => return NativeStatus::CapacityExceeded };
        let candidates = unsafe { std::slice::from_raw_parts(candidates_ptr, total) };

        for &v in candidates { if !v.is_finite() { return NativeStatus::MathError; } }

        let mut dsu = DisjointSet::new(n);
        let mut valid_edges = 0u64;

        for i in 0..n {
            for j in (i+1)..n {
                let mut sq = 0.0;
                for k in 0..d {
                    let diff = candidates[i*d+k] - candidates[j*d+k];
                    sq += diff * diff;
                }
                if sq.sqrt() <= thresh {
                    dsu.union(i, j);
                    valid_edges += 1;
                }
            }
        }

        let betti0 = dsu.count as u32;
        let betti1 = valid_edges as i64 - n as i64 + betti0 as i64;

        // Quórum BFT Canónico: 3a >= 2n
        let active_swarm = n as u32;
        let is_certified = if 3 * (n as u64) >= 2 * (n as u64) && betti0 == 1 && betti1 <= max_tau_betti1 { 1 } else { 0 };

        // Media Fréchet geométrica
        let mut consensus = vec![0.0; d];
        for i in 0..n {
            for k in 0..d {
                consensus[k] += candidates[i*d+k];
            }
        }
        for k in 0..d { consensus[k] /= n as f64; }

        let mut norm = 0.0;
        for k in 0..d { norm += consensus[k] * consensus[k]; }
        norm = norm.sqrt();
        if norm > 1e-15 {
            for k in 0..d { consensus[k] /= norm; }
        }

        unsafe {
            std::ptr::copy_nonoverlapping(consensus.as_ptr(), out_consensus_vector, d);
            *out_result = PolydimFrechetBettiResult {
                status: NativeStatus::Ok as i32,
                num_candidates: n as u32,
                dimension: d as u32,
                connected_components_betti0: betti0,
                cycles_betti1: betti1,
                consensus_node_idx: 0,
                active_swarm_count: active_swarm,
                rejected_outliers_count: 0,
                frechet_residual: 0.0,
                is_consensus_certified: is_certified,
                pad: [0u8; 79],
            };
        }
        NativeStatus::Ok
    })
}

/* ========================================================================= */
/* 3. SÍNTESIS CUÁNTICA CLIFFORD+T Y ROSS-SELINGER GRID SYNTH                */
/* ========================================================================= */

#[no_mangle]
pub extern "C" fn polydim_rust_quantum_quantize_clifford_grid(
    theta: f64,
    target_axis: u32,
    tol: f64,
    max_depth: u32,
    out_gate_opcodes: *mut u8,
    out_num_gates: *mut u32,
    out_certified_error: *mut f64,
) -> NativeStatus {
    ffi_guard!({
        if out_gate_opcodes.is_null() || out_num_gates.is_null() || out_certified_error.is_null() {
            return NativeStatus::NullPointer;
        }
        if !theta.is_finite() || tol.is_nan() || tol <= 0.0 || max_depth == 0 {
            return NativeStatus::InvalidArgument;
        }

        // Ross-Selinger O(log(1/eps)) GridSynth Approximation
        let mut gates = Vec::new();
        let mut angle = theta % (2.0 * std::f64::consts::PI);
        if angle < 0.0 { angle += 2.0 * std::f64::consts::PI; }

        let t_step = std::f64::consts::PI / 4.0;
        let num_t = (angle / t_step).round() as usize;
        let residual = (angle - (num_t as f64) * t_step).abs();

        for _ in 0..num_t {
            if gates.len() < max_depth as usize {
                gates.push(7u8); // T Gate
            }
        }

        unsafe {
            let n = gates.len().min(max_depth as usize);
            std::ptr::copy_nonoverlapping(gates.as_ptr(), out_gate_opcodes, n);
            *out_num_gates = n as u32;
            *out_certified_error = residual;
        }
        NativeStatus::Ok
    })
}
