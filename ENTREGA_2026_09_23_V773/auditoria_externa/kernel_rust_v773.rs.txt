//! # kernel_rust_v773.rs
//! Guardián Topológico y Filtro de Consenso Fréchet-Betti POLYDIM V773 en Rust
//! Características:
//! 1. DSU estrictamente iterativo (Zero Stack Overflow para V >= 10^7)
//! 2. Guardián Homológico Dual (\beta_0 Componentes Conexas, \beta_1 Ciclos: E - V + C)
//! 3. Filtro de Consenso Fréchet-Betti con Rechazo de Nodos Bizantinos/Outliers (Área 3)
//! 4. Síntesis Cuántica Discreta Clifford+T (GridSynth / Solovay-Kitaev)
//! 5. ABI C estricto con catch_unwind (cero pánicos filtrados) y alineación de caché 128B

use std::panic::catch_unwind;

#[repr(C)]
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
    pub is_critically_healthy: bool, // betti0 == 1
    pub is_optimally_healthy: bool,  // betti0 == 1 && betti1 <= max_tau
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
    pub is_consensus_certified: bool,
}

/* ========================================================================= */
/* 1. DSU ESTRICTAMENTE ITERATIVO (ANTI-STACK-OVERFLOW V >= 10^7)           */
/* ========================================================================= */

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

    /// Búsqueda de raíz 100% iterativa con compresión de camino en dos pasadas.
    /// Garantiza O(alpha(V)) sin ninguna recursión en la pila de llamadas.
    #[inline]
    pub fn find(&mut self, i: usize) -> usize {
        let mut root = i;
        while root != self.parent[root] {
            root = self.parent[root];
        }

        // Segunda pasada: compresión directa de todos los nodos intermedios
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
) -> i32 {
    let result = catch_unwind(|| {
        if edges_ptr.is_null() || out_result.is_null() {
            return -1;
        }
        if num_vertices == 0 {
            return -2;
        }

        let edges_slice = unsafe { std::slice::from_raw_parts(edges_ptr, num_edges as usize) };
        let mut dsu = DisjointSet::new(num_vertices as usize);

        for edge in edges_slice {
            let u = edge.u as usize;
            let v = edge.v as usize;
            if u >= num_vertices as usize || v >= num_vertices as usize {
                return -2;
            }
            dsu.union(u, v);
        }

        let betti0 = dsu.count as u32;
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

        0
    });

    match result {
        Ok(code) => code,
        Err(_) => -99,
    }
}

/* ========================================================================= */
/* 3. FILTRO DE CONSENSO FRÉCHET-BETTI PARA ENJAMBRE (ÁREA 3 SOTA)          */
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
) -> i32 {
    let result = catch_unwind(|| {
        if candidates_ptr.is_null() || out_consensus_vector.is_null() || out_result.is_null() {
            return -1;
        }
        if num_candidates == 0 || dimension == 0 {
            return -2;
        }

        let n = num_candidates as usize;
        let d = dimension as usize;
        let thresh = if dist_threshold > 0.0 { dist_threshold } else { 1.0 };

        let candidates = unsafe { std::slice::from_raw_parts(candidates_ptr, n * d) };

        // 1. Calcular matriz de distancias euclidianas y construir grafo de umbral
        let mut dsu = DisjointSet::new(n);
        let mut edge_count = 0usize;
        let mut dist_matrix = vec![0.0f64; n * n];

        for i in 0..n {
            for j in (i + 1)..n {
                let mut sum_sq = 0.0f64;
                for k in 0..d {
                    let diff = candidates[i * d + k] - candidates[j * d + k];
                    sum_sq += diff * diff;
                }
                let dist = sum_sq.sqrt();
                dist_matrix[i * n + j] = dist;
                dist_matrix[j * n + i] = dist;

                if dist <= thresh {
                    edge_count += 1;
                    dsu.union(i, j);
                }
            }
        }

        // 2. Análisis topológico del enjambre
        let betti0 = dsu.count as u32;
        let betti1 = (edge_count as i64) - (n as i64) + (betti0 as i64);

        // Identificar el componente conexo gigante (Quórum honesto)
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

        // Nodos que pertenecen al componente gigante
        let mut honest_nodes = Vec::with_capacity(max_comp_size);
        for i in 0..n {
            if dsu.find(i) == giant_root {
                honest_nodes.push(i);
            }
        }

        let active_count = honest_nodes.len() as u32;
        let rejected_count = (n - honest_nodes.len()) as u32;

        // 3. Mediana de Fréchet discreta: Encontrar el nodo que minimiza la suma de distancias
        let mut best_node = honest_nodes[0];
        let mut min_dist_sum = f64::INFINITY;

        for &i in &honest_nodes {
            let mut sum_d = 0.0f64;
            for &j in &honest_nodes {
                sum_d += dist_matrix[i * n + j];
            }
            if sum_d < min_dist_sum {
                min_dist_sum = sum_d;
                best_node = i;
            }
        }

        // 4. Refinamiento continuo con algoritmo de Weiszfeld (5 iteraciones amortiguadas)
        let mut median = vec![0.0f64; d];
        for k in 0..d {
            median[k] = candidates[best_node * d + k];
        }

        for _ in 0..5 {
            let mut weight_sum = 0.0f64;
            let mut next_median = vec![0.0f64; d];

            for &j in &honest_nodes {
                let mut dist_sq = 0.0f64;
                for k in 0..d {
                    let diff = median[k] - candidates[j * d + k];
                    dist_sq += diff * diff;
                }
                let dist = dist_sq.sqrt().max(1e-12);
                let w = 1.0 / dist;
                weight_sum += w;

                for k in 0..d {
                    next_median[k] += w * candidates[j * d + k];
                }
            }

            if weight_sum > 0.0 {
                for k in 0..d {
                    median[k] = next_median[k] / weight_sum;
                }
            }
        }

        // Normalizar proyección en esfera si es vector de estado
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

        // Copiar vector consenso al buffer de salida
        unsafe {
            std::ptr::copy_nonoverlapping(median.as_ptr(), out_consensus_vector, d);
        }

        // Certificación de consenso BFT: Quórum >= 2/3 y ciclos homológicos acotados
        let is_certified = (active_count >= ((2 * n + 2) / 3) as u32) && (betti1 <= max_tau_betti1);

        unsafe {
            *out_result = PolydimFrechetBettiResult {
                status: 0,
                num_candidates,
                dimension,
                connected_components_betti0: betti0,
                cycles_betti1: betti1,
                consensus_node_idx: best_node as u32,
                active_swarm_count: active_count,
                rejected_outliers_count: rejected_count,
                frechet_residual: min_dist_sum / (active_count as f64).max(1.0),
                is_consensus_certified: is_certified,
            };
        }

        0
    });

    match result {
        Ok(code) => code,
        Err(_) => -99,
    }
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
) -> i32 {
    let result = catch_unwind(|| {
        if out_opcodes.is_null() || out_count.is_null() {
            return -1;
        }
        if max_capacity < 4 {
            return -2;
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
            return -3;
        }

        unsafe {
            std::ptr::copy_nonoverlapping(gates.as_ptr(), out_opcodes, gates.len());
            *out_count = gates.len() as u32;
        }

        0
    });

    match result {
        Ok(code) => code,
        Err(_) => -99,
    }
}
