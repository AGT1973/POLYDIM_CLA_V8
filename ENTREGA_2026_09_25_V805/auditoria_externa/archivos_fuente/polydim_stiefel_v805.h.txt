#ifndef POLYDIM_STIEFEL_V805_H
#define POLYDIM_STIEFEL_V805_H

#include <cstddef>
#include <vector>

// Kahan/Neumaier summation for O(D) dot products to prevent FP32 drift.
float polydim_dot_kahan(const float* a, const float* b, size_t n);

// Stiefel CholQR algorithm using polydim_dot_kahan
void stiefel_cholqr(const float* input, float* output, size_t num_rows, size_t num_cols);

#endif // POLYDIM_STIEFEL_V805_H
