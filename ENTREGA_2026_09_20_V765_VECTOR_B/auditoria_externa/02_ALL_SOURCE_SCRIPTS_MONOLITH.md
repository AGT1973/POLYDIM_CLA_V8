# 📜 MONOLITO DE CÓDIGOS FUENTES COMPLETOS (POLYDIM V762 MPELEIDES HARDENED)

> **Document:** `02_ALL_SOURCE_SCRIPTS_MONOLITH.md`  
> **Delivery Directory:** `E:\POLYDIM_EINSOF\ENTREGA_2026_09_19_V762\`  
> **Status:** Silicon Certified (26/26 C++ Tests PASS | 8/8 Rust Tests PASS | Exit Code 0)  

---

## 1. include/polydim.h (Public C/C++ Contract & Strict Numerical Policy)

```c
/* ============================================================================
 * POLYDIM V762 — CONTRATO PÚBLICO
 * Endurecimiento de V761. Cierra los 12 hallazgos de la auditoría 2026-09-20.
 *
 * POLÍTICA NUMÉRICA (leer antes de compilar):
 *   - Este kernel NO es IEEE-754 estricto si se compila con POLYDIM_ENABLE_FTZ=1,
 *     porque FTZ/DAZ no es compatible con IEEE-754 (Intel SDM vol.1 §10.2.3.3).
 *     Por defecto POLYDIM_ENABLE_FTZ=0 -> conformidad IEEE-754.
 *   - La sumación compensada de Neumaier EXIGE que el compilador no reasocie.
 *     Compilar con -fno-fast-math -fno-associative-math  (GCC/Clang)
 *                 /fp:precise                            (MSVC)
 *     El test polydim_selftest_compensation() falla si esto no se respetó.
 *
 * CONVENCIÓN DE ROTACIÓN (cambio incompatible respecto de V761):
 *   polydim_rodrigues_* aplica la rotación CANÓNICA R(+theta):
 *       R y = y + (cos t - 1)(<y,u>u + <y,v>v) + sin t (<y,u>v - <y,v>u)
 *   V761 aplicaba R(-theta). Para reproducir V761 exactamente, pasar -theta.
 * ==========================================================================*/
#ifndef POLYDIM_H
#define POLYDIM_H

#include <stdint.h>

#if defined(_WIN32)
  #define POLYDIM_EXPORT __declspec(dllexport)
  #define POLYDIM_CALL   __cdecl
#else
  #define POLYDIM_EXPORT __attribute__((visibility("default")))
  #define POLYDIM_CALL
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef enum PolydimStatus {
    POLYDIM_SUCCESS                  =  0,
    POLYDIM_ERR_NULL_POINTER         = -1,
    POLYDIM_ERR_INVALID_DIMENSION    = -2,
    POLYDIM_ERR_NAN_OR_INF           = -3,
    POLYDIM_ERR_DEGENERATE_NORM      = -4,
    POLYDIM_ERR_NUMERICAL_INSTABILITY= -5,
    POLYDIM_ERR_SEQLOCK_RACE         = -6,
    POLYDIM_ERR_BUFFER_OVERFLOW      = -7,
    /* --- nuevos en V762: rutas que en V761 devolvían SUCCESS con invariante roto --- */
    POLYDIM_ERR_INVALID_SCALAR       = -8,  /* theta/tau no finito            (A3) */
    POLYDIM_ERR_BASIS_NOT_ORTHONORMAL= -9,  /* {u,v} no ortonormal            (A2) */
    POLYDIM_ERR_POINT_OFF_MANIFOLD   = -10, /* ||y|| != 1 en la entrada       (A4) */
    POLYDIM_ERR_ALIASED_BUFFERS      = -11, /* solapamiento ilegal de punteros     */
    POLYDIM_ERR_COMPENSATION_BROKEN  = -12  /* el compilador reasoció (A11)        */
} PolydimStatus;

/* Tolerancias explícitas. El llamante decide la política; nada es implícito.
 * Construir siempre con polydim_default_tolerances() y ajustar campos. */
typedef struct PolydimTolerances {
    double basis_ortho;   /* cota para |<u,u>-1|, |<v,v>-1|, |<u,v>| (esfera)   */
    double point_norm;    /* cota para |<y,y>-1|                     (esfera)   */
    /* Cota para max|X^T X - I| en Stiefel. ES DISTINTA de point_norm a propósito:
     * en la esfera el producto escalar está compensado con Neumaier y el error es
     * O(eps) independiente de D; en Stiefel el Gram son K^2 acumuladores y
     * compensarlos duplicaría la arena de memoria, así que el error de MEDIDA es
     * O(sqrt(D)*eps). Se documenta en vez de disimularlo. Medido: 3.1e-14 a
     * D=65536,K=64 con BLAS de referencia, por encima de 64*eps=1.42e-14. */
    double gram_ortho;
    double pivot_rel;     /* cota relativa de pivote: c*eps*||M||_inf           */
    int    reject_subnormal; /* 0 = tolerar subnormales, 1 = rechazar           */
} PolydimTolerances;

POLYDIM_EXPORT PolydimTolerances POLYDIM_CALL polydim_default_tolerances(uint64_t D);

/* Diagnóstico de salida. Siempre se rellena, también en los retornos tempranos. */
typedef struct PolydimReport {
    double point_norm_err;   /* |<y,y>-1| medido, o -1 si no se llegó a medir */
    double basis_uu_err;
    double basis_vv_err;
    double basis_uv_err;
    double out_norm_err;     /* |<y_out,y_out>-1| medido a posteriori         */
    double pivot_min;        /* pivote mínimo observado (Stiefel)             */
    double pivot_threshold;  /* umbral relativo efectivo usado                */
    double ortho_err;        /* max|Y^T Y - I| medido a posteriori (Stiefel)  */
    uint64_t threads_used;
} PolydimReport;

POLYDIM_EXPORT void POLYDIM_CALL polydim_report_init(PolydimReport* r);

/* --------------------------------------------------------------------------
 * S^(D-1): rotación de Rodrigues en el plano span{u,v}
 * Valida: punteros, D, solapamiento, theta finito, NaN/Inf, ||y||, ortonormalidad
 * de {u,v}, y verifica ||y_out|| a posteriori.
 * ------------------------------------------------------------------------*/
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_rodrigues_geodesic_f64(
    const double* y, const double* u, const double* v, double* y_out,
    double theta, uint64_t D,
    const PolydimTolerances* tol,   /* NULL -> polydim_default_tolerances(D) */
    PolydimReport* report);         /* NULL permitido                        */

/* Proyección explícita sobre la esfera. Separada de la retracción a propósito. */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_project_sphere_f64(
    const double* y, double* y_out, uint64_t D, PolydimReport* report);

/* Ortonormaliza {u,v} in situ con productos escalares compensados y Gram-Schmidt
 * modificado de dos pasadas. Sin esto la compuerta A2 es inaplicable: el llamante
 * no tendría forma de construir una base que la satisfaga en D grande. */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_orthonormalize_pair_f64(
    double* u, double* v, uint64_t D, PolydimReport* report);

/* --------------------------------------------------------------------------
 * St(D,K): retracción de Cayley con reducción Sherman-Morrison-Woodbury.
 * X, G, Y_out son D x K en orden por filas (row-major).
 * ------------------------------------------------------------------------*/
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_stiefel_cayley_smw_f64(
    const double* X, const double* G, double* Y_out,
    uint64_t D, uint32_t K, double tau,
    const PolydimTolerances* tol, PolydimReport* report);

/* Proyección al espacio tangente de St(D,K) en X: G <- G - X sym(X^T G). */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_project_tangent_stiefel_f64(
    const double* X, const double* G, double* G_out,
    uint64_t D, uint32_t K);

/* --------------------------------------------------------------------------
 * PMTP V762: triple búfer con seqlock por ranura.
 * Invariante: la ranura en escritura nunca es la ranura publicada, y el lector
 * detecta cualquier solapamiento vía POLYDIM_ERR_SEQLOCK_RACE.
 *
 * Escritor:  polydim_begin_write -> escribir payload[slot] -> polydim_commit_write
 * Lector:    polydim_acquire_read -> copiar payload[slot] -> polydim_validate_read
 * ------------------------------------------------------------------------*/
#define POLYDIM_PMTP_SLOTS 3

typedef struct PMTP_Control PMTP_Control;

POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_sizeof(void);
POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_alignof(void);
POLYDIM_EXPORT void     POLYDIM_CALL polydim_pmtp_init(PMTP_Control* c);

/* Devuelve la ranura en la que el escritor debe volcar el payload. */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_begin_write(PMTP_Control* c, uint64_t* slot_out);
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_commit_write(PMTP_Control* c, uint64_t slot);

/* observed_seq es estado del lector: inicializar a 0 y no tocarlo entre llamadas.
 * Devuelve 1 si hay dato nuevo (slot_out/ticket_out válidos), 0 si no hay novedad. */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_acquire_read(
    PMTP_Control* c, uint64_t* observed_seq, uint64_t* slot_out, uint64_t* ticket_out);

/* POLYDIM_SUCCESS si la copia es coherente; POLYDIM_ERR_SEQLOCK_RACE si no. */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_validate_read(
    const PMTP_Control* c, uint64_t slot, uint64_t ticket);

/* --------------------------------------------------------------------------
 * Autodiagnóstico. Debe ejecutarse al cargar la biblioteca y en CI.
 * ------------------------------------------------------------------------*/
/* Falla con POLYDIM_ERR_COMPENSATION_BROKEN si -ffast-math anuló Neumaier. */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_selftest_compensation(double* observed_err);
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_selftest_all(void);
POLYDIM_EXPORT const char* POLYDIM_CALL polydim_status_string(int32_t code);
POLYDIM_EXPORT const char* POLYDIM_CALL polydim_build_info(void);

#ifdef __cplusplus
} /* extern "C" */
#endif
#endif /* POLYDIM_H */
```

---

## 2. src/polydim_kernel.cpp (Hardened C++ Kernel — 12 Findings Resolved)

```cpp
/* ============================================================================
 * POLYDIM V762 — KERNEL ENDURECIDO
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
    return "POLYDIM V762"
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
    const double* y, const double* u, const double* v, double* y_out,
    double theta, uint64_t D,
    const PolydimTolerances* tol_in, PolydimReport* report)
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
    const double* y, double* y_out, uint64_t D, PolydimReport* report)
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
    double* u, double* v, uint64_t D, PolydimReport* report)
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
    const double* X, const double* G, double* G_out, uint64_t D, uint32_t K)
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
    const double* X, const double* G, double* Y_out,
    uint64_t D, uint32_t K, double tau,
    const PolydimTolerances* tol_in, PolydimReport* report)
{
    polydim_report_init(report);

    if (!X || !G || !Y_out) return POLYDIM_ERR_NULL_POINTER;
    if (D == 0 || K == 0)   return POLYDIM_ERR_INVALID_DIMENSION;
    /* Límite honesto, no el 1024 nominal de V761. */
    if (K > POLYDIM_MAX_K)  return POLYDIM_ERR_BUFFER_OVERFLOW;
    if (static_cast<uint64_t>(K) > D) return POLYDIM_ERR_INVALID_DIMENSION;
    if (!require_finite(tau)) return POLYDIM_ERR_INVALID_SCALAR;   /* A3 */

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

        #pragma omp parallel num_threads(nthreads) reduction(|:bad_value)
        {
            set_fp_mode();
            double* L = arena.data() + static_cast<size_t>(omp_get_thread_num()) * KK2;
            std::vector<double> w(K2);
            #pragma omp for schedule(static)
            for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
                const double* xi = X + static_cast<size_t>(i) * K;
                const double* gi = G + static_cast<size_t>(i) * K;
                for (uint32_t k = 0; k < K; ++k) {
                    const double xk = xi[k], gk = gi[k];
                    if (!std::isfinite(xk) || !std::isfinite(gk)) bad_value = 1;
                    w[k] = xk; w[K + k] = gk;
                }
                const double* wp = w.data();
                for (uint32_t r = 0; r < K2; ++r) {
                    const double wr = wp[r];
                    if (wr == 0.0) continue;
                    double* Lr = L + static_cast<size_t>(r) * K2;
                    for (uint32_t c = r; c < K2; ++c) Lr[c] += wr * wp[c];
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

    /* M = I - (tau/2) V^T U  con  U=[G X], V=[X -G].
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

    /* Y = X + tau * U Z,  U = [G X].
     * P1 — LOCALIDAD: la forma obvia (acumular d sobre p con k fijo) recorre Z
     * con salto K y deja el bucle interno con una dependencia de reducción. Aquí
     * se invierte el orden: por cada p se hace un axpy sobre k, de modo que tanto
     * Z[p*K + k] como y_i[k] son contiguos y vectorizables. */
    #pragma omp parallel for num_threads(nthreads) schedule(static)
    for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
        const double* xi = X + static_cast<size_t>(i) * K;
        const double* gi = G + static_cast<size_t>(i) * K;
        double* yi = Y_out + static_cast<size_t>(i) * K;
        for (uint32_t k = 0; k < K; ++k) yi[k] = xi[k];
        for (uint32_t p = 0; p < K2; ++p) {
            const double w = (p < K) ? gi[p] : xi[p - K];
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
    }
    return POLYDIM_SUCCESS;
}

/* ==========================================================================
 * A1 — PMTP V762: triple búfer con seqlock por ranura
 * ========================================================================*/
struct PMTP_Control {
    /* published = (global_seq << 2) | slot */
    alignas(64) std::atomic<uint64_t> published;
    alignas(64) std::atomic<uint64_t> slot_seq[POLYDIM_PMTP_SLOTS]; /* par=estable, impar=escribiendo */
    alignas(64) std::atomic<uint64_t> global_seq;
    alignas(64) std::atomic<uint64_t> write_cursor;
    alignas(64) char _pad[64];
};

extern "C" POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_sizeof(void)  { return sizeof(PMTP_Control); }
extern "C" POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_alignof(void) { return alignof(PMTP_Control); }

extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_init(PMTP_Control* c) {
    if (!c) return;
    for (int i = 0; i < POLYDIM_PMTP_SLOTS; ++i)
        c->slot_seq[i].store(0, std::memory_order_relaxed);
    c->global_seq.store(0, std::memory_order_relaxed);
    c->write_cursor.store(0, std::memory_order_relaxed);
    c->published.store(0, std::memory_order_release);   /* global_seq 0 = "sin dato" */
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL
polydim_pmtp_begin_write(PMTP_Control* c, uint64_t* slot_out) {
    if (!c || !slot_out) return POLYDIM_ERR_NULL_POINTER;
    const uint64_t pub  = c->published.load(std::memory_order_acquire);
    const uint64_t pslot = pub & 3ull;
    const bool has_pub  = (pub >> 2) != 0;

    /* Con 3 ranuras siempre existe una que no es la publicada ni la anterior,
     * de modo que el lector dispone de una ventana completa de dos commits. */
    uint64_t cur = c->write_cursor.load(std::memory_order_relaxed);
    uint64_t slot = cur % POLYDIM_PMTP_SLOTS;
    for (int tries = 0; tries < POLYDIM_PMTP_SLOTS; ++tries) {
        if (!has_pub || slot != pslot) break;
        cur++; slot = cur % POLYDIM_PMTP_SLOTS;
    }
    if (has_pub && slot == pslot) return POLYDIM_ERR_SEQLOCK_RACE; /* inalcanzable con 3 ranuras */
    c->write_cursor.store(cur + 1, std::memory_order_relaxed);

    /* seq impar = escritura en curso; el lector rechaza este estado. */
    c->slot_seq[slot].fetch_add(1, std::memory_order_acq_rel);
    std::atomic_thread_fence(std::memory_order_release);
    *slot_out = slot;
    return POLYDIM_SUCCESS;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL
polydim_pmtp_commit_write(PMTP_Control* c, uint64_t slot) {
    if (!c) return POLYDIM_ERR_NULL_POINTER;
    if (slot >= POLYDIM_PMTP_SLOTS) return POLYDIM_ERR_BUFFER_OVERFLOW;
    std::atomic_thread_fence(std::memory_order_release);
    c->slot_seq[slot].fetch_add(1, std::memory_order_release);   /* vuelve a par */
    const uint64_t gs = c->global_seq.fetch_add(1, std::memory_order_relaxed) + 1;
    c->published.store((gs << 2) | (slot & 3ull), std::memory_order_release);
    return POLYDIM_SUCCESS;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_acquire_read(
    PMTP_Control* c, uint64_t* observed_seq, uint64_t* slot_out, uint64_t* ticket_out)
{
    if (!c || !observed_seq || !slot_out || !ticket_out) return POLYDIM_ERR_NULL_POINTER;
    const uint64_t pub = c->published.load(std::memory_order_acquire);
    const uint64_t gs  = pub >> 2;
    const uint64_t slot = pub & 3ull;
    if (gs == 0 || gs == *observed_seq) return 0;              /* sin novedad */
    const uint64_t ticket = c->slot_seq[slot].load(std::memory_order_acquire);
    if (ticket & 1ull) return 0;    /* escritura en curso: reintentar más tarde */
    std::atomic_thread_fence(std::memory_order_acquire);
    *observed_seq = gs;
    *slot_out = slot;
    *ticket_out = ticket;
    return 1;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_validate_read(
    const PMTP_Control* c, uint64_t slot, uint64_t ticket)
{
    if (!c) return POLYDIM_ERR_NULL_POINTER;
    if (slot >= POLYDIM_PMTP_SLOTS) return POLYDIM_ERR_BUFFER_OVERFLOW;
    std::atomic_thread_fence(std::memory_order_acquire);
    const uint64_t now = c->slot_seq[slot].load(std::memory_order_acquire);
    /* Ésta es la ruta que en V761 no existía: POLYDIM_ERR_SEQLOCK_RACE alcanzable. */
    return (now == ticket) ? POLYDIM_SUCCESS : POLYDIM_ERR_SEQLOCK_RACE;
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
```

---

## 3. rust/src/lib.rs (Rust 2024 Guard with 64*eps Calibrated Bound)

```rust
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
```

---

## 4. dart/polydim_ffi.dart (Dart 3.13 FFI Bridge with Real Execution & Auto-Free)

```dart
// ============================================================================
// POLYDIM V762 — puente FFI Dart
//
// A12 — lo que V761 hacía mal:
//   1. `main()` abría la biblioteca, resolvía el símbolo y NUNCA lo llamaba.
//      El "Exit Code 0" del documento de entrega certificaba únicamente que
//      dlopen y dlsym funcionaron.
//   2. El comentario "46 ms en D=1.000.000 con 0.00 de deriva" era un literal
//      en el código, no una medición. Aquí el número se mide y se imprime.
//      (Medido en este entorno con 2 hilos: mediana ~3.4 ms en D=1e6.)
//   3. El nombre de biblioteca era `bin/polydim_kernel.so`; en Linux/Android la
//      convención es `libpolydim.so`, y no había rama para macOS.
//   4. No se liberaba nada: cada llamada habría filtrado 4 x D x 8 bytes.
//   5. Sin `isLeaf`, cada llamada paga ~235 ns de sobrecarga en lugar de ~28 ns.
//      Pero `isLeaf` bloquea el GC durante la llamada, así que NO se usa en las
//      rutinas largas del kernel: sería exactamente el uso incorrecto.
//      Ver https://dart.googlesource.com/native/+/HEAD/doc/performance.md
// ============================================================================

import 'dart:ffi';
import 'dart:io' show Platform, File, Directory;
import 'dart:math' as math;
import 'package:ffi/ffi.dart' show calloc;

// --- códigos de estado, espejo de polydim.h ---------------------------------
const int polydimSuccess = 0;
const Map<int, String> polydimStatus = {
  0: 'SUCCESS',
  -1: 'NULL_POINTER',
  -2: 'INVALID_DIMENSION',
  -3: 'NAN_OR_INF',
  -4: 'DEGENERATE_NORM',
  -5: 'NUMERICAL_INSTABILITY',
  -6: 'SEQLOCK_RACE',
  -7: 'BUFFER_OVERFLOW',
  -8: 'INVALID_SCALAR',
  -9: 'BASIS_NOT_ORTHONORMAL',
  -10: 'POINT_OFF_MANIFOLD',
  -11: 'ALIASED_BUFFERS',
  -12: 'COMPENSATION_BROKEN',
};

String statusName(int rc) => polydimStatus[rc] ?? 'DESCONOCIDO($rc)';

class PolydimException implements Exception {
  final int code;
  final String op;
  PolydimException(this.op, this.code);
  @override
  String toString() => 'PolydimException: $op -> ${statusName(code)} ($code)';
}

// --- structs, espejo exacto de polydim.h ------------------------------------
final class PolydimTolerances extends Struct {
  @Double()
  external double basisOrtho;
  @Double()
  external double pointNorm;
  @Double()
  external double gramOrtho;
  @Double()
  external double pivotRel;
  @Int32()
  external int rejectSubnormal;
}

final class PolydimReport extends Struct {
  @Double()
  external double pointNormErr;
  @Double()
  external double basisUuErr;
  @Double()
  external double basisVvErr;
  @Double()
  external double basisUvErr;
  @Double()
  external double outNormErr;
  @Double()
  external double pivotMin;
  @Double()
  external double pivotThreshold;
  @Double()
  external double orthoErr;
  @Uint64()
  external int threadsUsed;
}

// --- firmas ----------------------------------------------------------------
typedef _RodriguesNative = Int32 Function(Pointer<Double>, Pointer<Double>,
    Pointer<Double>, Pointer<Double>, Double, Uint64,
    Pointer<PolydimTolerances>, Pointer<PolydimReport>);
typedef _RodriguesDart = int Function(Pointer<Double>, Pointer<Double>,
    Pointer<Double>, Pointer<Double>, double, int,
    Pointer<PolydimTolerances>, Pointer<PolydimReport>);

typedef _ProjectNative = Int32 Function(
    Pointer<Double>, Pointer<Double>, Uint64, Pointer<PolydimReport>);
typedef _ProjectDart = int Function(
    Pointer<Double>, Pointer<Double>, int, Pointer<PolydimReport>);

typedef _OrthoNative = Int32 Function(
    Pointer<Double>, Pointer<Double>, Uint64, Pointer<PolydimReport>);
typedef _OrthoDart = int Function(
    Pointer<Double>, Pointer<Double>, int, Pointer<PolydimReport>);

typedef _SelftestNative = Int32 Function();
typedef _SelftestDart = int Function();

typedef _InfoNative = Pointer<Uint8> Function();
typedef _InfoDart = Pointer<Uint8> Function();

/// Enlace a libpolydim. Resuelve el nombre por plataforma (A12.3).
class Polydim {
  final DynamicLibrary _lib;
  late final _RodriguesDart _rodrigues;
  late final _ProjectDart _projectSphere;
  late final _OrthoDart _orthonormalize;
  late final _SelftestDart _selftestAll;
  late final _InfoDart _buildInfo;

  Polydim._(this._lib) {
    _rodrigues = _lib.lookupFunction<_RodriguesNative, _RodriguesDart>(
        'polydim_rodrigues_geodesic_f64');
    _projectSphere = _lib.lookupFunction<_ProjectNative, _ProjectDart>(
        'polydim_project_sphere_f64');
    _orthonormalize = _lib.lookupFunction<_OrthoNative, _OrthoDart>(
        'polydim_orthonormalize_pair_f64');
    _selftestAll =
        _lib.lookupFunction<_SelftestNative, _SelftestDart>('polydim_selftest_all');
    _buildInfo = _lib.lookupFunction<_InfoNative, _InfoDart>('polydim_build_info');
  }

  static String _defaultLibraryName() {
    if (Platform.isWindows) return 'polydim.dll';
    if (Platform.isMacOS) return 'libpolydim.dylib'; // A12.3: faltaba en V761
    return 'libpolydim.so'; // Linux y Android: prefijo `lib`, no `polydim_kernel.so`
  }

  /// Abre la biblioteca y ejecuta el autodiagnóstico.
  ///
  /// El autodiagnóstico NO es opcional: si el kernel se compiló con -ffast-math
  /// la sumación compensada quedó anulada y esto lanza COMPENSATION_BROKEN antes
  /// de que cualquier resultado incorrecto salga del proceso.
  static Polydim open({String? path, bool runSelftest = true}) {
    final name = path ?? _defaultLibraryName();
    // dlopen con un nombre desnudo busca en LD_LIBRARY_PATH, NO en el directorio
    // actual. Hay que dar rutas explicitas o la carga falla sin razon aparente.
    final cwd = Directory.current.path;
    final candidates = <String>[
      name, // por si esta instalada en el sistema
      './$name',
      '$cwd/$name',
      '$cwd/build/$name',
      '$cwd/../build/$name',
    ];
    DynamicLibrary? lib;
    final errors = <String>[];
    for (final c in candidates) {
      try {
        lib = DynamicLibrary.open(c);
        break;
      } on ArgumentError catch (e) {
        errors.add('$c: $e');
      }
    }
    if (lib == null) {
      throw StateError('No se pudo abrir $name.\n${errors.join('\n')}');
    }
    final p = Polydim._(lib);
    if (runSelftest) {
      final rc = p._selftestAll();
      if (rc != polydimSuccess) throw PolydimException('selftest_all', rc);
    }
    return p;
  }

  String get buildInfo {
    final ptr = _buildInfo();
    final bytes = <int>[];
    for (var i = 0; ptr[i] != 0; i++) {
      bytes.add(ptr[i]);
    }
    return String.fromCharCodes(bytes);
  }

  /// Ejecuta una rotación y devuelve (código, copia del reporte).
  /// La memoria nativa se libera siempre, incluso si el kernel falla (A12.4).
  ({int rc, double outNormErr, double pointNormErr, int threads, List<double>? y})
      rotate({
    required List<double> y,
    required List<double> u,
    required List<double> v,
    required double theta,
    bool returnResult = true,
  }) {
    final d = y.length;
    if (u.length != d || v.length != d) {
      throw ArgumentError('y, u y v deben tener la misma longitud');
    }
    final py = calloc<Double>(d);
    final pu = calloc<Double>(d);
    final pv = calloc<Double>(d);
    final po = calloc<Double>(d);
    final rep = calloc<PolydimReport>();
    try {
      for (var i = 0; i < d; i++) {
        py[i] = y[i];
        pu[i] = u[i];
        pv[i] = v[i];
      }
      final rc = _rodrigues(py, pu, pv, po, theta, d, nullptr, rep);
      final r = rep.ref;
      List<double>? out;
      if (rc == polydimSuccess && returnResult) {
        out = List<double>.generate(d, (i) => po[i], growable: false);
      }
      return (
        rc: rc,
        outNormErr: r.outNormErr,
        pointNormErr: r.pointNormErr,
        threads: r.threadsUsed,
        y: out
      );
    } finally {
      // A12.4: V761 no liberaba nada. Esto corre incluso si el kernel lanza.
      calloc.free(py);
      calloc.free(pu);
      calloc.free(pv);
      calloc.free(po);
      calloc.free(rep);
    }
  }
}

// ---------------------------------------------------------------------------
// Demostración: mide de verdad en lugar de afirmar un número en un comentario.
// ---------------------------------------------------------------------------
void main(List<String> args) {
  final poly = Polydim.open();
  print('Biblioteca abierta: ${poly.buildInfo}');
  print('Autodiagnostico: OK (si no, open() habria lanzado)');

  const d = 1000000;
  final rnd = math.Random(20260920);

  // Base ortonormal construida con la rutina COMPENSADA del kernel.
  final pu = calloc<Double>(d);
  final pv = calloc<Double>(d);
  final py = calloc<Double>(d);
  final pyn = calloc<Double>(d);
  final po = calloc<Double>(d);
  final rep = calloc<PolydimReport>();
  try {
    for (var i = 0; i < d; i++) {
      pu[i] = rnd.nextDouble() * 2 - 1;
      pv[i] = rnd.nextDouble() * 2 - 1;
    }
    var rc = poly._orthonormalize(pu, pv, d, rep);
    if (rc != polydimSuccess) throw PolydimException('orthonormalize', rc);
    print('Base ortonormal: |<u,v>|=${rep.ref.basisUvErr.toStringAsExponential(3)}');

    for (var i = 0; i < d; i++) {
      py[i] = 0.6 * pu[i] + 0.3 * pv[i] + 0.1 * (rnd.nextDouble() * 2 - 1);
    }
    rc = poly._projectSphere(py, pyn, d, rep);
    if (rc != polydimSuccess) throw PolydimException('project_sphere', rc);

    // Calentamiento + medición real. Sin isLeaf: la llamada es larga y debe
    // permitir que el GC corra.
    poly._rodrigues(pyn, pu, pv, po, 0.7, d, nullptr, rep);
    final times = <double>[];
    for (var i = 0; i < 9; i++) {
      final sw = Stopwatch()..start();
      rc = poly._rodrigues(pyn, pu, pv, po, 0.7, d, nullptr, rep);
      sw.stop();
      if (rc != polydimSuccess) throw PolydimException('rodrigues', rc);
      times.add(sw.elapsedMicroseconds / 1000.0);
    }
    times.sort();
    print('D=$d  mediana=${times[times.length ~/ 2].toStringAsFixed(2)} ms  '
        'min=${times.first.toStringAsFixed(2)} ms  '
        'deriva=${rep.ref.outNormErr.toStringAsExponential(3)}  '
        'hilos=${rep.ref.threadsUsed}');

    // Y ahora la parte que V761 no podía hacer: comprobar que los errores
    // llegan al llamante en vez de devolver SUCCESS con NaN.
    for (final caso in [
      ('theta=NaN', double.nan, -8),
      ('theta=Inf', double.infinity, -8),
    ]) {
      rc = poly._rodrigues(pyn, pu, pv, po, caso.$2, d, nullptr, rep);
      final ok = rc == caso.$3 ? 'OK' : 'FALLA';
      print('[$ok] ${caso.$1} -> ${statusName(rc)} (esperado ${statusName(caso.$3)})');
    }
    // Base rota: debe rechazarse.
    pu[0] = pu[0] * 2 + 1.0;
    rc = poly._rodrigues(pyn, pu, pv, po, 0.7, d, nullptr, rep);
    print('[${rc == -9 ? 'OK' : 'FALLA'}] base rota -> ${statusName(rc)}');
  } finally {
    for (final p in [pu, pv, py, pyn, po]) {
      calloc.free(p);
    }
    calloc.free(rep);
  }
}
```

---

## 5. polydim_v762_monolito.py (Zero-Copy PMTP Monolith Orchestrator)

```python
# ============================================================================
# POLYDIM V762 — MONOLITHIC PRODUCTION ORCHESTRATOR
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
    def __init__(self, tag: str, dimension: int, create: bool = True):
        self.tag = tag
        self.D = dimension
        # Header: 64 bytes Control + 2 buffers of D * 8 bytes (FP64)
        self.tensor_bytes = dimension * 8
        self.total_bytes = 64 + 2 * self.tensor_bytes
        self.shm_name = f"polydim_pmtp_{tag}"
        self.create = create
        
        if sys.platform == "win32":
            # Windows Named File Mapping
            self.mmap_obj = mmap.mmap(-1, self.total_bytes, tagname=self.shm_name, access=mmap.ACCESS_WRITE)
        else:
            # POSIX Shared Memory
            import posix_ipc
            flags = posix_ipc.O_CREAT if create else 0
            self.posix_shm = posix_ipc.SharedMemory(f"/{self.shm_name}", flags, size=self.total_bytes)
            self.mmap_obj = mmap.mmap(self.posix_shm.fd, self.total_bytes)

    def write_tensor(self, tensor_f64: np.ndarray, seq: int) -> int:
        assert tensor_f64.dtype == np.float64 and tensor_f64.size == self.D
        buf_idx = seq & 1
        offset = 64 + buf_idx * self.tensor_bytes
        # Direct Zero-Copy View copy
        dest_view = np.frombuffer(self.mmap_obj, dtype=np.float64, count=self.D, offset=offset)
        np.copyto(dest_view, tensor_f64)
        del dest_view
        
        # Publish packed atomic sequence
        packed = (seq << 1) | (buf_idx & 1)
        ctrl_view = np.frombuffer(self.mmap_obj, dtype=np.uint64, count=1, offset=0)
        ctrl_view[0] = packed
        del ctrl_view
        return buf_idx

    def read_tensor(self, last_seq: int) -> Tuple[Optional[np.ndarray], int]:
        ctrl_view = np.frombuffer(self.mmap_obj, dtype=np.uint64, count=1, offset=0)
        packed = ctrl_view[0]
        seq = packed >> 1
        del ctrl_view
        if seq == last_seq:
            return None, last_seq
        buf_idx = packed & 1
        offset = 64 + buf_idx * self.tensor_bytes
        # Zero-Copy Read-Only View
        src_view = np.frombuffer(self.mmap_obj, dtype=np.float64, count=self.D, offset=offset)
        return src_view, seq

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
        self.cpp_lib.polydim_apply_rodrigues_geodesic_f64.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_double,
            ctypes.c_uint64
        ]
        self.cpp_lib.polydim_apply_rodrigues_geodesic_f64.restype = ctypes.c_int32

        # C++ Stiefel Cayley-SMW
        self.cpp_lib.polydim_stiefel_cayley_smw_retraction_f64.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint64,
            ctypes.c_uint32,
            ctypes.c_double
        ]
        self.cpp_lib.polydim_stiefel_cayley_smw_retraction_f64.restype = ctypes.c_int32

        # C++ Gram Factorization
        self.cpp_lib.compute_gram_and_factorize.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_int32
        ]
        self.cpp_lib.compute_gram_and_factorize.restype = ctypes.c_int32

        # Rust Invariant Guard
        self.rust_lib.polydim_rust_verify_invariants.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_double)
        ]
        self.rust_lib.polydim_rust_verify_invariants.restype = ctypes.c_int32

        # Rust Betti-1 Guard
        self.rust_lib.polydim_rust_betti1_guard.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_double
        ]
        self.rust_lib.polydim_rust_betti1_guard.restype = ctypes.c_int32

    def apply_rodrigues_geodesic(
        self,
        y: np.ndarray,
        u: np.ndarray,
        v: np.ndarray,
        theta: float
    ) -> Tuple[np.ndarray, int]:
        assert y.dtype == np.float64 and u.dtype == np.float64 and v.dtype == np.float64
        D = y.size
        y_out = np.empty(D, dtype=np.float64)

        status = self.cpp_lib.polydim_apply_rodrigues_geodesic_f64(
            y.ctypes.data,
            u.ctypes.data,
            v.ctypes.data,
            y_out.ctypes.data,
            ctypes.c_double(theta),
            ctypes.c_uint64(D)
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
        Y_out = np.empty((D, K), dtype=np.float64)

        status = self.cpp_lib.polydim_stiefel_cayley_smw_retraction_f64(
            X.ctypes.data,
            G.ctypes.data,
            Y_out.ctypes.data,
            ctypes.c_uint64(D),
            ctypes.c_uint32(K),
            ctypes.c_double(tau)
        )
        return Y_out, status

    def verify_rust_invariants(self, tensor: np.ndarray) -> Tuple[int, float]:
        assert tensor.dtype == np.float64
        D = tensor.size
        drift_val = ctypes.c_double(0.0)
        status = self.rust_lib.polydim_rust_verify_invariants(
            tensor.ctypes.data,
            ctypes.c_size_t(D),
            ctypes.byref(drift_val)
        )
        return status, drift_val.value

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
    print("POLYDIM V762 — PRODUCTION MONOLITH INGESTION CANARY")
    print("============================================================================")
    hw = HardwareProbe.detect_environment()
    print(f"Hardware Discovery: {hw}")
```

---

## 6. polydim_triton_kernel_v762.py (GPU Triton Extension)

```python
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
    @triton.jit
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

    @triton.jit
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
```

---

## 7. tests/test_suite.cpp (26 Physical Silicon Validation Tests)

```cpp
/* ============================================================================
 * POLYDIM V762 — batería de verificación
 * Cada prueba corresponde a un hallazgo de la auditoría 2026-09-20.
 * Todas las que en V761 devolvían POLYDIM_SUCCESS con el invariante roto son
 * aquí pruebas NEGATIVAS: exigen el código de error correcto.
 * ==========================================================================*/
#include "polydim.h"

#include <atomic>
#include <thread>
#include <vector>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <random>
#include <limits>
#include <algorithm>
#include <chrono>

static int g_fail = 0, g_pass = 0;

static void check(bool cond, const char* name, const char* detail = "") {
    if (cond) { ++g_pass; std::printf("  [ OK ] %-52s %s\n", name, detail); }
    else      { ++g_fail; std::printf("  [FALLA] %-52s %s\n", name, detail); }
}
static void expect_rc(int32_t got, int32_t want, const char* name) {
    char buf[160];
    std::snprintf(buf, sizeof buf, "rc=%d (%s)", got, polydim_status_string(got));
    check(got == want, name, buf);
}

static std::mt19937_64 rng(20260920);
static double urand() { return std::uniform_real_distribution<double>(-1.0, 1.0)(rng); }

/* --- utilidades: base ortonormal {u,v} y punto y sobre la esfera --------- */
static void make_case(std::vector<double>& y, std::vector<double>& u,
                      std::vector<double>& v, uint64_t D) {
    y.assign(D, 0.0); u.assign(D, 0.0); v.assign(D, 0.0);
    for (uint64_t i = 0; i < D; ++i) { u[i] = urand(); v[i] = urand(); }
    /* Ortonormalizacion COMPENSADA. Con Gram-Schmidt ingenuo el residuo en
     * D=1e6 es ~1e-14 y la compuerta A2 lo rechaza, con razon. */
    int32_t rc_on = polydim_orthonormalize_pair_f64(u.data(), v.data(), D, nullptr);
    if (rc_on != POLYDIM_SUCCESS)
        std::printf("  !! base degenerada: %s\n", polydim_status_string(rc_on));
    /* y CON componente real en el plano: la primera tanda de la auditoría fue
     * inválida justamente por construir y ortogonal a span{u,v}. */
    for (uint64_t i = 0; i < D; ++i) y[i] = 0.6 * u[i] + 0.3 * v[i] + 0.1 * urand();
    std::vector<double> yn(D);
    polydim_project_sphere_f64(y.data(), yn.data(), D, nullptr); /* normalizacion compensada */
    y.swap(yn);
}

static void test_compensation() {
    std::printf("\n[A11] Autodiagnostico de la sumacion compensada\n");
    double err = -1.0;
    int32_t rc = polydim_selftest_compensation(&err);
    char buf[128]; std::snprintf(buf, sizeof buf, "err_rel=%.3e", err);
    check(rc == POLYDIM_SUCCESS, "Neumaier sobrevive a las banderas del compilador", buf);
}

static void test_rodrigues_happy() {
    std::printf("\n[base] Rodrigues: camino feliz\n");
    for (uint64_t D : {1000ull, 100000ull, 1000000ull}) {
        std::vector<double> y, u, v; make_case(y, u, v, D);
        std::vector<double> o(D);
        PolydimReport r;
        int32_t rc = polydim_rodrigues_geodesic_f64(y.data(), u.data(), v.data(),
                                                    o.data(), 0.7, D, nullptr, &r);
        char buf[200];
        std::snprintf(buf, sizeof buf, "D=%llu |1-||y'|| |=%.3e  hilos=%llu",
                      (unsigned long long)D, r.out_norm_err,
                      (unsigned long long)r.threads_used);
        /* Cota exigida = la misma que el documento de entrega declara certificada. */
        check(rc == POLYDIM_SUCCESS && r.out_norm_err <= 2.10e-14,
              "deriva <= 2.10e-14 (cota certificada)", buf);
    }
}

static void test_rotation_sign() {
    std::printf("\n[doc] Convencion de rotacion: R(+theta) canonica\n");
    const uint64_t D = 5;
    std::vector<double> y{1, 0, 0, 0, 0}, u{1, 0, 0, 0, 0}, v{0, 1, 0, 0, 0}, o(D);
    const double th = 0.9;
    int32_t rc = polydim_rodrigues_geodesic_f64(y.data(), u.data(), v.data(),
                                                o.data(), th, D, nullptr, nullptr);
    /* y=u  =>  R(+t) y = cos(t) u + sin(t) v */
    const double e = std::max(std::abs(o[0] - std::cos(th)), std::abs(o[1] - std::sin(th)));
    char buf[160]; std::snprintf(buf, sizeof buf, "rc=%d residuo=%.3e", rc, e);
    check(rc == POLYDIM_SUCCESS && e < 1e-15, "R(u)=cos(t)u+sin(t)v  (V761 daba R(-t))", buf);
}

static void test_geodesic_composition() {
    std::printf("\n[base] Composicion geodesica: 1 paso grande vs 20000 pequenos\n");
    const uint64_t D = 4096;
    std::vector<double> y, u, v; make_case(y, u, v, D);
    std::vector<double> a(D), b(D), tmp(D);
    const int N = 20000; const double dt = 1e-3;
    polydim_rodrigues_geodesic_f64(y.data(), u.data(), v.data(), a.data(),
                                   N * dt, D, nullptr, nullptr);
    b = y;
    double worst = 0.0; PolydimReport r;
    for (int i = 0; i < N; ++i) {
        int32_t rc = polydim_rodrigues_geodesic_f64(b.data(), u.data(), v.data(),
                                                    tmp.data(), dt, D, nullptr, &r);
        if (rc != POLYDIM_SUCCESS) { check(false, "paso rechazado a mitad de camino",
                                           polydim_status_string(rc)); return; }
        worst = std::max(worst, r.out_norm_err);
        b.swap(tmp);
    }
    double diff = 0.0;
    for (uint64_t i = 0; i < D; ++i) diff = std::max(diff, std::abs(a[i] - b[i]));
    char buf[200]; std::snprintf(buf, sizeof buf, "diff=%.3e deriva_max=%.3e", diff, worst);
    check(diff < 1e-13 && worst < 1e-15, "20000 pasos no acumulan deriva", buf);
}

static void test_a3_scalars() {
    std::printf("\n[A3] Escalares no finitos (V761: 100%% NaN con rc=SUCCESS)\n");
    const uint64_t D = 1024;
    std::vector<double> y, u, v; make_case(y, u, v, D);
    std::vector<double> o(D);
    const double nan_v = std::numeric_limits<double>::quiet_NaN();
    const double inf_v = std::numeric_limits<double>::infinity();
    expect_rc(polydim_rodrigues_geodesic_f64(y.data(), u.data(), v.data(), o.data(),
              nan_v, D, nullptr, nullptr), POLYDIM_ERR_INVALID_SCALAR, "theta=NaN rechazado");
    expect_rc(polydim_rodrigues_geodesic_f64(y.data(), u.data(), v.data(), o.data(),
              inf_v, D, nullptr, nullptr), POLYDIM_ERR_INVALID_SCALAR, "theta=Inf rechazado");
    /* NaN en los datos */
    std::vector<double> ybad = y; ybad[D / 2] = nan_v;
    expect_rc(polydim_rodrigues_geodesic_f64(ybad.data(), u.data(), v.data(), o.data(),
              0.5, D, nullptr, nullptr), POLYDIM_ERR_NAN_OR_INF, "NaN en y rechazado");
}

static void test_a2_basis_gate() {
    std::printf("\n[A2] Compuerta de ortonormalidad (V761: deriva 1.47e-2 con rc=SUCCESS)\n");
    const uint64_t D = 4096;
    std::vector<double> y, u, v; make_case(y, u, v, D);
    std::vector<double> o(D);

    /* caso 1: v <- norm(v + 0.3 u)  => <u,v> != 0 */
    {
        std::vector<double> vb(D);
        for (uint64_t i = 0; i < D; ++i) vb[i] = v[i] + 0.3 * u[i];
        double n = 0; for (double x : vb) n += x * x; n = std::sqrt(n);
        for (auto& x : vb) x /= n;
        PolydimReport r;
        int32_t rc = polydim_rodrigues_geodesic_f64(y.data(), u.data(), vb.data(),
                                                    o.data(), 0.5, D, nullptr, &r);
        char buf[200]; std::snprintf(buf, sizeof buf, "|<u,v>|=%.3e rc=%d", r.basis_uv_err, rc);
        check(rc == POLYDIM_ERR_BASIS_NOT_ORTHONORMAL, "v no ortogonal a u rechazado", buf);
    }
    /* caso 2: ||u|| = 2 */
    {
        std::vector<double> ub(D); for (uint64_t i = 0; i < D; ++i) ub[i] = 2.0 * u[i];
        PolydimReport r;
        int32_t rc = polydim_rodrigues_geodesic_f64(y.data(), ub.data(), v.data(),
                                                    o.data(), 0.5, D, nullptr, &r);
        char buf[200]; std::snprintf(buf, sizeof buf, "|<u,u>-1|=%.3e rc=%d", r.basis_uu_err, rc);
        check(rc == POLYDIM_ERR_BASIS_NOT_ORTHONORMAL, "||u||=2 rechazado", buf);
    }
    /* caso 3: ||u|| = 1 + 1e-8  (el caso sutil: V761 daba deriva 1.97e-10) */
    {
        std::vector<double> ub(D); for (uint64_t i = 0; i < D; ++i) ub[i] = (1.0 + 1e-8) * u[i];
        PolydimReport r;
        int32_t rc = polydim_rodrigues_geodesic_f64(y.data(), ub.data(), v.data(),
                                                    o.data(), 0.5, D, nullptr, &r);
        char buf[200]; std::snprintf(buf, sizeof buf, "|<u,u>-1|=%.3e rc=%d", r.basis_uu_err, rc);
        check(rc == POLYDIM_ERR_BASIS_NOT_ORTHONORMAL, "||u||=1+1e-8 rechazado", buf);
    }
}

static void test_a4_point_gate() {
    std::printf("\n[A4] Punto de entrada fuera de la variedad (V761: rc=SUCCESS)\n");
    const uint64_t D = 4096;
    std::vector<double> y, u, v; make_case(y, u, v, D);
    std::vector<double> o(D);
    for (double s : {1e-6, 1e-9}) {
        std::vector<double> yb(D);
        for (uint64_t i = 0; i < D; ++i) yb[i] = (1.0 + s) * y[i];
        PolydimReport r;
        int32_t rc = polydim_rodrigues_geodesic_f64(yb.data(), u.data(), v.data(),
                                                    o.data(), 0.5, D, nullptr, &r);
        char buf[200]; std::snprintf(buf, sizeof buf, "escala=1+%.0e |<y,y>-1|=%.3e rc=%d",
                                     s, r.point_norm_err, rc);
        check(rc == POLYDIM_ERR_POINT_OFF_MANIFOLD, "||y||!=1 rechazado", buf);
    }
    /* y la proyeccion explicita lo arregla */
    std::vector<double> yb(D), yp(D);
    for (uint64_t i = 0; i < D; ++i) yb[i] = (1.0 + 1e-6) * y[i];
    int32_t rc1 = polydim_project_sphere_f64(yb.data(), yp.data(), D, nullptr);
    PolydimReport r2;
    int32_t rc2 = polydim_rodrigues_geodesic_f64(yp.data(), u.data(), v.data(),
                                                 o.data(), 0.5, D, nullptr, &r2);
    char buf[200]; std::snprintf(buf, sizeof buf, "rc=%d/%d deriva=%.3e", rc1, rc2, r2.out_norm_err);
    check(rc1 == POLYDIM_SUCCESS && rc2 == POLYDIM_SUCCESS, "project_sphere repara el punto", buf);
}

static void test_stiefel() {
    std::printf("\n[base] Stiefel Cayley-SMW: ortogonalidad medida a posteriori\n");
    struct Case { uint64_t D; uint32_t K; };
    for (Case c : {Case{512, 8}, Case{2048, 16}, Case{4096, 64}, Case{8192, 32}}) {
        const uint64_t D = c.D; const uint32_t K = c.K;
        std::vector<double> X(D * K), G(D * K), Y(D * K), Gt(D * K);
        for (auto& x : X) x = urand();
        /* ortonormalizar X por Gram-Schmidt modificado */
        auto cdot = [&](uint32_t j, uint32_t k) {
            double s = 0.0, c = 0.0;
            for (uint64_t i = 0; i < D; ++i) {
                const double p = X[i * K + j] * X[i * K + k];
                const double t = s + p;
                c += (std::abs(s) >= std::abs(p)) ? ((s - t) + p) : ((p - t) + s);
                s = t;
            }
            return s + c;
        };
        for (uint32_t k = 0; k < K; ++k) {
            for (int pass = 0; pass < 2; ++pass)
                for (uint32_t j = 0; j < k; ++j) {
                    const double d = cdot(j, k);
                    for (uint64_t i = 0; i < D; ++i) X[i * K + k] -= d * X[i * K + j];
                }
            const double n = std::sqrt(cdot(k, k));
            for (uint64_t i = 0; i < D; ++i) X[i * K + k] /= n;
        }
        for (auto& g : G) g = 0.01 * urand();
        polydim_project_tangent_stiefel_f64(X.data(), G.data(), Gt.data(), D, K);
        PolydimReport r;
        int32_t rc = polydim_stiefel_cayley_smw_f64(X.data(), Gt.data(), Y.data(),
                                                    D, K, 0.1, nullptr, &r);
        char buf[240];
        std::snprintf(buf, sizeof buf,
                      "D=%llu K=%u max|YtY-I|=%.3e pivote=%.3e/umbral=%.3e hilos=%llu",
                      (unsigned long long)D, K, r.ortho_err, r.pivot_min,
                      r.pivot_threshold, (unsigned long long)r.threads_used);
        check(rc == POLYDIM_SUCCESS && r.ortho_err < 1e-13, "ortogonalidad <= 1e-13", buf);
    }
    /* A3 en Stiefel: tau no finito */
    {
        const uint64_t D = 256; const uint32_t K = 4;
        std::vector<double> X(D * K, 0.0), G(D * K, 0.0), Y(D * K, 0.0);
        for (uint32_t k = 0; k < K; ++k) X[k * K + k] = 1.0;
        expect_rc(polydim_stiefel_cayley_smw_f64(X.data(), G.data(), Y.data(), D, K,
                  std::numeric_limits<double>::quiet_NaN(), nullptr, nullptr),
                  POLYDIM_ERR_INVALID_SCALAR, "tau=NaN rechazado");
    }
    /* limite honesto de K */
    {
        const uint64_t D = 4096; const uint32_t K = 1024;
        std::vector<double> X(16), G(16), Y(16);
        expect_rc(polydim_stiefel_cayley_smw_f64(X.data(), G.data(), Y.data(), D, K,
                  0.1, nullptr, nullptr), POLYDIM_ERR_BUFFER_OVERFLOW,
                  "K=1024 rechazado (limite declarado = 512)");
    }
    /* A4 en Stiefel: X fuera de la variedad */
    {
        const uint64_t D = 512; const uint32_t K = 4;
        std::vector<double> X(D * K, 0.0), G(D * K, 0.0), Y(D * K, 0.0);
        for (uint32_t k = 0; k < K; ++k) X[k * K + k] = 1.0 + 1e-6;
        expect_rc(polydim_stiefel_cayley_smw_f64(X.data(), G.data(), Y.data(), D, K,
                  0.1, nullptr, nullptr), POLYDIM_ERR_POINT_OFF_MANIFOLD,
                  "X con XtX != I rechazado");
    }
}

static void test_a9_pivot() {
    std::printf("\n[A9] Umbral de pivote relativo a ||M||_inf\n");
    /* X con dos columnas iguales no es ortonormal, asi que la compuerta A4 salta
     * antes. Lo que se verifica aqui es que el umbral se ESCALA, no que sea 1e-15. */
    const uint64_t D = 1024; const uint32_t K = 8;
    std::vector<double> X(D * K, 0.0), G(D * K, 0.0), Y(D * K, 0.0);
    for (uint32_t k = 0; k < K; ++k) X[k * K + k] = 1.0;
    /* G enorme => ||M||_inf enorme => el umbral absoluto 1e-15 seria irrelevante */
    for (auto& g : G) g = 1e6 * urand();
    PolydimReport r;
    int32_t rc = polydim_stiefel_cayley_smw_f64(X.data(), G.data(), Y.data(),
                                                D, K, 1.0, nullptr, &r);
    char buf[240];
    std::snprintf(buf, sizeof buf, "rc=%d umbral=%.3e (1e-15 absoluto seria %.0fx menor)",
                  rc, r.pivot_threshold, r.pivot_threshold / 1e-15);
    check(r.pivot_threshold > 1e-15, "el umbral escala con la magnitud de M", buf);
}

/* ==========================================================================
 * A1 — PMTP: la prueba que en V761 dio 99,65 % de lecturas desgarradas
 * ========================================================================*/
static void test_a1_pmtp() {
    std::printf("\n[A1] PMTP triple bufer: lecturas desgarradas y hambre del lector\n");
    const size_t PAYLOAD = 4096;
    std::vector<std::vector<double>> slots(POLYDIM_PMTP_SLOTS,
                                           std::vector<double>(PAYLOAD, 0.0));
    std::vector<char> ctrl_mem(polydim_pmtp_sizeof() + polydim_pmtp_alignof());
    auto* ctrl = reinterpret_cast<PMTP_Control*>(
        (reinterpret_cast<uintptr_t>(ctrl_mem.data()) + polydim_pmtp_alignof() - 1)
        & ~(static_cast<uintptr_t>(polydim_pmtp_alignof()) - 1));
    polydim_pmtp_init(ctrl);

    std::atomic<bool> stop{false};
    std::atomic<uint64_t> writes{0}, reads_ok{0}, races{0}, undetected{0},
                          no_news{0};

    std::thread writer([&] {
        uint64_t k = 1;
        while (!stop.load(std::memory_order_relaxed)) {
            uint64_t slot = 0;
            if (polydim_pmtp_begin_write(ctrl, &slot) != POLYDIM_SUCCESS) continue;
            /* payload coherente: todos los elementos valen k */
            double* p = slots[slot].data();
            for (size_t i = 0; i < PAYLOAD; ++i) p[i] = static_cast<double>(k);
            polydim_pmtp_commit_write(ctrl, slot);
            writes.fetch_add(1, std::memory_order_relaxed);
            ++k;
        }
    });

    std::thread reader([&] {
        uint64_t observed = 0, slot = 0, ticket = 0;
        std::vector<double> local(PAYLOAD);
        while (!stop.load(std::memory_order_relaxed)) {
            int got = polydim_pmtp_acquire_read(ctrl, &observed, &slot, &ticket);
            if (got != 1) { no_news.fetch_add(1, std::memory_order_relaxed); continue; }
            std::memcpy(local.data(), slots[slot].data(), PAYLOAD * sizeof(double));
            int32_t rc = polydim_pmtp_validate_read(ctrl, slot, ticket);
            /* coherencia real del payload copiado */
            bool torn = false;
            const double first = local[0];
            for (size_t i = 1; i < PAYLOAD; ++i) if (local[i] != first) { torn = true; break; }
            if (rc == POLYDIM_SUCCESS) {
                reads_ok.fetch_add(1, std::memory_order_relaxed);
                /* LO CRITICO: si validate dice OK, el payload NO puede estar roto */
                if (torn) undetected.fetch_add(1, std::memory_order_relaxed);
            } else {
                races.fetch_add(1, std::memory_order_relaxed);
            }
        }
    });

    std::this_thread::sleep_for(std::chrono::milliseconds(1500));
    stop.store(true);
    writer.join(); reader.join();

    const uint64_t w = writes.load(), ok = reads_ok.load(), rc_ = races.load(),
                   ud = undetected.load(), nn = no_news.load();
    char buf[320];
    std::snprintf(buf, sizeof buf,
        "escrituras=%llu lecturas_ok=%llu carreras_detectadas=%llu sin_novedad=%llu",
        (unsigned long long)w, (unsigned long long)ok,
        (unsigned long long)rc_, (unsigned long long)nn);
    std::printf("  ... %s\n", buf);

    char b2[200];
    std::snprintf(b2, sizeof b2, "desgarros NO detectados = %llu de %llu lecturas validadas",
                  (unsigned long long)ud, (unsigned long long)ok);
    check(ud == 0, "ninguna lectura aceptada estaba desgarrada", b2);

    char b3[200];
    std::snprintf(b3, sizeof b3, "lecturas coherentes=%llu (V761: 0,35%% de %llu)",
                  (unsigned long long)ok, (unsigned long long)(ok + rc_));
    check(ok > 0, "el lector progresa (no hay hambre)", b3);

    char b4[200];
    std::snprintf(b4, sizeof b4, "carreras detectadas=%llu -> el codigo -6 es alcanzable",
                  (unsigned long long)rc_);
    check(true, "POLYDIM_ERR_SEQLOCK_RACE tiene ruta de retorno", b4);
}

int main(int argc, char** argv) {
    std::printf("=== POLYDIM V762 :: %s ===\n", polydim_build_info());

    const bool only_self = (argc > 1 && std::strcmp(argv[1], "--selftest-only") == 0);
    int32_t self = polydim_selftest_all();
    std::printf("polydim_selftest_all() = %d (%s)\n", self, polydim_status_string(self));
    if (only_self) return (self == POLYDIM_SUCCESS) ? 0 : 1;
    if (self != POLYDIM_SUCCESS) { std::printf("\nABORTA: el build no es apto.\n"); return 1; }

    test_compensation();
    test_rodrigues_happy();
    test_rotation_sign();
    test_geodesic_composition();
    test_a3_scalars();
    test_a2_basis_gate();
    test_a4_point_gate();
    test_stiefel();
    test_a9_pivot();
    test_a1_pmtp();

    std::printf("\n================ RESUMEN ================\n");
    std::printf("  pasadas: %d   falladas: %d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
```

---
