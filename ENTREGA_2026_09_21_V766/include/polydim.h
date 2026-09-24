/* ============================================================================
 * POLYDIM V763 — CONTRATO PÚBLICO
 * Endurecimiento de V761/V762. Cierra todos los hallazgos P0/P1.
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
    const double* __restrict__ y, const double* __restrict__ u, const double* __restrict__ v, double* __restrict__ y_out,
    double theta, uint64_t D,
    const PolydimTolerances* tol,   /* NULL -> polydim_default_tolerances(D) */
    PolydimReport* report);         /* NULL permitido                        */

/* Proyección explícita sobre la esfera. Separada de la retracción a propósito. */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_project_sphere_f64(
    const double* __restrict__ y, double* __restrict__ y_out, uint64_t D, PolydimReport* __restrict__ report);

/* Ortonormaliza {u,v} in situ con productos escalares compensados y Gram-Schmidt
 * modificado de dos pasadas. Sin esto la compuerta A2 es inaplicable: el llamante
 * no tendría forma de construir una base que la satisfaga en D grande. */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_orthonormalize_pair_f64(
    double* __restrict__ u, double* __restrict__ v, uint64_t D, PolydimReport* __restrict__ report);

/* --------------------------------------------------------------------------
 * St(D,K): retracción de Cayley con reducción Sherman-Morrison-Woodbury.
 * X, G, Y_out son D x K en orden por filas (row-major).
 * ------------------------------------------------------------------------*/
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_stiefel_cayley_smw_f64(
    const double* __restrict__ X, const double* __restrict__ G, double* __restrict__ Y_out,
    uint64_t D, uint32_t K, double tau,
    const PolydimTolerances* __restrict__ tol, PolydimReport* __restrict__ report);

/* Proyección al espacio tangente de St(D,K) en X: G <- G - X sym(X^T G). */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_project_tangent_stiefel_f64(
    const double* __restrict__ X, const double* __restrict__ G, double* __restrict__ G_out,
    uint64_t D, uint32_t K);

/* Factorización ortogonal CholQR2 con bloques L2 (Tiling). In-place en X. */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_cholqr2_f64(
    double* __restrict__ X, uint64_t D, uint32_t K);

/* --------------------------------------------------------------------------
 * PMTP V762: triple búfer con seqlock por ranura.
 * Invariante: la ranura en escritura nunca es la ranura publicada, y el lector
 * detecta cualquier solapamiento vía POLYDIM_ERR_SEQLOCK_RACE.
 *
 * Escritor:  polydim_begin_write -> escribir payload[slot] -> polydim_commit_write
 * Lector:    polydim_acquire_read -> copiar payload[slot] -> polydim_validate_read
 * ------------------------------------------------------------------------*/
#define POLYDIM_PMTP_SLOTS 4

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
