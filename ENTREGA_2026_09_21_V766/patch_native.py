import sys

old_native = """            pivot_min = std::min(pivot_min, best);
            if (!(best > pivot_thr)) {
                if (report) report->pivot_min = pivot_min;
                return POLYDIM_ERR_NUMERICAL_INSTABILITY;
            }"""

new_native = """            pivot_min = std::min(pivot_min, best);
            if (!(best > pivot_thr)) {
                // Adaptive Tikhonov fallback for Native LU
                double lambda = std::max(1e-12, tol.pivot_rel * m_inf);
                for (uint32_t i = k; i < K2; ++i) {
                    M[static_cast<size_t>(i) * K2 + i] += lambda * (M[static_cast<size_t>(i) * K2 + i] >= 0 ? 1.0 : -1.0);
                }
                best = std::abs(M[static_cast<size_t>(k) * K2 + k]);
                piv = k;
                for (uint32_t r = k + 1; r < K2; ++r) {
                    const double a = std::abs(M[static_cast<size_t>(r) * K2 + k]);
                    if (a > best) { best = a; piv = r; }
                }
                if (!(best > pivot_thr)) {
                    if (report) report->pivot_min = pivot_min;
                    return POLYDIM_ERR_NUMERICAL_INSTABILITY;
                }
            }"""

content = open('src/polydim_kernel.cpp').read()
if old_native in content:
    open('src/polydim_kernel.cpp', 'w').write(content.replace(old_native, new_native))
    print('Native path updated successfully')
else:
    print('Error: Could not find old Native path exactly')
