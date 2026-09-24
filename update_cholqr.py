import os
import re

CPP_PATH = 'E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V767/kernel_cpp_v767.cpp'
with open(CPP_PATH, 'r', encoding='utf-8') as f:
    text = f.read()

new_cholqr = """extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_cholqr2_f64(
    double* __restrict__ X,
    uint64_t D,
    uint32_t K
) {
    try {
        if (!X) return POLYDIM_ERR_NULL_POINTER;
        if (D == 0 || K == 0 || D < K) return POLYDIM_ERR_INVALID_DIMENSION;
        if (K > 1024) return POLYDIM_ERR_BUFFER_OVERFLOW;

        set_fp_mode();
        const int64_t TILE = 8192;
        int max_threads = omp_get_max_threads();
        
        const double eps = 2.220446049250313e-16;
        int max_iters = 3;
        bool converged = false;

        for (int step = 0; step < max_iters; ++step) {
            std::vector<double> thread_XTX(static_cast<size_t>(max_threads) * K * K, 0.0);
            int nan_detected = 0;

            #pragma omp parallel reduction(|:nan_detected)
            {
                set_fp_mode();
                int tid = omp_get_thread_num();
                double* local_xtx = &thread_XTX[static_cast<size_t>(tid) * K * K];

                #pragma omp for schedule(dynamic)
                for (int64_t b = 0; b < static_cast<int64_t>(D); b += TILE) {
                    int64_t b_end = std::min(b + TILE, static_cast<int64_t>(D));
                    for (int64_t i = b; i < b_end; ++i) {
                        const double* xi = &X[static_cast<size_t>(i) * K];
                        for (uint32_t r = 0; r < K; ++r) {
                            double xr = xi[r];
                            if (std::isnan(xr) || std::isinf(xr)) {
                                nan_detected = 1;
                            }
                            for (uint32_t c = r; c < K; ++c) {
                                local_xtx[r * K + c] = std::fma(xr, xi[c], local_xtx[r * K + c]);
                            }
                        }
                    }
                }
            }

            if (nan_detected) return POLYDIM_ERR_NAN_OR_INF;

            std::vector<double> A(static_cast<size_t>(K) * K, 0.0);
            for (int t = 0; t < max_threads; ++t) {
                double* l_xtx = &thread_XTX[static_cast<size_t>(t) * K * K];
                for (uint32_t r = 0; r < K; ++r) {
                    for (uint32_t c = r; c < K; ++c) {
                        A[r * K + c] += l_xtx[r * K + c];
                    }
                }
            }

            double max_diag = 0.0;
            for (uint32_t r = 0; r < K; ++r) {
                if (A[r * K + r] > max_diag) max_diag = A[r * K + r];
                for (uint32_t c = r + 1; c < K; ++c) {
                    A[c * K + r] = A[r * K + c];
                }
            }
            
            // Post-verify if step > 0
            if (step > 0) {
                double max_err = 0.0;
                for (uint32_t r = 0; r < K; ++r) {
                    for (uint32_t c = 0; c < K; ++c) {
                        double expected = (r == c) ? 1.0 : 0.0;
                        double err = std::abs(A[r * K + c] - expected);
                        if (err > max_err) max_err = err;
                    }
                }
                if (max_err < eps * D * 10.0) {
                    converged = true;
                    break;
                }
            }

            // Relative pivot threshold
            double tol = eps * static_cast<double>(D) * max_diag;
            if (tol < 1e-14) tol = 1e-14;

            std::vector<double> L(static_cast<size_t>(K) * K, 0.0);
            for (uint32_t i = 0; i < K; ++i) {
                for (uint32_t j = 0; j <= i; ++j) {
                    double s = A[i * K + j];
                    for (uint32_t k = 0; k < j; ++k) {
                        s -= L[i * K + k] * L[j * K + k];
                    }
                    if (i == j) {
                        if (s <= tol) return POLYDIM_ERR_DEGENERATE_NORM;
                        L[i * K + i] = std::sqrt(s);
                    } else {
                        L[i * K + j] = s / L[j * K + j];
                    }
                }
            }

            #pragma omp parallel for schedule(static)
            for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
                double* xi = &X[static_cast<size_t>(i) * K];
                for (uint32_t k = 0; k < K; ++k) {
                    double val = xi[k];
                    for (uint32_t j = 0; j < k; ++j) {
                        val -= L[k * K + j] * xi[j];
                    }
                    xi[k] = val / L[k * K + k];
                }
            }
        }
        
        if (!converged) return POLYDIM_ERR_NUMERICAL_INSTABILITY;
        return POLYDIM_SUCCESS;
    }
    catch (const std::bad_alloc&) {
        return POLYDIM_ERR_ALLOC;
    }
    catch (...) {
        return POLYDIM_ERR_INTERNAL;
    }
}
"""

match = re.search(r'extern \"C\" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_cholqr2_f64.*?return POLYDIM_ERR_INTERNAL;\s*\}\s*\}', text, re.DOTALL)
if match:
    new_text = text[:match.start()] + new_cholqr.strip() + text[match.end():]
    with open(CPP_PATH, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("CholQR2 updated")
else:
    print("Failed to find CholQR2")
