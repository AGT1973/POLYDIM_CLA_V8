/**
 * @file kernel_cpp_v773.cpp
 * @brief Kernel Monolítico C++ POLYDIM V773:
 *        - Stiefel Solver con Shifted CholQR y Retracción Cayley-SMW
 *        - Non-Temporal Streaming Stores (AVX2 _mm256_stream_pd)
 *        - Wait-Free SPSC Telemetry Ring Buffer (128B Cache-Line Isolated)
 *        - Strict Allocator Pairing & Refcounted PolydimHandle
 *        - Concurrencia Banked Slot Lease RCU & Gram DSYRK FP Dual Mode
 * @copyright POLYDIM Architecture - 2026
 */

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <atomic>
#include <algorithm>
#include <vector>
#include <immintrin.h>

#if defined(_OPENMP)
#include <omp.h>
#endif

#include "../include/polydim_solver_abi.h"
#include "../include/polydim_blas_loader.h"

#define POLYDIM_ALIGN 128
#define TILE_D 32
#define TILE_K 32

/* ========================================================================= */
/* 1. MODO FLOTANTE DUAL IEEE-754: DETERMINISTIC (TwoSum) vs THROUGHPUT     */
/* ========================================================================= */

typedef enum {
    POLYDIM_FP_DETERMINISTIC = 0,
    POLYDIM_FP_THROUGHPUT    = 1
} PolydimFpMode;

static std::atomic<int32_t> g_fp_mode{POLYDIM_FP_THROUGHPUT};

extern "C" void polydim_set_fp_mode(int32_t mode) {
    g_fp_mode.store(mode, std::memory_order_relaxed);
}

extern "C" int32_t polydim_get_fp_mode() {
    return g_fp_mode.load(std::memory_order_relaxed);
}

/* Algoritmo TwoSum de Knuth (Exact Roundoff Addition) */
static inline void knuth_two_sum(double a, double b, double* s, double* t) {
    double sum = a + b;
    double b_virtual = sum - a;
    double a_virtual = sum - b_virtual;
    double b_roundoff = b - b_virtual;
    double a_roundoff = a - a_virtual;
    *s = sum;
    *t = a_roundoff + b_roundoff;
}

/* Reducción determinista por árbol binario de potencias de 2 */
static double twosum_tree_reduce(const double* data, size_t N) {
    if (N == 0) return 0.0;
    if (N == 1) return data[0];

    std::vector<double> current(data, data + N);
    std::vector<double> errors;
    errors.reserve(N / 2 + 1);

    while (current.size() > 1) {
        size_t n_pairs = current.size() / 2;
        std::vector<double> next_level;
        next_level.reserve(n_pairs + (current.size() % 2));

        for (size_t i = 0; i < n_pairs; ++i) {
            double s, t;
            knuth_two_sum(current[2 * i], current[2 * i + 1], &s, &t);
            next_level.push_back(s);
            if (std::abs(t) > 0.0) {
                errors.push_back(t);
            }
        }
        if (current.size() % 2 != 0) {
            next_level.push_back(current.back());
        }
        current = std::move(next_level);
    }

    double total_sum = current[0];
    for (double err : errors) {
        double s, t;
        knuth_two_sum(total_sum, err, &s, &t);
        total_sum = s + t;
    }
    return total_sum;
}

/* ========================================================================= */
/* 2. NON-TEMPORAL STREAMING STORES (AVX2 / SSE2)                           */
/* ========================================================================= */

extern "C" int32_t polydim_stream_copy_nt(double* dest, const double* src, size_t count) {
    if (!dest || !src) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (count == 0) return POLYDIM_STATUS_OK;

    size_t i = 0;
    // Si dest está alineado a 16 bytes (SSE2 disponible en todo CPU x86_64)
    uintptr_t dest_addr = reinterpret_cast<uintptr_t>(dest);
    if ((dest_addr % 16 == 0) && count >= 2) {
        size_t sse_blocks = count / 2;
        #pragma omp parallel for schedule(static)
        for (size_t b = 0; b < sse_blocks; ++b) {
            size_t idx = b * 2;
            __m128d data = _mm_loadu_pd(&src[idx]);
            _mm_stream_pd(&dest[idx], data);
        }
        i = sse_blocks * 2;
        _mm_sfence();
    }

    // Copia del residuo
    for (; i < count; ++i) {
        dest[i] = src[i];
    }

    return POLYDIM_STATUS_OK;
}

/* ========================================================================= */
/* 3. STRICT ALLOCATOR PAIRING & REFCOUNTED POLYDIM_HANDLE                  */
/* ========================================================================= */

static std::atomic<uint64_t> g_allocation_seq{1};

extern "C" void* polydim_alloc_aligned(size_t bytes, size_t alignment) {
    size_t align = (alignment > 0) ? alignment : 64;
    // Alineación en potencia de 2
    if ((align & (align - 1)) != 0) align = 64;

#if defined(_MSC_VER) || defined(__MINGW32__) || defined(__MINGW64__)
    return _aligned_malloc(bytes, align);
#else
    void* ptr = nullptr;
    if (posix_memalign(&ptr, align, bytes) != 0) return nullptr;
    return ptr;
#endif
}

extern "C" void polydim_free_aligned(void* ptr) {
    if (!ptr) return;
#if defined(_MSC_VER) || defined(__MINGW32__) || defined(__MINGW64__)
    _aligned_free(ptr);
#else
    free(ptr);
#endif
}

extern "C" PolydimHandle* polydim_handle_create(size_t bytes, size_t alignment) {
    void* data = polydim_alloc_aligned(bytes, alignment);
    if (!data) return nullptr;

    PolydimHandle* handle = static_cast<PolydimHandle*>(std::malloc(sizeof(PolydimHandle)));
    if (!handle) {
        polydim_free_aligned(data);
        return nullptr;
    }

    handle->data = data;
    handle->bytes = bytes;
    handle->refcount = 1;
    handle->flags = 0;
    handle->allocation_id = g_allocation_seq.fetch_add(1, std::memory_order_relaxed);
    return handle;
}

extern "C" void polydim_handle_retain(PolydimHandle* handle) {
    if (!handle) return;
    std::atomic<int32_t>* ref = reinterpret_cast<std::atomic<int32_t>*>(&handle->refcount);
    ref->fetch_add(1, std::memory_order_relaxed);
}

extern "C" void polydim_handle_release(PolydimHandle* handle) {
    if (!handle) return;
    std::atomic<int32_t>* ref = reinterpret_cast<std::atomic<int32_t>*>(&handle->refcount);
    if (ref->fetch_sub(1, std::memory_order_acq_rel) == 1) {
        if (handle->data) {
            polydim_free_aligned(handle->data);
            handle->data = nullptr;
        }
        std::free(handle);
    }
}

/* ========================================================================= */
/* 4. WAIT-FREE SPSC TELEMETRY RING BUFFER (128B ISOLATED CACHE-LINES)      */
/* ========================================================================= */

extern "C" int32_t polydim_spsc_init(PolydimSpscRing* ring, size_t capacity) {
    if (!ring) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (capacity < 2 || (capacity & (capacity - 1)) != 0) {
        return POLYDIM_STATUS_ERR_INVALID_DIM; // Capacidad debe ser potencia de 2
    }

    size_t total_bytes = capacity * sizeof(PolydimTelemetryEvent);
    PolydimTelemetryEvent* buffer = static_cast<PolydimTelemetryEvent*>(polydim_alloc_aligned(total_bytes, 128));
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

extern "C" int32_t polydim_spsc_push(PolydimSpscRing* ring, const PolydimTelemetryEvent* event) {
    if (!ring || !event || !ring->ring_buffer) return POLYDIM_STATUS_ERR_NULL_PTR;

    std::atomic<uint64_t>* w_atomic = reinterpret_cast<std::atomic<uint64_t>*>(&ring->write_index);
    std::atomic<uint64_t>* r_atomic = reinterpret_cast<std::atomic<uint64_t>*>(&ring->read_index);

    uint64_t w = w_atomic->load(std::memory_order_relaxed);
    uint64_t r = r_atomic->load(std::memory_order_acquire);

    if (w - r >= ring->capacity) {
        return POLYDIM_STATUS_ERR_RING_FULL;
    }

    ring->ring_buffer[w & ring->capacity_mask] = *event;
    w_atomic->store(w + 1, std::memory_order_release);
    return POLYDIM_STATUS_OK;
}

extern "C" int32_t polydim_spsc_pop(PolydimSpscRing* ring, PolydimTelemetryEvent* event) {
    if (!ring || !event || !ring->ring_buffer) return POLYDIM_STATUS_ERR_NULL_PTR;

    std::atomic<uint64_t>* w_atomic = reinterpret_cast<std::atomic<uint64_t>*>(&ring->write_index);
    std::atomic<uint64_t>* r_atomic = reinterpret_cast<std::atomic<uint64_t>*>(&ring->read_index);

    uint64_t r = r_atomic->load(std::memory_order_relaxed);
    uint64_t w = w_atomic->load(std::memory_order_acquire);

    if (r == w) {
        return POLYDIM_STATUS_ERR_RING_EMPTY;
    }

    *event = ring->ring_buffer[r & ring->capacity_mask];
    r_atomic->store(r + 1, std::memory_order_release);
    return POLYDIM_STATUS_OK;
}

extern "C" void polydim_spsc_destroy(PolydimSpscRing* ring) {
    if (!ring) return;
    if (ring->ring_buffer) {
        polydim_free_aligned(ring->ring_buffer);
        ring->ring_buffer = nullptr;
    }
    ring->capacity = 0;
    ring->capacity_mask = 0;
}

/* ========================================================================= */
/* 5. GRAMIANA SIMÉTRICA: X^T * X (DSYRK / L1-L2 TILED PACKING)             */
/* ========================================================================= */

int32_t polydim_gram_dsyrk(
    const double* X,
    size_t D,
    size_t K,
    double* K_out,
    uint32_t num_threads
) {
    if (!X || !K_out) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (D == 0 || K == 0) return POLYDIM_STATUS_ERR_INVALID_DIM;

    int threads = (num_threads > 0) ? (int)num_threads : 1;
#if defined(_OPENMP)
    if (threads > 1) {
        omp_set_num_threads(threads);
    }
#endif

    std::memset(K_out, 0, K * K * sizeof(double));

    int fp_mode = g_fp_mode.load(std::memory_order_relaxed);

    if (fp_mode == POLYDIM_FP_DETERMINISTIC) {
        for (size_t i = 0; i < K; ++i) {
            for (size_t j = i; j < K; ++j) {
                std::vector<double> products(D);
                for (size_t d = 0; d < D; ++d) {
                    products[d] = X[d * K + i] * X[d * K + j];
                }
                double val = twosum_tree_reduce(products.data(), D);
                K_out[i * K + j] = val;
                K_out[j * K + i] = val;
            }
        }
    } else {
        BlasLoader::instance().compute_dsyrk(
            CblasRowMajor, CblasUpper, CblasTrans,
            K, D,
            1.0, X, K,
            0.0, K_out, K,
            num_threads
        );

        for (size_t i = 0; i < K; ++i) {
            for (size_t j = 0; j < i; ++j) {
                K_out[i * K + j] = K_out[j * K + i];
            }
        }
    }

    return POLYDIM_STATUS_OK;
}

extern "C" const char* polydim_get_blas_backend_name() {
    return BlasLoader::instance().backend_name();
}

extern "C" void polydim_set_blas_num_threads(int32_t num_threads) {
    typedef void (*openblas_set_threads_fn)(int);
    HMODULE mod = BlasLoader::instance().is_blas_loaded() ? GetModuleHandleA("libopenblas.dll") : nullptr;
    if (mod) {
        auto fn = (openblas_set_threads_fn)GetProcAddress(mod, "openblas_set_num_threads");
        if (fn) fn(num_threads);
    }
}

extern "C" void polydim_set_omp_num_threads(int32_t num_threads) {
#if defined(_OPENMP)
    if (num_threads > 0) {
        omp_set_num_threads(num_threads);
    }
#endif
}

/* ========================================================================= */
/* 6. OPERACIONES MATRICIALES KxK CONFINADAS A L1                           */
/* ========================================================================= */

static void matmul_kxk(const double* A, const double* B, double* C, size_t K) {
    std::memset(C, 0, K * K * sizeof(double));
    for (size_t i = 0; i < K; ++i) {
        for (size_t k = 0; k < K; ++k) {
            double a_ik = A[i * K + k];
            #pragma omp simd
            for (size_t j = 0; j < K; ++j) {
                C[i * K + j] += a_ik * B[k * K + j];
            }
        }
    }
}

static double matrix_frobenius_norm_diff(const double* A, const double* B, size_t size) {
    double sum = 0.0;
    #pragma omp simd reduction(+:sum)
    for (size_t i = 0; i < size; ++i) {
        double diff = A[i] - B[i];
        sum += diff * diff;
    }
    return std::sqrt(sum);
}

static bool solve_linear_system_kxk(double* A, double* B, size_t K, size_t NRHS) {
    for (size_t i = 0; i < K; ++i) {
        size_t pivot = i;
        double max_val = std::abs(A[i * K + i]);
        for (size_t r = i + 1; r < K; ++r) {
            double val = std::abs(A[r * K + i]);
            if (val > max_val) {
                max_val = val;
                pivot = r;
            }
        }
        if (max_val < 1e-15) return false;

        if (pivot != i) {
            for (size_t c = 0; c < K; ++c) std::swap(A[i * K + c], A[pivot * K + c]);
            for (size_t c = 0; c < NRHS; ++c) std::swap(B[i * NRHS + c], B[pivot * NRHS + c]);
        }

        double diag = A[i * K + i];
        for (size_t c = i; c < K; ++c) A[i * K + c] /= diag;
        for (size_t c = 0; c < NRHS; ++c) B[i * NRHS + c] /= diag;

        for (size_t r = 0; r < K; ++r) {
            if (r != i) {
                double factor = A[r * K + i];
                for (size_t c = i; c < K; ++c) A[r * K + c] -= factor * A[i * K + c];
                for (size_t c = 0; c < NRHS; ++c) B[r * NRHS + c] -= factor * B[i * NRHS + c];
            }
        }
    }
    return true;
}

/* ========================================================================= */
/* 7. RETRACCIÓN SHIFTED CHOLQR2 & CAYLEY-SMW (AREA 5 SOTA)                 */
/* ========================================================================= */

static int32_t apply_shifted_cholqr2(
    double* X,
    size_t D,
    size_t K,
    double shift_regularization,
    uint32_t num_threads
) {
    std::vector<double> Gram(K * K, 0.0);
    polydim_gram_dsyrk(X, D, K, Gram.data(), num_threads);

    // Calcular traza para shift adaptativo si es necesario
    double trace_gram = 0.0;
    for (size_t i = 0; i < K; ++i) trace_gram += Gram[i * K + i];
    double shift = (shift_regularization > 0.0) ? shift_regularization : 1e-14;

    std::vector<double> L(K * K, 0.0);
    for (size_t i = 0; i < K; ++i) {
        for (size_t j = 0; j <= i; ++j) {
            double sum = 0.0;
            for (size_t k = 0; k < j; ++k) {
                sum += L[i * K + k] * L[j * K + k];
            }
            if (i == j) {
                double val = Gram[i * K + i] - sum;
                if (val <= 1e-14) {
                    // Regularización dinámica Shifted CholQR
                    val += shift;
                }
                if (val <= 0.0) val = 1e-15;
                L[i * K + j] = std::sqrt(val);
            } else {
                L[i * K + j] = (Gram[i * K + j] - sum) / L[j * K + j];
            }
        }
    }

    // Invertir triangular inferior L
    std::vector<double> Linv(K * K, 0.0);
    for (size_t i = 0; i < K; ++i) {
        Linv[i * K + i] = 1.0 / L[i * K + i];
        for (size_t j = 0; j < i; ++j) {
            double sum = 0.0;
            for (size_t k = j; k < i; ++k) {
                sum += L[i * K + k] * Linv[k * K + j];
            }
            Linv[i * K + j] = -sum / L[i * K + i];
        }
    }

    // X = X * (L^-1)^T
    #pragma omp parallel for schedule(static)
    for (size_t d = 0; d < D; ++d) {
        std::vector<double> row_temp(K, 0.0);
        for (size_t k = 0; k < K; ++k) {
            double acc = 0.0;
            for (size_t j = 0; j < K; ++j) {
                acc += X[d * K + j] * Linv[k * K + j];
            }
            row_temp[k] = acc;
        }
        for (size_t k = 0; k < K; ++k) {
            X[d * K + k] = row_temp[k];
        }
    }

    return POLYDIM_STATUS_OK;
}

static int32_t retract_cayley_smw_gram(
    double* X,
    const double* G,
    size_t D,
    size_t K,
    double tau,
    double shift_regularization,
    uint32_t num_threads
) {
    std::vector<double> XtX(K * K, 0.0);
    std::vector<double> XtG(K * K, 0.0);
    std::vector<double> GtG(K * K, 0.0);

    polydim_gram_dsyrk(X, D, K, XtX.data(), num_threads);

    #pragma omp parallel for schedule(static) collapse(2)
    for (size_t i0 = 0; i0 < K; i0 += TILE_K) {
        for (size_t j0 = 0; j0 < K; j0 += TILE_K) {
            size_t i_max = std::min(i0 + TILE_K, K);
            size_t j_max = std::min(j0 + TILE_K, K);

            for (size_t d0 = 0; d0 < D; d0 += TILE_D) {
                size_t d_max = std::min(d0 + TILE_D, D);
                for (size_t i = i0; i < i_max; ++i) {
                    for (size_t j = j0; j < j_max; ++j) {
                        double acc_xg = 0.0;
                        double acc_gg = 0.0;
                        #pragma omp simd reduction(+:acc_xg, acc_gg)
                        for (size_t d = d0; d < d_max; ++d) {
                            acc_xg += X[d * K + i] * G[d * K + j];
                            if (j >= i) acc_gg += G[d * K + i] * G[d * K + j];
                        }
                        #pragma omp atomic
                        XtG[i * K + j] += acc_xg;
                        if (j >= i) {
                            #pragma omp atomic
                            GtG[i * K + j] += acc_gg;
                        }
                    }
                }
            }
        }
    }

    for (size_t i = 0; i < K; ++i) {
        for (size_t j = 0; j < i; ++j) {
            GtG[i * K + j] = GtG[j * K + i];
        }
    }

    std::vector<double> XtX_XtG(K * K, 0.0);
    matmul_kxk(XtX.data(), XtG.data(), XtX_XtG.data(), K);

    std::vector<double> GpGp(K * K, 0.0);
    for (size_t i = 0; i < K; ++i) {
        for (size_t j = 0; j < K; ++j) {
            double dot = 0.0;
            for (size_t k = 0; k < K; ++k) {
                dot += XtG[k * K + i] * XtX_XtG[k * K + j];
            }
            GpGp[i * K + j] = GtG[i * K + j] - dot;
        }
    }

    std::vector<double> H(K * K, 0.0);
    matmul_kxk(GpGp.data(), XtX.data(), H.data(), K);

    std::vector<double> S(K * K, 0.0);
    std::vector<double> RHS_S(K * K, 0.0);
    double tau_sq_fourth = 0.25 * tau * tau;
    double half_tau = 0.5 * tau;

    for (size_t idx = 0; idx < K * K; ++idx) {
        S[idx] = tau_sq_fourth * H[idx];
        RHS_S[idx] = -half_tau * H[idx];
    }
    for (size_t i = 0; i < K; ++i) {
        S[i * K + i] += 1.0;
    }

    if (!solve_linear_system_kxk(S.data(), RHS_S.data(), K, K)) {
        return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
    }

    const double* Z2 = RHS_S.data();

    std::vector<double> XtX_Z2(K * K, 0.0);
    matmul_kxk(XtX.data(), Z2, XtX_Z2.data(), K);

    std::vector<double> Z1(K * K, 0.0);
    for (size_t idx = 0; idx < K * K; ++idx) {
        Z1[idx] = XtX[idx] + half_tau * XtX_Z2[idx];
    }

    std::vector<double> XtG_Z1(K * K, 0.0);
    matmul_kxk(XtG.data(), Z1.data(), XtG_Z1.data(), K);

    std::vector<double> Coef_X(K * K, 0.0);
    for (size_t idx = 0; idx < K * K; ++idx) {
        Coef_X[idx] = Z2[idx] - XtG_Z1[idx];
    }

    #pragma omp parallel for schedule(static)
    for (size_t d = 0; d < D; ++d) {
        std::vector<double> row_update(K, 0.0);
        for (size_t k = 0; k < K; ++k) {
            double g_term = 0.0;
            double x_term = 0.0;
            for (size_t j = 0; j < K; ++j) {
                g_term += G[d * K + j] * Z1[j * K + k];
                x_term += X[d * K + j] * Coef_X[j * K + k];
            }
            row_update[k] = X[d * K + k] - tau * g_term - tau * x_term;
        }
        for (size_t k = 0; k < K; ++k) {
            X[d * K + k] = row_update[k];
        }
    }

    // Estabilización con Shifted CholQR
    return apply_shifted_cholqr2(X, D, K, shift_regularization, num_threads);
}

/* ========================================================================= */
/* 8. SOLVER MONOLÍTICO DE STIEFEL (C++ SINGLE-SHOT PIPELINE)               */
/* ========================================================================= */

int32_t polydim_stiefel_optimize(
    const double*               problem_data,
    size_t                      problem_size,
    double*                     X,
    size_t                      D,
    size_t                      K,
    const PolydimSolverOptions* options,
    PolydimSolverResult*        result,
    PolydimTelemetryBuffer*     telemetry
) {
    if (!X || !options || !result) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (D == 0 || K == 0 || K > D) return POLYDIM_STATUS_ERR_INVALID_DIM;

    auto t_start = std::chrono::high_resolution_clock::now();

    uint64_t max_iters = options->max_iterations > 0 ? options->max_iterations : 100;
    double grad_tol = options->gradient_tolerance > 0 ? options->gradient_tolerance : 1e-6;
    double step_tol = options->step_tolerance > 0 ? options->step_tolerance : 1e-8;
    double ortho_tol = options->ortho_tolerance > 0 ? options->ortho_tolerance : 1e-6;
    double lr = options->learning_rate > 0 ? options->learning_rate : 1e-3;
    uint32_t sample_period = options->sampling_period > 0 ? options->sampling_period : 1;
    uint32_t num_threads = options->num_threads > 0 ? options->num_threads : 1;
    double shift_reg = options->shift_regularization;

    // Buffer temporal de Gradiente Euclidiano G
    std::vector<double> G(D * K, 0.0);
    std::vector<double> I_K(K * K, 0.0);
    for (size_t i = 0; i < K; ++i) I_K[i * K + i] = 1.0;

    int32_t final_status = POLYDIM_STATUS_MAX_ITERATIONS;
    uint64_t iter = 0;
    double current_obj = 0.0;
    double current_grad_norm = 0.0;
    double current_ortho_err = 0.0;

    for (iter = 0; iter < max_iters; ++iter) {
        // 1. Evaluación de Objetivo y Gradiente Euclidiano: f(X) = 0.5 * ||X - Target||_F^2
        current_obj = 0.0;
        #pragma omp parallel for reduction(+:current_obj) schedule(static)
        for (size_t i = 0; i < D * K; ++i) {
            double target_val = (problem_data && i < problem_size) ? problem_data[i] : 0.0;
            double diff = X[i] - target_val;
            G[i] = diff;
            current_obj += 0.5 * diff * diff;
        }

        // 2. Proyección Tangente sobre Stiefel: G_tan = G - X * sym(X^T * G)
        std::vector<double> XtG(K * K, 0.0);
        #pragma omp parallel for schedule(static) collapse(2)
        for (size_t i0 = 0; i0 < K; i0 += TILE_K) {
            for (size_t j0 = 0; j0 < K; j0 += TILE_K) {
                size_t i_max = std::min(i0 + TILE_K, K);
                size_t j_max = std::min(j0 + TILE_K, K);
                for (size_t d = 0; d < D; ++d) {
                    for (size_t i = i0; i < i_max; ++i) {
                        for (size_t j = j0; j < j_max; ++j) {
                            double val = X[d * K + i] * G[d * K + j];
                            #pragma omp atomic
                            XtG[i * K + j] += val;
                        }
                    }
                }
            }
        }

        std::vector<double> SymXtG(K * K, 0.0);
        for (size_t i = 0; i < K; ++i) {
            for (size_t j = 0; j < K; ++j) {
                SymXtG[i * K + j] = 0.5 * (XtG[i * K + j] + XtG[j * K + i]);
            }
        }

        current_grad_norm = 0.0;
        #pragma omp parallel for reduction(+:current_grad_norm) schedule(static)
        for (size_t d = 0; d < D; ++d) {
            for (size_t k = 0; k < K; ++k) {
                double corr = 0.0;
                for (size_t j = 0; j < K; ++j) {
                    corr += X[d * K + j] * SymXtG[j * K + k];
                }
                G[d * K + k] -= corr;
                current_grad_norm += G[d * K + k] * G[d * K + k];
            }
        }
        current_grad_norm = std::sqrt(current_grad_norm);

        // 3. Chequeo de Convergencia
        if (current_grad_norm < grad_tol) {
            final_status = POLYDIM_STATUS_CONVERGED_GRADIENT;
            break;
        }

        // 4. Retracción de Variedad
        int32_t ret_st = 0;
        if (options->retraction_type == POLYDIM_RETRACTION_CAYLEY_SMW) {
            ret_st = retract_cayley_smw_gram(X, G.data(), D, K, lr, shift_reg, num_threads);
        } else {
            // Gradiente descendente en espacio ambiente + Shifted CholQR
            #pragma omp parallel for schedule(static)
            for (size_t i = 0; i < D * K; ++i) {
                X[i] -= lr * G[i];
            }
            ret_st = apply_shifted_cholqr2(X, D, K, shift_reg, num_threads);
        }

        if (ret_st != 0) {
            final_status = ret_st;
            break;
        }

        // 5. Cálculo de Error de Ortogonalidad ||X^T X - I||_F
        std::vector<double> Gram(K * K, 0.0);
        polydim_gram_dsyrk(X, D, K, Gram.data(), num_threads);
        current_ortho_err = matrix_frobenius_norm_diff(Gram.data(), I_K.data(), K * K);

        if (current_ortho_err > ortho_tol && iter > 5) {
            final_status = POLYDIM_STATUS_ERR_ORTHO_VIOLATION;
            break;
        }

        // 6. Registro de Telemetría
        if (telemetry && telemetry->points && (iter % sample_period == 0)) {
            if (telemetry->recorded_count < telemetry->capacity) {
                auto now = std::chrono::high_resolution_clock::now();
                uint64_t elapsed_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(now - t_start).count();
                PolydimTelemetryPoint& pt = telemetry->points[telemetry->recorded_count++];
                pt.iteration = iter;
                pt.objective_value = current_obj;
                pt.gradient_norm = current_grad_norm;
                pt.step_size = lr;
                pt.ortho_error = current_ortho_err;
                pt.elapsed_time_ns = elapsed_ns;
            }
        }
    }

    auto t_end = std::chrono::high_resolution_clock::now();
    uint64_t total_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(t_end - t_start).count();

    // Verificación final de ortogonalidad
    std::vector<double> Gram_final(K * K, 0.0);
    polydim_gram_dsyrk(X, D, K, Gram_final.data(), num_threads);
    current_ortho_err = matrix_frobenius_norm_diff(Gram_final.data(), I_K.data(), K * K);

    result->status = final_status;
    result->iterations_executed = iter;
    result->final_objective = current_obj;
    result->final_grad_norm = current_grad_norm;
    result->final_ortho_error = current_ortho_err;
    result->total_time_ns = total_ns;

    switch (final_status) {
        case POLYDIM_STATUS_CONVERGED_GRADIENT:
            std::snprintf(result->status_message, sizeof(result->status_message), "Converged: Gradient norm below tolerance.");
            break;
        case POLYDIM_STATUS_MAX_ITERATIONS:
            std::snprintf(result->status_message, sizeof(result->status_message), "Completed maximum iterations.");
            break;
        case POLYDIM_STATUS_ERR_ORTHO_VIOLATION:
            std::snprintf(result->status_message, sizeof(result->status_message), "Error: Stiefel manifold orthogonality violated.");
            break;
        default:
            std::snprintf(result->status_message, sizeof(result->status_message), "Optimization terminated with status code %d.", final_status);
            break;
    }

    return final_status;
}

/* ========================================================================= */
/* 9. BANKED SLOT LEASE RCU (ZERO-COPY IPC PMTP)                            */
/* ========================================================================= */

static int pmtp_is_process_alive(uint32_t pid) {
    if (pid == 0) return 0;
#if defined(_WIN32)
    HANDLE h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, (DWORD)pid);
    if (h == NULL) {
        DWORD err = GetLastError();
        return (err == ERROR_ACCESS_DENIED) ? 1 : 0;
    }
    DWORD exit_code = 0;
    if (GetExitCodeProcess(h, &exit_code)) {
        CloseHandle(h);
        return (exit_code == STILL_ACTIVE) ? 1 : 0;
    }
    CloseHandle(h);
    return 0;
#else
    return (kill((pid_t)pid, 0) == 0) ? 1 : 0;
#endif
}

extern "C" int32_t pmtp_reap_orphaned_leases(
    PmtpBankedSlotHeader* header, 
    uint32_t target_bank, 
    uint64_t timeout_ns, 
    uint32_t* num_reclaimed
) {
    if (!header || !num_reclaimed) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (target_bank > 1) return POLYDIM_STATUS_ERR_INVALID_DIM;

    *num_reclaimed = 0;
    PmtpReaderLease* leases = (target_bank == 0) ? header->leases_bank0 : header->leases_bank1;

    for (size_t i = 0; i < PMTP_MAX_READERS_PER_BANK; ++i) {
        std::atomic<uint32_t>* state_atom = reinterpret_cast<std::atomic<uint32_t>*>(&leases[i].state);
        uint32_t cur_state = state_atom->load(std::memory_order_acquire);

        if (cur_state == PMTP_LEASE_ACTIVE) {
            uint32_t pid = leases[i].pid;
            if (!pmtp_is_process_alive(pid)) {
                state_atom->store(PMTP_LEASE_RECLAIMED, std::memory_order_release);
                (*num_reclaimed)++;
                ((std::atomic<uint32_t>*)&header->num_reclaimed_orphans)->fetch_add(1, std::memory_order_relaxed);
            }
        }
    }

    return POLYDIM_STATUS_OK;
}

extern "C" int32_t pmtp_banked_slot_acquire_reader(
    PmtpBankedSlotHeader* header, 
    uint32_t* acquired_bank,
    uint32_t* acquired_slot_idx,
    uint32_t pid, 
    uint64_t start_time_ns
) {
    if (!header || !acquired_bank || !acquired_slot_idx) return POLYDIM_STATUS_ERR_NULL_PTR;

    uint32_t bank = ((std::atomic<uint32_t>*)&header->active_bank)->load(std::memory_order_acquire);
    PmtpReaderLease* leases = (bank == 0) ? header->leases_bank0 : header->leases_bank1;

    for (size_t i = 0; i < PMTP_MAX_READERS_PER_BANK; ++i) {
        std::atomic<uint32_t>* state_atom = reinterpret_cast<std::atomic<uint32_t>*>(&leases[i].state);
        uint32_t cur_state = state_atom->load(std::memory_order_relaxed);

        if (cur_state == PMTP_LEASE_FREE || cur_state == PMTP_LEASE_CLOSED || cur_state == PMTP_LEASE_RECLAIMED) {
            leases[i].pid = pid;
            leases[i].process_start_time_ns = start_time_ns;
            leases[i].generation = header->sequence;
            
            state_atom->store(PMTP_LEASE_ACTIVE, std::memory_order_release);
            *acquired_bank = bank;
            *acquired_slot_idx = static_cast<uint32_t>(i);
            return POLYDIM_STATUS_OK;
        }
    }

    return -11; // Sin slot libre
}

extern "C" int32_t pmtp_banked_slot_release_reader(PmtpBankedSlotHeader* header, uint32_t bank, uint32_t slot_idx) {
    if (!header || slot_idx >= PMTP_MAX_READERS_PER_BANK) return POLYDIM_STATUS_ERR_NULL_PTR;

    PmtpReaderLease* leases = (bank == 0) ? header->leases_bank0 : header->leases_bank1;
    std::atomic<uint32_t>* state_atom = reinterpret_cast<std::atomic<uint32_t>*>(&leases[slot_idx].state);
    state_atom->store(PMTP_LEASE_CLOSED, std::memory_order_release);
    return POLYDIM_STATUS_OK;
}

extern "C" int32_t pmtp_banked_slot_acquire_writer(PmtpBankedSlotHeader* header, uint32_t* write_bank, uint32_t pid, uint64_t start_time_ns) {
    if (!header || !write_bank) return POLYDIM_STATUS_ERR_NULL_PTR;

    uint32_t expected = 0;
    if (!((std::atomic<uint32_t>*)&header->writer_active)->compare_exchange_strong(expected, 1, std::memory_order_acquire)) {
        return -10; // Writer contention
    }

    uint32_t active = ((std::atomic<uint32_t>*)&header->active_bank)->load(std::memory_order_relaxed);
    uint32_t target = 1 - active;
    PmtpReaderLease* target_leases = (target == 0) ? header->leases_bank0 : header->leases_bank1;

    int retries = 5000;
    while (retries-- > 0) {
        bool has_active_readers = false;
        for (size_t i = 0; i < PMTP_MAX_READERS_PER_BANK; ++i) {
            std::atomic<uint32_t>* state_atom = reinterpret_cast<std::atomic<uint32_t>*>(&target_leases[i].state);
            if (state_atom->load(std::memory_order_acquire) == PMTP_LEASE_ACTIVE) {
                has_active_readers = true;
                break;
            }
        }
        if (!has_active_readers) break;

        uint32_t reclaimed = 0;
        pmtp_reap_orphaned_leases(header, target, 1000000, &reclaimed);
    }

    header->owner_pid = pid;
    header->owner_start_time_ns = start_time_ns;
    *write_bank = target;
    return POLYDIM_STATUS_OK;
}

extern "C" int32_t pmtp_banked_slot_commit_writer(PmtpBankedSlotHeader* header, uint32_t write_bank) {
    if (!header) return POLYDIM_STATUS_ERR_NULL_PTR;

    std::atomic_thread_fence(std::memory_order_release);
    ((std::atomic<uint32_t>*)&header->active_bank)->store(write_bank, std::memory_order_release);
    ((std::atomic<uint64_t>*)&header->sequence)->fetch_add(1, std::memory_order_relaxed);
    ((std::atomic<uint32_t>*)&header->writer_active)->store(0, std::memory_order_release);
    return POLYDIM_STATUS_OK;
}

/* ========================================================================= */
/* 10. RESERVORIO ESTRUCTURADO WALSH-HADAMARD (LSM O(D log D), O(D) MEMORIA) */
/* ========================================================================= */

static void fwht_normalized_inplace(double* x, size_t D) {
    for (size_t len = 1; len < D; len <<= 1) {
        #pragma omp parallel for schedule(static)
        for (size_t i = 0; i < D; i += 2 * len) {
            for (size_t j = 0; j < len; ++j) {
                double u = x[i + j];
                double v = x[i + j + len];
                x[i + j] = u + v;
                x[i + j + len] = u - v;
            }
        }
    }

    double inv_sqrt_d = 1.0 / std::sqrt(static_cast<double>(D));
    #pragma omp parallel for simd schedule(static)
    for (size_t i = 0; i < D; ++i) {
        x[i] *= inv_sqrt_d;
    }
}

extern "C" int32_t polydim_structured_lsm_step(
    double*         state,
    const double*   input,
    const int8_t*   d1,
    const uint32_t* p1,
    const int8_t*   d2,
    const uint32_t* p2,
    size_t          D,
    double          alpha_leak,
    double          input_scale
) {
    if (!state || !d1 || !p1 || !d2 || !p2) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (D == 0 || (D & (D - 1)) != 0) return POLYDIM_STATUS_ERR_INVALID_DIM;

    std::vector<double> tmp(D, 0.0);

    #pragma omp parallel for schedule(static)
    for (size_t i = 0; i < D; ++i) {
        double s_val = state[p1[i]] * (d1[p1[i]] < 0 ? -1.0 : 1.0);
        tmp[i] = s_val;
    }

    fwht_normalized_inplace(tmp.data(), D);

    double alpha = (alpha_leak > 0.0 && alpha_leak <= 1.0) ? alpha_leak : 0.8;
    double in_scale = (input_scale != 0.0) ? input_scale : 1.0;

    #pragma omp parallel for schedule(static)
    for (size_t i = 0; i < D; ++i) {
        double w_act = tmp[p2[i]] * (d2[i] < 0 ? -1.0 : 1.0);
        double in_val = (input != nullptr) ? (in_scale * input[i]) : 0.0;
        double next_val = std::tanh(w_act + in_val);
        state[i] = (1.0 - alpha) * state[i] + alpha * next_val;
    }

    return POLYDIM_STATUS_OK;
}
