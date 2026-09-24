import sys

content = open('src/polydim_kernel.cpp').read()

old_blas = """        if (rcond < tol.pivot_rel || pmin < pivot_thr || rcond != rcond) {
            double lambda = std::max(1e-12, tol.pivot_rel * m_inf);
            for (int i = 0; i < n; ++i) {
                Mc[i * n + i] += lambda * (Mc[i * n + i] >= 0 ? 1.0 : -1.0);
            }
        }"""

new_blas = """        if (rcond < tol.pivot_rel || pmin < pivot_thr || rcond != rcond) {
            double lambda = std::max(1e-15, tol.pivot_rel * m_inf); // Removed 1e-12 hardcoded floor
            for (uint32_t r = 0; r < K2; ++r) {
                for (uint32_t c = 0; c < K2; ++c) {
                    Mc[static_cast<size_t>(c) * K2 + r] = M[static_cast<size_t>(r) * K2 + c];
                }
                Mc[static_cast<size_t>(r) * K2 + r] += lambda * (Mc[static_cast<size_t>(r) * K2 + r] >= 0 ? 1.0 : -1.0);
            }
            std::fill(jpvt.begin(), jpvt.end(), 0);
            dgeqp3_(&n, &n, Mc.data(), &n, jpvt.data(), tau_qr.data(), work.data(), &lwork, &info);
            if (info != 0) return POLYDIM_ERR_NUMERICAL_INSTABILITY;
        }"""

if old_blas in content:
    open('src/polydim_kernel.cpp', 'w').write(content.replace(old_blas, new_blas))
    print('BLAS path updated successfully')
else:
    print('Error: Could not find old BLAS path exactly')
