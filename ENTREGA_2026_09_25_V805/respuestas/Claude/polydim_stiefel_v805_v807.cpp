#include "polydim_stiefel_v805.h"
#include <cmath>
#include <algorithm>
#include <vector>

float polydim_dot_kahan(const float* a, const float* b, size_t n) {
    float sum = 0.0f;
    float c = 0.0f;
    for (size_t i = 0; i < n; ++i) {
        float product = a[i] * b[i];
        float t = sum + product;
        if (std::abs(sum) >= std::abs(product)) {
            c += (sum - t) + product;
        } else {
            c += (product - t) + sum;
        }
        sum = t;
    }
    return sum + c;
}

void stiefel_cholqr(const float* input, float* output, size_t num_rows, size_t num_cols) {
    std::vector<float> G(num_cols * num_cols, 0.0f);
    for (size_t i = 0; i < num_cols; ++i) {
        for (size_t j = i; j < num_cols; ++j) {
            float dot_val = polydim_dot_kahan(input + i * num_rows, input + j * num_rows, num_rows);
            G[i * num_cols + j] = dot_val;
            G[j * num_cols + i] = dot_val;
        }
    }

    // FIX V807 (real): regularizacion de Tikhonov ANTES de factorizar, no un
    // clamp post-hoc dentro del sqrt. El reporte 04 decia que esto ya estaba
    // hecho; no lo estaba (ver polydim_stiefel_orig.cpp linea 43: solo
    // sqrt(max(0,x)), sin +epsilon en la diagonal).
    float diag_scale = 0.0f;
    for (size_t i = 0; i < num_cols; ++i) diag_scale = std::max(diag_scale, G[i * num_cols + i]);
    const float epsilon = std::max(1e-6f, diag_scale * 1e-6f);
    for (size_t i = 0; i < num_cols; ++i) G[i * num_cols + i] += epsilon;

    std::vector<float> R(num_cols * num_cols, 0.0f);
    for (size_t i = 0; i < num_cols; ++i) {
        for (size_t j = 0; j <= i; ++j) {
            float sum = G[i * num_cols + j];
            for (size_t k = 0; k < j; ++k) {
                sum -= R[k * num_cols + i] * R[k * num_cols + j];
            }
            if (i == j) {
                R[j * num_cols + i] = std::sqrt(std::max(0.0f, sum));
            } else {
                if (R[j * num_cols + j] < 1e-7f) {
                    R[j * num_cols + i] = 0.0f;
                } else {
                    R[j * num_cols + i] = sum / R[j * num_cols + j];
                }
            }
        }
    }

    // FIX V807 (real): guardia en la division final. Antes: division por
    // R[i,i]==0 sin chequeo -> NaN/Inf silencioso propagado aguas abajo.
    for (size_t i = 0; i < num_cols; ++i) {
        float denom = R[i * num_cols + i];
        bool degenerate = std::abs(denom) < 1e-7f;
        for (size_t r = 0; r < num_rows; ++r) {
            float sum = input[i * num_rows + r];
            for (size_t j = 0; j < i; ++j) {
                sum -= output[j * num_rows + r] * R[j * num_cols + i];
            }
            output[i * num_rows + r] = degenerate ? 0.0f : (sum / denom);
        }
    }
}
