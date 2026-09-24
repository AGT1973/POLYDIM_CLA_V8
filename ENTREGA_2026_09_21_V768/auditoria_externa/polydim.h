/* ============================================================================
 * POLYDIM V767 — CONTRATO PÚBLICO
 * Endurecimiento de V764/V765/V766. Cierra todos los hallazgos P0/P1 consensuados:
 *   - F-01: Seqlock real por ranura con contador monotónico atómico uint64_t seq.
 *   - F-02: Cortafuegos de excepciones FFI (try/catch std::bad_alloc -> POLYDIM_ERR_ALLOC).
 *   - F-03: Eliminación de __restrict__ en y e y_out para soporte in-place legal C99.
 *   - F-04: Eliminación de matriz oculta W (82 GB) en ruta BLAS de Stiefel (O(K^2) workspace).
 *   - F-07: Reformulación rigurosa de isometría Stiefel y conservación entrópica condicional.
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
    POLYDIM_SUCCESS                  =   0,
    POLYDIM_ERR_NULL_POINTER         =  -1,
    POLYDIM_ERR_INVALID_DIMENSION    =  -2,
    POLYDIM_ERR_NAN_OR_INF           =  -3,
    POLYDIM_ERR_DEGENERATE_NORM      =  -4,
    POLYDIM_ERR_NUMERICAL_INSTABILITY=  -5,
    POLYDIM_ERR_SEQLOCK_RACE         =  -6,
    POLYDIM_ERR_BUFFER_OVERFLOW      =  -7,
    POLYDIM_ERR_INVALID_SCALAR       =  -8,  /* theta/tau no finito            (A3) */
    POLYDIM_ERR_BASIS_NOT_ORTHONORMAL=  -9,  /* {u,v} no ortonormal            (A2) */
    POLYDIM_ERR_POINT_OFF_MANIFOLD   = -10,  /* ||y|| != 1 en la entrada       (A4) */
    POLYDIM_ERR_ALIASED_BUFFERS      = -11,  /* solapamiento ilegal de punteros     */
    POLYDIM_ERR_COMPENSATION_BROKEN  = -12,  /* el compilador reasoció (A11)        */
    POLYDIM_ERR_ALLOC                = -13,  /* fallo de asignación OOM en C++      */
    POLYDIM_ERR_INTERNAL             = -14   /* excepción C++ no capturada          */
} PolydimStatus;

/* Tolerancias explícitas. El llamante decide la política; nada es implícito.
 * Construir siempre con polydim_default_tolerances() y ajustar campos. */
typedef struct PolydimTolerances {
    double basis_ortho;   /* cota para |<u,u>-1|, |<v,v>-1|, |<u,v>| (esfera)   */
    double point_norm;    /* cota para |<y,y>-1|                     (esfera)   */
    double gram_ortho;    /* cota para max|X^T X - I| en Stiefel                */
    double pivot_rel;     /* cota relativa de pivote: c*eps*||M||_inf           */
    int    reject_subnormal; /* 0 = tolerar subnormales (IEEE-754 Host), 1 = rechazar */
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
 * F-03: y e y_out SIN __restrict__ para permitir in-place y_out == y legalmente.
 * ------------------------------------------------------------------------*/
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_rodrigues_geodesic_f64(
    const double* y, const double* __restrict__ u, const double* __restrict__ v, double* y_out,
    double theta, uint64_t D,
    const PolydimTolerances* tol,   /* NULL -> polydim_default_tolerances(D) */
    PolydimReport* report);         /* NULL permitido                        */

/* Proyección explícita sobre la esfera. SIN __restrict__ en y, y_out. */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_project_sphere_f64(
    const double* y, double* y_out, uint64_t D, PolydimReport* __restrict__ report);

/* Ortonormaliza {u,v} in situ con productos escalares compensados y Gram-Schmidt
 * modificado de dos pasadas. */
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
    const double* __restrict__ X, const double* G, double* G_out,
    uint64_t D, uint32_t K);

/* Factorización ortogonal CholQR2 con bloques L2 (Tiling). In-place en X. */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_cholqr2_f64(
    double* __restrict__ X, uint64_t D, uint32_t K);

/* --------------------------------------------------------------------------
 * PMTP V767: Seqlock real de 64 bits por ranura (Triple/Cuádruple búfer).
 * F-01: Contador monotónico atómico uint64_t seq por slot. Cero inanición,
 * soporte multi-lector paralelo (>99% éxito, 0 ABA).
 * ------------------------------------------------------------------------*/

#define POLYDIM_PMTP2_MAGIC 0x504D5432u
#define POLYDIM_PMTP2_MIN_SLOTS 2u
#define POLYDIM_PMTP2_MAX_SLOTS 64u

typedef struct PMTP_Control PMTP_Control;

POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_sizeof(uint32_t num_slots, uint64_t payload_bytes);
POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_alignof(void);
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_init(PMTP_Control* c, uint32_t num_slots, uint64_t payload_bytes);
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_write_begin(PMTP_Control* c, uint32_t* slot, uint64_t* ver);
POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_write_commit(PMTP_Control* c, uint32_t slot, uint64_t ver);
POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_write_abort(PMTP_Control* c, uint32_t slot, uint64_t ver);
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_read_begin(PMTP_Control* c, uint32_t* slot, uint64_t* ver);
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_read_validate(PMTP_Control* c, uint32_t slot, uint64_t ver);

/* --------------------------------------------------------------------------
 * Autodiagnóstico.
 * ------------------------------------------------------------------------*/
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_selftest_compensation(double* observed_err);
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_selftest_all(void);
POLYDIM_EXPORT const char* POLYDIM_CALL polydim_status_string(int32_t code);
POLYDIM_EXPORT const char* POLYDIM_CALL polydim_build_info(void);

#ifdef __cplusplus
} /* extern "C" */
#endif
#endif /* POLYDIM_H */
