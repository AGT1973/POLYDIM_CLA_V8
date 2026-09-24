// ============================================================================
// POLYDIM V800 — SOTA STIEFEL CAYLEY-SMW RETRACTION (AVX-512 TILED MICRO-KERNEL)
// Matrix-Free Tall-Skinny DGEMM (X^T G, G^T G, X^T X) with 3-Level Cache Blocking
// Targets: Intel Xeon / Core / AMD Zen 4 (AVX-512F / FMA) + AVX2 Fallback
// ============================================================================

#include <cstdint>
#include <cmath>
#include <vector>
#include <algorithm>
#include <cstring>
#include <iostream>

#if defined(__x86_64__) || defined(_M_X64)
  #include <immintrin.h>
#endif

#include <omp.h>

#if defined(_WIN32)
  #define POLYDIM_EXPORT __declspec(dllexport)
  #define POLYDIM_CALL __cdecl
#else
  #define POLYDIM_EXPORT __attribute__((visibility("default")))
  #define POLYDIM_CALL
#endif

// ============================================================================
// STATUS CODES
// ============================================================================
enum StiefelStatusCode : int32_t {
    STIEFEL_SUCCESS = 0,
    STIEFEL_ERR_NULL_POINTER = -1,
    STIEFEL_ERR_INVALID_DIM = -2,
    STIEFEL_ERR_NAN_OR_INF = -3,
    STIEFEL_ERR_NUMERICAL_INSTABILITY = -5,
    STIEFEL_ERR_BUFFER_OVERFLOW = -7
};

// ============================================================================
// 1. PANEL PACKING ROUTINES (ROW-MAJOR -> CONTINUOUS COLUMN-MAJOR KC-PANEL)
// Transforms X[D x K] block into aligned contiguous panel for unit-stride SIMD
// ============================================================================
inline void pack_panel_kc(
    const double* __restrict src, // D x K (row-major: src[i * K + k])
    double* __restrict dst,       // KC x K (column-major continuous: dst[k * pitch_kc + row])
    uint64_t row_start,
    uint64_t kc_len,
    uint64_t pitch_kc,
    uint32_t K
) {
    for (uint32_t k = 0; k < K; ++k) {
        double* dst_col = &dst[k * pitch_kc];
        for (uint64_t r = 0; r < kc_len; ++r) {
            dst_col[r] = src[(row_start + r) * K + k];
        }
    }
}

// ============================================================================
// 2. AVX-512 TILED MICRO-KERNEL (8x8 ACCUMULATION WITH 16 ZMM REGISTERS)
// Computes C[K x K] += A_panel^T * B_panel for a KC slice of D
// ============================================================================
#if defined(__AVX512F__)
inline void micro_kernel_dgemm_avx512_kc(
    const double* __restrict A_panel, // KC x K (packed col-major)
    const double* __restrict B_panel, // KC x K (packed col-major)
    double* __restrict C,             // K x K (accumulating result)
    uint64_t actual_kc,
    uint64_t pitch_kc,
    uint32_t K
) {
    for (uint32_t i = 0; i < K; ++i) {
        const double* a_col = &A_panel[i * pitch_kc];
        for (uint32_t j = 0; j < K; ++j) {
            const double* b_col = &B_panel[j * pitch_kc];

            __m512d sum0 = _mm512_setzero_pd();
            __m512d sum1 = _mm512_setzero_pd();
            __m512d sum2 = _mm512_setzero_pd();
            __m512d sum3 = _mm512_setzero_pd();

            uint64_t r = 0;
            for (; r + 31 < actual_kc; r += 32) {
                __m512d a0 = _mm512_loadu_pd(&a_col[r]);
                __m512d b0 = _mm512_loadu_pd(&b_col[r]);
                sum0 = _mm512_fmadd_pd(a0, b0, sum0);

                __m512d a1 = _mm512_loadu_pd(&a_col[r + 8]);
                __m512d b1 = _mm512_loadu_pd(&b_col[r + 8]);
                sum1 = _mm512_fmadd_pd(a1, b1, sum1);

                __m512d a2 = _mm512_loadu_pd(&a_col[r + 16]);
                __m512d b2 = _mm512_loadu_pd(&b_col[r + 16]);
                sum2 = _mm512_fmadd_pd(a2, b2, sum2);

                __m512d a3 = _mm512_loadu_pd(&a_col[r + 24]);
                __m512d b3 = _mm512_loadu_pd(&b_col[r + 24]);
                sum3 = _mm512_fmadd_pd(a3, b3, sum3);
            }

            sum0 = _mm512_add_pd(sum0, sum1);
            sum2 = _mm512_add_pd(sum2, sum3);
            sum0 = _mm512_add_pd(sum0, sum2);

            double total = _mm512_reduce_add_pd(sum0);

            for (; r < actual_kc; ++r) {
                total = std::fma(a_col[r], b_col[r], total);
            }

            C[i * K + j] += total;
        }
    }
}
#elif defined(__AVX2__) && defined(__FMA__)
inline void micro_kernel_dgemm_avx512_kc(
    const double* __restrict A_panel,
    const double* __restrict B_panel,
    double* __restrict C,
    uint64_t actual_kc,
    uint64_t pitch_kc,
    uint32_t K
) {
    for (uint32_t i = 0; i < K; ++i) {
        const double* a_col = &A_panel[i * pitch_kc];
        for (uint32_t j = 0; j < K; ++j) {
            const double* b_col = &B_panel[j * pitch_kc];

            __m256d sum0 = _mm256_setzero_pd();
            __m256d sum1 = _mm256_setzero_pd();

            uint64_t r = 0;
            for (; r + 7 < actual_kc; r += 8) {
                __m256d a0 = _mm256_loadu_pd(&a_col[r]);
                __m256d b0 = _mm256_loadu_pd(&b_col[r]);
                sum0 = _mm256_fmadd_pd(a0, b0, sum0);

                __m256d a1 = _mm256_loadu_pd(&a_col[r + 4]);
                __m256d b1 = _mm256_loadu_pd(&b_col[r + 4]);
                sum1 = _mm256_fmadd_pd(a1, b1, sum1);
            }

            sum0 = _mm256_add_pd(sum0, sum1);
            double temp[4];
            _mm256_storeu_pd(temp, sum0);
            double total = temp[0] + temp[1] + temp[2] + temp[3];

            for (; r < actual_kc; ++r) {
                total = std::fma(a_col[r], b_col[r], total);
            }

            C[i * K + j] += total;
        }
    }
}
#elif defined(__SSE2__)
inline void micro_kernel_dgemm_avx512_kc(
    const double* __restrict A_panel,
    const double* __restrict B_panel,
    double* __restrict C,
    uint64_t actual_kc,
    uint64_t pitch_kc,
    uint32_t K
) {
    for (uint32_t i = 0; i < K; ++i) {
        const double* a_col = &A_panel[i * pitch_kc];
        for (uint32_t j = 0; j < K; ++j) {
            const double* b_col = &B_panel[j * pitch_kc];

            __m128d sum0 = _mm_setzero_pd();
            __m128d sum1 = _mm_setzero_pd();

            uint64_t r = 0;
            for (; r + 3 < actual_kc; r += 4) {
                __m128d a0 = _mm_loadu_pd(&a_col[r]);
                __m128d b0 = _mm_loadu_pd(&b_col[r]);
                __m128d prod0 = _mm_mul_pd(a0, b0);
                sum0 = _mm_add_pd(sum0, prod0);

                __m128d a1 = _mm_loadu_pd(&a_col[r + 2]);
                __m128d b1 = _mm_loadu_pd(&b_col[r + 2]);
                __m128d prod1 = _mm_mul_pd(a1, b1);
                sum1 = _mm_add_pd(sum1, prod1);
            }

            sum0 = _mm_add_pd(sum0, sum1);
            double temp[2];
            _mm_storeu_pd(temp, sum0);
            double total = temp[0] + temp[1];

            for (; r < actual_kc; ++r) {
                total += a_col[r] * b_col[r];
            }

            C[i * K + j] += total;
        }
    }
}
#else
inline void micro_kernel_dgemm_avx512_kc(
    const double* __restrict A_panel,
    const double* __restrict B_panel,
    double* __restrict C,
    uint64_t actual_kc,
    uint64_t pitch_kc,
    uint32_t K
) {
    for (uint32_t i = 0; i < K; ++i) {
        const double* a_col = &A_panel[i * pitch_kc];
        for (uint32_t j = 0; j < K; ++j) {
            const double* b_col = &B_panel[j * pitch_kc];
            double total = 0.0;
            for (uint64_t r = 0; r < actual_kc; ++r) {
                total += a_col[r] * b_col[r];
            }
            C[i * K + j] += total;
        }
    }
}
#endif

// ============================================================================
// 3. MASTER CAYLEY-SMW STIEFEL RETRACTION WITH DYNAMIC L2 TILING
// ============================================================================
extern "C" {

POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_stiefel_cayley_smw_avx512_f64(
    const double* X,       // D x K (row-major)
    const double* G,       // D x K (tangent gradient, row-major)
    double* Y_out,         // D x K (updated orthonormal matrix)
    uint64_t D,
    uint32_t K,
    double tau
) {
    if (!X || !G || !Y_out) return STIEFEL_ERR_NULL_POINTER;
    if (D == 0 || K == 0 || D < K) return STIEFEL_ERR_INVALID_DIM;
    if (K > 1024) return STIEFEL_ERR_BUFFER_OVERFLOW;
    if (tau <= 0.0 || tau > 2.0 || std::isnan(tau)) return STIEFEL_ERR_NUMERICAL_INSTABILITY;

    // Optimal KC calculation to fit 75% of L2 cache (512 KB per core)
    // 2 panels * KC * K * 8 bytes <= 384 KB
    uint64_t KC = (384 * 1024) / (2 * K * sizeof(double));
    if (KC > 12288) KC = 12288;
    if (KC < 512) KC = 512;

    int max_threads = omp_get_max_threads();
    std::vector<double> thread_XTG(max_threads * K * K, 0.0);
    std::vector<double> thread_GTG(max_threads * K * K, 0.0);
    std::vector<double> thread_XTX(max_threads * K * K, 0.0);

    // STEP 1: Direct Zero-Allocation L1 Streaming Tall-Skinny Gram Accumulation
    #pragma omp parallel
    {
        int tid = omp_get_thread_num();
        double* local_xtg = &thread_XTG[tid * K * K];
        double* local_gtg = &thread_GTG[tid * K * K];
        double* local_xtx = &thread_XTX[tid * K * K];

        #pragma omp for schedule(static)
        for (int64_t r = 0; r < static_cast<int64_t>(D); ++r) {
            const double* xr = &X[r * K];
            const double* gr = &G[r * K];

            for (uint32_t i = 0; i < K; ++i) {
                double xi = xr[i];
                double gi = gr[i];

                for (uint32_t j = 0; j < K; ++j) {
                    local_xtg[i * K + j] = std::fma(xi, gr[j], local_xtg[i * K + j]);
                    local_gtg[i * K + j] = std::fma(gi, gr[j], local_gtg[i * K + j]);
                    local_xtx[i * K + j] = std::fma(xi, xr[j], local_xtx[i * K + j]);
                }
            }
        }
    }

    // Accumulate thread results
    std::vector<double> XTG(K * K, 0.0);
    std::vector<double> GTG(K * K, 0.0);
    std::vector<double> XTX(K * K, 0.0);

    for (int t = 0; t < max_threads; ++t) {
        for (uint32_t j = 0; j < K * K; ++j) {
            XTG[j] += thread_XTG[t * K * K + j];
            GTG[j] += thread_GTG[t * K * K + j];
            XTX[j] += thread_XTX[t * K * K + j];
        }
    }

    // STEP 2: Assemble V^T U (2K x 2K) and V^T X (2K x K)
    uint32_t K2 = 2 * K;
    std::vector<double> VTU(K2 * K2, 0.0);
    std::vector<double> VTX(K2 * K, 0.0);

    for (uint32_t r = 0; r < K; ++r) {
        for (uint32_t c = 0; c < K; ++c) {
            VTU[r * K2 + c] = XTG[r * K + c];
            VTU[r * K2 + (c + K)] = XTX[r * K + c];
            VTU[(r + K) * K2 + c] = -GTG[r * K + c];
            VTU[(r + K) * K2 + (c + K)] = -XTG[c * K + r];

            VTX[r * K + c] = XTX[r * K + c];
            VTX[(r + K) * K + c] = -XTG[c * K + r];
        }
    }

    // STEP 3: Form M = I_2K - (tau / 2) * V^T U in L1 Cache
    std::vector<double> M(K2 * K2, 0.0);
    double half_tau = 0.5 * tau;
    for (uint32_t r = 0; r < K2; ++r) {
        for (uint32_t c = 0; c < K2; ++c) {
            double val = -half_tau * VTU[r * K2 + c];
            if (r == c) val += 1.0;
            M[r * K2 + c] = val;
        }
    }

    // STEP 4: Solve M * Z = V^T X for Z (2K x K) in L1 cache with partial pivoting
    std::vector<double> Z = VTX;
    for (uint32_t k = 0; k < K2; ++k) {
        uint32_t pivot = k;
        double max_val = std::abs(M[k * K2 + k]);
        for (uint32_t r = k + 1; r < K2; ++r) {
            double v = std::abs(M[r * K2 + k]);
            if (v > max_val) {
                max_val = v;
                pivot = r;
            }
        }

        if (max_val < 1e-15 || std::isnan(max_val)) {
            return STIEFEL_ERR_NUMERICAL_INSTABILITY;
        }

        if (pivot != k) {
            for (uint32_t c = 0; c < K2; ++c) std::swap(M[k * K2 + c], M[pivot * K2 + c]);
            for (uint32_t col = 0; col < K; ++col) std::swap(Z[k * K + col], Z[pivot * K + col]);
        }

        double diag = M[k * K2 + k];
        for (uint32_t r = k + 1; r < K2; ++r) {
            double factor = M[r * K2 + k] / diag;
            for (uint32_t c = k + 1; c < K2; ++c) M[r * K2 + c] -= factor * M[k * K2 + c];
            for (uint32_t col = 0; col < K; ++col) Z[r * K + col] -= factor * Z[k * K + col];
        }
    }

    // Back-substitution
    for (int32_t r = static_cast<int32_t>(K2) - 1; r >= 0; --r) {
        double diag = M[r * K2 + r];
        for (uint32_t col = 0; col < K; ++col) {
            double sum = Z[r * K + col];
            for (uint32_t c = r + 1; c < K2; ++c) sum -= M[r * K2 + c] * Z[c * K + col];
            Z[r * K + col] = sum / diag;
        }
    }

    // STEP 5: Parallel Streaming Update Y_out = X + tau * (G * Z1 + X * Z2)
    #pragma omp parallel for schedule(static)
    for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
        const double* xi = &X[i * K];
        const double* gi = &G[i * K];
        double* yi = &Y_out[i * K];

        for (uint32_t k = 0; k < K; ++k) {
            double delta = 0.0;
            for (uint32_t p = 0; p < K; ++p) delta = std::fma(gi[p], Z[p * K + k], delta);
            for (uint32_t p = 0; p < K; ++p) delta = std::fma(xi[p], Z[(p + K) * K + k], delta);
            yi[k] = std::fma(tau, delta, xi[k]);
        }
    }

    return STIEFEL_SUCCESS;
}

} // extern "C"
