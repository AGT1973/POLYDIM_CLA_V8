#include "polydim_stiefel_v805.h"
#include <cmath>
#include <algorithm>
#include <vector>
#include <cstring>

#if defined(_MSC_VER)
#  define PD_RESTRICT __restrict
#else
#  define PD_RESTRICT __restrict__
#endif

// Neumaier compensated summation with exact FMA product residual, branchless
float polydim_dot_kahan(const float* PD_RESTRICT a, const float* PD_RESTRICT b, size_t n) {
    float sum = 0.0f;
    float c = 0.0f;
    for (size_t i = 0; i < n; ++i) {
        float p = a[i] * b[i];
        float pe = std::fma(a[i], b[i], -p); // Exact product residual
        float t = sum + p;
        float s = std::fabs(sum);
        float q = std::fabs(p);
        float hi = (s >= q) ? sum : p;
        float lo = (s >= q) ? p : sum;
        c += (hi - t) + lo + pe;
        sum = t;
    }
    return sum + c;
}

void stiefel_cholqr(const float* PD_RESTRICT input, float* PD_RESTRICT output, size_t num_rows, size_t num_cols) {
    if (!input || !output || num_rows == 0 || num_cols == 0) return;

    // 1. Gram matrix G = A^T A accumulated in FP64 to prevent condition number squaring
    std::vector<double> G(num_cols * num_cols, 0.0);
    for (size_t i = 0; i < num_cols; ++i) {
        for (size_t j = i; j < num_cols; ++j) {
            double acc = 0.0;
            for (size_t r = 0; r < num_rows; ++r) {
                acc += static_cast<double>(input[i * num_rows + r]) * static_cast<double>(input[j * num_rows + r]);
            }
            G[i * num_cols + j] = acc;
            G[j * num_cols + i] = acc;
        }
    }

    // 2. Tikhonov Regularization: scale with MEAN diagonal (trace / num_cols)
    double trace = 0.0;
    for (size_t i = 0; i < num_cols; ++i) trace += G[i * num_cols + i];
    double mean_diag = trace / static_cast<double>(num_cols);
    double eps = (mean_diag > 0.0) ? std::max(1e-12, mean_diag * 1e-6) : 1e-12;
    for (size_t i = 0; i < num_cols; ++i) G[i * num_cols + i] += eps;

    // 3. Cholesky decomposition of regularized Gram matrix in FP64
    std::vector<double> R(num_cols * num_cols, 0.0);
    double pivot_tol = std::sqrt(eps) * 1e-3;

    for (size_t i = 0; i < num_cols; ++i) {
        for (size_t j = 0; j <= i; ++j) {
            double sum = G[i * num_cols + j];
            for (size_t k = 0; k < j; ++k) {
                sum -= R[k * num_cols + i] * R[k * num_cols + j];
            }
            if (i == j) {
                R[j * num_cols + i] = std::sqrt(std::max(eps, sum));
            } else {
                if (R[j * num_cols + j] < pivot_tol) {
                    R[j * num_cols + i] = 0.0;
                } else {
                    R[j * num_cols + i] = sum / R[j * num_cols + j];
                }
            }
        }
    }

    // 4. Output Q = A R^{-1} via forward substitution
    for (size_t i = 0; i < num_cols; ++i) {
        double denom = R[i * num_cols + i];
        bool degenerate = denom < pivot_tol;
        for (size_t r = 0; r < num_rows; ++r) {
            double sum = static_cast<double>(input[i * num_rows + r]);
            for (size_t j = 0; j < i; ++j) {
                sum -= static_cast<double>(output[j * num_rows + r]) * R[j * num_cols + i];
            }
            output[i * num_rows + r] = degenerate ? 0.0f : static_cast<float>(sum / denom);
        }
    }
}
