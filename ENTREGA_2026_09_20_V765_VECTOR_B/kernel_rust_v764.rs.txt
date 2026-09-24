// ============================================================================
// POLYDIM V762 — Verificador de invariantes (capa Rust)
//
// Cambios respecto de V761 y por qué:
//
// A5  TOLERANCIA. V761 usaba `tol = 2*d*EPS + 50*EPS` y además exigía
//     `drift > 1e-12` para reportar. El umbral efectivo era max(tol, 1e-12):
//     1.00e-12 en D=1e3 y 4.44e-10 en D=1e6, es decir 21 143x más laxo que el
//     2.10e-14 que el documento de entrega declaraba certificado. Aquí la cota
//     NO escala con D, porque el kernel usa sumación compensada y la deriva
//     medida es O(eps) independiente de D (0.00e+00 a D=1e6).
//
// A6  SUBNORMALES. Con FTZ/DAZ activo en el lado C++ un subnormal nunca llega
//     hasta aquí, así que el chequeo de V761 era código muerto. Y cuando FTZ
//     está apagado, un subnormal legítimo en un vector unitario disperso no es
//     un error. Pasa a ser un CONTADOR informativo, no un fallo.
//
// A7  `catch_unwind` en V761 era ornamental: no había ninguna operación capaz
//     de hacer panic, y bajo `panic = "abort"` el cierre no captura nada.
//     Aquí se conserva sólo porque los índices de slice SÍ pueden hacer panic,
//     y se documenta que exige `panic = "unwind"`. `unsafe_op_in_unsafe_fn`
//     queda resuelto con bloques `unsafe` internos explícitos (edición 2024).
//     Todas las salidas tempranas escriben los punteros de salida.
//
// A8  BETTI-1. Eliminado. El título de V761 prometía un "Guardián Topológico
//     Betti-1" y `ErrTopologyFragmented`, pero el código no calculaba ninguna
//     homología. Además beta_1(S^(D-1)) = 0 para todo D > 2, así que la
//     cantidad era vacua. No se sustituye por un placebo: lo que se verifica
//     es lo que se puede verificar en O(D) — la norma y la ortonormalidad.
// ============================================================================

#![deny(unsafe_op_in_unsafe_fn)]

use std::panic::{catch_unwind, AssertUnwindSafe};

pub const POLYDIM_SUCCESS: i32 = 0;
pub const POLYDIM_ERR_NULL_POINTER: i32 = -1;
pub const POLYDIM_ERR_INVALID_DIMENSION: i32 = -2;
pub const POLYDIM_ERR_NAN_OR_INF: i32 = -3;
pub const POLYDIM_ERR_DEGENERATE_NORM: i32 = -4;
pub const POLYDIM_ERR_BASIS_NOT_ORTHONORMAL: i32 = -9;
pub const POLYDIM_ERR_POINT_OFF_MANIFOLD: i32 = -10;
pub const POLYDIM_ERR_PANIC: i32 = -13;

const EPS: f64 = f64::EPSILON;

/// A5: cota fija, no escalada en D. 64*eps = 1.42e-14 <= 2.10e-14 publicado.
#[inline]
pub const fn polydim_certified_bound() -> f64 {
    64.0 * EPS
}

/// Acumulador Kahan-Babuska-Neumaier.
///
/// La resta `sum - t` es algebraicamente cero; sobrevive sólo porque Rust no
/// reasocia aritmética de punto flotante (a diferencia de C con `-ffast-math`).
/// Ésta es una garantía del lenguaje, no una bandera del build: es la razón por
/// la que la verificación vive en Rust y no en el mismo binario que el kernel.
#[derive(Clone, Copy, Default)]
struct Neumaier {
    sum: f64,
    c: f64,
}

impl Neumaier {
    #[inline]
    fn add(&mut self, v: f64) {
        let t = self.sum + v;
        if self.sum.abs() >= v.abs() {
            self.c += (self.sum - t) + v;
        } else {
            self.c += (v - t) + self.sum;
        }
        self.sum = t;
    }
    #[inline]
    fn total(&self) -> f64 {
        self.sum + self.c
    }
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct VerifyReport {
    /// |<y,y> - 1| medido con sumación compensada.
    pub norm_drift: f64,
    /// |<u,u> - 1|, |<v,v> - 1|, |<u,v>| — -1.0 si no se pasó base.
    pub basis_uu_err: f64,
    pub basis_vv_err: f64,
    pub basis_uv_err: f64,
    /// Cota aplicada. Se expone para que el llamante no tenga que adivinarla.
    pub bound_used: f64,
    /// A6: informativo, no causa fallo.
    pub subnormal_count: u64,
    pub nonfinite_count: u64,
}

impl Default for VerifyReport {
    fn default() -> Self {
        VerifyReport {
            norm_drift: -1.0,
            basis_uu_err: -1.0,
            basis_vv_err: -1.0,
            basis_uv_err: -1.0,
            bound_used: polydim_certified_bound(),
            subnormal_count: 0,
            nonfinite_count: 0,
        }
    }
}

/// Verifica que `y` esté sobre S^(D-1) y, si se aportan, que {u,v} sea una base
/// ortonormal del plano de rotación.
///
/// # Seguridad
/// `y` debe apuntar a `d` valores `f64` válidos y legibles. Igual `u` y `v` si
/// no son nulos. `report` debe ser nulo o apuntar a un `VerifyReport` escribible.
///
/// # Requisito del perfil
/// Requiere `panic = "unwind"`. Con `panic = "abort"` el `catch_unwind` no
/// captura nada y un índice fuera de rango aborta el proceso — que es
/// precisamente lo que no se quiere al cruzar una frontera FFI.
// Edicion 2024: `no_mangle` es un atributo unsafe y exige el envoltorio.
// V761 usaba `#[no_mangle]` a secas: no compila en 2024.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn polydim_rust_verify_invariants(
    y: *const f64,
    u: *const f64,
    v: *const f64,
    d: usize,
    report_out: *mut VerifyReport,
) -> i32 {
    // A7: el reporte se inicializa ANTES de cualquier retorno temprano.
    // V761 dejaba `max_drift_out` sin escribir en las salidas tempranas, así que
    // el llamante leía memoria no inicializada y la trataba como una deriva.
    let mut rep = VerifyReport::default();
    let flush = |r: &VerifyReport| {
        if !report_out.is_null() {
            unsafe { report_out.write(*r) };
        }
    };

    if y.is_null() {
        flush(&rep);
        return POLYDIM_ERR_NULL_POINTER;
    }
    if d == 0 {
        flush(&rep);
        return POLYDIM_ERR_INVALID_DIMENSION;
    }

    let result = catch_unwind(AssertUnwindSafe(|| {
        let ys: &[f64] = unsafe { std::slice::from_raw_parts(y, d) };

        let mut acc_yy = Neumaier::default();
        let mut subnormals: u64 = 0;
        let mut nonfinite: u64 = 0;

        for &yi in ys {
            if !yi.is_finite() {
                nonfinite += 1;
                continue;
            }
            // A6: se cuenta, no se rechaza.
            if yi != 0.0 && yi.is_subnormal() {
                subnormals += 1;
            }
            acc_yy.add(yi * yi);
        }
        rep.subnormal_count = subnormals;
        rep.nonfinite_count = nonfinite;

        if nonfinite > 0 {
            return POLYDIM_ERR_NAN_OR_INF;
        }

        let yy = acc_yy.total();
        if !(yy > 0.0) || !yy.is_finite() {
            return POLYDIM_ERR_DEGENERATE_NORM;
        }
        rep.norm_drift = (yy - 1.0).abs();

        let bound = rep.bound_used;
        // A5: sin el `&& drift > 1e-12` de V761. Si la deriva excede la cota,
        // se reporta. No hay piso silencioso que se coma los fallos reales.
        if rep.norm_drift > bound {
            return POLYDIM_ERR_POINT_OFF_MANIFOLD;
        }

        if !u.is_null() && !v.is_null() {
            let us: &[f64] = unsafe { std::slice::from_raw_parts(u, d) };
            let vs: &[f64] = unsafe { std::slice::from_raw_parts(v, d) };
            let mut a_uu = Neumaier::default();
            let mut a_vv = Neumaier::default();
            let mut a_uv = Neumaier::default();
            for i in 0..d {
                let (ui, vi) = (us[i], vs[i]);
                if !ui.is_finite() || !vi.is_finite() {
                    return POLYDIM_ERR_NAN_OR_INF;
                }
                a_uu.add(ui * ui);
                a_vv.add(vi * vi);
                a_uv.add(ui * vi);
            }
            rep.basis_uu_err = (a_uu.total() - 1.0).abs();
            rep.basis_vv_err = (a_vv.total() - 1.0).abs();
            rep.basis_uv_err = a_uv.total().abs();
            if rep.basis_uu_err > bound || rep.basis_vv_err > bound || rep.basis_uv_err > bound {
                return POLYDIM_ERR_BASIS_NOT_ORTHONORMAL;
            }
        }
        POLYDIM_SUCCESS
    }));

    flush(&rep);
    match result {
        Ok(code) => code,
        // V761 devolvía -5 aquí, indistinguible de una inestabilidad numérica.
        Err(_) => POLYDIM_ERR_PANIC,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn verify(y: &[f64], u: Option<&[f64]>, v: Option<&[f64]>) -> (i32, VerifyReport) {
        let mut rep = VerifyReport::default();
        let code = unsafe {
            polydim_rust_verify_invariants(
                y.as_ptr(),
                u.map_or(std::ptr::null(), |s| s.as_ptr()),
                v.map_or(std::ptr::null(), |s| s.as_ptr()),
                y.len(),
                &mut rep,
            )
        };
        (code, rep)
    }

    #[test]
    fn cota_no_escala_con_d() {
        // El punto de A5: la misma cota en D=1e3 y en D=1e6.
        assert_eq!(polydim_certified_bound(), 64.0 * EPS);
        assert!(polydim_certified_bound() <= 2.10e-14);
    }

    #[test]
    fn acepta_unitario() {
        let mut y = vec![0.0; 1_000];
        y[0] = 1.0;
        let (code, rep) = verify(&y, None, None);
        assert_eq!(code, POLYDIM_SUCCESS);
        assert_eq!(rep.norm_drift, 0.0);
    }

    #[test]
    fn rechaza_deriva_que_v761_aceptaba() {
        // V761 en D=1e6 admitía hasta 4.44e-10. Esta deriva de 1e-11 debe fallar.
        let d = 1_000_000;
        let mut y = vec![0.0; d];
        y[0] = (1.0f64 + 1e-11).sqrt();
        let (code, rep) = verify(&y, None, None);
        assert_eq!(code, POLYDIM_ERR_POINT_OFF_MANIFOLD, "deriva {}", rep.norm_drift);
    }

    #[test]
    fn detecta_base_no_ortonormal() {
        let d = 64;
        let mut y = vec![0.0; d];
        y[0] = 1.0;
        let mut u = vec![0.0; d];
        u[0] = 1.0;
        let mut v = vec![0.0; d];
        v[1] = 2.0; // ||v|| = 2
        let (code, rep) = verify(&y, Some(&u), Some(&v));
        assert_eq!(code, POLYDIM_ERR_BASIS_NOT_ORTHONORMAL);
        assert!((rep.basis_vv_err - 3.0).abs() < 1e-12);
    }

    #[test]
    fn subnormal_no_es_error() {
        // A6: un unitario con una componente subnormal es legítimo.
        let d = 8;
        let mut y = vec![0.0; d];
        y[0] = 1.0;
        y[1] = f64::MIN_POSITIVE / 4.0; // subnormal
        let (code, rep) = verify(&y, None, None);
        assert_eq!(code, POLYDIM_SUCCESS);
        assert_eq!(rep.subnormal_count, 1);
    }

    #[test]
    fn nan_se_reporta_como_nan() {
        let mut y = vec![0.0; 16];
        y[0] = 1.0;
        y[3] = f64::NAN;
        let (code, rep) = verify(&y, None, None);
        assert_eq!(code, POLYDIM_ERR_NAN_OR_INF);
        assert_eq!(rep.nonfinite_count, 1);
    }

    #[test]
    fn reporte_siempre_escrito_en_salida_temprana() {
        // A7: incluso con d = 0 el reporte queda inicializado, no basura.
        let mut rep = VerifyReport { norm_drift: 12345.0, ..Default::default() };
        let y = [1.0f64];
        let code = unsafe {
            polydim_rust_verify_invariants(
                y.as_ptr(), std::ptr::null(), std::ptr::null(), 0, &mut rep,
            )
        };
        assert_eq!(code, POLYDIM_ERR_INVALID_DIMENSION);
        assert_eq!(rep.norm_drift, -1.0, "el reporte no fue reinicializado");
    }

    #[test]
    fn neumaier_vence_a_la_suma_ingenua() {
        let n = 1_000_000;
        let small = EPS / 2.0;
        let mut acc = Neumaier::default();
        acc.add(1.0);
        let mut naive = 1.0f64;
        for _ in 0..n {
            acc.add(small);
            naive += small;
        }
        let expected = 1.0 + n as f64 * small;
        assert!((acc.total() - expected).abs() / expected < 1e-15);
        assert_eq!(naive, 1.0, "la suma ingenua debería perderlo todo");
    }
}
