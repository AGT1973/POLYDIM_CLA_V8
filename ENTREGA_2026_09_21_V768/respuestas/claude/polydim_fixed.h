/* ============================================================================
 * POLYDIM V768 — CONTRATO PÚBLICO (parche: contrato de aliasing consistente)
 * Cambios sobre el original en este pase:
 *   - G-01: se retira __restrict__ de todo puntero que participa de un chequeo
 *     defensivo en tiempo de ejecución (POLYDIM_ERR_ALIASED_BUFFERS,
 *     POLYDIM_ERR_BASIS_NOT_ORTHONORMAL). __restrict__ es una promesa de
 *     no-solapamiento al compilador: si esa promesa se rompe, el chequeo que
 *     depende de ella deja de estar garantizado, porque ya hay UB antes del
 *     chequeo. No puede coexistir "restrict" y "valido el aliasing en runtime"
 *     sobre el mismo par de punteros.
 *   - G-02: se unifica el criterio de 'report': nunca restrict, porque su
 *     única función es recibir diagnóstico y no hay razón para prohibir que
 *     el llamante reutilice el mismo buffer de reporte entre llamadas
 *     consecutivas o lo aliase con estructuras propias de logging.
 *   - Heredado sin cambios: F-01 a F-07 del original (Seqlock, firewall FFI,
 *     eliminación de matriz oculta en Stiefel, etc.) — no verificables desde
 *     el header solo, requieren el .cpp/.rs real.
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

typedef struct PolydimTolerances {
    double basis_ortho;
    double point_norm;
    double gram_ortho;
    double pivot_rel;
    int    reject_subnormal;
} PolydimTolerances;

POLYDIM_EXPORT PolydimTolerances POLYDIM_CALL polydim_default_tolerances(uint64_t D);

typedef struct PolydimReport {
    double point_norm_err;
    double basis_uu_err;
    double basis_vv_err;
    double basis_uv_err;
    double out_norm_err;
    double pivot_min;
    double pivot_threshold;
    double ortho_err;
    uint64_t threads_used;
} PolydimReport;

POLYDIM_EXPORT void POLYDIM_CALL polydim_report_init(PolydimReport* r);

/* --------------------------------------------------------------------------
 * S^(D-1): rotación de Rodrigues en el plano span{u,v}
 * G-01: u, v YA NO son __restrict__. La implementación DEBE comparar
 * punteros en runtime y devolver POLYDIM_ERR_ALIASED_BUFFERS si u==v (o
 * solapan parcialmente en rango [D]), ANTES de calcular basis_uv_err.
 * F-03 (heredado): y e y_out siguen sin __restrict__, in-place legal.
 * ------------------------------------------------------------------------*/
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_rodrigues_geodesic_f64(
    const double* y, const double* u, const double* v, double* y_out,
    double theta, uint64_t D,
    const PolydimTolerances* tol,
    PolydimReport* report);

POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_project_sphere_f64(
    const double* y, double* y_out, uint64_t D, PolydimReport* report);

/* G-01: u, v YA NO son __restrict__ (deben poder validarse como aliased).
 * La implementación debe rechazar u==v con POLYDIM_ERR_ALIASED_BUFFERS
 * antes de intentar ortonormalizar. */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_orthonormalize_pair_f64(
    double* u, double* v, uint64_t D, PolydimReport* report);

/* --------------------------------------------------------------------------
 * St(D,K): retracción de Cayley con reducción Sherman-Morrison-Woodbury.
 * G-01: X, G ya no son __restrict__ entre sí ni respecto de Y_out, para
 * permitir tanto la detección de aliasing ilegal como una futura variante
 * in-place (Y_out == X) si se decide soportarla explícitamente (pendiente
 * de decisión de diseño — documentar cuál de las dos se admite).
 * ------------------------------------------------------------------------*/
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_stiefel_cayley_smw_f64(
    const double* X, const double* G, double* Y_out,
    uint64_t D, uint32_t K, double tau,
    const PolydimTolerances* tol, PolydimReport* report);

POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_project_tangent_stiefel_f64(
    const double* X, const double* G, double* G_out,
    uint64_t D, uint32_t K);

POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_cholqr2_f64(
    double* X, uint64_t D, uint32_t K);

/* --------------------------------------------------------------------------
 * PMTP V768: Seqlock real de 64 bits por ranura.
 * ------------------------------------------------------------------------*/

#define POLYDIM_PMTP2_MAGIC 0x504D5432u
#define POLYDIM_PMTP2_MIN_SLOTS 2u
#define POLYDIM_PMTP2_MAX_SLOTS 64u

typedef struct PMTP_Control PMTP_Control;

POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_sizeof(uint32_t num_slots, uint64_t payload_bytes);
POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_alignof(void);
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_init(PMTP_Control* c, uint32_t num_slots, uint64_t payload_bytes);
/* G-03 (nuevo hallazgo, no corregible desde el header): no existe una
 * función de cierre (unlink/destroy) para el objeto de memoria compartida
 * POSIX que 03_MULTI_AI_TRIBUNAL_VERDICTS.md menciona como "shm.unlink".
 * Si esa responsabilidad vive en este contrato C, falta declararla aquí
 * (p.ej. polydim_pmtp_destroy / polydim_pmtp_unlink); si vive en la capa
 * Python/Dart que hace el mmap, entonces está bien que no esté acá, pero
 * conviene dejarlo dicho explícitamente en la documentación del contrato. */
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_write_begin(PMTP_Control* c, uint32_t* slot, uint64_t* ver);
POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_write_commit(PMTP_Control* c, uint32_t slot, uint64_t ver);
POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_write_abort(PMTP_Control* c, uint32_t slot, uint64_t ver);
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_read_begin(PMTP_Control* c, uint32_t* slot, uint64_t* ver);
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_read_validate(PMTP_Control* c, uint32_t slot, uint64_t ver);

POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_selftest_compensation(double* observed_err);
POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_selftest_all(void);
POLYDIM_EXPORT const char* POLYDIM_CALL polydim_status_string(int32_t code);
POLYDIM_EXPORT const char* POLYDIM_CALL polydim_build_info(void);

#ifdef __cplusplus
} /* extern "C" */
#endif
#endif /* POLYDIM_H */
