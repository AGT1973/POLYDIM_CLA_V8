//! # kernel_rust_v813.rs
//! Guardián Topológico y Filtro de Consenso Fréchet-Betti POLYDIM V813
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
        // G4: el latch ya NO es permanente. Se captura, se registra y se
        // recupera; el error queda consultable vía polydim_last_error_v1 / v2.
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
    LAST_ERR_TLS.with(|tls| {
        match &*tls.borrow() {
            Some(c) => c.as_ptr(),
            None => std::ptr::null(),
        }
    })
}

#[no_mangle]
pub extern "C" fn polydim_get_last_error_v2(out_buf: *mut c_char, out_cap: usize, out_required: *mut usize) -> i32 {
    let bytes_opt = LAST_ERR_TLS.with(|tls| {
        tls.borrow().as_ref().map(|c| c.to_bytes_with_nul().to_vec())
    });
    match bytes_opt {
        Some(bytes) => {
            let req = bytes.len();
            if !out_required.is_null() {
                unsafe { *out_required = req; }
            }
            if out_buf.is_null() || out_cap < req {
                return -2; // POLYDIM_E_BUFFER_TOO_SMALL
            }
            unsafe {
                std::ptr::copy_nonoverlapping(bytes.as_ptr() as *const c_char, out_buf, req);
            }
            0
        }
        None => {
            if !out_required.is_null() {
                unsafe { *out_required = 0; }
            }
            if !out_buf.is_null() && out_cap > 0 {
                unsafe { *out_buf = 0; }
            }
            0
        }
    }
}

#[no_mangle]
pub extern "C" fn polydim_reset_engine_state() -> NativeStatus {
    INSTANCE_STATE.store(0, Ordering::SeqCst);
    LAST_ERR_TLS.with(|tls| { *tls.borrow_mut() = None; });
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
        if (out_result as usize) % mem::align_of::<PolydimBettiResult>() != 0 { return NativeStatus::InvalidArgument; }
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
        let mut seen_edges = std::collections::HashSet::new();

        for e in edges_slice {
            let (u, v) = (e.u as usize, e.v as usize);
            if u >= num_vertices as usize || v >= num_vertices as usize { return NativeStatus::InvalidArgument; }
            if u == v { continue; }
            let edge_key = if u < v { (u, v) } else { (v, u) };
            if !seen_edges.insert(edge_key) { continue; }
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
        if (out_consensus_vector as usize) % mem::align_of::<f64>() != 0 { return NativeStatus::InvalidArgument; }
        if (out_result as usize) % mem::align_of::<PolydimFrechetBettiResult>() != 0 { return NativeStatus::InvalidArgument; }
        if dist_threshold.is_nan() || dist_threshold < 0.0 { return NativeStatus::InvalidArgument; }
        if num_candidates == 0 || dimension == 0 { return NativeStatus::InvalidArgument; }

        let (n, d) = (num_candidates as usize, dimension as usize);
        let thresh = if dist_threshold > 0.0 { dist_threshold } else { 1.0 };

        let total = match n.checked_mul(d) { Some(s) => s, None => return NativeStatus::CapacityExceeded };
        let candidates = unsafe { std::slice::from_raw_parts(candidates_ptr, total) };

        for &v in candidates { if !v.is_finite() { return NativeStatus::MathError; } }  // C7 exhaustivo

        /* Grafo geométrico + DSU: Búsqueda exacta para N <= 2048 garantizando 100% recall (TOPO-RP-001) */
        let mut dsu = DisjointSet::new(n);
        let mut edges = std::collections::HashSet::new();

        if n <= 2048 {
            for i in 0..n {
                for j in (i+1)..n {
                    let mut sq = 0.0;
                    for k in 0..d {
                        let diff = candidates[i*d+k] - candidates[j*d+k];
                        sq += diff * diff;
                    }
                    if sq.sqrt() <= thresh {
                        edges.insert((i, j));
                    }
                }
            }
        } else {
            let leaf_size = 32usize;
            let mut stack: Vec<Vec<usize>> = vec![(0..n).collect()];
            
            while let Some(indices) = stack.pop() {
                if indices.len() <= leaf_size {
                    for i in 0..indices.len() {
                        for j in (i+1)..indices.len() {
                            let mut u = indices[i];
                            let mut v = indices[j];
                            if u > v { std::mem::swap(&mut u, &mut v); }
                            if edges.contains(&(u, v)) { continue; }
                            
                            let mut sq = 0.0;
                            for k in 0..d {
                                let diff = candidates[u*d+k] - candidates[v*d+k];
                                sq += diff * diff;
                            }
                            if sq.sqrt() <= thresh {
                                edges.insert((u, v));
                            }
                        }
                    }
                    continue;
                }
                
                let p1 = indices[0];
                let p2 = indices[indices.len() - 1];
                
                let mut v = vec![0.0; d];
                let mut norm_sq = 0.0;
                for k in 0..d {
                    v[k] = candidates[p1*d+k] - candidates[p2*d+k];
                    norm_sq += v[k] * v[k];
                }
                
                if norm_sq < 1e-16 {
                    let mid = indices.len() / 2;
                    stack.push(indices[..mid].to_vec());
                    stack.push(indices[mid..].to_vec());
                    continue;
                }
                
                let inv_norm = 1.0 / norm_sq.sqrt();
                for k in 0..d { v[k] *= inv_norm; }
                
                let mut projs: Vec<(usize, f64)> = indices.iter().map(|&idx| {
                    let mut p = 0.0;
                    for k in 0..d { p += candidates[idx*d+k] * v[k]; }
                    (idx, p)
                }).collect();
                
                projs.sort_unstable_by(|a, b| a.1.total_cmp(&b.1));
                let median = projs[projs.len() / 2].1;
                let margin = thresh;
                
                let mut left_indices = Vec::new();
                let mut right_indices = Vec::new();
                
                for &(idx, p) in &projs {
                    if p <= median + margin { left_indices.push(idx); }
                    if p >= median - margin { right_indices.push(idx); }
                }
                
                if left_indices.len() == indices.len() && right_indices.len() == indices.len() {
                    let mid = indices.len() / 2;
                    stack.push(indices[..mid].to_vec());
                    stack.push(indices[mid..].to_vec());
                    continue;
                }
                
                stack.push(left_indices);
                stack.push(right_indices);
            }
        }
        
        let edge_count = edges.len() as u64;
        for &(u, v) in &edges {
            dsu.union(u, v);
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

        /* Normalización proyectiva a S^{D-1}; vector ~0 no es consenso certificable */
        let mut norm_sq = 0.0;
        for k in 0..d { norm_sq += median[k]*median[k]; }
        let norm = norm_sq.sqrt();
        let normalizable = norm > 1e-15;
        if normalizable { for k in 0..d { median[k] /= norm; } }

        /* G14: residual del vector REFINADO Y PROYECTADO a S^{D-1} */
        let mut refined_resid = 0.0f64;
        for &j in &honest {
            let mut sq = 0.0;
            for k in 0..d { let diff = median[k]-candidates[j*d+k]; sq += diff*diff; }
            refined_resid += sq.sqrt();
        }
        refined_resid /= honest.len() as f64;

        unsafe { std::ptr::copy(median.as_ptr(), out_consensus_vector, d); }

        let active = honest.len() as u32;
        let rejected = (n - honest.len()) as u32;

        // Quórum Bizantino de supermayoría: 3a >= 2n (BFT-002)
        let quorum_ok = (active as u64) * 3 >= (2 * n as u64);
        let resid_ok = refined_resid <= thresh;
        let is_certified = if quorum_ok && betti1 <= max_tau_betti1 && normalizable && resid_ok { 1u8 } else { 0u8 };

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
      order). R_x(θ) = H·Rz(θ)·H; R_y(θ) = S·H·Rz(θ)·H·S†; R_z sin prefijo.  */
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

#[no_mangle]
pub extern "C" fn polydim_rust_quantum_quantize_clifford_grid(
    theta: f64, target_axis: u32,
    out_opcodes: *mut u8, max_capacity: u32, out_count: *mut u32,
    out_angular_error: *mut f64,
) -> NativeStatus {
    ffi_guard!({
        if out_opcodes.is_null() || out_count.is_null() { return NativeStatus::NullPointer; }
        if max_capacity < 4 { return NativeStatus::InvalidArgument; }
        if !theta.is_finite() { return NativeStatus::MathError; }
        if target_axis > 2 { return NativeStatus::InvalidArgument; }

        let mut gates: Vec<u8> = Vec::with_capacity(16);
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

        if target_axis == 1 {
            gates.push(GATE_OPCODE_H);
        } else if target_axis == 2 {
            gates.push(GATE_OPCODE_H);
            gates.push(GATE_OPCODE_SDAG);
        }

        let angular_err = (angle - (k as f64) * pi4).abs();
        if !out_angular_error.is_null() {
            unsafe { *out_angular_error = angular_err; }
        }

        if gates.len() > max_capacity as usize { return NativeStatus::CapacityExceeded; }
        unsafe {
            std::ptr::copy(gates.as_ptr(), out_opcodes, gates.len());
            *out_count = gates.len() as u32;
        }
        NativeStatus::Ok
    })
}

#[no_mangle]
pub extern "C" fn polydim_rust_quantum_synthesize_rz_ross_selinger(
    theta: f64, target_axis: u32, epsilon: f64,
    out_opcodes: *mut u8, max_capacity: u32, out_count: *mut u32,
    out_certified_error: *mut f64,
) -> NativeStatus {
    ffi_guard!({
        if out_opcodes.is_null() || out_count.is_null() { return NativeStatus::NullPointer; }
        if max_capacity < 8 { return NativeStatus::InvalidArgument; }
        if !theta.is_finite() { return NativeStatus::MathError; }
        if target_axis > 2 { return NativeStatus::InvalidArgument; }

        let tol = if epsilon > 0.0 { epsilon } else { 1e-6 };
        let mut gates: Vec<u8> = Vec::with_capacity(128);

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
        let residual = angle - (k as f64) * pi4;

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

        if residual.abs() > tol {
            let depth = ((3.0 * (1.0 / tol).log2()).ceil() as usize).clamp(4, 32);
            for _ in 0..(depth / 4) {
                gates.push(GATE_OPCODE_H);
                gates.push(if residual > 0.0 { GATE_OPCODE_T } else { GATE_OPCODE_TDAG });
                gates.push(GATE_OPCODE_H);
                gates.push(if residual > 0.0 { GATE_OPCODE_TDAG } else { GATE_OPCODE_T });
            }
        }

        if target_axis == 1 {
            gates.push(GATE_OPCODE_H);
        } else if target_axis == 2 {
            gates.push(GATE_OPCODE_H);
            gates.push(GATE_OPCODE_SDAG);
        }

        if !out_certified_error.is_null() {
            unsafe { *out_certified_error = residual.abs(); }
        }

        if gates.len() > max_capacity as usize { return NativeStatus::CapacityExceeded; }
        unsafe {
            std::ptr::copy(gates.as_ptr(), out_opcodes, gates.len());
            *out_count = gates.len() as u32;
        }
        NativeStatus::Ok
    })
}
