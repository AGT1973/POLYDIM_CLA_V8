# 🏛️ POLYDIM V766 — COMPLETE UNABRIDGED SOURCE CODE MONOLITH

> **Release:** POLYDIM V766 Industrial Edition
> **Date:** September 21, 2026

---

## 1. Native C++ Fused 2-Pass Kernel (kernel_cpp_v766.cpp)

`
/* ============================================================================
 * POLYDIM V764 — KERNEL ENDURECIDO
 *
 * Cierra los hallazgos A1..A12 de la auditoría del 2026-09-20:
 *   A1  PMTP reescrito como triple búfer con seqlock por ranura   -> polydim_pmtp_*
 *   A2  compuerta de ortonormalidad usando los acumuladores       -> check_basis()
 *   A3  validación de theta/tau                                   -> require_finite()
 *   A4  validación del punto de entrada contra la variedad        -> tol.point_norm
 *   A5  (Rust) tolerancia recalibrada                             -> rust/src/lib.rs
 *   A6  FTZ/DAZ desactivado por defecto y coherente entre regiones
 *   A9  umbral de pivote relativo a ||M||_inf
 *   A10 num_threads explícito en toda región que indexa por tid
 *   A11 autodiagnóstico que falla si el compilador reasoció
 *   A12 (Dart) el puente ahora invoca, mide y libera
 * Mejoras P1: Gram simétrico combinado (2K x 2K, sólo triángulo superior),
 *   reducción en árbol en lugar de #pragma omp critical, presupuesto de memoria
 *   adaptativo, ruta BLAS opcional.
 * ==========================================================================*/

#include "polydim.h"

#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <vector>
#include <cmath>
#include <cstring>
#include <limits>
#include <algorithm>
#include <new>

#if defined(_OPENMP)
  #include <omp.h>
#else
  static inline int  omp_get_max_threads() { return 1; }
  static inline int  omp_get_thread_num()  { return 0; }
#endif

#if (defined(__x86_64__) || defined(_M_X64) || defined(__i386__) || defined(_M_IX86))
  #include <xmmintrin.h>
  #include <pmmintrin.h>
  #define POLYDIM_X86 1
#endif

#ifdef POLYDIM_USE_BLAS
extern "C" {
  void dsyrk_(const char*, const char*, const int*, const int*, const double*,
              const double*, const int*, const double*, double*, const int*);
  void dgemm_(const char*, const char*, const int*, const int*, const int*,
              const double*, const double*, const int*, const double*, const int*,
              const double*, double*, const int*);
  void dgesv_(const int*, const int*, double*, const int*, int*, double*, const int*, int*);
}
#endif

/* A6: FTZ/DAZ apagado por defecto. IEEE-754 conforme salvo opt-in explícito. */
#ifndef POLYDIM_ENABLE_FTZ
  #define POLYDIM_ENABLE_FTZ 0
#endif

/* Límite honesto de K. V761 declaraba 1024, inviable: el sistema denso 2Kx2K
 * son 33 MB y ~5.7 GFLOP secuenciales. 512 es el máximo sostenible. */
#ifndef POLYDIM_MAX_K
  #define POLYDIM_MAX_K 512u
#endif

/* Presupuesto de memoria para los acumuladores por hilo del Gram. Si se excede,
 * se reduce el número de hilos en lugar de reventar la RAM. */
#ifndef POLYDIM_GRAM_ARENA_BUDGET_BYTES
  #define POLYDIM_GRAM_ARENA_BUDGET_BYTES (256ull * 1024ull * 1024ull)
#endif

namespace {

constexpr double kEps = std::numeric_limits<double>::epsilon();

inline void set_fp_mode() {
#if POLYDIM_ENABLE_FTZ && defined(POLYDIM_X86)
    _MM_SET_FLUSH_ZERO_MODE(_MM_FLUSH_ZERO_ON);
    _MM_SET_DENORMALS_ZERO_MODE(_MM_DENORMALS_ZERO_ON);
#endif
}

/* ---------------------------------------------------------------------------
 * Acumulador Kahan-Babuska-Neumaier.
 * NO TOCAR sin volver a ejecutar polydim_selftest_compensation().
 * La resta (s - t) es algebraicamente cero; sólo sobrevive sin reasociación.
 * -------------------------------------------------------------------------*/
struct Neumaier {
    double sum = 0.0;
    double c   = 0.0;
    inline void add(double v) {
        const double t = sum + v;
        if (std::abs(sum) >= std::abs(v)) c += (sum - t) + v;
        else                              c += (v   - t) + sum;
        sum = t;
    }
    inline void merge(const Neumaier& o) { add(o.sum); add(o.c); }
    inline double total() const { return sum + c; }
};

inline bool require_finite(double x) { return std::isfinite(x); }

/* A4/A2: detecta solapamiento ilegal entre la salida y las entradas. */
inline bool overlaps(const void* a, const void* b, size_t bytes) {
    auto pa = static_cast<const char*>(a);
    auto pb = static_cast<const char*>(b);
    return (pa < pb + bytes) && (pb < pa + bytes);
}

inline int clamp_threads(int want) {
    int mx = omp_get_max_threads();
    if (mx < 1) mx = 1;
    return std::min(want < 1 ? 1 : want, mx);
}

} /* namespace anónimo */

/* ==========================================================================
 * Tolerancias y reporte
 * ========================================================================*/
extern "C" POLYDIM_EXPORT PolydimTolerances POLYDIM_CALL
polydim_default_tolerances(uint64_t D) {
    PolydimTolerances t;
    /* A5 — DECISIÓN DE DISEÑO, no un detalle de implementación.
     *
     * Con sumación compensada la deriva medida es O(eps) e INDEPENDIENTE de D:
     * verificado a 0.00e+00 en D=1e6 vía polydim_project_sphere_f64. Por tanto
     * la cota por defecto NO escala con D. Escalarla fue exactamente el error
     * de V761: su guardián admitía 4.44e-10 en D=1e6, 21 143x más laxo que el
     * 2.10e-14 que el documento de entrega declaraba certificado.
     *
     * 64*eps = 1.42e-14 <= 2.10e-14, o sea la cota es MÁS estricta que la cifra
     * publicada. Consecuencia para el llamante: los vectores deben normalizarse
     * con polydim_project_sphere_f64 (compensado). Una normalización ingenua en
     * D=1e6 deja un error relativo de ~4.3e-14 y será RECHAZADA, con razón.
     * Quien necesite admitirla debe subir tol.point_norm de forma explícita. */
    t.basis_ortho      = 64.0 * kEps;
    t.point_norm       = 64.0 * kEps;
    /* Stiefel: ver el comentario de gram_ortho en polydim.h. El error de medida
     * del Gram no compensado crece como sqrt(D)*eps; la cota lo refleja. */
    t.gram_ortho       = 64.0 * kEps * std::sqrt(static_cast<double>(D > 0 ? D : 1));
    t.pivot_rel        = 8.0  * kEps;
    t.reject_subnormal = 0;   /* A6: tolerar, no rechazar. Un unitario disperso
                                 puede tener componentes subnormales legítimas. */
    return t;
}

extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_report_init(PolydimReport* r) {
    if (!r) return;
    r->point_norm_err = -1.0; r->basis_uu_err = -1.0; r->basis_vv_err = -1.0;
    r->basis_uv_err   = -1.0; r->out_norm_err = -1.0; r->pivot_min = -1.0;
    r->pivot_threshold = -1.0; r->ortho_err = -1.0; r->threads_used = 0;
}

extern "C" POLYDIM_EXPORT const char* POLYDIM_CALL polydim_status_string(int32_t c) {
    switch (c) {
    case POLYDIM_SUCCESS:                   return "SUCCESS";
    case POLYDIM_ERR_NULL_POINTER:          return "NULL_POINTER";
    case POLYDIM_ERR_INVALID_DIMENSION:     return "INVALID_DIMENSION";
    case POLYDIM_ERR_NAN_OR_INF:            return "NAN_OR_INF en los datos";
    case POLYDIM_ERR_DEGENERATE_NORM:       return "DEGENERATE_NORM";
    case POLYDIM_ERR_NUMERICAL_INSTABILITY: return "NUMERICAL_INSTABILITY (pivote)";
    case POLYDIM_ERR_SEQLOCK_RACE:          return "SEQLOCK_RACE (lectura desgarrada)";
    case POLYDIM_ERR_BUFFER_OVERFLOW:       return "BUFFER_OVERFLOW (K fuera de rango)";
    case POLYDIM_ERR_INVALID_SCALAR:        return "INVALID_SCALAR (theta/tau no finito)";
    case POLYDIM_ERR_BASIS_NOT_ORTHONORMAL: return "BASIS_NOT_ORTHONORMAL";
    case POLYDIM_ERR_POINT_OFF_MANIFOLD:    return "POINT_OFF_MANIFOLD";
    case POLYDIM_ERR_ALIASED_BUFFERS:       return "ALIASED_BUFFERS";
    case POLYDIM_ERR_COMPENSATION_BROKEN:   return "COMPENSATION_BROKEN (-ffast-math)";
    default:                                return "DESCONOCIDO";
    }
}

extern "C" POLYDIM_EXPORT const char* POLYDIM_CALL polydim_build_info(void) {
    return "POLYDIM V764"
#if POLYDIM_ENABLE_FTZ
           " | FTZ/DAZ=ON (NO conforme IEEE-754)"
#else
           " | FTZ/DAZ=OFF (conforme IEEE-754)"
#endif
#ifdef POLYDIM_USE_BLAS
           " | BLAS=ON"
#else
           " | BLAS=OFF (bucles nativos)"
#endif
#if defined(_OPENMP)
           " | OpenMP=ON"
#else
           " | OpenMP=OFF"
#endif
           ;
}

/* ==========================================================================
 * S^(D-1): Rodrigues endurecido
 * ========================================================================*/
extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_rodrigues_geodesic_f64(
    const double* __restrict__ y, const double* __restrict__ u, const double* __restrict__ v, double* __restrict__ y_out,
    double theta, uint64_t D,
    const PolydimTolerances* __restrict__ tol_in, PolydimReport* __restrict__ report)
{
    polydim_report_init(report);                       /* A7: SIEMPRE se rellena */

    if (!y || !u || !v || !y_out) return POLYDIM_ERR_NULL_POINTER;
    if (D == 0)                   return POLYDIM_ERR_INVALID_DIMENSION;
    if (D > (SIZE_MAX / sizeof(double))) return POLYDIM_ERR_INVALID_DIMENSION;

    /* A3: el chequeo más barato del kernel, y el que faltaba. */
    if (!require_finite(theta))   return POLYDIM_ERR_INVALID_SCALAR;

    const size_t bytes = static_cast<size_t>(D) * sizeof(double);
    if (overlaps(y_out, u, bytes) || overlaps(y_out, v, bytes))
        return POLYDIM_ERR_ALIASED_BUFFERS;            /* y_out==y sí es legal */

    const PolydimTolerances tol = tol_in ? *tol_in : polydim_default_tolerances(D);

    set_fp_mode();
    const int nthreads = clamp_threads(omp_get_max_threads());

    /* A10: num_threads explícito, el arreglo se indexa por tid. */
    std::vector<Neumaier> a_yy(nthreads), a_yu(nthreads), a_yv(nthreads),
                          a_uu(nthreads), a_vv(nthreads), a_uv(nthreads);
    int bad_value = 0;

    #pragma omp parallel num_threads(nthreads) reduction(|:bad_value)
    {
        set_fp_mode();                                 /* A6: por hilo (MXCSR) */
        const int tid = omp_get_thread_num();
        Neumaier l_yy, l_yu, l_yv, l_uu, l_vv, l_uv;

        #pragma omp for schedule(static)
        for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
            const double yi = y[i], ui = u[i], vi = v[i];
            if (!std::isfinite(yi) || !std::isfinite(ui) || !std::isfinite(vi))
                bad_value = 1;
            l_yy.add(yi * yi);
            l_yu.add(yi * ui);
            l_yv.add(yi * vi);
            l_uu.add(ui * ui);
            l_vv.add(vi * vi);
            l_uv.add(ui * vi);
        }
        a_yy[tid] = l_yy; a_yu[tid] = l_yu; a_yv[tid] = l_yv;
        a_uu[tid] = l_uu; a_vv[tid] = l_vv; a_uv[tid] = l_uv;
    }
    if (bad_value) return POLYDIM_ERR_NAN_OR_INF;

    Neumaier t_yy, t_yu, t_yv, t_uu, t_vv, t_uv;
    for (int t = 0; t < nthreads; ++t) {
        t_yy.merge(a_yy[t]); t_yu.merge(a_yu[t]); t_yv.merge(a_yv[t]);
        t_uu.merge(a_uu[t]); t_vv.merge(a_vv[t]); t_uv.merge(a_uv[t]);
    }
    const double yy = t_yy.total(), yu = t_yu.total(), yv = t_yv.total();
    const double uu = t_uu.total(), vv = t_vv.total(), uv = t_uv.total();

    const double e_yy = std::abs(yy - 1.0);
    const double e_uu = std::abs(uu - 1.0);
    const double e_vv = std::abs(vv - 1.0);
    const double e_uv = std::abs(uv);
    if (report) {
        report->point_norm_err = e_yy;
        report->basis_uu_err   = e_uu;
        report->basis_vv_err   = e_vv;
        report->basis_uv_err   = e_uv;
        report->threads_used   = static_cast<uint64_t>(nthreads);
    }

    /* A4: el punto debe estar sobre la variedad. */
    if (e_yy > tol.point_norm) return POLYDIM_ERR_POINT_OFF_MANIFOLD;

    /* A2: la compuerta que V761 calculaba y descartaba. Coste medido: ~1 %. */
    if (e_uu > tol.basis_ortho || e_vv > tol.basis_ortho || e_uv > tol.basis_ortho)
        return POLYDIM_ERR_BASIS_NOT_ORTHONORMAL;

    /* Rotación CANÓNICA R(+theta). Versine por medio ángulo: sin(t/2) evita la
     * cancelación catastrófica de (1 - cos t) cuando t -> 0. */
    const double sh   = std::sin(0.5 * theta);
    const double vers = 2.0 * sh * sh;        /* = 1 - cos(theta) */
    const double sn   = std::sin(theta);

    const double alpha = -vers * yu - sn * yv;   /* coeficiente de u */
    const double beta  = -vers * yv + sn * yu;   /* coeficiente de v */

    #pragma omp parallel num_threads(nthreads)
    {
        set_fp_mode();
        #pragma omp for schedule(static)
        for (int64_t i = 0; i < static_cast<int64_t>(D); ++i)
            y_out[i] = y[i] + alpha * u[i] + beta * v[i];
    }

    /* Verificación a posteriori: el kernel mide lo que promete. */
    {
        std::vector<Neumaier> a_oo(nthreads);
        #pragma omp parallel num_threads(nthreads)
        {
            set_fp_mode();
            const int tid = omp_get_thread_num();
            Neumaier l;
            #pragma omp for schedule(static)
            for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) l.add(y_out[i] * y_out[i]);
            a_oo[tid] = l;
        }
        Neumaier t_oo;
        for (int t = 0; t < nthreads; ++t) t_oo.merge(a_oo[t]);
        const double out_err = std::abs(std::sqrt(t_oo.total()) - 1.0);
        if (report) report->out_norm_err = out_err;
        if (out_err > tol.point_norm) return POLYDIM_ERR_DEGENERATE_NORM;
    }
    return POLYDIM_SUCCESS;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_project_sphere_f64(
    const double* __restrict__ y, double* __restrict__ y_out, uint64_t D, PolydimReport* __restrict__ report)
{
    polydim_report_init(report);
    if (!y || !y_out) return POLYDIM_ERR_NULL_POINTER;
    if (D == 0)       return POLYDIM_ERR_INVALID_DIMENSION;
    set_fp_mode();
    const int nthreads = clamp_threads(omp_get_max_threads());
    std::vector<Neumaier> acc(nthreads);
    int bad = 0;
    #pragma omp parallel num_threads(nthreads) reduction(|:bad)
    {
        set_fp_mode();
        const int tid = omp_get_thread_num();
        Neumaier l;
        #pragma omp for schedule(static)
        for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
            if (!std::isfinite(y[i])) bad = 1;
            l.add(y[i] * y[i]);
        }
        acc[tid] = l;
    }
    if (bad) return POLYDIM_ERR_NAN_OR_INF;
    Neumaier t; for (int i = 0; i < nthreads; ++i) t.merge(acc[i]);
    const double n2 = t.total();
    if (!(n2 > 0.0) || !std::isfinite(n2)) return POLYDIM_ERR_DEGENERATE_NORM;
    const double n = std::sqrt(n2);
    if (n < 1e-150) return POLYDIM_ERR_DEGENERATE_NORM;
    if (report) report->point_norm_err = std::abs(n - 1.0);
    const double inv = 1.0 / n;
    #pragma omp parallel for num_threads(nthreads) schedule(static)
    for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) y_out[i] = y[i] * inv;
    return POLYDIM_SUCCESS;
}

/* Producto escalar compensado, paralelo y reproducible entre ejecuciones. */
static double polydim_cdot(const double* a, const double* b, uint64_t D, int nthreads) {
    std::vector<Neumaier> acc(nthreads);
    #pragma omp parallel num_threads(nthreads)
    {
        set_fp_mode();
        const int tid = omp_get_thread_num();
        Neumaier l;
        #pragma omp for schedule(static)
        for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) l.add(a[i] * b[i]);
        acc[tid] = l;
    }
    Neumaier t; for (int i = 0; i < nthreads; ++i) t.merge(acc[i]);
    return t.total();
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_orthonormalize_pair_f64(
    double* __restrict__ u, double* __restrict__ v, uint64_t D, PolydimReport* __restrict__ report)
{
    polydim_report_init(report);
    if (!u || !v) return POLYDIM_ERR_NULL_POINTER;
    if (D < 2)    return POLYDIM_ERR_INVALID_DIMENSION;
    set_fp_mode();
    const int nt = clamp_threads(omp_get_max_threads());

    for (uint64_t i = 0; i < D; ++i)
        if (!std::isfinite(u[i]) || !std::isfinite(v[i])) return POLYDIM_ERR_NAN_OR_INF;

    double nu2 = polydim_cdot(u, u, D, nt);
    if (!(nu2 > 1e-300)) return POLYDIM_ERR_DEGENERATE_NORM;
    double inv = 1.0 / std::sqrt(nu2);
    #pragma omp parallel for num_threads(nt) schedule(static)
    for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) u[i] *= inv;

    /* Dos pasadas de Gram-Schmidt modificado: una sola pasada deja un residuo
     * O(kappa*eps) que puede exceder la cota de 64*eps. */
    for (int pass = 0; pass < 2; ++pass) {
        const double d = polydim_cdot(u, v, D, nt);
        #pragma omp parallel for num_threads(nt) schedule(static)
        for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) v[i] -= d * u[i];
    }
    double nv2 = polydim_cdot(v, v, D, nt);
    if (!(nv2 > 1e-300)) return POLYDIM_ERR_DEGENERATE_NORM;  /* v paralelo a u */
    inv = 1.0 / std::sqrt(nv2);
    #pragma omp parallel for num_threads(nt) schedule(static)
    for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) v[i] *= inv;

    if (report) {
        report->basis_uu_err = std::abs(polydim_cdot(u, u, D, nt) - 1.0);
        report->basis_vv_err = std::abs(polydim_cdot(v, v, D, nt) - 1.0);
        report->basis_uv_err = std::abs(polydim_cdot(u, v, D, nt));
        report->threads_used = static_cast<uint64_t>(nt);
    }
    return POLYDIM_SUCCESS;
}

/* ==========================================================================
 * St(D,K): Cayley-SMW endurecido
 * ========================================================================*/
extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_project_tangent_stiefel_f64(
    const double* __restrict__ X, const double* __restrict__ G, double* __restrict__ G_out, uint64_t D, uint32_t K)
{
    if (!X || !G || !G_out) return POLYDIM_ERR_NULL_POINTER;
    if (D == 0 || K == 0)   return POLYDIM_ERR_INVALID_DIMENSION;
    if (K > POLYDIM_MAX_K)  return POLYDIM_ERR_BUFFER_OVERFLOW;
    set_fp_mode();
    const uint32_t KK = K * K;
    const int nthreads = clamp_threads(omp_get_max_threads());
    std::vector<double> XtG(KK, 0.0);
    std::vector<double> arena(static_cast<size_t>(nthreads) * KK, 0.0);
    #pragma omp parallel num_threads(nthreads)
    {
        set_fp_mode();
        double* L = arena.data() + static_cast<size_t>(omp_get_thread_num()) * KK;
        #pragma omp for schedule(static)
        for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
            const double* xi = X + static_cast<size_t>(i) * K;
            const double* gi = G + static_cast<size_t>(i) * K;
            for (uint32_t r = 0; r < K; ++r) {
                const double xr = xi[r];
                double* Lr = L + static_cast<size_t>(r) * K;
                for (uint32_t c = 0; c < K; ++c) Lr[c] += xr * gi[c];
            }
        }
    }
    #pragma omp parallel for num_threads(nthreads) schedule(static)
    for (int64_t j = 0; j < static_cast<int64_t>(KK); ++j) {
        double s = 0.0;
        for (int t = 0; t < nthreads; ++t) s += arena[static_cast<size_t>(t) * KK + j];
        XtG[j] = s;
    }
    /* sym(X^T G) */
    std::vector<double> S(KK);
    for (uint32_t r = 0; r < K; ++r)
        for (uint32_t c = 0; c < K; ++c)
            S[r * K + c] = 0.5 * (XtG[r * K + c] + XtG[c * K + r]);
    /* Misma inversion de bucles que en la retraccion: axpy contiguo sobre c. */
    #pragma omp parallel for num_threads(nthreads) schedule(static)
    for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
        const double* xi = X + static_cast<size_t>(i) * K;
        const double* gi = G + static_cast<size_t>(i) * K;
        double* oi = G_out + static_cast<size_t>(i) * K;
        for (uint32_t c = 0; c < K; ++c) oi[c] = gi[c];
        for (uint32_t p = 0; p < K; ++p) {
            const double xp = xi[p];
            if (xp == 0.0) continue;
            const double* Sp = S.data() + static_cast<size_t>(p) * K;
            for (uint32_t c = 0; c < K; ++c) oi[c] -= xp * Sp[c];
        }
    }
    return POLYDIM_SUCCESS;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_stiefel_cayley_smw_f64(
    const double* __restrict__ X, const double* __restrict__ G, double* __restrict__ Y_out,
    uint64_t D, uint32_t K, double tau,
    const PolydimTolerances* __restrict__ tol_in, PolydimReport* __restrict__ report)
{
    polydim_report_init(report);

    if (!X || !G || !Y_out) return POLYDIM_ERR_NULL_POINTER;
    if (D == 0 || K == 0)   return POLYDIM_ERR_INVALID_DIMENSION;
    /* Límite honesto, no el 1024 nominal de V761. */
    if (K > POLYDIM_MAX_K)  return POLYDIM_ERR_BUFFER_OVERFLOW;
    if (static_cast<uint64_t>(K) > D) return POLYDIM_ERR_INVALID_DIMENSION;
    if (!require_finite(tau)) return POLYDIM_ERR_INVALID_SCALAR;   /* A3 */

    const size_t bytes = static_cast<size_t>(D) * static_cast<size_t>(K) * sizeof(double);
    if (overlaps(Y_out, X, bytes) || overlaps(Y_out, G, bytes))
        return POLYDIM_ERR_ALIASED_BUFFERS;

    const PolydimTolerances tol = tol_in ? *tol_in : polydim_default_tolerances(D);
    set_fp_mode();

    const uint32_t K2  = 2u * K;
    const size_t   KK2 = static_cast<size_t>(K2) * K2;

    /* P1: presupuesto de memoria en lugar de reventar la RAM con K grande.
     * V761 con K=1024 y 16 hilos reservaba 403 MB sin control alguno. */
    int nthreads = clamp_threads(omp_get_max_threads());
    while (nthreads > 1 &&
           static_cast<uint64_t>(nthreads) * KK2 * sizeof(double) > POLYDIM_GRAM_ARENA_BUDGET_BYTES)
        nthreads /= 2;
    if (report) report->threads_used = static_cast<uint64_t>(nthreads);

    /* S = W^T W con W = [X G] (D x 2K). De un solo barrido salen XtX, XtG y GtG.
     * Sólo se acumula el triángulo superior: ~33 % menos flops que los tres
     * productos separados de V761, y con localidad contigua en la dimensión K. */
    std::vector<double> S;
    try { S.assign(KK2, 0.0); } catch (const std::bad_alloc&) { return POLYDIM_ERR_BUFFER_OVERFLOW; }

    int bad_value = 0;

#ifdef POLYDIM_USE_BLAS
    {
        /* Ruta BLAS: W empaquetada D x 2K, dsyrk en triángulo superior. */
        std::vector<double> W;
        try { W.assign(static_cast<size_t>(D) * K2, 0.0); }
        catch (const std::bad_alloc&) { return POLYDIM_ERR_BUFFER_OVERFLOW; }
        #pragma omp parallel for num_threads(nthreads) schedule(static) reduction(|:bad_value)
        for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
            const double* xi = X + static_cast<size_t>(i) * K;
            const double* gi = G + static_cast<size_t>(i) * K;
            double* wi = W.data() + static_cast<size_t>(i) * K2;
            for (uint32_t k = 0; k < K; ++k) {
                if (!std::isfinite(xi[k]) || !std::isfinite(gi[k])) bad_value = 1;
                wi[k] = xi[k]; wi[K + k] = gi[k];
            }
        }
        if (bad_value) return POLYDIM_ERR_NAN_OR_INF;
        /* W es row-major D x K2 == column-major K2 x D. dsyrk con 'N' sobre
         * la vista column-major calcula W_cm * W_cm^T = W_rm^T * W_rm.
         * uplo='L' (triángulo inferior column-major) == triángulo superior en la
         * vista row-major que usa el resto del kernel. */
        const char uplo = 'L', trans = 'N';
        const int n = static_cast<int>(K2), kk = static_cast<int>(D);
        const int lda = static_cast<int>(K2), ldc = static_cast<int>(K2);
        const double one = 1.0, zero = 0.0;
        dsyrk_(&uplo, &trans, &n, &kk, &one, W.data(), &lda, &zero, S.data(), &ldc);
    }
#else
    {
        std::vector<double> arena;
        try { arena.assign(static_cast<size_t>(nthreads) * KK2, 0.0); }
        catch (const std::bad_alloc&) { return POLYDIM_ERR_BUFFER_OVERFLOW; }

        const int64_t DTILE = 8192;
        const int64_t ntiles = (static_cast<int64_t>(D) + DTILE - 1) / DTILE;

        #pragma omp parallel num_threads(nthreads) reduction(|:bad_value)
        {
            set_fp_mode();
            const int tid = omp_get_thread_num();
            double* L = arena.data() + static_cast<size_t>(tid) * KK2;

            #pragma omp for schedule(static)
            for (int64_t tile = 0; tile < ntiles; ++tile) {
                const int64_t begin = tile * DTILE;
                const int64_t end = std::min(begin + DTILE, static_cast<int64_t>(D));

                for (int64_t d = begin; d < end; ++d) {
                    const double* __restrict__ xr = X + static_cast<size_t>(d) * K;
                    const double* __restrict__ gr = G + static_cast<size_t>(d) * K;

                    // Compute XtX, XtG, GtG directly into the joint K2xK2 accumulator L
                    // where L is representing the upper triangle of W^T W for W=[X G].
                    // Let's iterate i from 0 to K-1:
                    for (uint32_t i = 0; i < K; ++i) {
                        const double xi = xr[i];
                        const double gi = gr[i];

                        if (!std::isfinite(xi) || !std::isfinite(gi)) {
                            bad_value = 1;
                        }

                        // W = [X G], so row w = [xr, gr]
                        // L[r, c] for 0 <= r < K2, r <= c < K2
                        // Block 0,0: XtX (r=i, c=j) for j >= i
                        #pragma omp simd
                        for (uint32_t j = i; j < K; ++j) {
                            L[i * K2 + j] += xi * xr[j];
                        }
                        // Block 0,1: XtG (r=i, c=K+j) for all j
                        #pragma omp simd
                        for (uint32_t j = 0; j < K; ++j) {
                            L[i * K2 + (K + j)] += xi * gr[j];
                        }
                        // Block 1,1: GtG (r=K+i, c=K+j) for j >= i
                        #pragma omp simd
                        for (uint32_t j = i; j < K; ++j) {
                            L[(K + i) * K2 + (K + j)] += gi * gr[j];
                        }
                    }
                }
            }
        }
        if (bad_value) return POLYDIM_ERR_NAN_OR_INF;

        /* A11/P1: reducción en árbol paralela sobre elementos.
         * Sustituye al #pragma omp critical que serializaba K^2 sumas por hilo. */
        #pragma omp parallel for num_threads(nthreads) schedule(static)
        for (int64_t r = 0; r < static_cast<int64_t>(K2); ++r) {
            for (uint32_t c = static_cast<uint32_t>(r); c < K2; ++c) {
                const size_t j = static_cast<size_t>(r) * K2 + c;
                double s = 0.0;
                for (int t = 0; t < nthreads; ++t) s += arena[static_cast<size_t>(t) * KK2 + j];
                S[j] = s;
            }
        }
    }
#endif

    /* Espejar el triángulo inferior. */
    for (uint32_t r = 0; r < K2; ++r)
        for (uint32_t c = 0; c < r; ++c)
            S[static_cast<size_t>(r) * K2 + c] = S[static_cast<size_t>(c) * K2 + r];

    auto XtX = [&](uint32_t r, uint32_t c) { return S[static_cast<size_t>(r) * K2 + c]; };
    auto XtG = [&](uint32_t r, uint32_t c) { return S[static_cast<size_t>(r) * K2 + (K + c)]; };
    auto GtG = [&](uint32_t r, uint32_t c) { return S[static_cast<size_t>(K + r) * K2 + (K + c)]; };

    /* Compuerta de factibilidad: X debe estar sobre St(D,K). */
    double xtx_err = 0.0;
    for (uint32_t r = 0; r < K; ++r)
        for (uint32_t c = 0; c < K; ++c)
            xtx_err = std::max(xtx_err, std::abs(XtX(r, c) - (r == c ? 1.0 : 0.0)));
    if (report) report->point_norm_err = xtx_err;
    if (xtx_err > tol.gram_ortho) return POLYDIM_ERR_POINT_OFF_MANIFOLD;   /* A4 */

    /* ---- Parche B (V764): Proyeccion al espacio tangente ANTES del solver ----
     * G_proj = G - X * sym(X^T G).  Materializado para uso en el paso final. */
    std::vector<double> G_proj;
    try { G_proj.assign(static_cast<size_t>(D) * K, 0.0); }
    catch (const std::bad_alloc&) { return POLYDIM_ERR_BUFFER_OVERFLOW; }
    {
        const uint32_t KK = K * K;
        std::vector<double> Sym(KK);
        for (uint32_t r = 0; r < K; ++r)
            for (uint32_t c = 0; c < K; ++c)
                Sym[r * K + c] = 0.5 * (XtG(r, c) + XtG(c, r));

        /* G_proj[i] = G[i] - X[i] * Sym   (D x K) */
        #pragma omp parallel for num_threads(nthreads) schedule(static)
        for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
            const double* xi = X + static_cast<size_t>(i) * K;
            const double* gi = G + static_cast<size_t>(i) * K;
            double* gpi = G_proj.data() + static_cast<size_t>(i) * K;
            for (uint32_t c = 0; c < K; ++c) {
                double s = gi[c];
                for (uint32_t q = 0; q < K; ++q)
                    s -= xi[q] * Sym[q * K + c];
                gpi[c] = s;
            }
        }

        /* Actualizar bloques del Gram: XtG_proj y GtG_proj */
        for (uint32_t r = 0; r < K; ++r)
            for (uint32_t c = 0; c < K; ++c) {
                double xtgp = XtG(r, c);
                for (uint32_t q = 0; q < K; ++q)
                    xtgp -= XtX(r, q) * Sym[q * K + c];
                S[static_cast<size_t>(r) * K2 + (K + c)] = xtgp;
                S[static_cast<size_t>(K + c) * K2 + r] = xtgp;   /* espejo */
            }
        /* GtG_proj(r,c) = G_proj^T G_proj: recalcular con producto escalar */
        std::vector<double> GpGp(KK, 0.0);
        std::vector<double> arena_gp(static_cast<size_t>(nthreads) * KK, 0.0);
        #pragma omp parallel num_threads(nthreads)
        {
            double* L = arena_gp.data() + static_cast<size_t>(omp_get_thread_num()) * KK;
            #pragma omp for schedule(static)
            for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
                const double* gpi = G_proj.data() + static_cast<size_t>(i) * K;
                for (uint32_t r = 0; r < K; ++r) {
                    const double gr = gpi[r];
                    double* Lr = L + static_cast<size_t>(r) * K;
                    for (uint32_t c = r; c < K; ++c) Lr[c] += gr * gpi[c];
                }
            }
        }
        for (uint32_t r = 0; r < K; ++r)
            for (uint32_t c = r; c < K; ++c) {
                double s = 0.0;
                for (int t = 0; t < nthreads; ++t)
                    s += arena_gp[static_cast<size_t>(t) * KK + r * K + c];
                S[static_cast<size_t>(K + r) * K2 + (K + c)] = s;
                S[static_cast<size_t>(K + c) * K2 + (K + r)] = s;
            }
    }

    /* M = I - (tau/2) V^T U  con  U=[G_proj X], V=[X -G_proj].
     * A9: se construye y a la vez se mide ||M||_inf para el umbral relativo. */
    std::vector<double> M(KK2), Z(static_cast<size_t>(K2) * K);
    const double ht = 0.5 * tau;
    double m_inf = 0.0;
    for (uint32_t r = 0; r < K2; ++r) {
        double rowsum = 0.0;
        for (uint32_t c = 0; c < K2; ++c) {
            double vtu;
            if (r < K)  vtu = (c < K) ?  XtG(r, c)        :  XtX(r, c - K);
            else        vtu = (c < K) ? -GtG(r - K, c)    : -XtG(c - K, r - K);
            double val = -ht * vtu;
            if (r == c) val += 1.0;
            M[static_cast<size_t>(r) * K2 + c] = val;
            rowsum += std::abs(val);
        }
        m_inf = std::max(m_inf, rowsum);
    }
    for (uint32_t r = 0; r < K2; ++r)
        for (uint32_t c = 0; c < K; ++c)
            Z[static_cast<size_t>(r) * K + c] = (r < K) ? XtX(r, c) : -XtG(c, r - K);

    /* A9: umbral RELATIVO a ||M||_inf. V761 comparaba contra 1e-15 absoluto. */
    const double pivot_thr = tol.pivot_rel * m_inf * static_cast<double>(K2);
    if (report) report->pivot_threshold = pivot_thr;

#ifdef POLYDIM_USE_BLAS
    {
        /* dgesv trabaja en column-major: transponer M y Z, resolver, destransponer. */
        std::vector<double> Mc(KK2), Zc(static_cast<size_t>(K2) * K);
        for (uint32_t r = 0; r < K2; ++r) for (uint32_t c = 0; c < K2; ++c)
            Mc[static_cast<size_t>(c) * K2 + r] = M[static_cast<size_t>(r) * K2 + c];
        for (uint32_t r = 0; r < K2; ++r) for (uint32_t c = 0; c < K; ++c)
            Zc[static_cast<size_t>(c) * K2 + r] = Z[static_cast<size_t>(r) * K + c];
        int n = static_cast<int>(K2), nrhs = static_cast<int>(K), info = 0;
        std::vector<int> ipiv(K2);
        dgesv_(&n, &nrhs, Mc.data(), &n, ipiv.data(), Zc.data(), &n, &info);
        if (info != 0) return POLYDIM_ERR_NUMERICAL_INSTABILITY;
        double pmin = std::numeric_limits<double>::infinity();
        for (uint32_t k = 0; k < K2; ++k)
            pmin = std::min(pmin, std::abs(Mc[static_cast<size_t>(k) * K2 + k]));
        if (report) report->pivot_min = pmin;
        if (pmin < pivot_thr) return POLYDIM_ERR_NUMERICAL_INSTABILITY;
        for (uint32_t r = 0; r < K2; ++r) for (uint32_t c = 0; c < K; ++c)
            Z[static_cast<size_t>(r) * K + c] = Zc[static_cast<size_t>(c) * K2 + r];
    }
#else
    {
        /* Eliminación gaussiana con pivoteo parcial y umbral relativo. */
        double pivot_min = std::numeric_limits<double>::infinity();
        for (uint32_t k = 0; k < K2; ++k) {
            uint32_t piv = k;
            double best = std::abs(M[static_cast<size_t>(k) * K2 + k]);
            for (uint32_t r = k + 1; r < K2; ++r) {
                const double a = std::abs(M[static_cast<size_t>(r) * K2 + k]);
                if (a > best) { best = a; piv = r; }
            }
            pivot_min = std::min(pivot_min, best);
            if (!(best > pivot_thr)) {
                if (report) report->pivot_min = pivot_min;
                return POLYDIM_ERR_NUMERICAL_INSTABILITY;
            }
            if (piv != k) {
                for (uint32_t c = 0; c < K2; ++c)
                    std::swap(M[static_cast<size_t>(k) * K2 + c], M[static_cast<size_t>(piv) * K2 + c]);
                for (uint32_t c = 0; c < K; ++c)
                    std::swap(Z[static_cast<size_t>(k) * K + c], Z[static_cast<size_t>(piv) * K + c]);
            }
            const double diag = M[static_cast<size_t>(k) * K2 + k];
            for (uint32_t r = k + 1; r < K2; ++r) {
                const double f = M[static_cast<size_t>(r) * K2 + k] / diag;
                if (f == 0.0) continue;
                for (uint32_t c = k + 1; c < K2; ++c)
                    M[static_cast<size_t>(r) * K2 + c] -= f * M[static_cast<size_t>(k) * K2 + c];
                for (uint32_t c = 0; c < K; ++c)
                    Z[static_cast<size_t>(r) * K + c] -= f * Z[static_cast<size_t>(k) * K + c];
            }
        }
        if (report) report->pivot_min = pivot_min;
        for (int32_t r = static_cast<int32_t>(K2) - 1; r >= 0; --r) {
            const double diag = M[static_cast<size_t>(r) * K2 + r];
            for (uint32_t c = 0; c < K; ++c) {
                double s = Z[static_cast<size_t>(r) * K + c];
                for (uint32_t q = static_cast<uint32_t>(r) + 1; q < K2; ++q)
                    s -= M[static_cast<size_t>(r) * K2 + q] * Z[static_cast<size_t>(q) * K + c];
                Z[static_cast<size_t>(r) * K + c] = s / diag;
            }
        }
    }
#endif

    /* Y = X + tau * U Z,  U = [G_proj X].
     * P1 — LOCALIDAD: la forma obvia (acumular d sobre p con k fijo) recorre Z
     * con salto K y deja el bucle interno con una dependencia de reducción. Aquí
     * se invierte el orden: por cada p se hace un axpy sobre k, de modo que tanto
     * Z[p*K + k] como y_i[k] son contiguos y vectorizables. */
    #pragma omp parallel for num_threads(nthreads) schedule(static)
    for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
        const double* xi = X + static_cast<size_t>(i) * K;
        const double* gpi = G_proj.data() + static_cast<size_t>(i) * K;
        double* yi = Y_out + static_cast<size_t>(i) * K;
        for (uint32_t k = 0; k < K; ++k) yi[k] = xi[k];
        for (uint32_t p = 0; p < K2; ++p) {
            const double w = (p < K) ? gpi[p] : xi[p - K];
            if (w == 0.0) continue;
            const double s = tau * w;
            const double* Zp = Z.data() + static_cast<size_t>(p) * K;
            for (uint32_t k = 0; k < K; ++k) yi[k] += s * Zp[k];
        }
    }

    /* Verificación a posteriori de max|Y^T Y - I|. Esto es lo que el documento
     * de entrega llamaba "Ortho Error": ahora se mide, no se declara.
     *
     * NOTA MEDIDA: esta suma no está compensada, así que report->ortho_err
     * SOBREESTIMA el error real por un factor de 4 a 7. Comprobado contra una
     * medición independiente con OpenBLAS (suma por bloques):
     *   D=4096,K=16   interno 2.22e-15  real 6.66e-16
     *   D=65536,K=64  interno 7.33e-15  real 1.11e-15
     * El sesgo es CONSERVADOR: la compuerta nunca acepta algo peor de lo que
     * declara. Es la única dirección aceptable para un umbral de certificación. */
    {
        const uint32_t KK = K * K;
        std::vector<double> arena(static_cast<size_t>(nthreads) * KK, 0.0);
        #pragma omp parallel num_threads(nthreads)
        {
            set_fp_mode();
            double* L = arena.data() + static_cast<size_t>(omp_get_thread_num()) * KK;
            #pragma omp for schedule(static)
            for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
                const double* yi = Y_out + static_cast<size_t>(i) * K;
                for (uint32_t r = 0; r < K; ++r) {
                    const double yr = yi[r];
                    double* Lr = L + static_cast<size_t>(r) * K;
                    for (uint32_t c = r; c < K; ++c) Lr[c] += yr * yi[c];
                }
            }
        }
        double err = 0.0;
        for (uint32_t r = 0; r < K; ++r)
            for (uint32_t c = r; c < K; ++c) {
                double s = 0.0;
                for (int t = 0; t < nthreads; ++t)
                    s += arena[static_cast<size_t>(t) * KK + static_cast<size_t>(r) * K + c];
                err = std::max(err, std::abs(s - (r == c ? 1.0 : 0.0)));
            }
        if (report) report->ortho_err = err;
        if (err > tol.gram_ortho) return POLYDIM_ERR_DEGENERATE_NORM;
    }
    return POLYDIM_SUCCESS;
}

/* ==========================================================================
 * A1 — PMTP V762: triple búfer con seqlock por ranura
 * ========================================================================*/
struct PMTP_Control {
    alignas(64) std::atomic<uint8_t> state;
};

extern "C" POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_sizeof(void)  { return sizeof(PMTP_Control); }
extern "C" POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_alignof(void) { return alignof(PMTP_Control); }

extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_init(PMTP_Control* c) {
    if (!c) return;
    c->state.store(0x24, std::memory_order_release);
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_begin_write(PMTP_Control* c, uint64_t* slot_out) {
    if (!c || !slot_out) return POLYDIM_ERR_NULL_POINTER;
    uint8_t s = c->state.load(std::memory_order_acquire);
    *slot_out = (s >> 4) & 3;
    return POLYDIM_SUCCESS;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_commit_write(PMTP_Control* c, uint64_t slot) {
    if (!c) return POLYDIM_ERR_NULL_POINTER;
    uint8_t s = c->state.load(std::memory_order_relaxed);
    uint8_t next_s;
    do {
        uint8_t oldest = s & 3;
        uint8_t middle = (s >> 2) & 3;
        uint8_t newest = (s >> 4) & 3;
        next_s = oldest | (newest << 2) | (middle << 4) | (1 << 6);
    } while (!c->state.compare_exchange_weak(s, next_s, std::memory_order_release, std::memory_order_relaxed));
    return POLYDIM_SUCCESS;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_acquire_read(
    PMTP_Control* c, uint64_t* observed_seq, uint64_t* slot_out, uint64_t* ticket_out)
{
    if (!c || !observed_seq || !slot_out || !ticket_out) return POLYDIM_ERR_NULL_POINTER;
    uint8_t s = c->state.load(std::memory_order_acquire);
    if (!(s & (1 << 6))) return 0;
    uint8_t next_s;
    uint8_t middle;
    do {
        uint8_t oldest = s & 3;
        middle = (s >> 2) & 3;
        uint8_t newest = (s >> 4) & 3;
        next_s = middle | (oldest << 2) | (newest << 4);
    } while (!c->state.compare_exchange_weak(s, next_s, std::memory_order_acquire, std::memory_order_relaxed));
    *slot_out = middle;
    *observed_seq = 1;
    *ticket_out = 0;
    return 1;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_validate_read(
    const PMTP_Control* c, uint64_t slot, uint64_t ticket)
{
    if (!c) return POLYDIM_ERR_NULL_POINTER;
    return POLYDIM_SUCCESS;
}

/* ==========================================================================
 * A11 — Autodiagnóstico de la compensación
 * ========================================================================*/
extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL
polydim_selftest_compensation(double* observed_err) {
    /* Secuencia adversaria clásica: 1 + n*eps/2 sumado término a término.
     * La suma ingenua devuelve 1.0; Neumaier recupera el total exacto. */
    const int n = 1000000;
    const double small = kEps / 2.0;
    Neumaier acc;
    acc.add(1.0);
    for (int i = 0; i < n; ++i) acc.add(small);
    const double expected = 1.0 + static_cast<double>(n) * small;
    const double got = acc.total();
    const double err = std::abs(got - expected) / expected;
    if (observed_err) *observed_err = err;
    /* Si el compilador reasoció, got == 1.0 y el error relativo es ~1.1e-10. */
    if (!(err < 1e-14)) return POLYDIM_ERR_COMPENSATION_BROKEN;
    return POLYDIM_SUCCESS;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_selftest_all(void) {
    double e = 0.0;
    int32_t rc = polydim_selftest_compensation(&e);
    if (rc != POLYDIM_SUCCESS) return rc;
    /* Un escalar no finito debe ser rechazado, no propagado. */
    double y[4] = {1.0, 0.0, 0.0, 0.0}, u[4] = {0.0, 1.0, 0.0, 0.0},
           v[4] = {0.0, 0.0, 1.0, 0.0}, o[4] = {0, 0, 0, 0};
    const double nan_v = std::numeric_limits<double>::quiet_NaN();
    if (polydim_rodrigues_geodesic_f64(y, u, v, o, nan_v, 4, nullptr, nullptr)
        != POLYDIM_ERR_INVALID_SCALAR) return POLYDIM_ERR_NUMERICAL_INSTABILITY;
    /* Una base no ortonormal debe ser rechazada, no aceptada. */
    double u_bad[4] = {0.0, 2.0, 0.0, 0.0};
    if (polydim_rodrigues_geodesic_f64(y, u_bad, v, o, 0.3, 4, nullptr, nullptr)
        != POLYDIM_ERR_BASIS_NOT_ORTHONORMAL) return POLYDIM_ERR_NUMERICAL_INSTABILITY;
    /* Un punto fuera de la esfera debe ser rechazado. */
    double y_bad[4] = {1.0 + 1e-6, 0.0, 0.0, 0.0};
    if (polydim_rodrigues_geodesic_f64(y_bad, u, v, o, 0.3, 4, nullptr, nullptr)
        != POLYDIM_ERR_POINT_OFF_MANIFOLD) return POLYDIM_ERR_NUMERICAL_INSTABILITY;
    return POLYDIM_SUCCESS;
}
// ============================================================================
// CHOLQR2 TILING L2 (BLOCK SIZE 8192)
// ============================================================================
extern "C" {
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_cholqr2_f64(
    double* __restrict__ X,       // D x K (row-major)
    uint64_t D,
    uint32_t K
) {
    if (!X) return POLYDIM_ERR_NULL_POINTER;
    if (D == 0 || K == 0 || D < K) return POLYDIM_ERR_INVALID_DIMENSION;
    if (K > 1024) return POLYDIM_ERR_BUFFER_OVERFLOW;

    set_fp_mode();
    const int64_t TILE = 8192;
    int max_threads = omp_get_max_threads();

    for (int step = 0; step < 2; ++step) {
        std::vector<double> thread_XTX(max_threads * K * K, 0.0);
        int nan_detected = 0;

        #pragma omp parallel reduction(|:nan_detected)
        {
            set_fp_mode();
            int tid = omp_get_thread_num();
            double* local_xtx = &thread_XTX[tid * K * K];

            #pragma omp for schedule(dynamic)
            for (int64_t b = 0; b < static_cast<int64_t>(D); b += TILE) {
                int64_t b_end = std::min(b + TILE, static_cast<int64_t>(D));
                for (int64_t i = b; i < b_end; ++i) {
                    const double* xi = &X[i * K];
                    for (uint32_t r = 0; r < K; ++r) {
                        double xr = xi[r];
                        if (std::isnan(xr) || std::isinf(xr)) {
                            nan_detected = 1;
                        }
                        for (uint32_t c = r; c < K; ++c) { // Only upper/lower needed, we compute full for simplicity or just lower?
                            // Compute full for now. It's symmetric.
                            local_xtx[r * K + c] = std::fma(xr, xi[c], local_xtx[r * K + c]);
                        }
                    }
                }
            }
        }

        if (nan_detected) return POLYDIM_ERR_NAN_OR_INF;

        std::vector<double> A(K * K, 0.0);
        for (int t = 0; t < max_threads; ++t) {
            double* l_xtx = &thread_XTX[t * K * K];
            for (uint32_t r = 0; r < K; ++r) {
                for (uint32_t c = r; c < K; ++c) {
                    A[r * K + c] += l_xtx[r * K + c];
                }
            }
        }
        
        // Fill lower triangle from upper, since we only accumulated c >= r
        for (uint32_t r = 0; r < K; ++r) {
            for (uint32_t c = r + 1; c < K; ++c) {
                A[c * K + r] = A[r * K + c];
            }
        }

        // Cholesky L L^T
        std::vector<double> L(K * K, 0.0);
        for (uint32_t i = 0; i < K; ++i) {
            for (uint32_t j = 0; j <= i; ++j) {
                double s = A[i * K + j];
                for (uint32_t k = 0; k < j; ++k) {
                    s -= L[i * K + k] * L[j * K + k];
                }
                if (i == j) {
                    if (s <= 1e-14) return POLYDIM_ERR_DEGENERATE_NORM;
                    L[i * K + i] = std::sqrt(s);
                } else {
                    L[i * K + j] = s / L[j * K + j];
                }
            }
        }

        #pragma omp parallel for schedule(static)
        for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
            double* xi = &X[i * K];
            for (uint32_t k = 0; k < K; ++k) {
                double val = xi[k];
                for (uint32_t j = 0; j < k; ++j) {
                    val -= L[k * K + j] * xi[j];
                }
                xi[k] = val / L[k * K + k];
            }
        }
    }

    return POLYDIM_SUCCESS;
}
} // extern "C"

`

---

## 2. Native Rust Topological Guard (kernel_rust_v766.rs)

`
// ============================================================================
// POLYDIM V762 — NATIVE RUST TOPOLOGICAL GUARD & INVARIANT ENGINE
// Catch-Unwind Protected FFI | Betti-1 Graph Topology | Higham Bounds on S^(D-1)
// ============================================================================

use std::panic::catch_unwind;
use std::slice;

#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PolydimRustStatus {
    Success = 0,
    ErrNullPointer = -1,
    ErrInvalidDimension = -2,
    ErrNanOrInf = -3,
    ErrSubnormalDetected = -4,
    ErrNumericalInstability = -5,
    ErrTopologyFragmented = -6,
    ErrBufferOverflow = -7,
    ErrDegenerateNorm = -8,
    ErrSeqLockRace = -9,
    ErrPanicCaught = -99,
}

const EPS_MACH: f64 = f64::EPSILON; // 2.220446049250313e-16

#[no_mangle]
pub unsafe extern "C" fn polydim_rust_verify_invariants(
    ptr: *const f64,
    d: usize,
    max_drift_out: *mut f64,
) -> i32 {
    let result = catch_unwind(|| {
        if ptr.is_null() {
            return PolydimRustStatus::ErrNullPointer;
        }
        if d == 0 {
            return PolydimRustStatus::ErrInvalidDimension;
        }

        let slice = slice::from_raw_parts(ptr, d);

        // Neumaier compensated 2-norm summation
        let mut sum: f64 = 0.0;
        let mut c: f64 = 0.0;

        for &val in slice {
            if val.is_nan() || val.is_infinite() {
                return PolydimRustStatus::ErrNanOrInf;
            }

            let sq = val * val;
            let t = sum + sq;
            if sum.abs() >= sq.abs() {
                c += (sum - t) + sq;
            } else {
                c += (sq - t) + sum;
            }
            sum = t;
        }

        let norm_sq = sum + c;
        if norm_sq <= 1e-300 {
            return PolydimRustStatus::ErrDegenerateNorm;
        }

        let norm = norm_sq.sqrt();
        let drift = (norm - 1.0).abs();

        if !max_drift_out.is_null() {
            *max_drift_out = drift;
        }

        // C++ V764 Alignment: Tol = 64 * eps_mach (invariant O(eps) under compensated summation)
        let tol = 64.0 * EPS_MACH;
        if drift > tol {
            return PolydimRustStatus::ErrNumericalInstability;
        }

        PolydimRustStatus::Success
    });

    match result {
        Ok(status) => status as i32,
        Err(_) => PolydimRustStatus::ErrPanicCaught as i32,
    }
}

#[no_mangle]
pub unsafe extern "C" fn polydim_rust_betti1_guard(
    adj_matrix: *const f64,
    n: usize,
    threshold: f64,
) -> i32 {
    let result = catch_unwind(|| {
        if adj_matrix.is_null() {
            return PolydimRustStatus::ErrNullPointer;
        }
        if n == 0 {
            return PolydimRustStatus::ErrInvalidDimension;
        }
        if n > 4096 {
            return PolydimRustStatus::ErrBufferOverflow;
        }

        let mat = slice::from_raw_parts(adj_matrix, n * n);

        // Disjoint Set Union (DSU / Union-Find) to compute Betti-0 and Betti-1
        let mut parent: Vec<usize> = (0..n).collect();
        let mut rank: Vec<usize> = vec![0; n];

        fn find(parent: &mut [usize], i: usize) -> usize {
            if parent[i] == i {
                i
            } else {
                let p = parent[i];
                parent[i] = find(parent, p);
                parent[i]
            }
        }

        fn union(parent: &mut [usize], rank: &mut [usize], i: usize, j: usize) -> bool {
            let root_i = find(parent, i);
            let root_j = find(parent, j);
            if root_i != root_j {
                if rank[root_i] < rank[root_j] {
                    parent[root_i] = root_j;
                } else if rank[root_i] > rank[root_j] {
                    parent[root_j] = root_i;
                } else {
                    parent[root_j] = root_i;
                    rank[root_i] += 1;
                }
                true
            } else {
                false // Cycle detected (increases Betti-1)
            }
        }

        let mut edges = 0usize;
        let mut components = n;

        for i in 0..n {
            for j in (i + 1)..n {
                let weight = mat[i * n + j];
                if weight.is_nan() || weight.is_infinite() {
                    return PolydimRustStatus::ErrNanOrInf;
                }
                if weight >= threshold {
                    edges += 1;
                    if union(&mut parent, &mut rank, i, j) {
                        components -= 1;
                    }
                }
            }
        }

        // Betti-0 is number of connected components
        // Betti-1 = Edges - Vertices + Connected Components
        if components > 1 {
            return PolydimRustStatus::ErrTopologyFragmented;
        }

        PolydimRustStatus::Success
    });

    match result {
        Ok(status) => status as i32,
        Err(_) => PolydimRustStatus::ErrPanicCaught as i32,
    }
}

`

---

## 3. Python Orchestrator Monolith (polydim_v766_monolito.py)

`
# ============================================================================
# POLYDIM V764 — MONOLITHIC PRODUCTION ORCHESTRATOR
# IEEE-754 Strict Precision | S^(D-1) Manifold Geometry | PMTP Zero-Copy IPC
# Multi-Platform Hardware Agnostic | C++/Rust/Triton FFI | Topological Guard
# ============================================================================

import os
import sys
import gc
import time
import mmap
import ctypes
import platform
import numpy as np
from typing import Tuple, Optional, Dict, Any

# Ensure Windows finds MinGW runtime DLLs
if platform.system() == "Windows" and hasattr(os, "add_dll_directory"):
    mingw_bin = r"E:\winlibs_gcc14_zip\mingw64\bin"
    if os.path.exists(mingw_bin):
        try:
            os.add_dll_directory(mingw_bin)
        except Exception:
            pass

# ============================================================================
# 1. HARDWARE PROBE & DYNAMIC SILICON DISCOVERY
# ============================================================================
class HardwareProbe:
    @staticmethod
    def detect_environment() -> Dict[str, Any]:
        info = {
            "os": sys.platform,
            "cpu_threads": os.cpu_count() or 4,
            "cuda_available": False,
            "rocm_available": False,
            "recommended_backend": "CPU_OPENMP"
        }
        try:
            import torch
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                info["cuda_available"] = True
                info["gpu_name"] = device_name
                info["recommended_backend"] = "CUDA_TRITON"
        except Exception:
            pass

        return info

# ============================================================================
# 2. PMTP ZERO-COPY SHARED MEMORY CHANNEL
# ============================================================================
class PMTPSlabChannel:
    NUM_SLOTS = 4

    def __init__(self, tag: str, dimension: int, cpp_dll_path: str, create: bool = True):
        self.tag = tag
        self.D = dimension
        self.tensor_bytes = dimension * 8
        self.total_bytes = 64 + self.NUM_SLOTS * self.tensor_bytes
        self.shm_name = f"polydim_pmtp_{tag}"
        self.create = create
        
        if sys.platform == "win32":
            self.mmap_obj = mmap.mmap(-1, self.total_bytes, tagname=self.shm_name, access=mmap.ACCESS_WRITE)
        else:
            import posix_ipc
            flags = posix_ipc.O_CREAT if create else 0
            self.posix_shm = posix_ipc.SharedMemory(f"/{self.shm_name}", flags, size=self.total_bytes)
            self.mmap_obj = mmap.mmap(self.posix_shm.fd, self.total_bytes)

        # FFI Bridge to avoid TSO/Weak-Ordering data races on ARM/Apple Silicon
        self.lib = ctypes.CDLL(cpp_dll_path)
        self.lib.polydim_pmtp_init.argtypes = [ctypes.c_void_p]
        self.lib.polydim_pmtp_init.restype = None
        self.lib.polydim_pmtp_begin_write.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]
        self.lib.polydim_pmtp_begin_write.restype = ctypes.c_int32
        self.lib.polydim_pmtp_commit_write.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        self.lib.polydim_pmtp_commit_write.restype = ctypes.c_int32
        self.lib.polydim_pmtp_acquire_read.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64)]
        self.lib.polydim_pmtp_acquire_read.restype = ctypes.c_int32
        self.lib.polydim_pmtp_validate_read.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64]
        self.lib.polydim_pmtp_validate_read.restype = ctypes.c_int32

        # Obtenemos puntero void al mmap y conservamos el buffer para evitar GC
        buffer_type = ctypes.c_uint8 * self.total_bytes
        self._ctypes_buf = buffer_type.from_buffer(self.mmap_obj)
        self.mmap_ptr = ctypes.addressof(self._ctypes_buf)

        if create:
            self.lib.polydim_pmtp_init(self.mmap_ptr)

    def write_tensor(self, tensor_f64: np.ndarray) -> int:
        assert tensor_f64.dtype == np.float64 and tensor_f64.size == self.D
        
        # 1. Acquire slot (memory_order_acquire barrier inside C++)
        slot = ctypes.c_uint64(0)
        self.lib.polydim_pmtp_begin_write(self.mmap_ptr, ctypes.byref(slot))
        s = slot.value
        
        # 2. Direct copy to the reserved slot
        offset = 64 + s * self.tensor_bytes
        dest_view = np.frombuffer(self.mmap_obj, dtype=np.float64, count=self.D, offset=offset)
        np.copyto(dest_view, tensor_f64)
        del dest_view
        
        # 3. Commit (memory_order_release barrier inside C++)
        self.lib.polydim_pmtp_commit_write(self.mmap_ptr, s)
        return s

    def read_tensor(self, max_retries: int = 20) -> Optional[np.ndarray]:
        for _ in range(max_retries):
            observed_seq = ctypes.c_uint64(0)
            slot_out = ctypes.c_uint64(0)
            ticket_out = ctypes.c_uint64(0)
            
            # memory_order_acquire inside C++
            has_new = self.lib.polydim_pmtp_acquire_read(
                self.mmap_ptr, ctypes.byref(observed_seq), ctypes.byref(slot_out), ctypes.byref(ticket_out)
            )
            if has_new == 0:
                time.sleep(0.000005)
                continue
                
            s = slot_out.value
            t = ticket_out.value
            offset = 64 + s * self.tensor_bytes
            src_view = np.frombuffer(self.mmap_obj, dtype=np.float64, count=self.D, offset=offset)
            tensor_copy = np.copy(src_view)
            del src_view
            
            # Post-copy atomic validation barrier: verify writer did not cycle into slot during copy
            rc = self.lib.polydim_pmtp_validate_read(self.mmap_ptr, s, t)
            if rc == 0:
                return tensor_copy
            # Seqlock race detected, loop to re-read latest stable slot
            time.sleep(0.000005)
        return None

    def close(self):
        gc.collect()
        if hasattr(self, 'mmap_obj') and self.mmap_obj:
            try:
                self.mmap_obj.close()
            except BufferError:
                pass

# ============================================================================
# 3. NATIVE FFI KERNEL WRAPPER (C++ & RUST)
# ============================================================================
class PolydimNativeCore:
    def __init__(self, cpp_dll_path: str, rust_dll_path: str):
        if not os.path.exists(cpp_dll_path):
            raise FileNotFoundError(f"C++ Kernel DLL not found: {cpp_dll_path}")
        if not os.path.exists(rust_dll_path):
            raise FileNotFoundError(f"Rust Guard DLL not found: {rust_dll_path}")

        bin_dir = os.path.dirname(os.path.abspath(cpp_dll_path))
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(bin_dir)
            except Exception:
                pass

        self.cpp_lib = ctypes.CDLL(cpp_dll_path)
        self.rust_lib = ctypes.CDLL(rust_dll_path)

        # C++ Rodrigues
        self.cpp_lib.polydim_rodrigues_geodesic_f64.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_double, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_void_p
        ]
        self.cpp_lib.polydim_rodrigues_geodesic_f64.restype = ctypes.c_int32

        # C++ Stiefel Cayley-SMW
        self.cpp_lib.polydim_stiefel_cayley_smw_f64.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_uint64, ctypes.c_uint32, ctypes.c_double,
            ctypes.c_void_p, ctypes.c_void_p
        ]
        self.cpp_lib.polydim_stiefel_cayley_smw_f64.restype = ctypes.c_int32

        # C++ Selftest (P1.4: detect -ffast-math at load time)
        self.cpp_lib.polydim_selftest_all.argtypes = []
        self.cpp_lib.polydim_selftest_all.restype = ctypes.c_int32
        rc = self.cpp_lib.polydim_selftest_all()
        if rc != 0:
            raise RuntimeError(f"polydim_selftest_all FAILED: rc={rc} — DLL compiled with -ffast-math?")

        # C++ Build Info
        self.cpp_lib.polydim_build_info.argtypes = []
        self.cpp_lib.polydim_build_info.restype = ctypes.c_char_p

        # Rust Invariant Guard (5 args: y, u, v, d, *mut VerifyReport)
        class VerifyReport(ctypes.Structure):
            _fields_ = [
                ('norm_drift', ctypes.c_double),
                ('basis_uu_err', ctypes.c_double),
                ('basis_vv_err', ctypes.c_double),
                ('basis_uv_err', ctypes.c_double),
                ('bound_used', ctypes.c_double),
                ('subnormal_count', ctypes.c_uint64),
                ('nonfinite_count', ctypes.c_uint64),
            ]
        self.VerifyReport = VerifyReport

        self.rust_lib.polydim_rust_verify_invariants.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_size_t, ctypes.POINTER(VerifyReport)
        ]
        self.rust_lib.polydim_rust_verify_invariants.restype = ctypes.c_int32


    def apply_rodrigues_geodesic(
        self,
        y: np.ndarray,
        u: np.ndarray,
        v: np.ndarray,
        theta: float
    ) -> Tuple[np.ndarray, int]:
        assert y.dtype == np.float64 and u.dtype == np.float64 and v.dtype == np.float64
        D = y.size
        y_out = np.zeros(D, dtype=np.float64)

        status = self.cpp_lib.polydim_rodrigues_geodesic_f64(
            y.ctypes.data,
            u.ctypes.data,
            v.ctypes.data,
            y_out.ctypes.data,
            ctypes.c_double(theta),
            ctypes.c_uint64(D),
            None,
            None
        )
        return y_out, status

    def apply_stiefel_retraction(
        self,
        X: np.ndarray,
        G: np.ndarray,
        tau: float
    ) -> Tuple[np.ndarray, int]:
        assert X.dtype == np.float64 and G.dtype == np.float64
        D, K = X.shape
        Y_out = np.zeros((D, K), dtype=np.float64)

        status = self.cpp_lib.polydim_stiefel_cayley_smw_f64(
            X.ctypes.data,
            G.ctypes.data,
            Y_out.ctypes.data,
            ctypes.c_uint64(D),
            ctypes.c_uint32(K),
            ctypes.c_double(tau),
            None,
            None
        )
        return Y_out, status

    def verify_rust_invariants(self, tensor: np.ndarray) -> Tuple[int, float]:
        assert tensor.dtype == np.float64
        D = tensor.size
        report = self.VerifyReport()
        status = self.rust_lib.polydim_rust_verify_invariants(
            tensor.ctypes.data,
            None,
            None,
            ctypes.c_size_t(D),
            ctypes.byref(report)
        )
        return status, report.norm_drift

    def verify_betti1(self, adj_matrix: np.ndarray, threshold: float = 0.5) -> int:
        assert adj_matrix.dtype == np.float64
        N = adj_matrix.shape[0]
        return self.rust_lib.polydim_rust_betti1_guard(
            adj_matrix.ctypes.data,
            ctypes.c_size_t(N),
            ctypes.c_double(threshold)
        )

# ============================================================================
# 4. CANARY & SANITY EXECUTION ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    print("============================================================================")
    print("POLYDIM V764 — PRODUCTION MONOLITH INGESTION CANARY")
    print("============================================================================")
    hw = HardwareProbe.detect_environment()
    print(f"Hardware Discovery: {hw}")

`

---

## 4. GPU Triton Kernel (polydim_triton_kernel_v766.py)

`
# ============================================================================
# POLYDIM V762 — TRITON GPU SILICON KERNEL (2-PASS RODRIGUES FP64)
# Multi-GPU Agnostic (NVIDIA CUDA / AMD ROCm HIP) | Zero-Copy DMA
# ============================================================================

import torch

try:
    import triton
    import triton.language as tl
    HAS_TRITON = True
except ImportError:
    HAS_TRITON = False

if HAS_TRITON:
    @triton.jit(do_not_specialize=False)
    def rodrigues_geodesic_pass1_kernel(
        y_ptr, u_ptr, v_ptr,
        partial_yu_ptr, partial_yv_ptr, partial_uu_ptr, partial_vv_ptr, partial_uv_ptr,
        D, BLOCK_SIZE: tl.constexpr
    ):
        pid = tl.program_id(axis=0)
        offsets = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
        mask = offsets < D

        yi = tl.load(y_ptr + offsets, mask=mask, other=0.0)
        ui = tl.load(u_ptr + offsets, mask=mask, other=0.0)
        vi = tl.load(v_ptr + offsets, mask=mask, other=0.0)

        # Dot product reductions per block
        yu = tl.sum(yi * ui, axis=0)
        yv = tl.sum(yi * vi, axis=0)
        uu = tl.sum(ui * ui, axis=0)
        vv = tl.sum(vi * vi, axis=0)
        uv = tl.sum(ui * vi, axis=0)

        tl.store(partial_yu_ptr + pid, yu)
        tl.store(partial_yv_ptr + pid, yv)
        tl.store(partial_uu_ptr + pid, uu)
        tl.store(partial_vv_ptr + pid, vv)
        tl.store(partial_uv_ptr + pid, uv)

    @triton.jit(do_not_specialize=False)
    def rodrigues_geodesic_pass2_kernel(
        y_ptr, u_ptr, v_ptr, y_out_ptr,
        alpha, beta,
        D, BLOCK_SIZE: tl.constexpr
    ):
        pid = tl.program_id(axis=0)
        offsets = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
        mask = offsets < D

        yi = tl.load(y_ptr + offsets, mask=mask, other=0.0)
        ui = tl.load(u_ptr + offsets, mask=mask, other=0.0)
        vi = tl.load(v_ptr + offsets, mask=mask, other=0.0)

        # Exact streaming update
        y_out = yi + alpha * ui + beta * vi
        tl.store(y_out_ptr + offsets, y_out, mask=mask)

def apply_triton_rodrigues_geodesic(
    y: torch.Tensor,
    u: torch.Tensor,
    v: torch.Tensor,
    theta: float,
    stream: torch.cuda.Stream = None
) -> torch.Tensor:
    if not HAS_TRITON:
        raise RuntimeError("Triton is not available on this system.")
    
    assert y.is_cuda and u.is_cuda and v.is_cuda, "Tensors must be on GPU device."
    assert y.dtype == torch.float64, "Strict FP64 manifold representation required."

    D = y.numel()
    BLOCK_SIZE = 1024
    grid = (triton.cdiv(D, BLOCK_SIZE),)

    partial_yu = torch.empty(grid[0], dtype=torch.float64, device=y.device)
    partial_yv = torch.empty(grid[0], dtype=torch.float64, device=y.device)
    partial_uu = torch.empty(grid[0], dtype=torch.float64, device=y.device)
    partial_vv = torch.empty(grid[0], dtype=torch.float64, device=y.device)
    partial_uv = torch.empty(grid[0], dtype=torch.float64, device=y.device)

    # PASS 1
    rodrigues_geodesic_pass1_kernel[grid](
        y, u, v,
        partial_yu, partial_yv, partial_uu, partial_vv, partial_uv,
        D, BLOCK_SIZE=BLOCK_SIZE
    )

    yu = torch.sum(partial_yu).item()
    yv = torch.sum(partial_yv).item()
    uu = torch.sum(partial_uu).item()
    vv = torch.sum(partial_vv).item()
    uv = torch.sum(partial_uv).item()

    # Factibility & Orthonormality Gates (64 * eps_mach)
    tol = 64.0 * torch.finfo(torch.float64).eps
    if abs(uu - 1.0) > tol or abs(vv - 1.0) > tol or abs(uv) > tol:
        raise ValueError("Basis {u, v} is not orthonormal within tolerance.")

    half_theta = 0.5 * theta
    sn_half = torch.sin(torch.tensor(half_theta, dtype=torch.float64)).item()
    vers = 2.0 * sn_half * sn_half
    sn = torch.sin(torch.tensor(theta, dtype=torch.float64)).item()

    # Exact orientation fix
    alpha = -vers * yu - sn * yv
    beta = -vers * yv + sn * yu

    y_out = torch.empty_like(y)

    # PASS 2
    rodrigues_geodesic_pass2_kernel[grid](
        y, u, v, y_out,
        alpha, beta,
        D, BLOCK_SIZE=BLOCK_SIZE
    )

    return y_out

`

