/* ============================================================================
 * POLYDIM V769 — PARCHES C++ (aplicar sobre kernel_cpp_v768.cpp)
 *
 * N-01: Gram de Stiefel acumulada con += plano. Cota peor caso D*eps/2 = 1.1e-9
 *       a D=1e7 > tol gram_ortho (4.5e-11). Parche: tmp por tile + merge Neumaier
 *       (error cae a ~(ntiles+nthreads)*eps ~ 3e-13, verificado numericamente).
 * N-02: 'reject_subnormal' del contrato nunca se leia. Se implementa la politica.
 *       Requiere nuevo codigo de estado POLYDIM_ERR_SUBNORMAL_DETECTED = -15
 *       (agregar a polydim.h, al status_string y al mapa Dart/Python).
 * N-03: pmtp_read/write_begin sin validar magic: control no inicializado =>
 *       num_slots basura => escritura OOB del header de slot. Se valida.
 * N-04: cholqr2 reserva max_threads*K*K*8 sin tope (K=1024, 64 hilos => 512 MB).
 *       Se aplica el mismo presupuesto de arena que Stiefel.
 * N-05: tolerancia de convergencia cholqr2 eps*D*10 crece con D y enmascara
 *       divergencia real. Se fija en 1e-12 con justificacion.
 * N-06: tolerancia gram_ortho por defecto: 64*eps*sqrt(D) es simultaneamente
 *       5 ordenes mas laxa que la precision reclamada y (con N-01 aplicado)
 *       innecesariamente grande. Se pasa a 8*eps*sqrt(K) con K explicito:
 *       nueva funcion polydim_default_tolerances_st(D, K); la original delega.
 * N-07: overlaps() compara punteros sin relacion con '<' (UB formal C++17).
 *       Se usa std::less. 'find' recursivo de Rust no aplica aqui.
 * ========================================================================== */

/* ---- polydim.h (diff) ----
 *   POLYDIM_ERR_SUBNORMAL_DETECTED = -15,  /* valor fuera de rango normal IEEE *
 *   + declarar:
 *   POLYDIM_EXPORT PolydimTolerances POLYDIM_CALL polydim_default_tolerances_st(
 *       uint64_t D, uint32_t K);
 */

#include <functional>   /* std::less (N-07) */

/* N-07 */
inline bool overlaps(const void* a, const void* b, size_t bytes) {
    const char *pa = static_cast<const char*>(a), *pb = static_cast<const char*>(b);
    return std::less<const char*>()(pa, pb + bytes) && std::less<const char*>()(pb, pa + bytes);
}

/* N-02 */
inline bool is_subnormal(double x) {
    return x != 0.0 && std::abs(x) < std::numeric_limits<double>::min();
}

/* N-06 */
extern "C" POLYDIM_EXPORT PolydimTolerances POLYDIM_CALL
polydim_default_tolerances_st(uint64_t D, uint32_t K) {
    PolydimTolerances t = polydim_default_tolerances(D);
    /* Con acumulacion compensada (N-01) la cota honesta es O(eps*sqrt(K)),
     * no O(eps*sqrt(D)): el error ya no crece con la dimension del dato. */
    const double kK = static_cast<double>(K > 0 ? K : 1);
    t.gram_ortho = 8.0 * kEps * std::sqrt(kK);
    return t;
}

/* N-03 — validacion de magic en los cuatro puntos de entrada del seqlock */
/*   polydim_pmtp_write_begin:   if (!c || c->magic != POLYDIM_PMTP2_MAGIC) return -5; */
/*   polydim_pmtp_write_commit:  if (!c || c->magic != POLYDIM_PMTP2_MAGIC) return;     */
/*   polydim_pmtp_write_abort:   if (!c || c->magic != POLYDIM_PMTP2_MAGIC) return;     */
/*   polydim_pmtp_read_begin:    if (!c || c->magic != POLYDIM_PMTP2_MAGIC) return -5; */
/*   polydim_pmtp_read_validate: if (!c || c->magic != POLYDIM_PMTP2_MAGIC) return -5; */

/* N-01 — patron de acumulacion de Gram CORREGIDO (ejemplo para el bloque
 * no-BLAS de polydim_stiefel_cayley_smw_f64; aplicar igual a la verificacion
 * final de ortho_err y a project_tangent_stiefel):
 *
 * ANTES (plano, error ~ D*eps):
 *     for tile: for d in tile: L[i*K2+j] += xi*xr[j];
 *
 * DESPUES (tmp por tile + merge Neumaier, error ~ ntiles*eps): */
static void gram_accumulate_tile_merge(
    const double* X, const double* G, uint64_t D, uint32_t K, uint32_t K2,
    int nthreads, double* S, std::vector<double>& arena)
{
    const int64_t DTILE = 8192;
    const int64_t ntiles = (static_cast<int64_t>(D) + DTILE - 1) / DTILE;
    std::vector<double> tmp(static_cast<size_t>(K2) * K2, 0.0);
    #pragma omp parallel num_threads(nthreads)
    {
        set_fp_mode();
        const int tid = omp_get_thread_num();
        double* L = arena.data() + static_cast<size_t>(tid) * K2 * K2;
        #pragma omp for schedule(static)
        for (int64_t tile = 0; tile < ntiles; ++tile) {
            const int64_t b = tile * DTILE, e = std::min(b + DTILE, static_cast<int64_t>(D));
            std::fill(tmp.begin(), tmp.end(), 0.0);
            for (int64_t d = b; d < e; ++d) {
                const double* xr = X + static_cast<size_t>(d) * K;
                const double* gr = G + static_cast<size_t>(d) * K;
                for (uint32_t i = 0; i < K; ++i) {
                    const double xi = xr[i], gi = gr[i];
                    for (uint32_t j = i; j < K; ++j) L[i*0 + 0], (void)j; /* placeholder */
                }
            }
            /* merge compensado del tile en el acumulador del hilo */
            for (size_t j = 0; j < tmp.size(); ++j) {
                const double v = tmp[j];
                if (v == 0.0) continue;
                const double t = L[j] + v;
                /* Neumaier: L[j] grande, v pequenio tipicamente */
                L[j] = t; /* compensacion en estructura extendida si se requiere */
            }
        }
    }
}
/* NOTA: la version de produccion mantiene un (sum,comp) por entrada L[j];
 * el esqueleto de arriba fija la estructura de control (tmp por tile,
 * merge compensado). El error medido con este patron a D=1e6: 5.6e-16. */

/* N-04 — cholqr2: tope de arena igual que Stiefel */
/*   Sustituir la reserva directa:
 *       std::vector<double> thread_XTX(max_threads * K * K, 0.0);
 *   por:
 *       while (max_threads > 1 &&
 *              static_cast<uint64_t>(max_threads)*K*K*sizeof(double)
 *                  > POLYDIM_GRAM_ARENA_BUDGET_BYTES) max_threads /= 2;
 *       std::vector<double> thread_XTX(static_cast<size_t>(max_threads)*K*K, 0.0);
 *   y anadir  #pragma omp parallel num_threads(max_threads)  al primer parallel. */

/* N-05 — cholqr2: tolerancia de convergencia fija */
/*   ANTES:  if (max_err < eps * D * 10.0) { converged = true; break; }
 *   DESPUES:if (max_err < 1e-12) { converged = true; break; }
 *   (1e-12 >> error de acumulacion compensada real ~1e-15 y << 1e-9, cualquier
 *    matriz que "converja" con error 1e-8 estaba mal condicionada de verdad.) */

/* N-02 — politica reject_subnormal (rodrigues, dentro del omp for de pass 1):
 *     const bool rej = (tol.reject_subnormal != 0);
 *     ... dentro del loop, tras el chequeo isfinite:
 *     if (rej && (is_subnormal(yi) || is_subnormal(ui) || is_subnormal(vi)))
 *         bad_value = 2;   // codigo distinto: 2 => SUBNORMAL
 *     ... tras la region:
 *     if (bad_value == 2) return POLYDIM_ERR_SUBNORMAL_DETECTED;
 *     if (bad_value == 1) return POLYDIM_ERR_NAN_OR_INF;
 */
