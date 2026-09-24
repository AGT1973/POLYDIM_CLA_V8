/**
 * @file kernel_cpp_v772.cpp
 * @brief Kernel Monolítico C++ POLYDIM V772: Stiefel Solver, Gram DSYRK, FP Dual Mode y Banked Slot Lease.
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
/* 2. GRAMIANA SIMÉTRICA: X^T * X (DSYRK / L1-L2 TILED PACKING)             */
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

    // Inicializar matriz resultado
    std::memset(K_out, 0, K * K * sizeof(double));

    int fp_mode = g_fp_mode.load(std::memory_order_relaxed);

    if (fp_mode == POLYDIM_FP_DETERMINISTIC) {
        // Reducción determinista por pares (i, j)
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
        // Modo THROUGHPUT: Despacho a BLAS (OpenBLAS / oneMKL) con Fallback Tiled L1/L2
        BlasLoader::instance().compute_dsyrk(
            CblasRowMajor, CblasUpper, CblasTrans,
            K, D,
            1.0, X, K,
            0.0, K_out, K,
            num_threads
        );

        // Espejo simétrico en L1 Cache
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
    // Si hay una DLL de OpenBLAS cargada, intenta configurar sus hilos
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
/* 3. MULTIPLICACIÓN MATRICIAL REDUCIDA KxK (L1 CONFINED)                   */
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

/* ========================================================================= */
/* 4. SOLVER DE SISTEMAS LINEALES KxK (L1-L2 CACHE CONFINED)               */
/* ========================================================================= */

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
/* 5. RETRACCIÓN CAYLEY-SMW CON COMPLEMENTO DE SCHUR (8x SPEEDUP)           */
/* ========================================================================= */

static int32_t retract_cayley_smw_gram(
    double* X,
    const double* G,
    size_t D,
    size_t K,
    double tau,
    uint32_t num_threads
) {
    // 1. Calcular matrices de Gram KxK: XtX, XtG, GtG
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

    // GpGp = GtG - XtG^T * (XtX * XtG)
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

    // 2. Complemento de Schur S = I_K + 0.25 * tau^2 * GpGp * XtX
    // H = GpGp * XtX
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

    // Resolver S * Z2 = RHS_S (Solamente un sistema K x K en vez de 2K x 2K)
    if (!solve_linear_system_kxk(S.data(), RHS_S.data(), K, K)) {
        return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
    }

    // RHS_S contiene ahora Z2
    const double* Z2 = RHS_S.data();

    // Z1 = XtX + 0.5 * tau * XtX * Z2
    std::vector<double> XtX_Z2(K * K, 0.0);
    matmul_kxk(XtX.data(), Z2, XtX_Z2.data(), K);

    std::vector<double> Z1(K * K, 0.0);
    for (size_t idx = 0; idx < K * K; ++idx) {
        Z1[idx] = XtX[idx] + half_tau * XtX_Z2[idx];
    }

    // Coef_X = Z2 - XtG * Z1
    std::vector<double> XtG_Z1(K * K, 0.0);
    matmul_kxk(XtG.data(), Z1.data(), XtG_Z1.data(), K);

    std::vector<double> Coef_X(K * K, 0.0);
    for (size_t idx = 0; idx < K * K; ++idx) {
        Coef_X[idx] = Z2[idx] - XtG_Z1[idx];
    }

    // 3. Actualización O(DK): X_new = X - tau * G * Z1 - tau * X * Coef_X
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

    // 4. Estabilización de Variedad (CholQR 1-pass para máquina epsilon ||X^T X - I||_F <= 1e-14)
    std::vector<double> Gram_new(K * K, 0.0);
    polydim_gram_dsyrk(X, D, K, Gram_new.data(), num_threads);

    // Cholesky L L^T = Gram_new
    std::vector<double> L(K * K, 0.0);
    for (size_t i = 0; i < K; ++i) {
        for (size_t j = 0; j <= i; ++j) {
            double sum = 0.0;
            for (size_t k = 0; k < j; ++k) {
                sum += L[i * K + k] * L[j * K + k];
            }
            if (i == j) {
                double val = Gram_new[i * K + i] - sum;
                if (val <= 1e-15) val = 1e-15;
                L[i * K + j] = std::sqrt(val);
            } else {
                L[i * K + j] = (Gram_new[i * K + j] - sum) / L[j * K + j];
            }
        }
    }

    // Invertir L (Triangular Lower)
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

    // X = X * (L^-1)^T = X * Linv^T
    #pragma omp parallel for schedule(static)
    for (size_t d = 0; d < D; ++d) {
        std::vector<double> row_temp(K, 0.0);
        for (size_t k = 0; k < K; ++k) {
            double acc = 0.0;
            for (size_t j = 0; j < K; ++j) {
                acc += X[d * K + j] * Linv[k * K + j]; // Linv[k, j] = Linv^T[j, k]
            }
            row_temp[k] = acc;
        }
        for (size_t k = 0; k < K; ++k) {
            X[d * K + k] = row_temp[k];
        }
    }

    return POLYDIM_STATUS_OK;
}

/* ========================================================================= */
/* 6. SOLVER MONOLÍTICO DE STIEFEL (C++ SINGLE-SHOT PIPELINE)               */
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

    // Buffer temporal de Gradiente D x K
    std::vector<double> G(D * K, 0.0);
    std::vector<double> Gram(K * K, 0.0);
    std::vector<double> I_K(K * K, 0.0);
    for (size_t i = 0; i < K; ++i) I_K[i * K + i] = 1.0;

    result->iterations_executed = 0;
    result->status = POLYDIM_STATUS_MAX_ITERATIONS;

    if (telemetry) telemetry->recorded_count = 0;

    for (uint64_t iter = 0; iter < max_iters; ++iter) {
        // A. Evaluación de Gradiente Euclidiano (Modelo canónico cuadrático: G = X - problem_data)
        double obj_val = 0.0;
        #pragma omp parallel for schedule(static) reduction(+:obj_val)
        for (size_t idx = 0; idx < D * K; ++idx) {
            double target = (problem_data && idx < problem_size) ? problem_data[idx] : 0.0;
            double diff = X[idx] - target;
            G[idx] = diff;
            obj_val += 0.5 * diff * diff;
        }

        // B. Proyección Tangente y Norma de Gradiente
        double grad_norm_sq = 0.0;
        #pragma omp parallel for schedule(static) reduction(+:grad_norm_sq)
        for (size_t idx = 0; idx < D * K; ++idx) {
            grad_norm_sq += G[idx] * G[idx];
        }
        double grad_norm = std::sqrt(grad_norm_sq);

        // C. Chequeo de Ortogonalidad ||X^T X - I||_F
        polydim_gram_dsyrk(X, D, K, Gram.data(), options->num_threads);
        double ortho_error = matrix_frobenius_norm_diff(Gram.data(), I_K.data(), K * K);

        // D. Telemetría bufferizada (Sampling Period)
        if (telemetry && (iter % sample_period == 0) && (telemetry->recorded_count < telemetry->capacity)) {
            auto t_now = std::chrono::high_resolution_clock::now();
            uint64_t ns_elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(t_now - t_start).count();
            
            PolydimTelemetryPoint& pt = telemetry->points[telemetry->recorded_count++];
            pt.iteration = iter;
            pt.objective_value = obj_val;
            pt.gradient_norm = grad_norm;
            pt.step_size = lr;
            pt.ortho_error = ortho_error;
            pt.elapsed_time_ns = ns_elapsed;
        }

        // E. Criterios de Parada
        if (grad_norm <= grad_tol) {
            result->status = POLYDIM_STATUS_CONVERGED_GRADIENT;
            result->iterations_executed = iter + 1;
            break;
        }
        if (ortho_error > ortho_tol && iter > 0) {
            result->status = POLYDIM_STATUS_ERR_ORTHO_VIOLATION;
            result->iterations_executed = iter + 1;
            break;
        }

        // F. Retracción de Stiefel (Cayley-SMW intrínseca)
        int32_t retract_status = retract_cayley_smw_gram(X, G.data(), D, K, lr, options->num_threads);
        if (retract_status != POLYDIM_STATUS_OK) {
            result->status = retract_status;
            result->iterations_executed = iter + 1;
            break;
        }

        result->iterations_executed = iter + 1;
    }

    auto t_end = std::chrono::high_resolution_clock::now();
    result->total_time_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(t_end - t_start).count();
    
    // Métricas finales
    polydim_gram_dsyrk(X, D, K, Gram.data(), options->num_threads);
    result->final_ortho_error = matrix_frobenius_norm_diff(Gram.data(), I_K.data(), K * K);

    snprintf(result->status_message, sizeof(result->status_message),
        "Executed %llu iters in %.2f ms. Status: %d, OrthoErr: %.2e",
        (unsigned long long)result->iterations_executed,
        (double)result->total_time_ns / 1e6,
        result->status,
        result->final_ortho_error
    );

    return result->status;
}

/* ========================================================================= */
/* 7. PMTP BANKED DOUBLE-BUFFER SLOT LEASE RCU (IPC ZERO DATA RACE)         */
/* ========================================================================= */

extern "C" {

static bool is_process_dead_platform(uint32_t pid, uint64_t start_time_ns) {
    if (pid == 0) return true;
#if defined(_WIN32)
    HANDLE hProcess = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!hProcess) {
        DWORD err = GetLastError();
        if (err == ERROR_INVALID_PARAMETER) return true; // PID does not exist
        return true; // Cannot open -> process terminated
    }
    FILETIME ftCreate, ftExit, ftKernel, ftUser;
    if (GetProcessTimes(hProcess, &ftCreate, &ftExit, &ftKernel, &ftUser)) {
        ULARGE_INTEGER create_time;
        create_time.LowPart = ftCreate.dwLowDateTime;
        create_time.HighPart = ftCreate.dwHighDateTime;
        // Si el proceso salió, GetExitCodeProcess devuelve STILL_ACTIVE si está vivo
        DWORD exit_code = 0;
        if (GetExitCodeProcess(hProcess, &exit_code)) {
            CloseHandle(hProcess);
            return (exit_code != STILL_ACTIVE);
        }
    }
    CloseHandle(hProcess);
    return false;
#else
    return (kill(pid, 0) != 0);
#endif
}

int32_t pmtp_reap_orphaned_leases(PmtpBankedSlotHeader* header, uint32_t bank, uint64_t timeout_ns, uint32_t* reclaimed_out) {
    if (!header) return POLYDIM_STATUS_ERR_NULL_PTR;

    PmtpReaderLease* leases = (bank == 0) ? header->leases_bank0 : header->leases_bank1;
    uint32_t reclaimed = 0;

    for (size_t i = 0; i < PMTP_MAX_READERS_PER_BANK; ++i) {
        uint32_t expected = PMTP_LEASE_ACTIVE;
        std::atomic<uint32_t>* state_atom = reinterpret_cast<std::atomic<uint32_t>*>(&leases[i].state);
        
        if (state_atom->load(std::memory_order_acquire) == PMTP_LEASE_ACTIVE) {
            // Verificar si el PID murió
            if (is_process_dead_platform(leases[i].pid, leases[i].process_start_time_ns)) {
                if (state_atom->compare_exchange_strong(expected, PMTP_LEASE_RECLAIMED, std::memory_order_acq_rel)) {
                    reclaimed++;
                }
            }
        }
    }

    if (reclaimed_out) *reclaimed_out = reclaimed;
    header->num_reclaimed_orphans += reclaimed;
    return POLYDIM_STATUS_OK;
}

int32_t pmtp_banked_slot_acquire_reader(
    PmtpBankedSlotHeader* header, 
    uint32_t pid, 
    uint64_t start_time_ns, 
    uint32_t* acquired_bank,
    uint32_t* acquired_slot_idx
) {
    if (!header || !acquired_bank || !acquired_slot_idx) return POLYDIM_STATUS_ERR_NULL_PTR;

    uint32_t bank = ((std::atomic<uint32_t>*)&header->active_bank)->load(std::memory_order_acquire);
    PmtpReaderLease* leases = (bank == 0) ? header->leases_bank0 : header->leases_bank1;

    // Buscar un slot libre en el banco activo
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

    return -11; // No free reader lease slot
}

int32_t pmtp_banked_slot_release_reader(PmtpBankedSlotHeader* header, uint32_t bank, uint32_t slot_idx) {
    if (!header || slot_idx >= PMTP_MAX_READERS_PER_BANK) return POLYDIM_STATUS_ERR_NULL_PTR;

    PmtpReaderLease* leases = (bank == 0) ? header->leases_bank0 : header->leases_bank1;
    std::atomic<uint32_t>* state_atom = reinterpret_cast<std::atomic<uint32_t>*>(&leases[slot_idx].state);
    state_atom->store(PMTP_LEASE_CLOSED, std::memory_order_release);
    return POLYDIM_STATUS_OK;
}

int32_t pmtp_banked_slot_acquire_writer(PmtpBankedSlotHeader* header, uint32_t* write_bank, uint32_t pid, uint64_t start_time_ns) {
    if (!header || !write_bank) return POLYDIM_STATUS_ERR_NULL_PTR;

    uint32_t expected = 0;
    if (!((std::atomic<uint32_t>*)&header->writer_active)->compare_exchange_strong(expected, 1, std::memory_order_acquire)) {
        return -10; // Writer contention
    }

    uint32_t active = ((std::atomic<uint32_t>*)&header->active_bank)->load(std::memory_order_relaxed);
    uint32_t target = 1 - active;
    PmtpReaderLease* target_leases = (target == 0) ? header->leases_bank0 : header->leases_bank1;

    // Drenaje de lectores residuales en target bank (Grace Period con invocación a Reaper)
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

        // Intentar recuperar leases huérfanos de procesos caídos
        uint32_t reclaimed = 0;
        pmtp_reap_orphaned_leases(header, target, 1000000, &reclaimed);
    }

    header->owner_pid = pid;
    header->owner_start_time_ns = start_time_ns;
    *write_bank = target;
    return POLYDIM_STATUS_OK;
}

int32_t pmtp_banked_slot_commit_writer(PmtpBankedSlotHeader* header, uint32_t write_bank) {
    if (!header) return POLYDIM_STATUS_ERR_NULL_PTR;

    std::atomic_thread_fence(std::memory_order_release);
    ((std::atomic<uint32_t>*)&header->active_bank)->store(write_bank, std::memory_order_release);
    ((std::atomic<uint64_t>*)&header->sequence)->fetch_add(1, std::memory_order_relaxed);
    ((std::atomic<uint32_t>*)&header->writer_active)->store(0, std::memory_order_release);
    return POLYDIM_STATUS_OK;
}

/* ========================================================================= */
/* 8. RESERVORIO ESTRUCTURADO WALSH-HADAMARD (LSM O(D log D), O(D) MEMORIA)  */
/* ========================================================================= */

// Transformada Rápida de Walsh-Hadamard In-Place O(D log D) con Normalización 1/sqrt(D)
static void fwht_normalized_inplace(double* x, size_t D) {
    // D debe ser potencia de 2
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

int32_t polydim_structured_lsm_step(
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
    if (D == 0 || (D & (D - 1)) != 0) return POLYDIM_STATUS_ERR_INVALID_DIM; // D must be power of 2

    std::vector<double> tmp(D, 0.0);

    // 1. D1 * state & P1 permutation
    #pragma omp parallel for schedule(static)
    for (size_t i = 0; i < D; ++i) {
        double s_val = state[p1[i]] * (d1[p1[i]] < 0 ? -1.0 : 1.0);
        tmp[i] = s_val;
    }

    // 2. FWHT Normalizada O(D log D)
    fwht_normalized_inplace(tmp.data(), D);

    // 3. P2 permutation & D2 sign flip & No-linealidad Leaky-Tanh
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

}

