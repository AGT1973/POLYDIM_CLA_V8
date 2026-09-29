//! kernel_rust_v815.rs
//! Kernel Topológico Rust POLYDIM V815 (Master Release)
//! Guardián de Invariantes Topológicas, Betti-1 Flat DSU y Filtro Fréchet-BFT

use std::cell::RefCell;
use std::collections::HashSet;
use std::ffi::CString;
use std::os::raw::{c_char, c_double, c_int, c_longlong, c_uint};
use std::panic::catch_unwind;

thread_local! {
    static LAST_ERR_STR: RefCell<Option<CString>> = RefCell::new(None);
}

fn set_last_error(msg: &str) {
    LAST_ERR_STR.with(|cell| {
        let c_str = CString::new(msg).unwrap_or_else(|_| CString::new("Error parsing error string").unwrap());
        *cell.borrow_mut() = Some(c_str);
    });
}

#[no_mangle]
pub extern "C" fn polydim_rust_get_last_error() -> *const c_char {
    LAST_ERR_STR.with(|cell| {
        match cell.borrow().as_ref() {
            Some(c_str) => c_str.as_ptr(),
            None => std::ptr::null(),
        }
    })
}

#[repr(C, align(8))]
#[derive(Debug, Clone)]
pub struct PolydimFrechetBettiResultV815 {
    pub status: c_int,
    pub num_candidates: c_uint,
    pub dimension: c_uint,
    pub connected_components_betti0: c_uint,
    pub cycles_betti1: c_longlong,
    pub consensus_node_idx: c_uint,
    pub active_swarm_count: c_uint,
    pub rejected_outliers_count: c_uint,
    pub frechet_residual: c_double,
    pub is_consensus_certified: u8,
    pub pad: [u8; 79],
}

impl Default for PolydimFrechetBettiResultV815 {
    fn default() -> Self {
        Self {
            status: 0,
            num_candidates: 0,
            dimension: 0,
            connected_components_betti0: 0,
            cycles_betti1: 0,
            consensus_node_idx: 0,
            active_swarm_count: 0,
            rejected_outliers_count: 0,
            frechet_residual: 0.0,
            is_consensus_certified: 0,
            pad: [0u8; 79],
        }
    }
}

pub struct FlatDsu {
    parent: Vec<usize>,
    rank: Vec<u8>,
}

impl FlatDsu {
    pub fn new(n: usize) -> Self {
        Self {
            parent: (0..n).collect(),
            rank: vec![0; n],
        }
    }

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
        true
    }
}

#[no_mangle]
pub extern "C" fn polydim_rust_compute_betti_flat_v815(
    num_nodes: c_uint,
    edges_u64_ptr: *const u64,
    num_edges: c_uint,
    betti0_out: *mut c_uint,
    betti1_out: *mut c_longlong,
) -> c_int {
    let result = catch_unwind(|| {
        if edges_u64_ptr.is_null() || betti0_out.is_null() || betti1_out.is_null() {
            set_last_error("Null pointer provided to polydim_rust_compute_betti_flat_v815");
            return -1;
        }

        let n = num_nodes as usize;
        let m = num_edges as usize;
        let edges_slice = unsafe { std::slice::from_raw_parts(edges_u64_ptr, m) };

        let mut dsu = FlatDsu::new(n);
        let mut unique_edges = HashSet::with_capacity(m);
        let mut num_trees_edges = 0usize;

        for &packed in edges_slice {
            let u = (packed >> 32) as usize;
            let v = (packed & 0xFFFF_FFFF) as usize;
            if u >= n || v >= n || u == v {
                continue;
            }
            let canonical = if u < v { (u, v) } else { (v, u) };
            if !unique_edges.insert(canonical) {
                continue;
            }
            if dsu.union(u, v) {
                num_trees_edges += 1;
            }
        }

        let mut roots = HashSet::new();
        for i in 0..n {
            roots.insert(dsu.find(i));
        }

        let betti0 = roots.len();
        let total_unique_edges = unique_edges.len();
        let betti1 = (total_unique_edges as i64) - (num_trees_edges as i64);

        unsafe {
            *betti0_out = betti0 as c_uint;
            *betti1_out = betti1 as c_longlong;
        }

        0
    });

    match result {
        Ok(code) => code,
        Err(_) => {
            set_last_error("Panic caught in polydim_rust_compute_betti_flat_v815");
            -99
        }
    }
}

#[no_mangle]
pub extern "C" fn polydim_rust_frechet_betti_filter_v815(
    candidates_ptr: *const c_double,
    num_candidates: c_uint,
    dimension: c_uint,
    radius: c_double,
    max_iter: c_longlong,
    consensus_out_ptr: *mut c_double,
    result_out: *mut PolydimFrechetBettiResultV815,
) -> c_int {
    let outcome = catch_unwind(|| {
        if candidates_ptr.is_null() || consensus_out_ptr.is_null() || result_out.is_null() {
            set_last_error("Null pointer provided to polydim_rust_frechet_betti_filter_v815");
            return -1;
        }

        let n = num_candidates as usize;
        let d = dimension as usize;
        if n == 0 || d == 0 {
            set_last_error("Invalid candidate count or dimension");
            return -2;
        }

        let total_len = n * d;
        let raw_slice = unsafe { std::slice::from_raw_parts(candidates_ptr, total_len) };

        // 1. Promedio Fréchet Esférico inicial
        let mut mean_vec = vec![0.0f64; d];
        for i in 0..n {
            let row = &raw_slice[i * d..(i + 1) * d];
            for k in 0..d {
                mean_vec[k] += row[k];
            }
        }
        let norm_mean: f64 = mean_vec.iter().map(|&x| x * x).sum::<f64>().sqrt();
        if norm_mean > 1e-15 {
            for k in 0..d {
                mean_vec[k] /= norm_mean;
            }
        }

        // 2. Iteración Weiszfeld adaptativa
        let iterations = if max_iter > 0 { max_iter as usize } else { 10 };
        for _ in 0..iterations {
            let mut next_vec = vec![0.0f64; d];
            let mut total_weight = 0.0f64;
            for i in 0..n {
                let row = &raw_slice[i * d..(i + 1) * d];
                let dist: f64 = mean_vec.iter().zip(row.iter()).map(|(a, b)| (a - b).powi(2)).sum::<f64>().sqrt();
                let w = if dist > 1e-12 { 1.0 / dist } else { 1.0 / 1e-12 };
                total_weight += w;
                for k in 0..d {
                    next_vec[k] += w * row[k];
                }
            }
            if total_weight > 0.0 {
                let norm_next: f64 = next_vec.iter().map(|&x| x * x).sum::<f64>().sqrt();
                if norm_next > 1e-15 {
                    for k in 0..d {
                        mean_vec[k] = next_vec[k] / norm_next;
                    }
                }
            }
        }

        // 3. Evaluar Residual de Fréchet y Grafo de Proximidad
        let mut packed_edges = Vec::new();
        let mut residual = 0.0f64;
        let mut inlier_count = 0usize;

        for i in 0..n {
            let row_i = &raw_slice[i * d..(i + 1) * d];
            let dist_to_mean: f64 = mean_vec.iter().zip(row_i.iter()).map(|(a, b)| (a - b).powi(2)).sum::<f64>().sqrt();
            residual += dist_to_mean;
            if dist_to_mean <= radius {
                inlier_count += 1;
            }

            for j in (i + 1)..n {
                let row_j = &raw_slice[j * d..(j + 1) * d];
                let pair_dist: f64 = row_i.iter().zip(row_j.iter()).map(|(a, b)| (a - b).powi(2)).sum::<f64>().sqrt();
                if pair_dist <= radius {
                    let packed = ((i as u64) << 32) | (j as u64);
                    packed_edges.push(packed);
                }
            }
        }
        residual /= n as f64;

        // 4. Betti Invariants
        let mut b0: c_uint = 0;
        let mut b1: c_longlong = 0;
        let st = polydim_rust_compute_betti_flat_v815(
            n as c_uint,
            packed_edges.as_ptr(),
            packed_edges.len() as c_uint,
            &mut b0,
            &mut b1,
        );
        if st != 0 {
            return st;
        }

        // 5. Quórum BFT 3a >= 2n
        let is_certified = if (3 * inlier_count) >= (2 * n) && b0 == 1 { 1u8 } else { 0u8 };

        unsafe {
            std::ptr::copy_nonoverlapping(mean_vec.as_ptr(), consensus_out_ptr, d);
            let res = &mut *result_out;
            res.status = 0;
            res.num_candidates = n as c_uint;
            res.dimension = d as c_uint;
            res.connected_components_betti0 = b0;
            res.cycles_betti1 = b1;
            res.consensus_node_idx = 0;
            res.active_swarm_count = inlier_count as c_uint;
            res.rejected_outliers_count = (n - inlier_count) as c_uint;
            res.frechet_residual = residual;
            res.is_consensus_certified = is_certified;
        }

        0
    });

    match outcome {
        Ok(code) => code,
        Err(_) => {
            set_last_error("Panic caught in polydim_rust_frechet_betti_filter_v815");
            -99
        }
    }
}
