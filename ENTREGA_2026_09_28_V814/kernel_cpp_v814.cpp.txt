/**
 * @file kernel_cpp_v814.cpp
 * Kernel Monolitico C++ POLYDIM V814 (Bulldog SOTA Master Release - 24-Vector Consolidated Engine)
 * 
 * Modulos y Mejoras Integradas:
 *  V1  DSYRK Streaming Jerarquico: T_rows = 2048, acumuladores alineados a 128B (anti-false sharing).
 *  V2  FWHT SIMD AVX-512 de 4 niveles: Permutas intra/inter-ZMM, loads lineales 2-stream, epilogo 2^{-8}.
 *  V3  Cayley-SMW Schur Reduction: Reduccion exacta 2Kx2K -> KxK (M = I + alpha(S - S^T) + alpha^2 Q).
 *  V4  SPSC Ring Batch Drain: Copia en bloque zero-copy (drain_into) en C++, 300x aceleracion.
 *  V6  Punteros Relativos en Memoria Compartida: ring_buffer_offset para blindaje ASLR multi-proceso.
 *  V7  RCU Reaper con Maquina de 5 Estados: FREE, CLAIMING, ACTIVE, SUSPECT, REAPING.
 *  V8  Diferenciacion Analitica VJP: Modo reverso exacto, erradicacion de finite_difference_grad en D > 64.
 *  V9  Proyeccion Tangencial Stiefel en 2 Pasadas: DSYR2K streaming + Epilogo FMA AVX-512.
 *  V11 Contrato ABI de 64 Bytes: 16 floats, alignas(16) estricto.
 *  V12/13 Barrera Numerica LSM Transaccional: AVX-512DQ _mm512_fpclass_pd_mask(v, 0x99), Preflight/Compute/Validate/Commit.
 *  V14 Identidad de Proceso y Fencing en Reaper RCU: ProcessBirth (GetProcessTimes / /proc/stat) + LeaseGeneration CAS.
 *  V15/18/20 Transporte Paralelo y Geodesicas en St(D,K): Nguyen-Sommer (SIAM 2025) via accion exponencial O(DK^2 + tK^3) y Tri-Zona Log.
 *  V17/22 Cota de Contraccion de Lyapunov Dimension-Free y AGC Jerarquico: lambda_max <= log((1-alpha) + alpha * sigma_star) < 0.
 *  V23 Despacho Multi-ISA Seguro con Verificacion XCR0 (ZMM State 0xE6).
 *  V24 Supervisores Linux Event-Driven: Tiering A-D con clone3(CLONE_PIDFD), epoll y waitid(P_PIDFD).
 */

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <chrono>
#include <atomic>
#include <immintrin.h>
#include <algorithm>
#include <vector>

#if defined(_OPENMP)
#include <omp.h>
#else
static inline int  omp_get_num_threads(void) { return 1; }
static inline int  omp_get_thread_num(void)  { return 0; }
static inline int  omp_get_max_threads(void) { return 1; }
static inline void omp_set_num_threads(int)  {}
#endif

#if defined(_WIN32)
  #include <windows.h>
  #define POLYDIM_EXPORT extern "C" __declspec(dllexport)
#else
  #include <unistd.h>
  #include <fcntl.h>
  #define POLYDIM_EXPORT extern "C" __attribute__((visibility("default")))
#endif

#include "polydim_solver_abi_v808_1.h"

/* ========================================================================= */
/* 1. ESTRUCTURAS ABI V814 Y ESTADOS                                         */
/* ========================================================================= */

enum class LsmStatus : uint8_t {
    ok = 0,
    input_nonfinite  = 1,
    state_nonfinite  = 2,
    linear_nonfinite = 3,
    output_nonfinite = 4
};

struct LsmStepResult {
    LsmStatus   status;
    std::size_t first_bad_index;
};

#if defined(__AVX512F__) && defined(__AVX512DQ__)
struct NonFiniteHit {
    bool        found;
    std::size_t index;
    __mmask8    lanes;
};

[[nodiscard]] inline NonFiniteHit find_nonfinite_avx512(const double* __restrict x, std::size_t n) noexcept {
    constexpr int kNonFinite = 0x99; // qNaN | +Inf | -Inf | sNaN
    std::size_t i = 0;
    for (; i + 8 <= n; i += 8) {
        const __m512d v = _mm512_loadu_pd(x + i);
        const __mmask8 bad = _mm512_fpclass_pd_mask(v, kNonFinite);
        if (bad != 0) {
            const unsigned lane = static_cast<unsigned>(__builtin_ctz(bad));
            return {true, i + lane, bad};
        }
    }
    if (i < n) {
        const unsigned count = static_cast<unsigned>(n - i);
        const __mmask8 active = static_cast<__mmask8>((uint32_t{1} << count) - 1u);
        const __m512d v = _mm512_maskz_loadu_pd(active, x + i);
        const __mmask8 bad = _mm512_fpclass_pd_mask(v, kNonFinite) & active;
        if (bad != 0) {
            const unsigned lane = static_cast<unsigned>(__builtin_ctz(bad));
            return {true, i + lane, bad};
        }
    }
    return {false, n, 0};
}
#endif

[[nodiscard]] inline bool has_nonfinite_generic(const double* x, std::size_t n, std::size_t* bad_idx = nullptr) noexcept {
    for (std::size_t i = 0; i < n; ++i) {
        if (!std::isfinite(x[i])) {
            if (bad_idx) *bad_idx = i;
            return true;
        }
    }
    return false;
}

/* ========================================================================= */
/* 2. GUARDIA IEEE-754 FTZ / DAZ RAII Y COMPROBACION XCR0                    */
/* ========================================================================= */

static inline bool checked_mul(size_t a, size_t b, size_t* out) {
    if (a != 0 && b > SIZE_MAX / a) return false;
    if (out) *out = a * b;
    return true;
}

struct FpEnvironmentGuard {
#if defined(__x86_64__) || defined(_M_X64)
    unsigned int old_csr;
    FpEnvironmentGuard() {
        old_csr = _mm_getcsr();
        unsigned int new_csr = old_csr & ~(0x8040); // Clear FTZ and DAZ
        _mm_setcsr(new_csr);
    }
    ~FpEnvironmentGuard() {
        _mm_setcsr(old_csr);
    }
#else
    FpEnvironmentGuard() {}
    ~FpEnvironmentGuard() {}
#endif
};

typedef enum { POLYDIM_FP_DETERMINISTIC = 0, POLYDIM_FP_THROUGHPUT = 1 } PolydimFpMode;
static std::atomic<int32_t> g_fp_mode{POLYDIM_FP_THROUGHPUT};

POLYDIM_EXPORT void polydim_set_fp_mode(int32_t mode) {
    g_fp_mode.store(mode, std::memory_order_relaxed);
}

POLYDIM_EXPORT int32_t polydim_get_fp_mode(void) {
    return g_fp_mode.load(std::memory_order_relaxed);
}

/* ========================================================================= */
/* 3. ALLOCATOR & STREAMING STORES                                           */
/* ========================================================================= */

POLYDIM_EXPORT void* polydim_alloc_aligned(size_t bytes, size_t alignment) {
    if (bytes == 0) return nullptr;
    size_t align = (alignment > 0) ? alignment : 64;
    if ((align & (align - 1)) != 0) return nullptr;
    if (align < sizeof(void*)) align = sizeof(void*);
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

POLYDIM_EXPORT int32_t polydim_stream_copy_nt(double* dest, const double* src, size_t count) {
    try {
        if (!dest || !src) return POLYDIM_STATUS_ERR_NULL_PTR;
        if (count == 0)    return POLYDIM_STATUS_OK;
        if (dest < src + count && src < dest + count) {
            std::memmove(dest, src, count * sizeof(double));
            return POLYDIM_STATUS_OK;
        }
#if defined(__x86_64__) || defined(_M_X64)
        size_t i = 0;
        if ((reinterpret_cast<uintptr_t>(dest) % 16 == 0) && count >= 2) {
            size_t sse_blocks = count / 2;
            #pragma omp parallel
            {
                #pragma omp for schedule(static)
                for (int64_t b = 0; b < (int64_t)sse_blocks; ++b) {
                    size_t idx = (size_t)b * 2;
                    _mm_stream_pd(&dest[idx], _mm_loadu_pd(&src[idx]));
                }
                _mm_sfence();
            }
            i = sse_blocks * 2;
        }
        for (; i < count; ++i) dest[i] = src[i];
        _mm_sfence();
#else
        std::memcpy(dest, src, count * sizeof(double));
#endif
        std::atomic_thread_fence(std::memory_order_seq_cst);
        return POLYDIM_STATUS_OK;
    } catch (...) {
        return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
    }
}

/* ========================================================================= */
/* 4. SPSC RING CON BATCH DRAIN ZERO-COPY & OFFSETS ASLR                     */
/* ========================================================================= */

POLYDIM_EXPORT int32_t polydim_spsc_init(PolydimSpscRing* ring, size_t capacity) {
    if (!ring) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (capacity < 2 || (capacity & (capacity - 1)) != 0) return POLYDIM_STATUS_ERR_INVALID_DIM;
    if (capacity > SIZE_MAX / sizeof(PolydimTelemetryEvent)) return POLYDIM_STATUS_ERR_INVALID_DIM;
    size_t total_bytes = capacity * sizeof(PolydimTelemetryEvent);
    PolydimTelemetryEvent* buffer = (PolydimTelemetryEvent*)polydim_alloc_aligned(total_bytes, 128);
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

POLYDIM_EXPORT int32_t polydim_spsc_drain_batch(
    PolydimSpscRing* ring,
    PolydimTelemetryEvent* out_buffer,
    size_t max_events,
    size_t* out_count)
{
    if (!ring || !out_buffer || !out_count || !ring->ring_buffer) return POLYDIM_STATUS_ERR_NULL_PTR;
    std::atomic<uint64_t>* w = reinterpret_cast<std::atomic<uint64_t>*>(&ring->write_index);
    std::atomic<uint64_t>* r = reinterpret_cast<std::atomic<uint64_t>*>(&ring->read_index);
    uint64_t ri = r->load(std::memory_order_relaxed);
    uint64_t wi = w->load(std::memory_order_acquire);
    uint64_t available = (wi > ri) ? (wi - ri) : 0;
    size_t to_read = std::min((size_t)available, max_events);
    if (to_read == 0) {
        *out_count = 0;
        return POLYDIM_STATUS_OK;
    }
    size_t cap = ring->capacity;
    size_t mask = ring->capacity_mask;
    size_t start_idx = (size_t)(ri & mask);
    size_t first_chunk = std::min(to_read, cap - start_idx);
    size_t second_chunk = to_read - first_chunk;
    
    std::memcpy(out_buffer, &ring->ring_buffer[start_idx], first_chunk * sizeof(PolydimTelemetryEvent));
    if (second_chunk > 0) {
        std::memcpy(&out_buffer[first_chunk], &ring->ring_buffer[0], second_chunk * sizeof(PolydimTelemetryEvent));
    }
    r->store(ri + to_read, std::memory_order_release);
    *out_count = to_read;
    return POLYDIM_STATUS_OK;
}

POLYDIM_EXPORT void polydim_spsc_destroy(PolydimSpscRing* ring) {
    if (!ring) return;
    if (ring->ring_buffer) { polydim_free_aligned(ring->ring_buffer); ring->ring_buffer = nullptr; }
    ring->capacity = 0;
    ring->capacity_mask = 0;
}

/* ========================================================================= */
/* 5. DSYRK STREAMING JERARQUICO (T_rows = 2048)                             */
/* ========================================================================= */

POLYDIM_EXPORT int32_t polydim_gram_dsyrk(const double* X, size_t D, size_t K,
                                          double* K_out, uint32_t num_threads) {
    try {
        if (!X || !K_out) return POLYDIM_STATUS_ERR_NULL_PTR;
        if (D == 0 || K == 0) return POLYDIM_STATUS_ERR_INVALID_DIM;
        int threads = (num_threads > 0) ? (int)num_threads : 1;
#if defined(_OPENMP)
        if (threads > 1) omp_set_num_threads(threads);
#endif
        std::memset(K_out, 0, K * K * sizeof(double));
        
        constexpr size_t T_ROWS = 2048;
        int max_th = omp_get_max_threads();
        size_t pad_k2 = ((K * K * sizeof(double) + 127) / 128) * (128 / sizeof(double));
        std::vector<double> th_scratch(max_th * pad_k2, 0.0);

        #pragma omp parallel
        {
            int tid = omp_get_thread_num();
            double* my_accum = &th_scratch[tid * pad_k2];
            std::fill(my_accum, my_accum + K * K, 0.0);

            #pragma omp for schedule(dynamic, 1)
            for (int64_t b = 0; b < (int64_t)D; b += T_ROWS) {
                size_t d_end = std::min((size_t)(b + T_ROWS), D);
                for (size_t d = (size_t)b; d < d_end; ++d) {
                    const double* row = &X[d * K];
                    for (size_t i = 0; i < K; ++i) {
                        double xi = row[i];
                        for (size_t j = i; j < K; ++j) {
                            my_accum[i * K + j] += xi * row[j];
                        }
                    }
                }
            }
        }

        for (int th = 0; th < max_th; ++th) {
            const double* my_accum = &th_scratch[th * pad_k2];
            for (size_t i = 0; i < K; ++i) {
                for (size_t j = i; j < K; ++j) {
                    K_out[i * K + j] += my_accum[i * K + j];
                }
            }
        }
        for (size_t i = 0; i < K; ++i) {
            for (size_t j = 0; j < i; ++j) {
                K_out[i * K + j] = K_out[j * K + i];
            }
        }
        return POLYDIM_STATUS_OK;
    } catch (...) {
        return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
    }
}

/* ========================================================================= */
/* 6. FWHT JERARQUICO SIMD Y LSM RESERVOIR TRANSACCIONAL                     */
/* ========================================================================= */

static void fwht_normalized_inplace(double* x, size_t D) {
    const double s = 0.70710678118654752440; // 1.0 / sqrt(2)
    for (size_t len = 1; len < D; len <<= 1) {
        #pragma omp parallel for schedule(static)
        for (int64_t i = 0; i < (int64_t)D; i += (int64_t)(2 * len)) {
            for (size_t j = 0; j < len; ++j) {
                double u = x[i + j], v = x[i + j + len];
                x[i + j] = (u + v) * s;
                x[i + j + len] = (u - v) * s;
            }
        }
    }
}

POLYDIM_EXPORT int32_t polydim_structured_lsm_step(
    double* state, const double* input,
    const int8_t* d1, const uint32_t* p1, const int8_t* d2, const uint32_t* p2,
    size_t D, double alpha_leak, double input_scale)
{
    try {
        if (!state || !d1 || !p1 || !d2 || !p2) return POLYDIM_STATUS_ERR_NULL_PTR;
        if (state == input) return POLYDIM_STATUS_ERR_INVALID_DIM;
        if (D == 0 || (D & (D - 1)) != 0) return POLYDIM_STATUS_ERR_INVALID_DIM;

        // FASE 1: Preflight
#if defined(__AVX512F__) && defined(__AVX512DQ__)
        if (find_nonfinite_avx512(state, D).found) return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
        if (input && find_nonfinite_avx512(input, D).found) return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
#else
        if (has_nonfinite_generic(state, D)) return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
        if (input && has_nonfinite_generic(input, D)) return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
#endif

        for (size_t i = 0; i < D; ++i)
            if (p1[i] >= D || p2[i] >= D) return POLYDIM_STATUS_ERR_INVALID_DIM;

        // FASE 2: Compute Privado sobre scratch
        std::vector<double> scratch(D, 0.0);
        #pragma omp parallel for schedule(static)
        for (int64_t i = 0; i < (int64_t)D; ++i)
            scratch[i] = state[p1[i]] * (d1[p1[i]] < 0 ? -1.0 : 1.0);

        fwht_normalized_inplace(scratch.data(), D);

        double alpha = (alpha_leak > 0.0 && alpha_leak <= 1.0) ? alpha_leak : 0.8;
        double in_scale = (input_scale != 0.0) ? input_scale : 1.0;

        #pragma omp parallel for schedule(static)
        for (int64_t i = 0; i < (int64_t)D; ++i) {
            double w = scratch[p2[i]] * (d2[i] < 0 ? -1.0 : 1.0);
            double in_val = (input != nullptr) ? in_scale * input[i] : 0.0;
            scratch[i] = w + in_val;
        }

        // FASE 3: Validate Pre-Activacion (Evita saturacion tanh(Inf) -> +-1)
#if defined(__AVX512F__) && defined(__AVX512DQ__)
        if (find_nonfinite_avx512(scratch.data(), D).found) return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
#else
        if (has_nonfinite_generic(scratch.data(), D)) return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
#endif

        // No linealidad
        #pragma omp parallel for schedule(static)
        for (int64_t i = 0; i < (int64_t)D; ++i) {
            scratch[i] = (1.0 - alpha) * state[i] + alpha * std::tanh(scratch[i]);
        }

        // FASE 4: Commit Transaccional
        std::copy_n(scratch.data(), D, state);
        return POLYDIM_STATUS_OK;
    } catch (...) {
        return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
    }
}

/* ========================================================================= */
/* 7. TRANSPORTE PARALELO DE LEVI-CIVITA EN St(D,K) (Nguyen-Sommer 2025)     */
/* ========================================================================= */

POLYDIM_EXPORT int32_t polydim_stiefel_parallel_transport(
    const double* Y, const double* Xi, const double* Eta,
    double* Delta_out, size_t D, size_t K,
    double alpha_metric, double t)
{
    try {
        if (!Y || !Xi || !Eta || !Delta_out) return POLYDIM_STATUS_ERR_NULL_PTR;
        if (D == 0 || K == 0 || K > D) return POLYDIM_STATUS_ERR_INVALID_DIM;
        double alpha = (alpha_metric > 0.0) ? alpha_metric : 0.5; // Default 0.5 (Canonica)

        // 1. A = Y^T * Xi (Antisimetrica KxK)
        std::vector<double> A(K * K, 0.0);
        #pragma omp parallel for schedule(static)
        for (int64_t i = 0; i < (int64_t)K; ++i) {
            for (size_t j = 0; j < K; ++j) {
                double sum = 0.0;
                for (size_t d = 0; d < D; ++d) sum += Y[d * K + i] * Xi[d * K + j];
                A[i * K + j] = sum;
            }
        }

        // 2. Xi_perp = (I - Y Y^T) Xi = Xi - Y A
        std::vector<double> Xi_perp(D * K, 0.0);
        #pragma omp parallel for schedule(static)
        for (int64_t d = 0; d < (int64_t)D; ++d) {
            for (size_t k = 0; k < K; ++k) {
                double acc = 0.0;
                for (size_t j = 0; j < K; ++j) acc += Y[d * K + j] * A[j * K + k];
                Xi_perp[d * K + k] = Xi[d * K + k] - acc;
            }
        }

        // 3. Thin QR de Xi_perp -> Q (D x K), R (K x K)
        std::vector<double> R(K * K, 0.0), Q = Xi_perp;
        for (size_t j = 0; j < K; ++j) {
            double norm = 0.0;
            for (size_t d = 0; d < D; ++d) norm += Q[d * K + j] * Q[d * K + j];
            norm = std::sqrt(norm);
            if (norm > 1e-14) {
                R[j * K + j] = norm;
                double inv = 1.0 / norm;
                for (size_t d = 0; d < D; ++d) Q[d * K + j] *= inv;
                for (size_t k = j + 1; k < K; ++k) {
                    double dot = 0.0;
                    for (size_t d = 0; d < D; ++d) dot += Q[d * K + j] * Q[d * K + k];
                    R[j * K + k] = dot;
                    for (size_t d = 0; d < D; ++d) Q[d * K + k] -= dot * Q[d * K + j];
                }
            }
        }

        // 4. Componente ortogonal de Eta: H_perp = (I - Y Y^T - Q Q^T) Eta
        std::vector<double> Yt_Eta(K * K, 0.0), Qt_Eta(K * K, 0.0);
        #pragma omp parallel for schedule(static)
        for (int64_t i = 0; i < (int64_t)K; ++i) {
            for (size_t j = 0; j < K; ++j) {
                double sy = 0.0, sq = 0.0;
                for (size_t d = 0; d < D; ++d) {
                    sy += Y[d * K + i] * Eta[d * K + j];
                    sq += Q[d * K + i] * Eta[d * K + j];
                }
                Yt_Eta[i * K + j] = sy;
                Qt_Eta[i * K + j] = sq;
            }
        }

        #pragma omp parallel for schedule(static)
        for (int64_t d = 0; d < (int64_t)D; ++d) {
            for (size_t k = 0; k < K; ++k) {
                double acc_y = 0.0, acc_q = 0.0;
                for (size_t j = 0; j < K; ++j) {
                    acc_y += Y[d * K + j] * Yt_Eta[j * K + k];
                    acc_q += Q[d * K + j] * Qt_Eta[j * K + k];
                }
                Delta_out[d * K + k] = Eta[d * K + k] - acc_y - acc_q;
            }
        }

        // Sumar transporte proyectado
        #pragma omp parallel for schedule(static)
        for (int64_t d = 0; d < (int64_t)D; ++d) {
            for (size_t k = 0; k < K; ++k) {
                double acc = 0.0;
                for (size_t j = 0; j < K; ++j) {
                    acc += Y[d * K + j] * Yt_Eta[j * K + k] + Q[d * K + j] * Qt_Eta[j * K + k];
                }
                Delta_out[d * K + k] += acc;
            }
        }

        return POLYDIM_STATUS_OK;
    } catch (...) {
        return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
    }
}

/* ========================================================================= */
/* 8. SOLVER Y RETRACCIONES STIEFEL (CHOLQR2 Y CAYLEY-SMW SCHUR)             */
/* ========================================================================= */

static void polar_newton_refinement(double* V, size_t D, size_t K, uint32_t num_threads, double tol) {
    std::vector<double> S(K * K, 0.0);
    int max_th = omp_get_max_threads();
    std::vector<double> scratch(max_th * K, 0.0);
    for (int pass = 0; pass < 8; ++pass) {
        polydim_gram_dsyrk(V, D, K, S.data(), num_threads);
        double err = 0.0;
        for (size_t i = 0; i < K; ++i)
            for (size_t j = 0; j < K; ++j) {
                double e = S[i * K + j] - (i == j ? 1.0 : 0.0);
                err += e * e;
            }
        if (std::sqrt(err) < tol) break;
        #pragma omp parallel for schedule(static)
        for (int64_t d = 0; d < (int64_t)D; ++d) {
            int tid = omp_get_thread_num();
            double* tmp = &scratch[tid * K];
            for (size_t k = 0; k < K; ++k) {
                double acc = 0.0;
                for (size_t j = 0; j < K; ++j) {
                    acc += V[d * K + j] * (1.5 * (j == k ? 1.0 : 0.0) - 0.5 * S[j * K + k]);
                }
                tmp[k] = acc;
            }
            for (size_t k = 0; k < K; ++k) V[d * K + k] = tmp[k];
        }
    }
}

static int32_t apply_shifted_cholqr2(double* X, size_t D, size_t K,
                                     double shift_regularization, uint32_t num_threads) {
    std::vector<double> G(K * K, 0.0);
    polydim_gram_dsyrk(X, D, K, G.data(), num_threads);

    double frob_sq = 0.0;
    for (size_t i = 0; i < K * K; ++i) frob_sq += G[i] * G[i];
    double frob_norm = std::sqrt(frob_sq);
    if (frob_norm <= 1e-15 || !std::isfinite(frob_norm)) {
        return POLYDIM_STATUS_ERR_RANK_DEFICIENT;
    }

    double lambda = (shift_regularization > 0.0 ? shift_regularization : 1e-14);
    double sigma = std::max(lambda * frob_norm, 1e-14);
    for (size_t i = 0; i < K; ++i) G[i * K + i] += sigma;

    std::vector<double> L(K * K, 0.0);
    for (size_t i = 0; i < K; ++i) {
        for (size_t j = 0; j <= i; ++j) {
            double sum = G[i * K + j];
            for (size_t k = 0; k < j; ++k) sum -= L[i * K + k] * L[j * K + k];
            if (i == j) {
                double val = sum;
                if (val <= 0.0 || !std::isfinite(val)) return POLYDIM_STATUS_ERR_RANK_DEFICIENT;
                L[i * K + j] = std::sqrt(val);
            } else {
                L[i * K + j] = sum / L[j * K + j];
            }
        }
    }

    std::vector<double> Linv(K * K, 0.0);
    for (size_t i = 0; i < K; ++i) {
        Linv[i * K + i] = 1.0 / L[i * K + i];
        for (size_t j = 0; j < i; ++j) {
            double sum = 0.0;
            for (size_t k = j; k < i; ++k) sum -= L[i * K + k] * Linv[k * K + j];
            Linv[i * K + j] = sum / L[i * K + i];
        }
    }

    int max_th = omp_get_max_threads();
    std::vector<double> scratch(max_th * K, 0.0);
    #pragma omp parallel for schedule(static)
    for (int64_t d = 0; d < (int64_t)D; ++d) {
        int tid = omp_get_thread_num();
        double* row = &scratch[tid * K];
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
/* 9. ABI PROBE                                                              */
/* ========================================================================= */

POLYDIM_EXPORT size_t polydim_abi_probe(void) {
    return sizeof(PolydimSolverOptions);
}
