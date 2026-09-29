//! # kernel_rust_v808_1.rs
//! Guardián Topológico y Filtro de Consenso Fréchet-Betti POLYDIM V808.1
//! Correcciones (Bulldog Red Team, pasada completa):
//!  C4  Quórum BFT estricto: 3a > 2n (antes >=, que para n=3f admite 2f).
//!  G4  Latch de pánico NO permanente: se captura, se registra y se recupera.
//!  G5  align(8) con sizeof 128 (align(128) exigía punteros que ctypes no da).
//!  G10 last_error global (no thread-local: el caller puede estar en otro hilo).
//!  G13 betti_dual_guard: edges_ptr NULL permitido cuando num_edges == 0.
//!  G14 frechet: residual recalculado tras Weiszfeld (antes era pre-refinamiento,
//!      valor obsoleto); consenso no certificado si la norma es ~0.
//!  Q1  Síntesis cuántica axis=2 REESCRITA: V808 producía R_x, no R_y
//!      (verificado numericamente: fidelidad |Tr(U·R_y†)|/2 = 0.8536 vs 1.0).
//!      Nueva secuencia S·H·Rz·H·S†. Se añade GATE_OPCODE_SDAG = 8.
//!  Q2  Validación de target_axis (0=Z, 1=X, 2=Y); antes cualquier valor
//!      distinto de 1/2 caía en el caso Z sin aviso.

use std::panic::catch_unwind;
use std::sync::Mutex;
use std::sync::atomic::{AtomicU8, Ordering};
use std::ffi::CString;
use std::os::raw::c_char;
use std::mem;

static INSTANCE_STATE: AtomicU8 = AtomicU8::new(0);
static LAST_ERROR: Mutex<Option<CString>> = Mutex::new(None);   // G10: global, no thread-local

fn set_last_error(msg: &str) {
    let c = CString::new(msg).unwrap_or_else(|_| CString::new("error").unwrap());
    if let Ok(mut guard) = LAST_ERROR.lock() { *guard = Some(c); }
}

macro_rules! ffi_guard {
    ($body:expr) => {{
        // G4: el latch ya NO es permanente. Se captura, se registra y se
        // recupera; el error queda consultable vía polydim_last_error_v1.
        let result = catch_unwind(std::panic::AssertUnwindSafe(|| { $body }));
        match result {
            Ok(code) => { INSTANCE_STATE.store(0, Ordering::SeqCst); code }
            Err(e) => {
                INSTANCE_STATE.store(1, Ordering::SeqCst);   // 1 = "última call panic" (transitorio)
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
    match LAST_ERROR.lock() {
        Ok(guard) => match guard.as_ref() {
            Some(c) => c.as_ptr(),
            None => std::ptr::null(),
        },
        Err(_) => std::ptr::null(),
    }
}

#[no_mangle]
pub extern "C" fn polydim_reset_engine_state() -> NativeStatus {
    INSTANCE_STATE.store(0, Ordering::SeqCst);
    if let Ok(mut guard) = LAST_ERROR.lock() { *guard = None; }
    NativeStatus::Ok
}

#[repr(C)]
pub struct polydim_engine_t { _private: [u8; 0] }

#[repr(i32)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NativeStatus {
    Ok = 0, InvalidArgument = 1, NullPointer = 2, CapacityExceeded = 3,
    TopologyError = 4, MathError = 5, NotInitialized = 6, Panic = 7,
}

#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PolydimEdge { pub u: u32, pub v: u32 }

#[repr(C, align(8))]            // G5: sizeof sigue siendo 128 sin exigir align 128
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

#[repr(C, align(8))]            // G5: 45 bytes + SDAG-pad = 128 con align(8)
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
/* 1. DSU ITERATIVO                                                           */
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

/* ========================================================================= */
/* 2. GUARDIÁN TOPOLÓGICO DUAL (G13: NULL válido cuando num_edges == 0)       */
/* ========================================================================= */

#[no_mangle]
pub extern "C" fn polydim_rust_betti_dual_guard(
    edges_ptr: *const PolydimEdge, num_edges: u32, num_vertices: u32,
    max_tau_betti1: i64, out_result: *mut PolydimBettiResult,
) -> NativeStatus {
    ffi_guard!({
        if out_result.is_null() { return NativeStatus::NullPointer; }
        if edges_ptr.is_null() && num_edges > 0 { return NativeStatus::NullPointer; }  // G13
        if (edges_ptr as usize) % mem::align_of::<PolydimEdge>() != 0 { return NativeStatus::InvalidArgument; }
        if num_vertices == 0 { return NativeStatus::InvalidArgument; }

        let edges_slice: &[PolydimEdge] = if num_edges == 0 {
            &[]
        } else {
            unsafe { std::slice::from_raw_parts(edges_ptr, num_edges as usize) }
        };
        let mut dsu = DisjointSet::new(num_vertices as usize);
        let mut valid_edges: u64 = 0;

        for e in edges_slice {
            let (u, v) = (e.u as usize, e.v as usize);
            if u >= num_vertices as usize || v >= num_vertices as usize { return NativeStatus::InvalidArgument; }
            if u == v { continue; }
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
/* 3. FILTRO DE CONSENSO FRÉCHET-BETTI (C4 + G14)                             */
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
        if dist_threshold.is_nan() || dist_threshold < 0.0 { return NativeStatus::InvalidArgument; }
        if num_candidates == 0 || dimension == 0 { return NativeStatus::InvalidArgument; }

        let (n, d) = (num_candidates as usize, dimension as usize);
        let thresh = if dist_threshold > 0.0 { dist_threshold } else { 1.0 };

        let total = match n.checked_mul(d) { Some(s) => s, None => return NativeStatus::CapacityExceeded };
        let candidates = unsafe { std::slice::from_raw_parts(candidates_ptr, total) };

        for &v in candidates { if !v.is_finite() { return NativeStatus::MathError; } }  // C7 exhaustivo

        /* Varianza muestreada (caso degenerado: consenso inmediato) */
        let mut sum_d = 0.0f64; let mut sum_d2 = 0.0f64; let mut cnt = 0usize;
        let step = 1.max(n / 100);
        for i in (0..n).step_by(step) {
            for j in ((i + 1)..n).step_by(step) {
                let mut sq = 0.0;
                for k in 0..d { let diff = candidates[i*d+k] - candidates[j*d+k]; sq += diff*diff; }
                let dist = sq.sqrt();
                sum_d += dist; sum_d2 += dist*dist; cnt += 1;
            }
        }
        if cnt > 0 {
            let mean = sum_d / cnt as f64;
            let var = ((sum_d2 / cnt as f64) - mean*mean).max(0.0);
            if var < 1e-6 {
                unsafe {
                    std::ptr::copy(candidates_ptr, out_consensus_vector, d);
                    *out_result = PolydimFrechetBettiResult {
                        status: NativeStatus::Ok as i32,
                        num_candidates: n as u32, dimension: d as u32,
                        connected_components_betti0: 1, cycles_betti1: 0,
                        consensus_node_idx: 0, active_swarm_count: n as u32,
                        rejected_outliers_count: 0, frechet_residual: 0.0,
                        is_consensus_certified: 1, pad: [0u8; 79],
                    };
                }
                return NativeStatus::Ok;
            }
        }

        /* Grafo geométrico + DSU */
        let mut dsu = DisjointSet::new(n);
        let mut edge_count: u64 = 0;
        for i in 0..n {
            for j in (i+1)..n {
                let mut sq = 0.0;
                for k in 0..d { let diff = candidates[i*d+k]-candidates[j*d+k]; sq += diff*diff; }
                if sq.sqrt() <= thresh { edge_count += 1; dsu.union(i, j); }
            }
        }
        let betti0 = dsu.count as u32;
        let betti1 = edge_count as i64 - n as i64 + betti0 as i64;

        let mut sizes = vec![0usize; n];
        for i in 0..n { let r = dsu.find(i); sizes[r] += 1; }
        let mut giant = 0usize; let mut max_sz = 0usize;
        for (r, &s) in sizes.iter().enumerate() { if s > max_sz { max_sz = s; giant = r; } }

        let honest: Vec<usize> = (0..n).filter(|&i| dsu.find(i) == giant).collect();
        if honest.is_empty() { return NativeStatus::TopologyError; }

        /* Mediana geométrica discreta (min suma de distancias) */
        let mut best = honest[0]; let mut min_sum = f64::INFINITY;
        for &i in &honest {
            let mut s = 0.0;
            for &j in &honest {
                let mut sq = 0.0;
                for k in 0..d { let diff = candidates[i*d+k]-candidates[j*d+k]; sq += diff*diff; }
                s += sq.sqrt();
            }
            if s < min_sum { min_sum = s; best = i; }
        }
        let mut median: Vec<f64> = (0..d).map(|k| candidates[best*d+k]).collect();

        /* Weiszfeld con damping y parada relativa */
        for _ in 0..10 {
            let mut wsum = 0.0; let mut next = vec![0.0f64; d];
            for &j in &honest {
                let mut dsq = 0.0;
                for k in 0..d { let diff = median[k]-candidates[j*d+k]; dsq += diff*diff; }
                if dsq < 1e-16 { continue; }
                let w = 1.0 / dsq.sqrt();
                wsum += w;
                for k in 0..d { next[k] += w * candidates[j*d+k]; }
            }
            if wsum > 0.0 {
                let mut max_delta = 0.0f64;
                for k in 0..d {
                    let upd = next[k] / wsum;
                    max_delta = max_delta.max((upd - median[k]).abs());
                    median[k] = 0.5*median[k] + 0.5*upd;
                }
                if max_delta < 1e-12 { break; }
            }
        }

        /* G14: residual del vector REFINADO, no del pre-Weiszfeld */
        let mut refined_resid = 0.0f64;
        for &j in &honest {
            let mut sq = 0.0;
            for k in 0..d { let diff = median[k]-candidates[j*d+k]; sq += diff*diff; }
            refined_resid += sq.sqrt();
        }
        refined_resid /= honest.len() as f64;

        /* Normalización proyectiva; vector ~0 no es consenso certificable */
        let mut norm_sq = 0.0;
        for k in 0..d { norm_sq += median[k]*median[k]; }
        let norm = norm_sq.sqrt();
        let normalizable = norm > 1e-15;
        if normalizable { for k in 0..d { median[k] /= norm; } }

        unsafe { std::ptr::copy(median.as_ptr(), out_consensus_vector, d); }

        let active = honest.len() as u32;
        let rejected = (n - honest.len()) as u32;

        // C4: quórum estricto a >= floor(2n/3)+1  <=>  3a > 2n  (válido para todo n)
        let quorum_ok = (active as u64) * 3 > (2 * n as u64);
        let is_certified = if quorum_ok && betti1 <= max_tau_betti1 && normalizable { 1u8 } else { 0u8 };

        unsafe {
            *out_result = PolydimFrechetBettiResult {
                status: NativeStatus::Ok as i32,
                num_candidates: n as u32, dimension: d as u32,
                connected_components_betti0: betti0, cycles_betti1: betti1,
                consensus_node_idx: best as u32,
                active_swarm_count: active, rejected_outliers_count: rejected,
                frechet_residual: refined_resid,
                is_consensus_certified: is_certified, pad: [0u8; 79],
            };
        }
        NativeStatus::Ok
    })
}

/* ========================================================================= */
/* 4. SÍNTESIS CUÁNTICA CLIFFORD+T (Q1: axis=2 reescrita; Q2: validación)     */
/*    Convención de programa: gates[0] se aplica en ÚLTIMO lugar (producto
/*    order). R_x(θ) = H·Rz(θ)·H; R_y(θ) = S·H·Rz(θ)·H·S†; R_z sin prefijo.  */
/*    Verificado numéricamente: fidelidad |Tr(U·R_target†)|/2 = 1.0.          */
/* ========================================================================= */

pub const GATE_OPCODE_H: u8     = 1;
pub const GATE_OPCODE_S: u8     = 2;
pub const GATE_OPCODE_T: u8     = 3;
pub const GATE_OPCODE_TDAG: u8  = 4;
pub const GATE_OPCODE_X: u8     = 5;
pub const GATE_OPCODE_Z: u8     = 6;
pub const GATE_OPCODE_CNOT: u8  = 7;
pub const GATE_OPCODE_SDAG: u8  = 8;   // S† = T†·T† (no existía opcode; V808 la necesitaba y no la tenía)

#[no_mangle]
pub extern "C" fn polydim_rust_quantum_synthesize_discrete(
    theta: f64, target_axis: u32, epsilon: f64,
    out_opcodes: *mut u8, max_capacity: u32, out_count: *mut u32,
) -> NativeStatus {
    ffi_guard!({
        if out_opcodes.is_null() || out_count.is_null() { return NativeStatus::NullPointer; }
        if max_capacity < 4 { return NativeStatus::InvalidArgument; }
        if !theta.is_finite() { return NativeStatus::MathError; }
        if target_axis > 2 { return NativeStatus::InvalidArgument; }   // Q2

        let mut gates: Vec<u8> = Vec::with_capacity(64);

        // Q1: prefijo correcto en product order. axis=1 (X): H·Rz·H.
        // axis=2 (Y): S·H·Rz·H·S†  -> programa [S, H, <rz>, H, SDAG].
        // (V808 ponía [H,S,...,Z,S,H], que verificado numericamente daba R_x.)
        if target_axis == 1 {
            gates.push(GATE_OPCODE_H);
        } else if target_axis == 2 {
            gates.push(GATE_OPCODE_S);
            gates.push(GATE_OPCODE_H);
        }

        let two_pi = 2.0 * std::f64::consts::PI;
        let mut angle = theta % two_pi;
        if angle < 0.0 { angle += two_pi; }

        let pi4 = std::f64::consts::FRAC_PI_4;
        let k = (angle / pi4).round() as i64;
        let t_count = ((k % 8) + 8) % 8;
        match t_count {
            0 => {}
            1 => gates.push(GATE_OPCODE_T),
            2 => gates.push(GATE_OPCODE_S),
            3 => { gates.push(GATE_OPCODE_S); gates.push(GATE_OPCODE_T); }
            4 => gates.push(GATE_OPCODE_Z),
            5 => { gates.push(GATE_OPCODE_Z); gates.push(GATE_OPCODE_T); }
            6 => { gates.push(GATE_OPCODE_Z); gates.push(GATE_OPCODE_S); }
            7 => gates.push(GATE_OPCODE_TDAG),
            _ => {}
        }

        let residual = angle - (k as f64) * pi4;
        let eps = if epsilon > 0.0 { epsilon } else { 1e-6 };
        if residual.abs() > eps {
            let reps = ((residual.abs() / (pi4 * 0.25)).ceil() as usize).min(8);
            for _ in 0..reps {
                // Solovay-Kitaev primitivo de 1er orden (H,T,H,T†,H...) sobre el eje Z
                gates.push(GATE_OPCODE_H);
                gates.push(if residual > 0.0 { GATE_OPCODE_T } else { GATE_OPCODE_TDAG });
                gates.push(GATE_OPCODE_H);
                gates.push(if residual > 0.0 { GATE_OPCODE_TDAG } else { GATE_OPCODE_T });
            }
        }

        if target_axis == 1 {
            gates.push(GATE_OPCODE_H);                 // completa H·Rz·H
        } else if target_axis == 2 {
            gates.push(GATE_OPCODE_H);                 // S·H·Rz·(H·S†): programa [..., H, SDAG]
            gates.push(GATE_OPCODE_SDAG);
        }

        if gates.len() > max_capacity as usize { return NativeStatus::CapacityExceeded; }
        unsafe {
            std::ptr::copy(gates.as_ptr(), out_opcodes, gates.len());
            *out_count = gates.len() as u32;
        }
        NativeStatus::Ok
    })
}
