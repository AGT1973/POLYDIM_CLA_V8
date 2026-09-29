#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <algorithm>
#include <vector>

#define MAX_K 64

// Standalone test for Block LDL^T with Rook pivoting
int block_ldlt_solve(const double* A_in, const double* B_in, int N, int K, double* X_out) {
    std::vector<double> A(A_in, A_in + N * N);
    std::vector<double> B(B_in, B_in + N * K);
    std::vector<int> piv(N);
    for (int i = 0; i < N; ++i) piv[i] = i;

    // We store L in the lower triangle of A, D on the diagonal blocks of A
    int i = 0;
    while (i < N) {
        if (i == N - 1) {
            // 1x1 block
            break;
        }

        // Find Rook pivot in submatrix A[i:N, i:N]
        int p_r = i, p_c = i;
        double max_val = std::abs(A[i * N + i]);
        for (int r = i; r < N; ++r) {
            for (int c = i; c < N; ++c) {
                double v = std::abs(A[r * N + c]);
                if (v > max_val) {
                    max_val = v;
                    p_r = r;
                    p_c = c;
                }
            }
        }

        // Check if 1x1 pivot is good enough or if we use 2x2
        double d_ii = std::abs(A[i * N + i]);
        const double alpha = (1.0 + std::sqrt(17.0)) / 8.0; // ~0.6404

        if (d_ii >= alpha * max_val || max_val < 1e-15) {
            // 1x1 Pivot at i
            double d = A[i * N + i];
            if (std::abs(d) < 1e-15) d = (d >= 0 ? 1e-15 : -1e-15);
            for (int r = i + 1; r < N; ++r) {
                double l = A[r * N + i] / d;
                A[r * N + i] = l;
                for (int c = i + 1; c <= r; ++c) {
                    A[r * N + c] -= l * A[c * N + i] * d; // using symmetric entry before overwrite
                }
            }
            for (int r = i + 1; r < N; ++r) {
                for (int c = r + 1; c < N; ++c) {
                    A[r * N + c] = A[c * N + r];
                }
            }
            i += 1;
        } else {
            // 2x2 Pivot: swap rows/cols (i, i+1) with (p_r, p_c)
            if (p_r != i) {
                for (int col = 0; col < N; ++col) std::swap(A[i * N + col], A[p_r * N + col]);
                for (int row = 0; row < N; ++row) std::swap(A[row * N + i], A[row * N + p_r]);
                std::swap(piv[i], piv[p_r]);
            }
            int next = (p_c == i ? p_r : p_c);
            if (next != i + 1 && next < N) {
                for (int col = 0; col < N; ++col) std::swap(A[(i + 1) * N + col], A[next * N + col]);
                for (int row = 0; row < N; ++row) std::swap(A[row * N + (i + 1)], A[row * N + next]);
                std::swap(piv[i + 1], piv[next]);
            }

            double d00 = A[i * N + i];
            double d01 = A[i * N + (i + 1)];
            double d10 = A[(i + 1) * N + i];
            double d11 = A[(i + 1) * N + (i + 1)];

            double det = d00 * d11 - d01 * d10;
            if (std::abs(det) < 1e-15) det = (det >= 0 ? 1e-15 : -1e-15);
            double inv00 =  d11 / det;
            double inv01 = -d01 / det;
            double inv10 = -d10 / det;
            double inv11 =  d00 / det;

            std::vector<double> L0(N, 0.0), L1(N, 0.0);
            for (int r = i + 2; r < N; ++r) {
                double a0 = A[r * N + i];
                double a1 = A[r * N + (i + 1)];
                L0[r] = a0 * inv00 + a1 * inv10;
                L1[r] = a0 * inv01 + a1 * inv11;
            }

            for (int r = i + 2; r < N; ++r) {
                for (int c = i + 2; c < N; ++c) {
                    double delta = L0[r] * (d00 * L0[c] + d01 * L1[c]) + L1[r] * (d10 * L0[c] + d11 * L1[c]);
                    A[r * N + c] -= delta;
                }
            }

            for (int r = i + 2; r < N; ++r) {
                A[r * N + i] = L0[r];
                A[r * N + (i + 1)] = L1[r];
            }
            i += 2;
        }
    }

    // Apply permutations to RHS B: P B
    std::vector<double> Y = B;
    for (int r = 0; r < N; ++r) {
        int p = piv[r];
        if (p != r) {
            for (int k = 0; k < K; ++k) {
                std::swap(Y[r * K + k], Y[p * K + k]);
            }
        }
    }

    // Forward solve: L W = P B
    for (int r = 0; r < N; ++r) {
        for (int c = 0; c < r; ++c) {
            double l_rc = A[r * N + c];
            for (int k = 0; k < K; ++k) {
                Y[r * K + k] -= l_rc * Y[c * K + k];
            }
        }
    }

    // Solve D Z = W
    std::vector<double> Z = Y;
    int idx = 0;
    while (idx < N) {
        if (idx + 1 < N && std::abs(A[idx * N + (idx + 1)]) > 1e-15) {
            // 2x2 Block
            double d00 = A[idx * N + idx];
            double d01 = A[idx * N + (idx + 1)];
            double d10 = A[(idx + 1) * N + idx];
            double d11 = A[(idx + 1) * N + (idx + 1)];
            double det = d00 * d11 - d01 * d10;
            if (std::abs(det) < 1e-15) det = (det >= 0 ? 1e-15 : -1e-15);
            for (int k = 0; k < K; ++k) {
                double w0 = Y[idx * K + k];
                double w1 = Y[(idx + 1) * K + k];
                Z[idx * K + k]       = (d11 * w0 - d01 * w1) / det;
                Z[(idx + 1) * K + k] = (-d10 * w0 + d00 * w1) / det;
            }
            idx += 2;
        } else {
            // 1x1 Block
            double d = A[idx * N + idx];
            if (std::abs(d) < 1e-15) d = (d >= 0 ? 1e-15 : -1e-15);
            for (int k = 0; k < K; ++k) {
                Z[idx * K + k] = Y[idx * K + k] / d;
            }
            idx += 1;
        }
    }

    // Back solve: L^T X_perm = Z
    std::vector<double> X_perm = Z;
    for (int r = N - 1; r >= 0; --r) {
        for (int c = r + 1; c < N; ++c) {
            double l_cr = A[c * N + r];
            for (int k = 0; k < K; ++k) {
                X_perm[r * K + k] -= l_cr * X_perm[c * K + k];
            }
        }
    }

    // Undo permutations: X = P^T X_perm
    for (int r = N - 1; r >= 0; --r) {
        int p = piv[r];
        if (p != r) {
            for (int k = 0; k < K; ++k) {
                std::swap(X_perm[r * K + k], X_perm[p * K + k]);
            }
        }
    }

    std::memcpy(X_out, X_perm.data(), N * K * sizeof(double));
    return 0;
}
