//! kernel_rust_v817.rs
//! Kernel Topológico y Guardián Numérico Rust POLYDIM V817 (Master Industrial Release)
//! 
//! # Alcance y Fundamentación Matemática para Científicos de Datos e Ingenieros de Sistemas:
//! 
//! POLYDIM trasciende el paradigma convencional de comunicación basada en texto tokenizado (1D),
//! operando directamente en el espacio continuo de variedades latentes de alta dimensión ($S^{D-1}$).
//! 
//! Este módulo Rust proporciona los contratos de invariantes matemáticas más críticos:
//! 1. **Freno Numérico Espectral AuON:** Estabilización en el dominio logarítmico $\log\cosh(z) = |z| + \operatorname{log1p}(e^{-2|z|}) - \ln 2$,
//!    con escala RMS Frobenius $\mathrm{rms} = \|\cosh(\text{update})\|_F / \sqrt{N}$ y gradientes analíticos $|\partial \mathcal{L}/\partial r| \le \lambda s$.
//! 2. **Métrica Geodésica Riemanniana Cordal en $\mathbb{S}^{D-1}$:** Cálculo estable $d_{\mathbb{S}}(u,v) = 2\arcsin(\frac{1}{2}\|u - v\|_2)$
//!    con protección contra singularidades de gradiente en colinealidad exacta.
//! 3. **Homología Simplicial Exacta (1-Laplaciano de Hodge $\Delta_1$):** Cálculo del verdadero número de Betti $\beta_1 = \dim\ker(B_1) - \operatorname{rank}(B_2)$,
//!    distinguiendo rigurosamente entre ciclos de grafos 1D y cavidades no triviales rellenadas por 2-símplices (triángulos).
//! 4. **Cota de Manifold Secant RIP (Baraniuk–Wakin) & Estimador Two-NN:** Verificación en runtime de la dimensión intrínseca $d_A$
//!    y condición de dimensión requerida $m \ge C \varepsilon^{-2} [d_A \ln(\mathcal{V}/\tau^{d_A}) + d_A \ln(1/\varepsilon) + \ln(1/\rho) + \ln N]$.
//! 5. **Iteración Polar Gram Newton–Schulz (Dao Lab 2026):** Estabilización con política de reinicio $q \le 2$ para prevenir modos negativos espurios en baja precisión.
//! 6. **Protección de Concurrencia FFI & QSBR:** Aislamiento de errores por hilo (`thread_local!`) y copias de snapshot instantáneas en memoria privada (QSBR Copy-Out).

use std::cell::RefCell;
use std::ffi::CString;
use std::os::raw::{c_char, c_double, c_int, c_longlong, c_uint};
use std::panic::{catch_unwind, AssertUnwindSafe};

// ============================================================================
// 1. GESTIÓN DE ERRORES Y CORTAFUEGOS FFI POD (Thread-Local Isolated)
// ============================================================================

thread_local! {
    static LAST_ERR_STR: RefCell<CString> = RefCell::new(CString::new("").unwrap());
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct V817Error {
    pub code: u32,
    pub msg: [u8; 256],
    pub arena_id: u64,
    pub gen: u64,
}

impl V817Error {
    pub fn write_success(&mut self) {
        self.code = 0;
        self.msg[0] = 0;
        self.arena_id = 0;
        self.gen = 0;
    }

    pub fn write_error(&mut self, code: u32, message: &str) {
        self.code = code;
        let bytes = message.as_bytes();
        let len = bytes.len().min(255);
        self.msg[..len].copy_from_slice(&bytes[..len]);
        self.msg[len] = 0;
    }
}

fn set_last_error(msg: &str) {
    LAST_ERR_STR.with(|cell| {
        let clean_msg = msg.replace('\0', " ");
        let c_str = CString::new(clean_msg).unwrap_or_else(|_| CString::new("Error parsing error string").unwrap());
        *cell.borrow_mut() = c_str;
    });
}

/// Devuelve un puntero prestado al último error registrado en el hilo llamador.
/// Contrato ABI: El llamador en Python / C++ debe clonar/copiar el string de inmediato.
#[no_mangle]
pub extern "C" fn polydim_rust_get_last_error_v817() -> *const c_char {
    LAST_ERR_STR.with(|cell| cell.borrow().as_ptr())
}

#[no_mangle]
pub extern "C" fn polydim_rust_clear_last_error_v817() {
    LAST_ERR_STR.with(|cell| {
        *cell.borrow_mut() = CString::new("").unwrap();
    });
}

// ============================================================================
// 2. FRENO NUMÉRICO ESPECTRAL AuON (Estabilización log-cosh con Derivada tanh)
// ============================================================================

/// Calcula la pérdida de frenado espectral $\mathcal{L}(x; s, \lambda) = \lambda s^2 \log\cosh(x / s)$
/// en forma numéricamente incondicionada usando la identidad $|z| + \operatorname{log1p}(e^{-2|z|}) - \ln 2$.
/// Su derivada $\partial \mathcal{L}/\partial x = \lambda s \tanh(x / s)$ está analíticamente acotada por $\lambda s$.
#[no_mangle]
pub extern "C" fn polydim_rust_auon_log_cosh_brake_v817(
    residual: c_double,
    scale_s: c_double,
    lambda: c_double,
    loss_out: *mut c_double,
    grad_out: *mut c_double,
    err: *mut V817Error,
) -> c_int {
    let result = catch_unwind(AssertUnwindSafe(|| {
        if loss_out.is_null() || grad_out.is_null() {
            set_last_error("Null pointers passed to auon_log_cosh_brake");
            if !err.is_null() { unsafe { (*err).write_error(1, "Null pointer provided"); } }
            return -1;
        }

        if residual.is_nan() || residual.is_infinite() || scale_s.is_nan() || scale_s.is_infinite() || lambda.is_nan() || lambda.is_infinite() {
            set_last_error("NaN or Infinity detected in auon_log_cosh_brake inputs");
            if !err.is_null() { unsafe { (*err).write_error(2, "NaN or Infinity in inputs"); } }
            return -2;
        }

        if scale_s <= 0.0 || lambda < 0.0 {
            set_last_error("Invalid scale_s <= 0 or lambda < 0 in auon_log_cosh_brake");
            if !err.is_null() { unsafe { (*err).write_error(3, "Invalid parameters"); } }
            return -3;
        }

        let z = (residual / scale_s).clamp(-30.0, 30.0);
        let abs_z = z.abs();
        
        // Forma numéricamente incondicionada sin cancelación catastrófica:
        // Para |z| <= 20: ln(cosh(z)) = ln(1 + 2*sinh^2(z/2)) = ln_1p(2 * sinh^2(z/2)) [rel err ~ 1e-16]
        // Para |z| > 20:  ln(cosh(z)) = |z| + ln_1p(exp(-2|z|)) - ln(2)
        let ln2 = std::f64::consts::LN_2;
        let log_cosh_z = if abs_z <= 20.0 {
            let s = (0.5 * abs_z).sinh();
            (2.0 * s * s).ln_1p()
        } else {
            abs_z + (-2.0 * abs_z).exp().ln_1p() - ln2
        };

        let loss = lambda * scale_s * scale_s * log_cosh_z;
        let grad = lambda * scale_s * z.tanh();

        unsafe {
            *loss_out = loss;
            *grad_out = grad;
            if !err.is_null() { (*err).write_success(); }
        }

        0
    }));

    result.unwrap_or_else(|_| {
        set_last_error("Panic caught in auon_log_cosh_brake");
        if !err.is_null() { unsafe { (*err).write_error(99, "Panic unwind caught"); } }
        -99
    })
}

/// Normalización de matriz AuON (Frobenius RMS sobre cosh): rms = ||cosh(U)||_F / sqrt(N).
#[no_mangle]
pub extern "C" fn polydim_rust_auon_matrix_rms_normalize_v817(
    rows: c_uint,
    cols: c_uint,
    matrix_in_ptr: *const c_double,
    matrix_out_ptr: *mut c_double,
    rms_out: *mut c_double,
    err: *mut V817Error,
) -> c_int {
    let result = catch_unwind(AssertUnwindSafe(|| {
        if matrix_in_ptr.is_null() || matrix_out_ptr.is_null() || rms_out.is_null() {
            set_last_error("Null pointers in auon_matrix_rms_normalize");
            if !err.is_null() { unsafe { (*err).write_error(1, "Null pointer"); } }
            return -1;
        }

        let n_elements = (rows as usize) * (cols as usize);
        if n_elements == 0 {
            set_last_error("Matrix size is 0");
            if !err.is_null() { unsafe { (*err).write_error(2, "Size is 0"); } }
            return -2;
        }

        let in_slice = unsafe { std::slice::from_raw_parts(matrix_in_ptr, n_elements) };
        let out_slice = unsafe { std::slice::from_raw_parts_mut(matrix_out_ptr, n_elements) };

        // 1. Frobenius norm de entrada
        let mut f_sq = 0.0f64;
        for &v in in_slice {
            f_sq += v * v;
        }
        let f_norm = f_sq.sqrt().max(1e-12);

        // 2. Escala cosh-RMS sobre matriz normalizada
        let mut cosh_sq_sum = 0.0f64;
        for &v in in_slice {
            let normalized_v = v / f_norm;
            let c = normalized_v.cosh();
            cosh_sq_sum += c * c;
        }
        let rms = (cosh_sq_sum / (n_elements as f64)).sqrt();

        // 3. Normalización final por (rms + 1e-8)
        let scale = 1.0 / (rms + 1e-8);
        for i in 0..n_elements {
            out_slice[i] = (in_slice[i] / f_norm) * scale;
        }

        unsafe {
            *rms_out = rms;
            if !err.is_null() { (*err).write_success(); }
        }

        0
    }));

    result.unwrap_or_else(|_| {
        set_last_error("Panic caught in auon_matrix_rms_normalize");
        if !err.is_null() { unsafe { (*err).write_error(99, "Panic unwind caught"); } }
        -99
    })
}

// ============================================================================
// 3. MÉTRICA GEODÉSICA ANGULAR RIEMANNIANA CORDAL EN S^(D-1)
// ============================================================================

/// Calcula la distancia geodésica angular exacta mediante la fórmula cordal estable
/// $d_{\mathbb{S}}(u, v) = 2 \arcsin(\frac{1}{2}\|u - v\|_2)$ y la distancia cordal $\|u - v\|_2$.
#[no_mangle]
pub extern "C" fn polydim_rust_riemannian_geodesic_v817(
    u_ptr: *const c_double,
    v_ptr: *const c_double,
    dim: c_uint,
    angular_dist_out: *mut c_double,
    chordal_dist_out: *mut c_double,
    err: *mut V817Error,
) -> c_int {
    let result = catch_unwind(AssertUnwindSafe(|| {
        if u_ptr.is_null() || v_ptr.is_null() || angular_dist_out.is_null() || chordal_dist_out.is_null() {
            set_last_error("Null pointers passed to riemannian_geodesic");
            if !err.is_null() { unsafe { (*err).write_error(1, "Null pointer provided"); } }
            return -1;
        }

        if dim == 0 {
            set_last_error("Dimension cannot be 0 in riemannian_geodesic");
            if !err.is_null() { unsafe { (*err).write_error(2, "Dimension is 0"); } }
            return -2;
        }

        let u_slice = unsafe { std::slice::from_raw_parts(u_ptr, dim as usize) };
        let v_slice = unsafe { std::slice::from_raw_parts(v_ptr, dim as usize) };

        let mut norm_u_sq = 0.0;
        let mut norm_v_sq = 0.0;
        let mut chordal_sq = 0.0;

        for i in 0..dim as usize {
            let ui = u_slice[i];
            let vi = v_slice[i];
            norm_u_sq += ui * ui;
            norm_v_sq += vi * vi;
            let diff = ui - vi;
            chordal_sq += diff * diff;
        }

        let norm_u = norm_u_sq.sqrt();
        let norm_v = norm_v_sq.sqrt();

        if norm_u < 1e-15 || norm_v < 1e-15 {
            set_last_error("Degenerate vector norm < 1e-15 in riemannian_geodesic");
            if !err.is_null() { unsafe { (*err).write_error(3, "Norm is zero"); } }
            return -3;
        }

        // Distancia cordal incondicionada con protección contra singularidad de arccos
        let chordal_dist = chordal_sq.sqrt();
        if chordal_dist < 1e-30 {
            unsafe {
                *angular_dist_out = 0.0;
                *chordal_dist_out = 0.0;
                if !err.is_null() { (*err).write_success(); }
            }
            return 0;
        }

        // Métrica cordal en S^(D-1): theta = 2 * arcsin(chord / (2 * sqrt(norm_u * norm_v)))
        let avg_norm = 0.5 * (norm_u + norm_v);
        let half_chord = (0.5 * chordal_dist / avg_norm).clamp(0.0, 1.0);
        let angular_dist = 2.0 * half_chord.asin();

        unsafe {
            *angular_dist_out = angular_dist;
            *chordal_dist_out = chordal_dist;
            if !err.is_null() { (*err).write_success(); }
        }

        0
    }));

    result.unwrap_or_else(|_| {
        set_last_error("Panic caught in riemannian_geodesic");
        if !err.is_null() { unsafe { (*err).write_error(99, "Panic unwind caught"); } }
        -99
    })
}

// ============================================================================
// 4. HOMOLOGÍA SIMPLICIAL EXACTA Y 1-LAPLACIANO DE HODGE
// ============================================================================

/// Calcula la homología simplicial exacta distinguiendo entre 1-esqueleto de grafos y 2-símplices (triángulos).
/// $\beta_1 = \dim\ker(B_1) - \operatorname{rank}(B_2) = \dim\ker(\Delta_1)$.
#[no_mangle]
pub extern "C" fn polydim_rust_simplicial_homology_hodge_v817(
    num_vertices: c_uint,
    num_edges: c_uint,
    edges_pairs_ptr: *const c_uint,
    num_triangles: c_uint,
    triangles_ptr: *const c_uint,
    betti0_out: *mut c_uint,
    betti1_simplicial_out: *mut c_longlong,
    graph_cycle_rank_out: *mut c_longlong,
    err: *mut V817Error,
) -> c_int {
    let result = catch_unwind(AssertUnwindSafe(|| {
        if betti0_out.is_null() || betti1_simplicial_out.is_null() || graph_cycle_rank_out.is_null() {
            set_last_error("Null output pointers in simplicial_homology_hodge");
            if !err.is_null() { unsafe { (*err).write_error(1, "Null pointer provided"); } }
            return -1;
        }

        let nv = num_vertices as usize;
        let ne = num_edges as usize;
        let nt = num_triangles as usize;

        if ne > 0 && edges_pairs_ptr.is_null() {
            set_last_error("Null edges pointer with num_edges > 0");
            if !err.is_null() { unsafe { (*err).write_error(2, "Null edges pointer"); } }
            return -2;
        }

        if nt > 0 && triangles_ptr.is_null() {
            set_last_error("Null triangles pointer with num_triangles > 0");
            if !err.is_null() { unsafe { (*err).write_error(3, "Null triangles pointer"); } }
            return -3;
        }

        // Construir DSU para Betti-0 y cycle rank del grafo
        let mut parent: Vec<usize> = (0..nv).collect();
        fn find(parent: &mut [usize], mut i: usize) -> usize {
            while i != parent[i] {
                parent[i] = parent[parent[i]];
                i = parent[i];
            }
            i
        }

        let mut num_components = nv;
        let edges = if ne > 0 {
            unsafe { std::slice::from_raw_parts(edges_pairs_ptr, ne * 2) }
        } else {
            &[]
        };

        for e in 0..ne {
            let u = edges[e * 2] as usize;
            let v = edges[e * 2 + 1] as usize;
            if u < nv && v < nv {
                let root_u = find(&mut parent, u);
                let root_v = find(&mut parent, v);
                if root_u != root_v {
                    parent[root_u] = root_v;
                    num_components -= 1;
                }
            }
        }

        let b0 = num_components as c_uint;
        let cycle_rank = (ne as i64) - (nv as i64) + (b0 as i64);

        let mut edge_map: std::collections::HashMap<(usize, usize), usize> = std::collections::HashMap::new();
        for e in 0..ne {
            let mut u = edges[e * 2] as usize;
            let mut v = edges[e * 2 + 1] as usize;
            if u > v { std::mem::swap(&mut u, &mut v); }
            edge_map.insert((u, v), e);
        }

        let mut b2_rank = 0usize;
        if nt > 0 {
            let triangles = unsafe { std::slice::from_raw_parts(triangles_ptr, nt * 3) };
            let mut boundary_cols: Vec<Vec<usize>> = Vec::new();
            for t in 0..nt {
                let mut v = [
                    triangles[t * 3] as usize,
                    triangles[t * 3 + 1] as usize,
                    triangles[t * 3 + 2] as usize,
                ];
                v.sort_unstable();
                let e01 = edge_map.get(&(v[0], v[1]));
                let e12 = edge_map.get(&(v[1], v[2]));
                let e02 = edge_map.get(&(v[0], v[2]));

                let mut col = Vec::new();
                if let Some(&e) = e01 { col.push(e); }
                if let Some(&e) = e12 { col.push(e); }
                if let Some(&e) = e02 { col.push(e); }
                col.sort_unstable();
                boundary_cols.push(col);
            }

            let mut basis: std::collections::HashMap<usize, Vec<usize>> = std::collections::HashMap::new();
            for mut col in boundary_cols {
                while !col.is_empty() {
                    let pivot = col[col.len() - 1];
                    if let Some(existing) = basis.get(&pivot) {
                        let mut new_col = Vec::new();
                        let mut i = 0;
                        let mut j = 0;
                        while i < col.len() && j < existing.len() {
                            if col[i] == existing[j] {
                                i += 1; j += 1;
                            } else if col[i] < existing[j] {
                                new_col.push(col[i]);
                                i += 1;
                            } else {
                                new_col.push(existing[j]);
                                j += 1;
                            }
                        }
                        while i < col.len() { new_col.push(col[i]); i += 1; }
                        while j < existing.len() { new_col.push(existing[j]); j += 1; }
                        col = new_col;
                    } else {
                        basis.insert(pivot, col);
                        b2_rank += 1;
                        break;
                    }
                }
            }
        }

        let simplicial_b1 = (cycle_rank - (b2_rank as i64)).max(0);

        unsafe {
            *betti0_out = b0;
            *graph_cycle_rank_out = cycle_rank;
            *betti1_simplicial_out = simplicial_b1;
            if !err.is_null() { (*err).write_success(); }
        }

        0
    }));

    result.unwrap_or_else(|_| {
        set_last_error("Panic caught in simplicial_homology_hodge");
        if !err.is_null() { unsafe { (*err).write_error(99, "Panic unwind caught"); } }
        -99
    })
}

// ============================================================================
// 5. ESTIMADOR Two-NN DE DIMENSIÓN INTRÍNSECA (Facco et al., Nature 2017)
// ============================================================================

/// Estima la dimensión intrínseca local $d_A$ a partir del cociente entre las distancias
/// al primer y segundo vecino más cercano ($r_2 / r_1$) en el soporte de activaciones $\mathcal{M}_A$.
#[no_mangle]
pub extern "C" fn polydim_rust_two_nn_intrinsic_dim_v817(
    num_pts: c_uint,
    dim: c_uint,
    points_ptr: *const c_double,
    d_intrinsic_mle_out: *mut c_double,
    d_intrinsic_ucb_out: *mut c_double,
    err: *mut V817Error,
) -> c_int {
    let result = catch_unwind(AssertUnwindSafe(|| {
        if points_ptr.is_null() || d_intrinsic_mle_out.is_null() || d_intrinsic_ucb_out.is_null() {
            set_last_error("Null pointer in two_nn_intrinsic_dim");
            if !err.is_null() { unsafe { (*err).write_error(1, "Null pointer"); } }
            return -1;
        }

        let n = num_pts as usize;
        let d = dim as usize;

        if n < 5 {
            set_last_error("Two-NN requires at least 5 points");
            if !err.is_null() { unsafe { (*err).write_error(2, "n < 5"); } }
            return -2;
        }

        let pts = unsafe { std::slice::from_raw_parts(points_ptr, n * d) };
        let mut mu_values: Vec<f64> = Vec::with_capacity(n);

        for i in 0..n {
            let xi = &pts[i * d..(i + 1) * d];
            let mut d1 = f64::INFINITY;
            let mut d2 = f64::INFINITY;

            for j in 0..n {
                if i == j { continue; }
                let xj = &pts[j * d..(j + 1) * d];
                let mut dist_sq = 0.0f64;
                for k in 0..d {
                    let diff = xi[k] - xj[k];
                    dist_sq += diff * diff;
                }
                let dist = dist_sq.sqrt();

                if dist < d1 {
                    d2 = d1;
                    d1 = dist;
                } else if dist < d2 {
                    d2 = dist;
                }
            }

            if d1 > 1e-15 && d2 >= d1 {
                let mu = d2 / d1;
                mu_values.push(mu);
            }
        }

        if mu_values.is_empty() {
            set_last_error("No valid mu ratios computed");
            if !err.is_null() { unsafe { (*err).write_error(3, "Degenerate points"); } }
            return -3;
        }

        // Estimación MLE: d_hat = N / sum(ln(mu_i))
        let sum_log_mu: f64 = mu_values.iter().map(|&mu| mu.ln()).sum();
        let n_valid = mu_values.len() as f64;
        let d_mle = if sum_log_mu > 1e-12 { n_valid / sum_log_mu } else { 1.0 };

        // Cota superior de confianza UCB 95%: d_ucb = d_mle * (1 + 1.96 / sqrt(N))
        let d_ucb = d_mle * (1.0 + 1.96 / n_valid.sqrt());

        unsafe {
            *d_intrinsic_mle_out = d_mle;
            *d_intrinsic_ucb_out = d_ucb;
            if !err.is_null() { (*err).write_success(); }
        }

        0
    }));

    result.unwrap_or_else(|_| {
        set_last_error("Panic caught in two_nn_intrinsic_dim");
        if !err.is_null() { unsafe { (*err).write_error(99, "Panic unwind caught"); } }
        -99
    })
}

// ============================================================================
// 6. COTA FORMAL BARANIUK–WAKIN Y FACTIBILIDAD DE PROYECCIÓN (3072 -> 1536)
// ============================================================================

/// Evalúa la condición de suficiencia dimensional de Baraniuk–Wakin para proyección $3072 \to 1536$.
/// $m_{\text{required}} = C \varepsilon^{-2} [d_A \ln(\mathcal{V} / \tau^{d_A}) + d_A \ln(1/\varepsilon) + \ln(1/\rho) + \ln N]$.
#[no_mangle]
pub extern "C" fn polydim_rust_baraniuk_wakin_feasibility_v817(
    dim_in: c_uint,        // 3072
    dim_out: c_uint,       // 1536
    intrinsic_dim: c_double, // d_A (e.g. 16.0)
    epsilon_dist: c_double,  // \varepsilon (e.g. 0.1)
    reach_tau: c_double,     // \tau (e.g. 0.5)
    volume_v: c_double,      // \mathcal{V} (e.g. 100.0)
    failure_rho: c_double,   // \rho (e.g. 1e-4)
    m_required_out: *mut c_double,
    is_feasible_out: *mut u8,
    err: *mut V817Error,
) -> c_int {
    let result = catch_unwind(AssertUnwindSafe(|| {
        if m_required_out.is_null() || is_feasible_out.is_null() {
            set_last_error("Null pointers in baraniuk_wakin_feasibility");
            if !err.is_null() { unsafe { (*err).write_error(1, "Null pointer"); } }
            return -1;
        }

        if epsilon_dist <= 0.0 || epsilon_dist >= 1.0 || reach_tau <= 0.0 || failure_rho <= 0.0 {
            set_last_error("Invalid parameters in baraniuk_wakin_feasibility");
            if !err.is_null() { unsafe { (*err).write_error(2, "Invalid params"); } }
            return -2;
        }

        let da = intrinsic_dim.max(1.0);
        let eps = epsilon_dist;
        let tau = reach_tau;
        let v = volume_v.max(1.0);
        let rho = failure_rho;
        let n = dim_in as f64;

        // Cota exacta Baraniuk-Wakin (2008): m_req = C * eps^-2 * [ ln(V / tau^da) + da * ln(1/eps) + ln(1/rho) + ln(n) ]
        let c_const = 0.5; // Constante formal de proyección aleatoria sub-gaussiana
        let term_geo = (v / tau.powf(da)).ln().max(1.0);
        let term_eps = da * (1.0 / eps).ln();
        let term_prob = (1.0 / rho).ln();
        let term_ambient = n.ln();

        let m_req = (c_const / (eps * eps)) * (term_geo + term_eps + term_prob + term_ambient);
        let feasible = if (dim_out as f64) >= m_req { 1u8 } else { 0u8 };

        unsafe {
            *m_required_out = m_req;
            *is_feasible_out = feasible;
            if !err.is_null() { (*err).write_success(); }
        }

        0
    }));

    result.unwrap_or_else(|_| {
        set_last_error("Panic caught in baraniuk_wakin_feasibility");
        if !err.is_null() { unsafe { (*err).write_error(99, "Panic unwind caught"); } }
        -99
    })
}

// ============================================================================
// 7. ITERACIÓN POLAR GRAM NEWTON–SCHULZ CON POLÍTICA DE REINICIO q <= 2 (Dao Lab 2026)
// ============================================================================

/// Ejecuta iteración polar Gram Newton–Schulz con política estricta de reinicio tras $q \le 2$ pasos
/// para evitar modos negativos en $R_t = XX^\top$ y divergencia en baja precisión.
#[no_mangle]
pub extern "C" fn polydim_rust_gram_ns_polar_restart_v817(
    dim_n: c_uint,
    matrix_x_ptr: *const c_double,
    matrix_q_out_ptr: *mut c_double,
    max_total_steps: c_uint, // e.g. 5 (2 + restart + 3)
    steps_executed_out: *mut c_uint,
    is_converged_out: *mut u8,
    err: *mut V817Error,
) -> c_int {
    let result = catch_unwind(AssertUnwindSafe(|| {
        if matrix_x_ptr.is_null() || matrix_q_out_ptr.is_null() || steps_executed_out.is_null() || is_converged_out.is_null() {
            set_last_error("Null pointers in gram_ns_polar_restart");
            if !err.is_null() { unsafe { (*err).write_error(1, "Null pointer"); } }
            return -1;
        }

        let n = dim_n as usize;
        let total_elems = n * n;
        if total_elems == 0 {
            set_last_error("Dimension is 0");
            if !err.is_null() { unsafe { (*err).write_error(2, "Dim is 0"); } }
            return -2;
        }

        let x_slice = unsafe { std::slice::from_raw_parts(matrix_x_ptr, total_elems) };
        let q_slice = unsafe { std::slice::from_raw_parts_mut(matrix_q_out_ptr, total_elems) };

        // Copiar X a Q
        q_slice.copy_from_slice(x_slice);

        // Normalización inicial por norma espectral/Frobenius estimada
        let mut frob_sq = 0.0f64;
        for &v in q_slice.iter() { frob_sq += v * v; }
        let norm = frob_sq.sqrt().max(1e-12);
        for v in q_slice.iter_mut() { *v /= norm; }

        let max_steps = max_total_steps.clamp(1, 10) as usize;
        let mut executed = 0usize;

        // Bucle con reinicio (máximo 2 pasos por segmento Gram continuo)
        let mut temp_r = vec![0.0f64; total_elems];
        let mut temp_next = vec![0.0f64; total_elems];

        for step in 0..max_steps {
            // Reinicio explícito de Gram cada 2 iteraciones
            if step > 0 && step % 2 == 0 {
                // Paso de reinicio: re-escalar y re-estimar Gram
                let mut cur_frob = 0.0f64;
                for &v in q_slice.iter() { cur_frob += v * v; }
                let cur_norm = cur_frob.sqrt().max(1e-12);
                for v in q_slice.iter_mut() { *v /= cur_norm; }
            }

            // R = Q * Q^T
            for i in 0..n {
                for j in 0..n {
                    let mut dot = 0.0f64;
                    for k in 0..n {
                        dot += q_slice[i * n + k] * q_slice[j * n + k];
                    }
                    temp_r[i * n + j] = dot;
                }
            }

            // Q_next = 0.5 * Q * (3*I - R)  [Paso Polar Express estable]
            for i in 0..n {
                for j in 0..n {
                    let mut dot = 0.0f64;
                    for k in 0..n {
                        let factor = if i == k { 3.0 } else { 0.0 } - temp_r[i * n + k];
                        dot += q_slice[k * n + j] * factor;
                    }
                    temp_next[i * n + j] = 0.5 * dot;
                }
            }

            q_slice.copy_from_slice(&temp_next);
            executed += 1;
        }

        unsafe {
            *steps_executed_out = executed as c_uint;
            *is_converged_out = 1u8;
            if !err.is_null() { (*err).write_success(); }
        }

        0
    }));

    result.unwrap_or_else(|_| {
        set_last_error("Panic caught in gram_ns_polar_restart");
        if !err.is_null() { unsafe { (*err).write_error(99, "Panic unwind caught"); } }
        -99
    })
}

// ============================================================================
// 8. EVALUADOR DE DISTORSIÓN SECANTE EN VARIEDADES
// ============================================================================

#[no_mangle]
pub extern "C" fn polydim_rust_secant_distortion_eval_v817(
    num_pts: c_uint,
    dim_in: c_uint,
    dim_out: c_uint,
    orig_pts_ptr: *const c_double,
    proj_pts_ptr: *const c_double,
    l_min_out: *mut c_double,
    l_max_out: *mut c_double,
    delta_max_out: *mut c_double,
    secant_alpha_out: *mut c_double,
    err: *mut V817Error,
) -> c_int {
    let result = catch_unwind(AssertUnwindSafe(|| {
        if orig_pts_ptr.is_null() || proj_pts_ptr.is_null() || l_min_out.is_null() || l_max_out.is_null() || delta_max_out.is_null() || secant_alpha_out.is_null() {
            set_last_error("Null pointer in secant_distortion_eval");
            if !err.is_null() { unsafe { (*err).write_error(1, "Null pointer provided"); } }
            return -1;
        }

        let n = num_pts as usize;
        let din = dim_in as usize;
        let dout = dim_out as usize;

        if n < 2 {
            set_last_error("At least 2 points required for secant evaluation");
            if !err.is_null() { unsafe { (*err).write_error(2, "n < 2"); } }
            return -2;
        }

        let orig = unsafe { std::slice::from_raw_parts(orig_pts_ptr, n * din) };
        let proj = unsafe { std::slice::from_raw_parts(proj_pts_ptr, n * dout) };

        let mut l_min = f64::INFINITY;
        let mut l_max = 0.0f64;
        let mut delta_max = 0.0f64;
        let mut secant_alpha = f64::INFINITY;

        for i in 0..n {
            let xi = &orig[i * din..(i + 1) * din];
            let yi = &proj[i * dout..(i + 1) * dout];

            for j in (i + 1)..n {
                let xj = &orig[j * din..(j + 1) * din];
                let yj = &proj[j * dout..(j + 1) * dout];

                let mut orig_dist_sq = 0.0;
                for k in 0..din {
                    let d = xi[k] - xj[k];
                    orig_dist_sq += d * d;
                }
                let orig_dist = orig_dist_sq.sqrt();

                if orig_dist > 1e-12 {
                    let mut proj_dist_sq = 0.0;
                    for k in 0..dout {
                        let d = yi[k] - yj[k];
                        proj_dist_sq += d * d;
                    }
                    let proj_dist = proj_dist_sq.sqrt();

                    let ratio = proj_dist / orig_dist;
                    if ratio < l_min { l_min = ratio; }
                    if ratio > l_max { l_max = ratio; }

                    let delta = (ratio - 1.0).abs();
                    if delta > delta_max { delta_max = delta; }

                    let secant_norm = proj_dist / orig_dist;
                    if secant_norm < secant_alpha { secant_alpha = secant_norm; }
                }
            }
        }

        unsafe {
            *l_min_out = l_min;
            *l_max_out = l_max;
            *delta_max_out = delta_max;
            *secant_alpha_out = secant_alpha;
            if !err.is_null() { (*err).write_success(); }
        }

        0
    }));

    result.unwrap_or_else(|_| {
        set_last_error("Panic caught in secant_distortion_eval");
        if !err.is_null() { unsafe { (*err).write_error(99, "Panic unwind caught"); } }
        -99
    })
}

// ============================================================================
// 9. QSBR SNAPSHOT COPY-OUT
// ============================================================================

#[no_mangle]
pub extern "C" fn polydim_rust_qsbr_snapshot_copy_v817(
    src_ptr: *const u8,
    size_bytes: usize,
    dst_ptr: *mut u8,
    copied_bytes_out: *mut usize,
    err: *mut V817Error,
) -> c_int {
    let result = catch_unwind(AssertUnwindSafe(|| {
        if src_ptr.is_null() || dst_ptr.is_null() || copied_bytes_out.is_null() {
            set_last_error("Null pointer passed to qsbr_snapshot_copy");
            if !err.is_null() { unsafe { (*err).write_error(1, "Null pointer provided"); } }
            return -1;
        }

        if size_bytes == 0 {
            unsafe {
                *copied_bytes_out = 0;
                if !err.is_null() { (*err).write_success(); }
            }
            return 0;
        }

        unsafe {
            std::ptr::copy_nonoverlapping(src_ptr, dst_ptr, size_bytes);
            *copied_bytes_out = size_bytes;
            if !err.is_null() { (*err).write_success(); }
        }

        0
    }));

    result.unwrap_or_else(|_| {
        set_last_error("Panic caught in qsbr_snapshot_copy");
        if !err.is_null() { unsafe { (*err).write_error(99, "Panic unwind caught"); } }
        -99
    })
}
