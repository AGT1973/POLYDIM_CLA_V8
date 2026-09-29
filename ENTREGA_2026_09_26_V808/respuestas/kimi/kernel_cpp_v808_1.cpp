/**
 * @file kernel_cpp_v808_1.cpp
 * Kernel Monolitico C++ POLYDIM V808.1 (Bulldog Red Team, 3ra pasada completa)
 * Correcciones integradas:
 *  G1  Firewall isfinite en el loop del solver -> POLYDIM_STATUS_ERR_NUMERICAL_NAN
 *  G2  CONVERGED_GRADIENT exige pertenencia a Stiefel; X nulo -> ERR_RANK_DEFICIENT
 *  G3  tiled_dsyrk respeta beta y elimina atomics innecesarios (cada (i,j) pertenece
 *      a un unico tile; se acumula en registro y se escribe una sola vez)
 *  G7  Shifted CholQR2: el shift Tikhonov se aplica a TODA la diagonal de G antes
 *      de factorizar (antes: patch por pivote que corrompia los off-diagonales)
 *  G8  solve_linear_system_general: umbral de pivote RELATIVO a max|A|
 *      (antes: 1e-15 absoluto -> falsos singulares/falsos positivos segun escala)
 *  G6' project_to_tangent_space y VtZ del Cayley: reduccion por scratch por hilo,
 *      sin O(D*K^2) atomicas (explica los 16819 ms del log)
 *  G11 polydim_alloc_aligned: alineacion minima sizeof(void*) (posix_memalign/
 *      _aligned_malloc la exigen multiplo de sizeof(void*))
 *  G12 spsc_init: overflow capacity*sizeof(Event) validado
 *  G9  lsm_step: validacion de permutaciones p1/p2 < D + firewall isfinite
 *  G3' matmul_kxk eliminada (codigo muerto)
 *  CONVERGED_STEP implementado (step_tolerance antes era campo muerto)
 */

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <chrono>
#include <atomic>
#include <algorithm>
#include <vector>
#include <immintrin.h>

#if defined(_OPENMP)
#include <omp.h>
#else
static inline int  omp_get_num_threads(void) { return 1; }
static inline int  omp_get_thread_num(void)  { return 0; }
#endif

#if defined(_WIN32)
  #include <windows.h>
  #define POLYDIM_EXPORT extern "C" __declspec(dllexport)
#else
  #define POLYDIM_EXPORT extern "C" __attribute__((visibility("default")))
#endif

#include "polydim_solver_abi_v808_1.h"
#include "polydim_blas_loader.h"

#define TILE_D 32
#define TILE_K 32

/* Barrera dura de deriva de ABI: Python debe comparar esto en el arranque. */
POLYDIM_EXPORT size_t polydim_abi_probe(void) {
    return sizeof(PolydimSolverOptions);
}

/* ========================================================================= */
/* 1. MODO FLOTANTE DUAL IEEE-754                                            */
/* ========================================================================= */

typedef enum { POLYDIM_FP_DETERMINISTIC = 0, POLYDIM_FP_THROUGHPUT = 1 } PolydimFpMode;

static std::atomic<int32_t> g_fp_mode{POLYDIM_FP_THROUGHPUT};

POLYDIM_EXPORT void polydim_set_fp_mode(int32_t mode) { g_fp_mode.store(mode, std::memory_order_relaxed); }
POLYDIM_EXPORT int32_t polydim_get_fp_mode(void)      { return g_fp_mode.load(std::memory_order_relaxed); }

static inline void knuth_two_sum(double a, double b, double* s, double* t) {
    double sum = a + b;
    double b_virtual = sum - a;
    double a_virtual = sum - b_virtual;
    *s = sum;
    *t = (a - a_virtual) + (b - b_virtual);
}

static double twosum_tree_reduce(const double* data, size_t N) {
    if (N == 0) return 0.0;
    if (N == 1) return data[0];
    std::vector<double> current(data, data + N), errors;
    errors.reserve(N);
    while (current.size() > 1) {
        size_t n_pairs = current.size() / 2;
        std::vector<double> next_level;
        next_level.reserve(n_pairs + (current.size() % 2));
        for (size_t i = 0; i < n_pairs; ++i) {
            double s, t;
            knuth_two_sum(current[2*i], current[2*i+1], &s, &t);
            next_level.push_back(s);
            if (t != 0.0) errors.push_back(t);
        }
        if (current.size() % 2) next_level.push_back(current.back());
        current = std::move(next_level);
    }
    double total = current[0];
    for (double err : errors) {
        double s, t;
        knuth_two_sum(total, err, &s, &t);
        total = s + t;
    }
    return total;
}

/* ========================================================================= */
/* 2. NON-TEMPORAL STREAMING STORES                                          */
/* ========================================================================= */

POLYDIM_EXPORT int32_t polydim_stream_copy_nt(double* dest, const double* src, size_t count) {
    if (!dest || !src) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (count == 0)    return POLYDIM_STATUS_OK;
    size_t i = 0;
    if ((reinterpret_cast<uintptr_t>(dest) % 16 == 0) && count >= 2) {
        size_t sse_blocks = count / 2;
        #pragma omp parallel
        {
            #pragma omp for schedule(static)
            for (size_t b = 0; b < sse_blocks; ++b) {
                size_t idx = b * 2;
                _mm_stream_pd(&dest[idx], _mm_loadu_pd(&src[idx]));
            }
            _mm_sfence();
        }
        i = sse_blocks * 2;
    }
    for (; i < count; ++i) dest[i] = src[i];
    #if defined(__x86_64__) || defined(_M_X64)
    _mm_sfence();
    #else
    std::atomic_thread_fence(std::memory_order_seq_cst);
    #endif
    return POLYDIM_STATUS_OK;
}

/* ========================================================================= */
/* 3. ALLOCATOR (G11: alineacion minima sizeof(void*))                        */
/* ========================================================================= */

static std::atomic<uint64_t> g_allocation_seq{1};

POLYDIM_EXPORT void* polydim_alloc_aligned(size_t bytes, size_t alignment) {
    size_t align = (alignment > 0) ? alignment : 64;
    if ((align & (align - 1)) != 0) align = 64;
    if (align < sizeof(void*)) align = sizeof(void*);   /* exigido por posix_memalign/_aligned_malloc */
#if defined(_MSC_VER) || defined(__MINGW32__) || defined(__MINGW64__)
    return _aligned_malloc(bytes, align);
#else
    void* ptr = nullptr;
    if (posix_memalign(&ptr, align, bytes) != 0) return nullptr;
    return ptr;
#endif
}

POLYDIM_EXPORT void polydim_free_aligned(void* ptr) {
    if (!ptr) return;
#if defined(_MSC_VER) || defined(__MINGW32__) || defined(__MINGW64__)
    _aligned_free(ptr);
#else
    free(ptr);
#endif
}

POLYDIM_EXPORT PolydimHandle* polydim_handle_create(size_t bytes, size_t alignment) {
    void* data = polydim_alloc_aligned(bytes, alignment);
    if (!data) return nullptr;
    PolydimHandle* h = static_cast<PolydimHandle*>(std::malloc(sizeof(PolydimHandle)));
    if (!h) { polydim_free_aligned(data); return nullptr; }
    h->data = data;
    h->bytes = bytes;
    reinterpret_cast<std::atomic<int32_t>*>(&h->refcount)->store(1, std::memory_order_release);
    h->flags = 0;
    h->allocation_id = g_allocation_seq.fetch_add(1, std::memory_order_relaxed);
    return h;
}

POLYDIM_EXPORT void polydim_handle_retain(PolydimHandle* h) {
    if (!h) return;
    reinterpret_cast<std::atomic<int32_t>*>(&h->refcount)->fetch_add(1, std::memory_order_relaxed);
}

POLYDIM_EXPORT void polydim_handle_release(PolydimHandle* h) {
    if (!h) return;
    if (reinterpret_cast<std::atomic<int32_t>*>(&h->refcount)->fetch_sub(1, std::memory_order_acq_rel) == 1) {
        if (h->data) { polydim_free_aligned(h->data); h->data = nullptr; }
        std::free(h);
    }
}

/* ========================================================================= */
/* 4. SPSC RING (G12: overflow de capacidad validado)                         */
/* ========================================================================= */

POLYDIM_EXPORT int32_t polydim_spsc_init(PolydimSpscRing* ring, size_t capacity) {
    if (!ring) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (capacity < 2 || (capacity & (capacity - 1)) != 0) return POLYDIM_STATUS_ERR_INVALID_DIM;
    if (capacity > SIZE_MAX / sizeof(PolydimTelemetryEvent)) return POLYDIM_STATUS_ERR_INVALID_DIM;
    size_t total_bytes = capacity * sizeof(PolydimTelemetryEvent);
    PolydimTelemetryEvent* buffer =
        static_cast<PolydimTelemetryEvent*>(polydim_alloc_aligned(total_bytes, 128));
    if (!buffer) return POLYDIM_STATUS_ERR_ALLOC;
    std::memset(buffer, 0, total_bytes);
    reinterpret_cast<std::atomic<uint64_t>*>(&ring->write_index)->store(0, std::memory_order_relaxed);
    reinterpret_cast<std::atomic<uint64_t>*>(&ring->read_index)->store(0, std::memory_order_relaxed);
    ring->capacity = capacity;
    ring->capacity_mask = capacity - 1;
    ring->ring_buffer = buffer;
    std::atomic_thread_fence(std::memory_order_seq_cst);
    return POLYDIM_STATUS_OK;
}

POLYDIM_EXPORT int32_t polydim_spsc_push(PolydimSpscRing* ring, const PolydimTelemetryEvent* event) {
    if (!ring || !event || !ring->ring_buffer) return POLYDIM_STATUS_ERR_NULL_PTR;
    std::atomic<uint64_t>* w = reinterpret_cast<std::atomic<uint64_t>*>(&ring->write_index);
    std::atomic<uint64_t>* r = reinterpret_cast<std::atomic<uint64_t>*>(&ring->read_index);
    uint64_t wi = w->load(std::memory_order_relaxed);
    uint64_t ri = r->load(std::memory_order_acquire);
    if (wi - ri >= ring->capacity) return POLYDIM_STATUS_ERR_RING_FULL;
    ring->ring_buffer[wi & ring->capacity_mask] = *event;
    std::atomic_thread_fence(std::memory_order_release);
    w->store(wi + 1, std::memory_order_release);
    return POLYDIM_STATUS_OK;
}

POLYDIM_EXPORT int32_t polydim_spsc_pop(PolydimSpscRing* ring, PolydimTelemetryEvent* event) {
    if (!ring || !event || !ring->ring_buffer) return POLYDIM_STATUS_ERR_NULL_PTR;
    std::atomic<uint64_t>* w = reinterpret_cast<std::atomic<uint64_t>*>(&ring->write_index);
    std::atomic<uint64_t>* r = reinterpret_cast<std::atomic<uint64_t>*>(&ring->read_index);
    uint64_t ri = r->load(std::memory_order_relaxed);
    uint64_t wi = w->load(std::memory_order_acquire);
    if (ri == wi) return POLYDIM_STATUS_ERR_RING_EMPTY;
    std::atomic_thread_fence(std::memory_order_acquire);
    *event = ring->ring_buffer[ri & ring->capacity_mask];
    r->store(ri + 1, std::memory_order_release);
    return POLYDIM_STATUS_OK;
}

POLYDIM_EXPORT void polydim_spsc_destroy(PolydimSpscRing* ring) {
    if (!ring) return;
    /* CONTRATO: solo llamar cuando productor y consumidor hayan terminado. */
    if (ring->ring_buffer) { polydim_free_aligned(ring->ring_buffer); ring->ring_buffer = nullptr; }
    ring->capacity = 0;
    ring->capacity_mask = 0;
}

/* ========================================================================= */
/* 5. GRAMIANA DSYRK (buffer reusable en modo determinista)                   */
/* ========================================================================= */

POLYDIM_EXPORT int32_t polydim_gram_dsyrk(const double* X, size_t D, size_t K,
                                          double* K_out, uint32_t num_threads) {
    if (!X || !K_out) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (D == 0 || K == 0) return POLYDIM_STATUS_ERR_INVALID_DIM;
    int threads = (num_threads > 0) ? (int)num_threads : 1;
#if defined(_OPENMP)
    if (threads > 1) omp_set_num_threads(threads);
#endif
    std::memset(K_out, 0, K * K * sizeof(double));
    if (g_fp_mode.load(std::memory_order_relaxed) == POLYDIM_FP_DETERMINISTIC) {
        std::vector<double> products(D);                 /* un solo buffer, no K^2/2 allocaciones */
        for (size_t i = 0; i < K; ++i) {
            for (size_t j = i; j < K; ++j) {
                for (size_t d = 0; d < D; ++d)
                    products[d] = X[d * K + i] * X[d * K + j];
                double val = twosum_tree_reduce(products.data(), D);
                K_out[i * K + j] = val;
                K_out[j * K + i] = val;
            }
        }
    } else {
        BlasLoader::instance().compute_dsyrk(CblasRowMajor, CblasUpper, CblasTrans,
            K, D, 1.0, X, K, 0.0, K_out, K, num_threads);
        for (size_t i = 0; i < K; ++i)
            for (size_t j = 0; j < i; ++j)
                K_out[i * K + j] = K_out[j * K + i];
    }
    return POLYDIM_STATUS_OK;
}

/* ========================================================================= */
/* 6. TILED DSYRK DE RESPALDO (G3: beta respetado, sin atomic) — reemplazo   */
/*    del fallback de BlasLoader para uso directo.                            */
/*    Invariante: cada (i,j) del triangulo superior pertenece a UN solo      */
/*    tile (i0,j0) con j0>=i0, luego puede acumularse en registro y escribir */
/*    una unica vez: c = alpha*acc + beta*c. Ninguna colision entre hilos.   */
/* ========================================================================= */

static void tiled_dsyrk_fixed(int trans, size_t n, size_t k,
                              double alpha, const double* a, size_t lda,
                              double beta, double* c, size_t ldc) {
    constexpr size_t TN = 32, TK = 32;
    #pragma omp parallel for schedule(static) collapse(2)
    for (int64_t i0 = 0; i0 < (int64_t)n; i0 += TN) {
        for (int64_t j0 = i0; j0 < (int64_t)n; j0 += TN) {   /* j0 >= i0: un solo tile por (i,j) */
            size_t i_max = std::min((size_t)(i0 + TN), n);
            size_t j_max = std::min((size_t)(j0 + TN), n);
            for (size_t i = (size_t)i0; i < i_max; ++i) {
                size_t j_start = (i0 == j0) ? std::max(i, (size_t)j0) : (size_t)j0;
                for (size_t j = j_start; j < j_max; ++j) {
                    double acc = 0.0;
                    if (trans == CblasTrans) {
                        #pragma omp simd reduction(+:acc)
                        for (size_t p = 0; p < k; ++p) acc += a[p * lda + i] * a[p * lda + j];
                    } else {
                        #pragma omp simd reduction(+:acc)
                        for (size_t p = 0; p < k; ++p) acc += a[i * lda + p] * a[j * lda + p];
                    }
                    c[i * ldc + j] = alpha * acc + beta * c[i * ldc + j];   /* beta respetado, 1 escritura */
                }
            }
        }
    }
}

/* ========================================================================= */
/* 7. SOLVER LINEAL (G8: umbral de pivote relativo a la escala de A)          */
/* ========================================================================= */

static bool solve_linear_system_general(double* A, double* B, size_t N, size_t NRHS) {
    /* Escala de referencia: max|A|. Un umbral absoluto (1e-15) declara
     * "singular" a sistemas legitimos pequenos y acepta pivotes basura en
     * sistemas grandes. */
    double scale = 0.0;
    for (size_t i = 0; i < N * N; ++i) scale = std::max(scale, std::abs(A[i]));
    if (!std::isfinite(scale)) return false;
    const double pivot_thresh = scale * 1e-15 + 1e-300;

    for (size_t i = 0; i < N; ++i) {
        size_t pivot = i;
        double max_val = std::abs(A[i * N + i]);
        for (size_t r = i + 1; r < N; ++r) {
            double v = std::abs(A[r * N + i]);
            if (v > max_val) { max_val = v; pivot = r; }
        }
        if (max_val < pivot_thresh) return false;
        if (pivot != i) {
            for (size_t cc = 0; cc < N; ++cc)     std::swap(A[i * N + cc], A[pivot * N + cc]);
            for (size_t cc = 0; cc < NRHS; ++cc)  std::swap(B[i * NRHS + cc], B[pivot * NRHS + cc]);
        }
        double diag = A[i * N + i];
        for (size_t cc = i; cc < N; ++cc)    A[i * N + cc] /= diag;
        for (size_t cc = 0; cc < NRHS; ++cc) B[i * NRHS + cc] /= diag;
        for (size_t r = 0; r < N; ++r) {
            if (r == i) continue;
            double f = A[r * N + i];
            if (f == 0.0) continue;
            for (size_t cc = i; cc < N; ++cc)    A[r * N + cc] -= f * A[i * N + cc];
            for (size_t cc = 0; cc < NRHS; ++cc) B[r * NRHS + cc] -= f * B[i * NRHS + cc];
        }
    }
    return true;
}

static double frobenius_diff(const double* A, const double* B, size_t n) {
    double s = 0.0;
    #pragma omp simd reduction(+:s)
    for (size_t i = 0; i < n; ++i) { double d = A[i] - B[i]; s += d * d; }
    return std::sqrt(s);
}

/* ========================================================================= */
/* 8. VtZ Y PROYECCION TANGENCIAL (G6': sin atomicas; scratch por hilo)       */
/* ========================================================================= */

/* VtZ[i*K+j] = sum_d V[d*K+i] * Z[d*K+j], d-parallel, merge O(K^2) una vez. */
static void compute_VtZ(const double* V, const double* Z, double* VtZ, size_t D, size_t K) {
    std::fill(VtZ, VtZ + K * K, 0.0);
    std::vector<double> scratch((size_t)omp_get_max_threads() * K * K, 0.0);
    #pragma omp parallel
    {
        double* local = scratch.data() + (size_t)omp_get_thread_num() * K * K;
        std::fill(local, local + K * K, 0.0);
        #pragma omp for schedule(static)
        for (int64_t d = 0; d < (int64_t)D; ++d) {
            for (size_t i = 0; i < K; ++i) {
                double v = V[d * K + i];
                #pragma omp simd
                for (size_t j = 0; j < K; ++j)
                    local[i * K + j] += v * Z[d * K + j];
            }
        }
        #pragma omp critical
        {
            for (size_t t = 0; t < K * K; ++t) VtZ[t] += local[t];
        }
    }
}

/* Z <- Z - V * sym(V^T Z)  (proyeccion ortogonal a T_V St(D,K) si V ortonormal) */
static void project_to_tangent_space(const double* V, double* Z, size_t D, size_t K) {
    std::vector<double> VtZ(K * K, 0.0);
    compute_VtZ(V, Z, VtZ.data(), D, K);
    std::vector<double> sym(K * K, 0.0);
    for (size_t i = 0; i < K; ++i)
        for (size_t j = 0; j < K; ++j)
            sym[i * K + j] = 0.5 * (VtZ[i * K + j] + VtZ[j * K + i]);
    #pragma omp parallel for schedule(static)
    for (int64_t d = 0; d < (int64_t)D; ++d) {
        double row[/*K*/ 256];                    /* K <= 256 en este kernel; ver guarda abajo */
        if (K > 256) { /* fallback lento, correcto para K grande */
            std::vector<double> tmp(K, 0.0);
            for (size_t k = 0; k < K; ++k) {
                double acc = 0.0;
                for (size_t j = 0; j < K; ++j) acc += V[d * K + j] * sym[j * K + k];
                tmp[k] = acc;
            }
            for (size_t k = 0; k < K; ++k) Z[d * K + k] -= tmp[k];
            continue;
        }
        for (size_t k = 0; k < K; ++k) {
            double acc = 0.0;
            for (size_t j = 0; j < K; ++j) acc += V[d * K + j] * sym[j * K + k];
            row[k] = acc;
        }
        for (size_t k = 0; k < K; ++k) Z[d * K + k] -= row[k];
    }
}

/* Refinamiento polar de Newton cuadratico con criterio de parada. */
static void polar_newton_refinement(double* V, size_t D, size_t K, uint32_t num_threads, double tol) {
    std::vector<double> S(K * K, 0.0);
    for (int pass = 0; pass < 8; ++pass) {
        polydim_gram_dsyrk(V, D, K, S.data(), num_threads);
        double err = 0.0;
        for (size_t i = 0; i < K; ++i)
            for (size_t j = 0; j < K; ++j) {
                double e = S[i * K + j] - (i == j ? 1.0 : 0.0);
                err += e * e;
            }
        if (std::sqrt(err) < tol) break;                 /* convergencia: 1 pasada no basta siempre */
        #pragma omp parallel for schedule(static)
        for (int64_t d = 0; d < (int64_t)D; ++d) {
            double tmp[256];
            if (K > 256) {
                std::vector<double> big(K, 0.0);
                for (size_t k = 0; k < K; ++k) {
                    double acc = 0.0;
                    for (size_t j = 0; j < K; ++j)
                        acc += V[d * K + j] * (1.5 * (j == k ? 1.0 : 0.0) - 0.5 * S[j * K + k]);
                    big[k] = acc;
                }
                for (size_t k = 0; k < K; ++k) V[d * K + k] = big[k];
                continue;
            }
            for (size_t k = 0; k < K; ++k) {
                double acc = 0.0;
                for (size_t j = 0; j < K; ++j)
                    acc += V[d * K + j] * (1.5 * (j == k ? 1.0 : 0.0) - 0.5 * S[j * K + k]);
                tmp[k] = acc;
            }
            for (size_t k = 0; k < K; ++k) V[d * K + k] = tmp[k];
        }
    }
}

/* ========================================================================= */
/* 9. SHIFTED CHOLQR2 (G7: shift a TODA la diagonal antes de factorizar)      */
/* ========================================================================= */

static int32_t apply_shifted_cholqr2(double* X, size_t D, size_t K,
                                     double shift_regularization, uint32_t num_threads) {
    std::vector<double> G(K * K, 0.0);
    polydim_gram_dsyrk(X, D, K, G.data(), num_threads);

    double trace = 0.0;
    for (size_t i = 0; i < K; ++i) trace += G[i * K + i];
    double mean_diag = trace / (double)K;

    /* Tikhonov REAL: G + sigma*I antes de factorizar. El patch por pivote de
     * V808 corrompia la coherencia de la factorizacion en los casos casi
     * singulares — que son exactamente los que el shift existe para salvar. */
    double sigma = (shift_regularization > 0.0 ? shift_regularization : 1e-14) * mean_diag;
    for (size_t i = 0; i < K; ++i) G[i * K + i] += sigma;

    std::vector<double> L(K * K, 0.0);
    for (size_t i = 0; i < K; ++i) {
        for (size_t j = 0; j <= i; ++j) {
            double sum = G[i * K + j];
            for (size_t k = 0; k < j; ++k) sum -= L[i * K + k] * L[j * K + k];
            if (i == j) {
                double val = sum;                          /* G ya regularizada: si aun asi cae,
                                                              es rango deficiente real */
                if (val <= 0.0) val = 1e-300;
                L[i * K + j] = std::sqrt(val);
            } else {
                L[i * K + j] = sum / L[j * K + j];
            }
        }
    }

    /* X = Q L^T  =>  Q = X L^{-T}. Linv = L^{-1} (triangular inferior). */
    std::vector<double> Linv(K * K, 0.0);
    for (size_t i = 0; i < K; ++i) {
        Linv[i * K + i] = 1.0 / L[i * K + i];
        for (size_t j = 0; j < i; ++j) {
            double sum = 0.0;
            for (size_t k = j; k < i; ++k) sum -= L[i * K + k] * Linv[k * K + j];
            Linv[i * K + j] = sum / L[i * K + i];
        }
    }

    #pragma omp parallel for schedule(static)
    for (int64_t d = 0; d < (int64_t)D; ++d) {
        double tmp[256];
        double* row = tmp;
        std::vector<double> big;
        if (K > 256) { big.resize(K); row = big.data(); }
        for (size_t k = 0; k < K; ++k) {
            double acc = 0.0;
            for (size_t j = 0; j < K; ++j) acc += X[d * K + j] * Linv[k * K + j];
            row[k] = acc;
        }
        for (size_t k = 0; k < K; ++k) X[d * K + k] = row[k];
    }

    polar_newton_refinement(X, D, K, num_threads, 1e-14);
    return POLYDIM_STATUS_OK;
}

/* ========================================================================= */
/* 10. RETRACCION CAYLEY-SMW                                                  */
/* ========================================================================= */

static int32_t retract_cayley_smw_mixed(double* V, double* Z, size_t D, size_t K,
                                        double tau, double shift_regularization, uint32_t num_threads) {
    project_to_tangent_space(V, Z, D, K);

    const size_t K2 = 2 * K;
    std::vector<double> VtV(K * K, 0.0), ZtZ(K * K, 0.0), VtZ(K * K, 0.0);
    polydim_gram_dsyrk(V, D, K, VtV.data(), num_threads);
    polydim_gram_dsyrk(Z, D, K, ZtZ.data(), num_threads);
    compute_VtZ(V, Z, VtZ.data(), D, K);

    std::vector<double> QtP(K2 * K2, 0.0);
    for (size_t i = 0; i < K; ++i)
        for (size_t j = 0; j < K; ++j) {
            QtP[i * K2 + j]             =  VtZ[i * K + j];
            QtP[i * K2 + (K + j)]       =  VtV[i * K + j];
            QtP[(K + i) * K2 + j]       = -ZtZ[i * K + j];
            QtP[(K + i) * K2 + (K + j)] = -VtZ[j * K + i];
        }

    std::vector<double> C(K2 * K2, 0.0);
    for (size_t i = 0; i < K2; ++i) {
        for (size_t j = 0; j < K2; ++j) C[i * K2 + j] = -0.5 * tau * QtP[i * K2 + j];
        C[i * K2 + i] += 1.0;
    }

    std::vector<double> RHS(K2 * K, 0.0);
    for (size_t i = 0; i < K; ++i)
        for (size_t j = 0; j < K; ++j) {
            RHS[i * K + j]       =  VtV[i * K + j];
            RHS[(K + i) * K + j] = -VtZ[j * K + i];
        }

    if (!solve_linear_system_general(C.data(), RHS.data(), K2, K)) {
        #pragma omp parallel for schedule(static)
        for (int64_t i = 0; i < (int64_t)(D * K); ++i) V[i] += tau * Z[i];
        return apply_shifted_cholqr2(V, D, K, shift_regularization, num_threads);
    }

    #pragma omp parallel for schedule(static)
    for (int64_t d = 0; d < (int64_t)D; ++d) {
        double upd[256];
        double* row = upd;
        std::vector<double> big;
        if (K > 256) { big.resize(K); row = big.data(); }
        for (size_t k = 0; k < K; ++k) {
            double acc = 0.0;
            for (size_t j = 0; j < K; ++j)
                acc += Z[d * K + j] * RHS[j * K + k] + V[d * K + j] * RHS[(K + j) * K + k];
            row[k] = V[d * K + k] + 0.5 * tau * acc;
        }
        for (size_t k = 0; k < K; ++k) V[d * K + k] = row[k];
    }

    polar_newton_refinement(V, D, K, num_threads, 1e-14);
    return POLYDIM_STATUS_OK;
}

/* ========================================================================= */
/* 11. SOLVER STIEFEL (G1 firewall NaN; G2 convergencia condicionada;         */
/*     CONVERGED_STEP habilitado)                                             */
/* ========================================================================= */

POLYDIM_EXPORT int32_t polydim_stiefel_optimize(
    const double* problem_data, size_t problem_size,
    double* X, size_t D, size_t K,
    const PolydimSolverOptions* options, PolydimSolverResult* result,
    PolydimTelemetryBuffer* telemetry)
{
    if (!X || !options || !result) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (D == 0 || K == 0 || K > D) return POLYDIM_STATUS_ERR_INVALID_DIM;

    auto t_start = std::chrono::high_resolution_clock::now();

    uint64_t max_iters  = options->max_iterations  > 0 ? options->max_iterations  : 100;
    double grad_tol     = options->gradient_tolerance > 0 ? options->gradient_tolerance : 1e-6;
    double step_tol     = options->step_tolerance  > 0 ? options->step_tolerance  : 0.0;
    double ortho_tol    = options->ortho_tolerance > 0 ? options->ortho_tolerance : 1e-5;
    double lr           = options->learning_rate   > 0 ? options->learning_rate   : 1e-3;
    uint32_t sample     = options->sampling_period > 0 ? options->sampling_period : 1;
    uint32_t nthreads   = options->num_threads     > 0 ? options->num_threads     : 1;
    double shift_reg    = options->shift_regularization;

    /* Firewall de entrada: X inicial finito y, si hay target, target finito. */
    for (size_t i = 0; i < D * K; ++i)
        if (!std::isfinite(X[i])) return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
    if (problem_data)
        for (size_t i = 0; i < problem_size && i < D * K; ++i)
            if (!std::isfinite(problem_data[i])) return POLYDIM_STATUS_ERR_NUMERICAL_NAN;

    std::vector<double> G(D * K, 0.0), I_K(K * K, 0.0);
    for (size_t i = 0; i < K; ++i) I_K[i * K + i] = 1.0;

    int32_t final_status = POLYDIM_STATUS_MAX_ITERATIONS;
    uint64_t iter = 0;
    double obj = 0.0, grad_norm = 0.0, ortho_err = 0.0;
    bool manifold_ok = true;

    for (iter = 0; iter < max_iters; ++iter) {
        obj = 0.0;
        #pragma omp parallel for reduction(+:obj) schedule(static)
        for (int64_t i = 0; i < (int64_t)(D * K); ++i) {
            double target = (problem_data && (size_t)i < problem_size) ? problem_data[i] : 0.0;
            double diff = X[i] - target;
            G[i] = diff;
            obj += 0.5 * diff * diff;
        }
        if (!std::isfinite(obj)) { final_status = POLYDIM_STATUS_ERR_NUMERICAL_NAN; break; }

        project_to_tangent_space(X, G.data(), D, K);

        grad_norm = 0.0;
        #pragma omp parallel for reduction(+:grad_norm) schedule(static)
        for (int64_t i = 0; i < (int64_t)(D * K); ++i) grad_norm += G[i] * G[i];
        grad_norm = std::sqrt(grad_norm);
        if (!std::isfinite(grad_norm)) { final_status = POLYDIM_STATUS_ERR_NUMERICAL_NAN; break; }

        if (grad_norm < grad_tol) { final_status = POLYDIM_STATUS_CONVERGED_GRADIENT; break; }

        /* CONVERGED_STEP: campo antes muerto, ahora operativo. */
        if (step_tol > 0.0 && lr * grad_norm < step_tol) { final_status = POLYDIM_STATUS_CONVERGED_STEP; break; }

        int32_t ret_st;
        if (options->retraction_type == POLYDIM_RETRACTION_CAYLEY_SMW) {
            std::vector<double> Z(D * K);
            #pragma omp parallel for schedule(static)
            for (int64_t i = 0; i < (int64_t)(D * K); ++i) Z[i] = -G[i];
            ret_st = retract_cayley_smw_mixed(X, Z.data(), D, K, lr, shift_reg, nthreads);
        } else {
            #pragma omp parallel for schedule(static)
            for (int64_t i = 0; i < (int64_t)(D * K); ++i) X[i] -= lr * G[i];
            ret_st = apply_shifted_cholqr2(X, D, K, shift_reg, nthreads);
        }
        if (ret_st != 0) { final_status = ret_st; break; }

        std::vector<double> Gram(K * K, 0.0);
        polydim_gram_dsyrk(X, D, K, Gram.data(), nthreads);
        ortho_err = frobenius_diff(Gram.data(), I_K.data(), K * K);
        if (!std::isfinite(ortho_err)) { final_status = POLYDIM_STATUS_ERR_NUMERICAL_NAN; break; }
        manifold_ok = (ortho_err <= ortho_tol);
        if (!manifold_ok && iter > 5) { final_status = POLYDIM_STATUS_ERR_ORTHO_VIOLATION; break; }

        if (telemetry && telemetry->points && (iter % sample == 0)
            && telemetry->recorded_count < telemetry->capacity) {
            auto now = std::chrono::high_resolution_clock::now();
            PolydimTelemetryPoint& pt = telemetry->points[telemetry->recorded_count++];
            pt.iteration = iter; pt.objective_value = obj; pt.gradient_norm = grad_norm;
            pt.step_size = lr; pt.ortho_error = ortho_err;
            pt.elapsed_time_ns = (uint64_t)std::chrono::duration_cast<std::chrono::nanoseconds>(now - t_start).count();
        }
    }

    auto t_end = std::chrono::high_resolution_clock::now();
    uint64_t total_ns = (uint64_t)std::chrono::duration_cast<std::chrono::nanoseconds>(t_end - t_start).count();

    std::vector<double> Gram_final(K * K, 0.0);
    polydim_gram_dsyrk(X, D, K, Gram_final.data(), nthreads);
    ortho_err = frobenius_diff(Gram_final.data(), I_K.data(), K * K);
    if (!std::isfinite(ortho_err)) {
        result->status = POLYDIM_STATUS_ERR_NUMERICAL_NAN;
        result->iterations_executed = iter; result->final_objective = obj;
        result->final_grad_norm = grad_norm; result->final_ortho_error = ortho_err;
        result->total_time_ns = total_ns;
        std::snprintf(result->status_message, sizeof(result->status_message),
                      "Error: non-finite orthogonality error (NaN/Inf firewall).");
        return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
    }
    manifold_ok = (ortho_err <= ortho_tol);

    /* G2: convergencia NUNCA se certifica fuera de la variedad. */
    bool grad_converged = (final_status == POLYDIM_STATUS_CONVERGED_GRADIENT
                        || final_status == POLYDIM_STATUS_CONVERGED_STEP);
    if (grad_converged && !manifold_ok) {
        /* Gradiente nulo con X degenerado (p.ej. X=0, target=0): es un punto
         * estacionario EUCLIDEO fuera de Stiefel, no una solucion. */
        final_status = (ortho_err > 1e-3) ? POLYDIM_STATUS_ERR_RANK_DEFICIENT
                                          : POLYDIM_STATUS_ERR_ORTHO_VIOLATION;
    }

    result->status = final_status;
    result->iterations_executed = iter;
    result->final_objective = obj;
    result->final_grad_norm = grad_norm;
    result->final_ortho_error = ortho_err;
    result->total_time_ns = total_ns;
    switch (final_status) {
        case POLYDIM_STATUS_CONVERGED_GRADIENT:
            std::snprintf(result->status_message, sizeof(result->status_message),
                          "Converged: gradient norm below tolerance, on-manifold.");
            break;
        case POLYDIM_STATUS_CONVERGED_STEP:
            std::snprintf(result->status_message, sizeof(result->status_message),
                          "Converged: step size below tolerance, on-manifold.");
            break;
        case POLYDIM_STATUS_ERR_RANK_DEFICIENT:
            std::snprintf(result->status_message, sizeof(result->status_message),
                          "Error: rank-deficient iterate; not on Stiefel manifold.");
            break;
        case POLYDIM_STATUS_ERR_NUMERICAL_NAN:
            std::snprintf(result->status_message, sizeof(result->status_message),
                          "Error: NaN/Inf firewall triggered.");
            break;
        case POLYDIM_STATUS_MAX_ITERATIONS:
            std::snprintf(result->status_message, sizeof(result->status_message),
                          "Completed maximum iterations.");
            break;
        default:
            std::snprintf(result->status_message, sizeof(result->status_message),
                          "Optimization terminated with status code %d.", final_status);
    }
    return final_status;
}

/* ========================================================================= */
/* 12. RESERVORIO LSM (G9: permutaciones validadas + firewall)                */
/* ========================================================================= */

static void fwht_normalized_inplace(double* x, size_t D) {
    for (size_t len = 1; len < D; len <<= 1) {
        #pragma omp parallel for schedule(static)
        for (int64_t i = 0; i < (int64_t)D; i += (int64_t)(2 * len)) {
            for (size_t j = 0; j < len; ++j) {
                double u = x[i + j], v = x[i + j + len];
                x[i + j] = u + v; x[i + j + len] = u - v;
            }
        }
    }
    double inv = 1.0 / std::sqrt((double)D);
    #pragma omp parallel for simd schedule(static)
    for (int64_t i = 0; i < (int64_t)D; ++i) x[i] *= inv;
}

POLYDIM_EXPORT int32_t polydim_structured_lsm_step(
    double* state, const double* input,
    const int8_t* d1, const uint32_t* p1, const int8_t* d2, const uint32_t* p2,
    size_t D, double alpha_leak, double input_scale)
{
    if (!state || !d1 || !p1 || !d2 || !p2) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (D == 0 || (D & (D - 1)) != 0) return POLYDIM_STATUS_ERR_INVALID_DIM;

    /* G9: un indice de permutacion corrupto es un OOB read silencioso. */
    for (size_t i = 0; i < D; ++i)
        if (p1[i] >= D || p2[i] >= D) return POLYDIM_STATUS_ERR_INVALID_DIM;

    std::vector<double> tmp(D, 0.0);
    #pragma omp parallel for schedule(static)
    for (int64_t i = 0; i < (int64_t)D; ++i)
        tmp[i] = state[p1[i]] * (d1[p1[i]] < 0 ? -1.0 : 1.0);

    fwht_normalized_inplace(tmp.data(), D);

    double alpha = (alpha_leak > 0.0 && alpha_leak <= 1.0) ? alpha_leak : 0.8;
    double in_scale = (input_scale != 0.0) ? input_scale : 1.0;

    #pragma omp parallel for schedule(static)
    for (int64_t i = 0; i < (int64_t)D; ++i) {
        double w = tmp[p2[i]] * (d2[i] < 0 ? -1.0 : 1.0);
        double in_val = (input != nullptr) ? in_scale * input[i] : 0.0;
        state[i] = (1.0 - alpha) * state[i] + alpha * std::tanh(w + in_val);
    }

    /* Firewall: un NaN en el estado se propaga por tanh para siempre. */
    for (size_t i = 0; i < D; ++i)
        if (!std::isfinite(state[i])) return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
    return POLYDIM_STATUS_OK;
}
