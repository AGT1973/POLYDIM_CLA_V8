// POLYDIM V800 - Production Rust Guard Kernel (Vardi-Zhang Weiszfeld + Iterative DSU + Fréchet-Betti BFT Consensus)

use std::panic::catch_unwind;

#[no_mangle]
pub extern "C" fn polydim_validate_tensor_v800(d: i64, k: i64, expected_bytes: usize) -> i32 {
    let result = catch_unwind(|| {
        if d <= 0 || k <= 0 { return -3; }
        if let Some(total) = d.checked_mul(k) {
            if let Some(bytes) = total.checked_mul(8) {
                if bytes as usize == expected_bytes { return 0; }
            }
        }
        -3
    });
    result.unwrap_or(-1)
}

#[no_mangle]
pub extern "C" fn polydim_higham_bound_v800(d: i64) -> f64 {
    let result = catch_unwind(|| {
        if d <= 0 { return 0.0; }
        50.0 * (d as f64).log2().ceil() * (f64::EPSILON / 2.0)
    });
    result.unwrap_or(0.0)
}

#[no_mangle]
pub extern "C" fn polydim_weiszfeld_swap_v800(ptr_a: *mut *mut f64, ptr_b: *mut *mut f64) -> i32 {
    let result = catch_unwind(|| {
        if ptr_a.is_null() || ptr_b.is_null() { return -1; }
        unsafe {
            let tmp = *ptr_a;
            *ptr_a = *ptr_b;
            *ptr_b = tmp;
        }
        0
    });
    result.unwrap_or(-1)
}

struct IterativeDSU {
    parent: Vec<i64>,
    size: Vec<i64>,
}

impl IterativeDSU {
    fn new(n: i64) -> Self {
        Self {
            parent: (0..n).collect(),
            size: vec![1; n as usize],
        }
    }

    fn find(&mut self, mut i: i64) -> i64 {
        let mut root = i;
        while self.parent[root as usize] != root {
            root = self.parent[root as usize];
        }
        let mut curr = i;
        while curr != root {
            let nxt = self.parent[curr as usize];
            self.parent[curr as usize] = root;
            curr = nxt;
        }
        root
    }

    fn union(&mut self, i: i64, j: i64) -> bool {
        let mut root_i = self.find(i);
        let mut root_j = self.find(j);
        if root_i != root_j {
            if self.size[root_i as usize] < self.size[root_j as usize] {
                std::mem::swap(&mut root_i, &mut root_j);
            }
            self.parent[root_j as usize] = root_i;
            self.size[root_i as usize] += self.size[root_j as usize];
            true
        } else {
            false
        }
    }
}

#[no_mangle]
pub extern "C" fn polydim_rust_iterative_dsu_betti(
    edges_ptr: *const [i64; 2],
    n_edges: i64,
    n_vertices: i64,
    out_beta0: *mut i64,
    out_beta1: *mut i64,
) -> i32 {
    let result = catch_unwind(|| {
        if edges_ptr.is_null() || out_beta0.is_null() || out_beta1.is_null() { return -1; }
        if n_vertices < 0 || n_edges < 0 { return -1; }

        let edges = unsafe { std::slice::from_raw_parts(edges_ptr, n_edges as usize) };
        let mut dsu = IterativeDSU::new(n_vertices);

        let mut components = n_vertices;
        for edge in edges {
            let u = edge[0];
            let v = edge[1];
            if u < 0 || u >= n_vertices || v < 0 || v >= n_vertices { return -1; }
            if dsu.union(u, v) { components -= 1; }
        }

        unsafe {
            *out_beta0 = components;
            *out_beta1 = n_edges - n_vertices + components;
        }
        0
    });
    result.unwrap_or(-1)
}

#[no_mangle]
pub extern "C" fn polydim_rust_frechet_betti_filter(
    agents_ptr: *const f64,
    d: i64,
    n_agents: i64,
    _k_neighbors: i64,
    cos_threshold: f64,
    out_median: *mut f64,
    out_n_inliers: *mut i64,
) -> i32 {
    let result = catch_unwind(|| {
        if agents_ptr.is_null() || out_median.is_null() || out_n_inliers.is_null() { return -1; }
        if d <= 0 || n_agents <= 0 { return -1; }

        let agents = unsafe { std::slice::from_raw_parts(agents_ptr, (n_agents * d) as usize) };
        
        let mut cur_median = vec![0.0; d as usize];
        for i in 0..n_agents {
            let offset = (i * d) as usize;
            for j in 0..(d as usize) {
                cur_median[j] += agents[offset + j] / (n_agents as f64);
            }
        }

        let epsilon = 1e-14;
        
        for _ in 0..200 {
            let mut next_median = vec![0.0; d as usize];
            let mut weight_sum = 0.0;

            for i in 0..n_agents {
                let offset = (i * d) as usize;
                let mut dist_sq = 0.0;
                for j in 0..(d as usize) {
                    let diff = agents[offset + j] - cur_median[j];
                    dist_sq += diff * diff;
                }
                let dist = dist_sq.sqrt();
                if dist > epsilon {
                    let w = 1.0 / dist;
                    weight_sum += w;
                    for j in 0..(d as usize) {
                        next_median[j] += agents[offset + j] * w;
                    }
                }
            }

            if weight_sum > 0.0 {
                for j in 0..(d as usize) {
                    next_median[j] /= weight_sum;
                }
            } else {
                break;
            }

            let mut shift_sq = 0.0;
            let mut cur_norm_sq = 0.0;
            for j in 0..(d as usize) {
                let diff = next_median[j] - cur_median[j];
                shift_sq += diff * diff;
                cur_norm_sq += cur_median[j] * cur_median[j];
            }

            cur_median = next_median;

            let cur_norm = cur_norm_sq.sqrt();
            let shift_norm = shift_sq.sqrt();
            if cur_norm > 0.0 && shift_norm / cur_norm < 1e-12 { break; }
            else if cur_norm == 0.0 && shift_norm < 1e-12 { break; }
        }

        let mut dsu = IterativeDSU::new(n_agents);
        for i in 0..n_agents {
            for j in (i + 1)..n_agents {
                let offset_i = (i * d) as usize;
                let offset_j = (j * d) as usize;
                let mut dot = 0.0;
                let mut norm_i_sq = 0.0;
                let mut norm_j_sq = 0.0;
                for c in 0..(d as usize) {
                    let vi = agents[offset_i + c];
                    let vj = agents[offset_j + c];
                    dot += vi * vj;
                    norm_i_sq += vi * vi;
                    norm_j_sq += vj * vj;
                }
                let norm_i = norm_i_sq.sqrt();
                let norm_j = norm_j_sq.sqrt();
                if norm_i > 0.0 && norm_j > 0.0 {
                    let cos_sim = dot / (norm_i * norm_j);
                    if cos_sim >= cos_threshold {
                        dsu.union(i, j);
                    }
                }
            }
        }

        let mut giant_comp = 0;
        let mut max_size = 0;
        for i in 0..n_agents {
            let root = dsu.find(i);
            let s = dsu.size[root as usize];
            if s > max_size {
                max_size = s;
                giant_comp = root;
            }
        }

        let mut inlier_count = 0;
        for i in 0..n_agents {
            if dsu.find(i) == giant_comp {
                inlier_count += 1;
            }
        }
        
        unsafe {
            for j in 0..(d as usize) {
                *out_median.add(j) = cur_median[j];
            }
            *out_n_inliers = inlier_count;
        }
        0
    });
    result.unwrap_or(-1)
}
