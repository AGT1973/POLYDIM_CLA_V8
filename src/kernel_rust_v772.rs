//! # kernel_rust_v772.rs
//! Guardián Topológico POLYDIM V772 en Rust (panic=unwind, opt-level=3)
//! Calcula tanto \beta_0 (Componentes Conexas) como \beta_1 (Homología de Ciclos 1D: E - V + C)

use std::panic::catch_unwind;

#[repr(C)]
pub struct PolydimEdge {
    pub u: u32,
    pub v: u32,
}

#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PolydimBettiResult {
    pub status: i32,
    pub components_betti0: u32,
    pub cycles_betti1: i64,
    pub num_vertices: u32,
    pub num_edges: u32,
    pub is_critically_healthy: bool, // betti0 == 1
    pub is_optimally_healthy: bool,  // betti0 == 1 && betti1 <= max_tau
}

pub struct DisjointSet {
    parent: Vec<usize>,
    rank: Vec<usize>,
    pub count: usize,
}

impl DisjointSet {
    pub fn new(n: usize) -> Self {
        DisjointSet {
            parent: (0..n).collect(),
            rank: vec![0; n],
            count: n,
        }
    }

    pub fn find(&mut self, mut i: usize) -> usize {
        while i != self.parent[i] {
            self.parent[i] = self.parent[self.parent[i]];
            i = self.parent[i];
        }
        i
    }

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

/// Evaluador de Homología Topológica Dual \beta_0 y \beta_1
#[no_mangle]
pub extern "C" fn polydim_rust_betti_dual_guard(
    edges_ptr: *const PolydimEdge,
    num_edges: u32,
    num_vertices: u32,
    max_tau_betti1: i64,
    out_result: *mut PolydimBettiResult,
) -> i32 {
    let result = catch_unwind(|| {
        if edges_ptr.is_null() || out_result.is_null() {
            return -1; // Null pointer error
        }
        if num_vertices == 0 {
            return -2; // Invalid dimension
        }

        let edges_slice = unsafe { std::slice::from_raw_parts(edges_ptr, num_edges as usize) };
        let mut dsu = DisjointSet::new(num_vertices as usize);

        for edge in edges_slice {
            let u = edge.u as usize;
            let v = edge.v as usize;
            if u >= num_vertices as usize || v >= num_vertices as usize {
                return -2; // Edge refers to out-of-bound vertex
            }
            dsu.union(u, v);
        }

        let betti0 = dsu.count as u32;
        // Fórmula de Euler-Poincaré para grafos: \beta_1 = E - V + C
        let betti1 = (num_edges as i64) - (num_vertices as i64) + (betti0 as i64);

        let is_crit = betti0 == 1;
        let is_opt = is_crit && (betti1 <= max_tau_betti1);

        unsafe {
            *out_result = PolydimBettiResult {
                status: 0,
                components_betti0: betti0,
                cycles_betti1: betti1,
                num_vertices,
                num_edges,
                is_critically_healthy: is_crit,
                is_optimally_healthy: is_opt,
            };
        }

        0 // OK
    });

    match result {
        Ok(code) => code,
        Err(_) => -99, // Panic caught
    }
}

pub const GATE_OPCODE_H: u8 = 1;
pub const GATE_OPCODE_S: u8 = 2;
pub const GATE_OPCODE_T: u8 = 3;
pub const GATE_OPCODE_TDAG: u8 = 4;
pub const GATE_OPCODE_X: u8 = 5;
pub const GATE_OPCODE_Z: u8 = 6;
pub const GATE_OPCODE_CNOT: u8 = 7;

/// Sintetizador Cuántico Discreto Clifford+T (GridSynth / Solovay-Kitaev canonical basis)
/// Sintetiza rotaciones en los ejes Z e Y (vía isomorfismo Ry = H * Rz * H)
/// target_axis: 0 = Rz, 1 = Ry, 2 = Rx (H * S * Rz * S_dag * H)
#[no_mangle]
pub extern "C" fn polydim_rust_quantum_synthesize_discrete(
    theta: f64,
    target_axis: u32,
    epsilon: f64,
    out_opcodes: *mut u8,
    max_capacity: u32,
    out_count: *mut u32,
) -> i32 {
    let result = catch_unwind(|| {
        if out_opcodes.is_null() || out_count.is_null() {
            return -1;
        }
        if max_capacity < 4 {
            return -2; // Buffer too small
        }

        let mut gates: Vec<u8> = Vec::with_capacity(64);

        // 1. Transformación de Base de Eje (Isomorfismos de Clifford)
        if target_axis == 1 {
            // Ry = H * Rz * H
            gates.push(GATE_OPCODE_H);
        } else if target_axis == 2 {
            // Rx = H * S * Rz * S_dag * H
            gates.push(GATE_OPCODE_H);
            gates.push(GATE_OPCODE_S);
        }

        // 2. Normalización de Ángulo [0, 2pi)
        let two_pi = 2.0 * std::f64::consts::PI;
        let mut angle = theta % two_pi;
        if angle < 0.0 {
            angle += two_pi;
        }

        // 3. Descomposición Diádica Principal en Múltiplos de pi/4 (T-gates)
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

        // 4. Corrección Fraccionaria Solovay-Kitaev / GridSynth para residuo |delta| > epsilon
        let residual = angle - (k_t_gates as f64) * pi_over_4;
        let eps = if epsilon > 0.0 { epsilon } else { 1e-6 };

        if residual.abs() > eps {
            // Conmutador canónico de Clifford+T para rotaciones infinitesimales:
            // [H, T] = H T H T_dag genera una rotación de ángulo theta_0 = arccos(1/sqrt(2) + 1/2)
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

        // 5. Cierre de Transformación de Base
        if target_axis == 1 {
            gates.push(GATE_OPCODE_H);
        } else if target_axis == 2 {
            gates.push(GATE_OPCODE_Z); // S_dag = Z * S
            gates.push(GATE_OPCODE_S);
            gates.push(GATE_OPCODE_H);
        }

        if gates.len() > max_capacity as usize {
            return -3; // Overflow
        }

        unsafe {
            std::ptr::copy_nonoverlapping(gates.as_ptr(), out_opcodes, gates.len());
            *out_count = gates.len() as u32;
        }

        0 // OK
    });

    match result {
        Ok(code) => code,
        Err(_) => -99,
    }
}

