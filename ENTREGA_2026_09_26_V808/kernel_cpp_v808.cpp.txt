/**
 * @file kernel_cpp_v808.cpp
 * @brief Kernel Monolítico C++ POLYDIM V808 Industrial:
 *        - Stiefel Retraction con Precisión Mixta (FP64 Core) y Proyección Tangencial
 *        - Refinamiento Polar Cuadrático de Newton (3I - S)/2
 *        - Non-Temporal Stores con Barrera de Memoria Simétrica
 *        - Anillo SPSC Wait-Free con Aislamiento de 128B
 *        - Banked RCU de 3 Épocas (Anti-Starvation, Anti-ABA con Epoch Counter)
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

#if defined(_WIN32)
#include <windows.h>
#else
#include <signal.h>
#include <sys/types.h>
#include <errno.h>
#endif

#include "polydim_solver_abi.h"
#include "polydim_blas_loader.h"

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

/* Algoritmo TwoSum de Knuth */
static inline void knuth_two_sum(double a, double b, double* s, double* t) {
    double sum = a + b;
    double b_virtual = sum - a;
    double a_virtual = sum - b_virtual;
    double b_roundoff = b - b_virtual;
    double a_roundoff = a - a_virtual;
    *s = sum;
    *t = a_roundoff + b_roundoff;
}

/* Reducción determinista por árbol binario */
static double twosum_tree_reduce(const double* data, size_t N) {
    if (N == 0) return 0.0;
    if (N == 1) return data[0];

    std::vector<double> current(data, data + N);
    std::vector<double> errors;
    errors.reserve(N);

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
/* 2. NON-TEMPORAL STREAMING STORES CON FENCING COMPLETO                     */
/* ========================================================================= */

extern "C" int32_t polydim_stream_copy_nt(double* dest, const double* src, size_t count) {
    if (!dest || !src) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (count == 0) return POLYDIM_STATUS_OK;

    size_t i = 0;
    uintptr_t dest_addr = reinterpret_cast<uintptr_t>(dest);
    if ((dest_addr % 16 == 0) && count >= 2) {
        size_t sse_blocks = count / 2;
        #pragma omp parallel
        {
            #pragma omp for schedule(static)
            for (size_t b = 0; b < sse_blocks; ++b) {
                size_t idx = b * 2;
                __m128d data = _mm_loadu_pd(&src[idx]);
                _mm_stream_pd(&dest[idx], data);
            }
            _mm_sfence();
        }
        i = sse_blocks * 2;
        _mm_sfence();
    }

    for (; i < count; ++i) {
        dest[i] = src[i];
    }

    #if defined(__x86_64__) || defined(_M_X64)
    _mm_sfence();
    #else
    std::atomic_thread_fence(std::memory_order_seq_cst);
    #endif

    return POLYDIM_STATUS_OK;
}

/* ========================================================================= */
/* 3. ALLOCATOR PAIRING & POLYDIM_HANDLE                                    */
/* ========================================================================= */

static std::atomic<uint64_t> g_allocation_seq{1};

extern "C" void* polydim_alloc_aligned(size_t bytes, size_t alignment) {
    size_t align = (alignment > 0) ? alignment : 64;
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
    reinterpret_cast<std::atomic<int32_t>*>(&handle->refcount)->store(1, std::memory_order_release);
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
/* 4. WAIT-FREE SPSC RING BUFFER CON BARRERAS SIMÉTRICAS                    */
/* ========================================================================= */

extern "C" int32_t polydim_spsc_init(PolydimSpscRing* ring, size_t capacity) {
    if (!ring) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (capacity < 2 || (capacity & (capacity - 1)) != 0) {
        return POLYDIM_STATUS_ERR_INVALID_DIM;
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
    std::atomic_thread_fence(std::memory_order_release);
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

    std::atomic_thread_fence(std::memory_order_acquire);
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
/* 5. GRAMIANA SIMÉTRICA DSYRK FP64                                         */
/* ========================================================================= */

extern "C" int32_t polydim_gram_dsyrk(
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

/* ========================================================================= */
/* 6. OPERACIONES MATRICIALES KxK Y FACTORIZACIÓN                           */
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

static bool solve_linear_system_general(double* A, double* B, size_t N, size_t NRHS) {
    for (size_t i = 0; i < N; ++i) {
        size_t pivot = i;
        double max_val = std::abs(A[i * N + i]);
        for (size_t r = i + 1; r < N; ++r) {
            double val = std::abs(A[r * N + i]);
            if (val > max_val) {
                max_val = val;
                pivot = r;
            }
        }
        if (max_val < 1e-15) return false;

        if (pivot != i) {
            for (size_t c = 0; c < N; ++c) std::swap(A[i * N + c], A[pivot * N + c]);
            for (size_t c = 0; c < NRHS; ++c) std::swap(B[i * NRHS + c], B[pivot * NRHS + c]);
        }

        double diag = A[i * N + i];
        for (size_t c = i; c < N; ++c) A[i * N + c] /= diag;
        for (size_t c = 0; c < NRHS; ++c) B[i * NRHS + c] /= diag;

        for (size_t r = 0; r < N; ++r) {
            if (r != i) {
                double factor = A[r * N + i];
                for (size_t c = i; c < N; ++c) A[r * N + c] -= factor * A[i * N + c];
                for (size_t c = 0; c < NRHS; ++c) B[r * NRHS + c] -= factor * B[i * NRHS + c];
            }
        }
    }
    return true;
}

/* ========================================================================= */
/* 7. PROYECCIÓN TANGENCIAL Y REFINAMIENTO POLAR DE NEWTON                  */
/* ========================================================================= */

// Proyección ortogonal exacta al espacio tangente T_V St(K, D):
// Z_tangente = Z - V * sym(V^T * Z)
static void project_to_tangent_space(
    const double* V,
    double* Z,
    size_t D,
    size_t K
) {
    std::vector<double> VtZ(K * K, 0.0);

    #pragma omp parallel for schedule(static) collapse(2)
    for (size_t i0 = 0; i0 < K; i0 += TILE_K) {
        for (size_t j0 = 0; j0 < K; j0 += TILE_K) {
            size_t i_max = std::min(i0 + TILE_K, K);
            size_t j_max = std::min(j0 + TILE_K, K);
            for (size_t d = 0; d < D; ++d) {
                for (size_t i = i0; i < i_max; ++i) {
                    for (size_t j = j0; j < j_max; ++j) {
                        double val = V[d * K + i] * Z[d * K + j];
                        #pragma omp atomic
                        VtZ[i * K + j] += val;
                    }
                }
            }
        }
    }

    std::vector<double> sym_VtZ(K * K, 0.0);
    for (size_t i = 0; i < K; ++i) {
        for (size_t j = 0; j < K; ++j) {
            sym_VtZ[i * K + j] = 0.5 * (VtZ[i * K + j] + VtZ[j * K + i]);
        }
    }

    #pragma omp parallel for schedule(static)
    for (size_t d = 0; d < D; ++d) {
        for (size_t k = 0; k < K; ++k) {
            double corr = 0.0;
            for (size_t j = 0; j < K; ++j) {
                corr += V[d * K + j] * sym_VtZ[j * K + k];
            }
            Z[d * K + k] -= corr;
        }
    }
}

// Refinamiento Newton polar cuadrático: V <- V * (3*I - V^T*V) / 2
static void polar_newton_refinement(double* V, size_t D, size_t K, uint32_t num_threads) {
    std::vector<double> S(K * K, 0.0);
    polydim_gram_dsyrk(V, D, K, S.data(), num_threads);

    std::vector<double> correction(K * K, 0.0);
    for (size_t i = 0; i < K; ++i) {
        for (size_t j = 0; j < K; ++j) {
            double identity_term = (i == j) ? 3.0 : 0.0;
            correction[i * K + j] = 0.5 * (identity_term - S[i * K + j]);
        }
    }

    #pragma omp parallel for schedule(static)
    for (size_t d = 0; d < D; ++d) {
        std::vector<double> row_temp(K, 0.0);
        for (size_t k = 0; k < K; ++k) {
            double acc = 0.0;
            for (size_t j = 0; j < K; ++j) {
                acc += V[d * K + j] * correction[j * K + k];
            }
            row_temp[k] = acc;
        }
        for (size_t k = 0; k < K; ++k) {
            V[d * K + k] = row_temp[k];
        }
    }
}

/* ========================================================================= */
/* 8. RETRACCIÓN SHIFTED CHOLQR2 Y CAYLEY-SMW EN PRECISIÓN MIXTA            */
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

    double trace_gram = 0.0;
    for (size_t i = 0; i < K; ++i) trace_gram += Gram[i * K + i];
    double mean_diag = trace_gram / static_cast<double>(K);
    double adaptive_shift = (shift_regularization > 0.0) ? shift_regularization * mean_diag : 1e-14 * mean_diag;

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
                    val += adaptive_shift;
                }
                if (val <= 0.0) val = 1e-15;
                L[i * K + j] = std::sqrt(val);
            } else {
                L[i * K + j] = (Gram[i * K + j] - sum) / L[j * K + j];
            }
        }
    }

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

    // Refinamiento Newton polar cuadrático
    polar_newton_refinement(X, D, K, num_threads);
    return POLYDIM_STATUS_OK;
}

static int32_t retract_cayley_smw_mixed(
    double* V,
    double* Z,
    size_t D,
    size_t K,
    double tau,
    double shift_regularization,
    uint32_t num_threads
) {
    // 1. Proyección obligatoria al espacio tangente T_V St(K, D)
    project_to_tangent_space(V, Z, D, K);

    // 2. Formación de matrices bloque P = [Z, V] y Q = [V, -Z] (D x 2K)
    // Acumulación en FP64 de Q^T * P (2K x 2K)
    size_t K2 = 2 * K;
    std::vector<double> QtP(K2 * K2, 0.0);

    // QtP = [ V^T*Z,   V^T*V  ]
    //       [-Z^T*Z,  -Z^T*V  ]
    std::vector<double> VtZ(K * K, 0.0);
    std::vector<double> VtV(K * K, 0.0);
    std::vector<double> ZtZ(K * K, 0.0);

    polydim_gram_dsyrk(V, D, K, VtV.data(), num_threads);
    polydim_gram_dsyrk(Z, D, K, ZtZ.data(), num_threads);

    #pragma omp parallel for schedule(static) collapse(2)
    for (size_t i0 = 0; i0 < K; i0 += TILE_K) {
        for (size_t j0 = 0; j0 < K; j0 += TILE_K) {
            size_t i_max = std::min(i0 + TILE_K, K);
            size_t j_max = std::min(j0 + TILE_K, K);
            for (size_t d = 0; d < D; ++d) {
                for (size_t i = i0; i < i_max; ++i) {
                    for (size_t j = j0; j < j_max; ++j) {
                        double val = V[d * K + i] * Z[d * K + j];
                        #pragma omp atomic
                        VtZ[i * K + j] += val;
                    }
                }
            }
        }
    }

    for (size_t i = 0; i < K; ++i) {
        for (size_t j = 0; j < K; ++j) {
            QtP[i * K2 + j]             = VtZ[i * K + j];
            QtP[i * K2 + (K + j)]       = VtV[i * K + j];
            QtP[(K + i) * K2 + j]       = -ZtZ[i * K + j];
            QtP[(K + i) * K2 + (K + j)] = -VtZ[j * K + i];
        }
    }

    // C = I_{2K} - 0.5 * tau * QtP
    std::vector<double> C(K2 * K2, 0.0);
    for (size_t i = 0; i < K2; ++i) {
        for (size_t j = 0; j < K2; ++j) {
            C[i * K2 + j] = -0.5 * tau * QtP[i * K2 + j];
        }
        C[i * K2 + i] += 1.0;
    }

    // RHS = Q^T * V (2K x K): [ V^T * V ]
    //                         [-Z^T * V ]
    std::vector<double> RHS(K2 * K, 0.0);
    for (size_t i = 0; i < K; ++i) {
        for (size_t j = 0; j < K; ++j) {
            RHS[i * K + j]       = VtV[i * K + j];
            RHS[(K + i) * K + j] = -VtZ[j * K + i];
        }
    }

    if (!solve_linear_system_general(C.data(), RHS.data(), K2, K)) {
        // Fallback robusto a Shifted CholQR2
        #pragma omp parallel for schedule(static)
        for (size_t i = 0; i < D * K; ++i) {
            V[i] += tau * Z[i];
        }
        return apply_shifted_cholqr2(V, D, K, shift_regularization, num_threads);
    }

    // V_new = V + 0.5 * tau * P * (C^{-1} * RHS)
    const double* Sol = RHS.data(); // 2K x K
    #pragma omp parallel for schedule(static)
    for (size_t d = 0; d < D; ++d) {
        std::vector<double> row_update(K, 0.0);
        for (size_t k = 0; k < K; ++k) {
            double p_term = 0.0;
            for (size_t j = 0; j < K; ++j) {
                p_term += Z[d * K + j] * Sol[j * K + k];
                p_term += V[d * K + j] * Sol[(K + j) * K + k];
            }
            row_update[k] = V[d * K + k] + 0.5 * tau * p_term;
        }
        for (size_t k = 0; k < K; ++k) {
            V[d * K + k] = row_update[k];
        }
    }

    // 3. Refinamiento Newton polar para exactitud de bit
    polar_newton_refinement(V, D, K, num_threads);
    return POLYDIM_STATUS_OK;
}

/* ========================================================================= */
/* 9. SOLVER MONOLÍTICO DE STIEFEL INDUSTRIAL                               */
/* ========================================================================= */

extern "C" int32_t polydim_stiefel_optimize(
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
    double ortho_tol = options->ortho_tolerance > 0 ? options->ortho_tolerance : 1e-5;
    double lr = options->learning_rate > 0 ? options->learning_rate : 1e-3;
    uint32_t sample_period = options->sampling_period > 0 ? options->sampling_period : 1;
    uint32_t num_threads = options->num_threads > 0 ? options->num_threads : 1;
    double shift_reg = options->shift_regularization;

    std::vector<double> G(D * K, 0.0);
    std::vector<double> I_K(K * K, 0.0);
    for (size_t i = 0; i < K; ++i) I_K[i * K + i] = 1.0;

    int32_t final_status = POLYDIM_STATUS_MAX_ITERATIONS;
    uint64_t iter = 0;
    double current_obj = 0.0;
    double current_grad_norm = 0.0;
    double current_ortho_err = 0.0;

    for (iter = 0; iter < max_iters; ++iter) {
        current_obj = 0.0;
        #pragma omp parallel for reduction(+:current_obj) schedule(static)
        for (size_t i = 0; i < D * K; ++i) {
            double target_val = (problem_data && i < problem_size) ? problem_data[i] : 0.0;
            double diff = X[i] - target_val;
            G[i] = diff;
            current_obj += 0.5 * diff * diff;
        }

        // Gradiente Riemannian tangencial
        project_to_tangent_space(X, G.data(), D, K);

        current_grad_norm = 0.0;
        #pragma omp parallel for reduction(+:current_grad_norm) schedule(static)
        for (size_t i = 0; i < D * K; ++i) {
            current_grad_norm += G[i] * G[i];
        }
        current_grad_norm = std::sqrt(current_grad_norm);

        if (current_grad_norm < grad_tol) {
            final_status = POLYDIM_STATUS_CONVERGED_GRADIENT;
            break;
        }

        int32_t ret_st = 0;
        if (options->retraction_type == POLYDIM_RETRACTION_CAYLEY_SMW) {
            // Z = -G (dirección de descenso)
            std::vector<double> Z(D * K);
            #pragma omp parallel for schedule(static)
            for (size_t i = 0; i < D * K; ++i) {
                Z[i] = -G[i];
            }
            ret_st = retract_cayley_smw_mixed(X, Z.data(), D, K, lr, shift_reg, num_threads);
        } else {
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

        std::vector<double> Gram(K * K, 0.0);
        polydim_gram_dsyrk(X, D, K, Gram.data(), num_threads);
        current_ortho_err = matrix_frobenius_norm_diff(Gram.data(), I_K.data(), K * K);

        if (current_ortho_err > ortho_tol && iter > 5) {
            final_status = POLYDIM_STATUS_ERR_ORTHO_VIOLATION;
            break;
        }

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
/* 10. BANKED RCU DE 3 ÉPOCAS CON CAS Y DRAIN SEQCST                        */
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
    int res = kill((pid_t)pid, 0);
    if (res == 0) return 1;
    if (errno == EPERM) return 1;
    return 0;
#endif
}

static PmtpReaderLease* get_bank_leases(PmtpBankedSlotHeader* header, uint32_t bank_idx) {
    switch (bank_idx % PMTP_NUM_RCU_SLOTS) {
        case 0: return header->leases_bank0;
        case 1: return header->leases_bank1;
        case 2: return header->leases_bank2;
        default: return header->leases_bank0;
    }
}

extern "C" int32_t pmtp_reap_orphaned_leases(
    PmtpBankedSlotHeader* header, 
    uint32_t target_bank, 
    uint64_t timeout_ns, 
    uint32_t* num_reclaimed
) {
    if (!header || !num_reclaimed) return POLYDIM_STATUS_ERR_NULL_PTR;

    *num_reclaimed = 0;
    PmtpReaderLease* leases = get_bank_leases(header, target_bank);

    for (size_t i = 0; i < PMTP_MAX_READERS_PER_BANK; ++i) {
        std::atomic<uint32_t>* state_atom = reinterpret_cast<std::atomic<uint32_t>*>(&leases[i].state);
        uint32_t cur_state = state_atom->load(std::memory_order_acquire);

        if (cur_state == PMTP_LEASE_ACTIVE) {
            uint32_t pid = leases[i].pid;
            if (!pmtp_is_process_alive(pid)) {
                uint32_t expected = PMTP_LEASE_ACTIVE;
                if (state_atom->compare_exchange_strong(expected, PMTP_LEASE_RECLAIMED, std::memory_order_acq_rel)) {
                    (*num_reclaimed)++;
                    reinterpret_cast<std::atomic<uint32_t>*>(&header->num_reclaimed_orphans)->fetch_add(1, std::memory_order_relaxed);
                }
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

    uint32_t epoch = reinterpret_cast<std::atomic<uint32_t>*>(&header->global_epoch)->load(std::memory_order_acquire);
    uint32_t bank = epoch % PMTP_NUM_RCU_SLOTS;
    PmtpReaderLease* leases = get_bank_leases(header, bank);

    for (size_t i = 0; i < PMTP_MAX_READERS_PER_BANK; ++i) {
        std::atomic<uint32_t>* state_atom = reinterpret_cast<std::atomic<uint32_t>*>(&leases[i].state);
        uint32_t cur_state = state_atom->load(std::memory_order_relaxed);

        if (cur_state == PMTP_LEASE_FREE || cur_state == PMTP_LEASE_CLOSED || cur_state == PMTP_LEASE_RECLAIMED) {
            uint32_t expected = cur_state;
            if (state_atom->compare_exchange_strong(expected, PMTP_LEASE_ACTIVE, std::memory_order_acq_rel)) {
                leases[i].pid = pid;
                leases[i].process_start_time_ns = start_time_ns;
                leases[i].epoch = epoch;
                leases[i].generation = reinterpret_cast<std::atomic<uint64_t>*>(&header->sequence)->load(std::memory_order_acquire);
                
                *acquired_bank = bank;
                *acquired_slot_idx = static_cast<uint32_t>(i);
                std::atomic_thread_fence(std::memory_order_acquire);
                return POLYDIM_STATUS_OK;
            }
        }
    }

    return POLYDIM_STATUS_ERR_NO_FREE_SLOT;
}

extern "C" int32_t pmtp_banked_slot_release_reader(PmtpBankedSlotHeader* header, uint32_t bank, uint32_t slot_idx) {
    if (!header || slot_idx >= PMTP_MAX_READERS_PER_BANK) return POLYDIM_STATUS_ERR_NULL_PTR;

    PmtpReaderLease* leases = get_bank_leases(header, bank);
    std::atomic<uint32_t>* state_atom = reinterpret_cast<std::atomic<uint32_t>*>(&leases[slot_idx].state);
    state_atom->store(PMTP_LEASE_CLOSED, std::memory_order_release);
    return POLYDIM_STATUS_OK;
}

extern "C" int32_t pmtp_banked_slot_acquire_writer(PmtpBankedSlotHeader* header, uint32_t* write_bank, uint32_t pid, uint64_t start_time_ns) {
    if (!header || !write_bank) return POLYDIM_STATUS_ERR_NULL_PTR;

    uint32_t expected = 0;
    if (!reinterpret_cast<std::atomic<uint32_t>*>(&header->writer_active)->compare_exchange_strong(expected, 1, std::memory_order_acq_rel)) {
        return POLYDIM_STATUS_ERR_WRITER_BUSY;
    }

    // Esquema de 3 épocas: el escritor drena el slot de hace 2 épocas
    uint32_t old_epoch = reinterpret_cast<std::atomic<uint32_t>*>(&header->global_epoch)->fetch_add(1, std::memory_order_acq_rel);
    std::atomic_thread_fence(std::memory_order_seq_cst);

    uint32_t drain_bank = (old_epoch + PMTP_NUM_RCU_SLOTS - 2) % PMTP_NUM_RCU_SLOTS;
    PmtpReaderLease* drain_leases = get_bank_leases(header, drain_bank);

    int retries = 10000;
    while (retries-- > 0) {
        bool has_active_readers = false;
        for (size_t i = 0; i < PMTP_MAX_READERS_PER_BANK; ++i) {
            std::atomic<uint32_t>* state_atom = reinterpret_cast<std::atomic<uint32_t>*>(&drain_leases[i].state);
            if (state_atom->load(std::memory_order_acquire) == PMTP_LEASE_ACTIVE) {
                has_active_readers = true;
                break;
            }
        }
        if (!has_active_readers) break;

        uint32_t reclaimed = 0;
        pmtp_reap_orphaned_leases(header, drain_bank, 1000000, &reclaimed);
    }

    std::atomic_thread_fence(std::memory_order_acquire);
    header->owner_pid = pid;
    header->owner_start_time_ns = start_time_ns;
    *write_bank = drain_bank;
    return POLYDIM_STATUS_OK;
}

extern "C" int32_t pmtp_banked_slot_commit_writer(PmtpBankedSlotHeader* header, uint32_t write_bank) {
    if (!header) return POLYDIM_STATUS_ERR_NULL_PTR;

    std::atomic_thread_fence(std::memory_order_release);
    reinterpret_cast<std::atomic<uint32_t>*>(&header->active_bank)->store(write_bank, std::memory_order_release);
    reinterpret_cast<std::atomic<uint64_t>*>(&header->sequence)->fetch_add(1, std::memory_order_relaxed);
    reinterpret_cast<std::atomic<uint32_t>*>(&header->writer_active)->store(0, std::memory_order_release);
    return POLYDIM_STATUS_OK;
}

/* ========================================================================= */
/* 11. RESERVORIO WALSH-HADAMARD (LSM O(D log D))                            */
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
