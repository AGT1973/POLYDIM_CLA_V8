import sys

content = open('src/polydim_kernel.cpp').read()

old_native = """        /* Eliminación gaussiana con pivoteo parcial y umbral relativo. */
        double pivot_min = std::numeric_limits<double>::infinity();
        for (uint32_t k = 0; k < K2; ++k) {
            uint32_t piv = k;
            double best = std::abs(M[static_cast<size_t>(k) * K2 + k]);
            for (uint32_t r = k + 1; r < K2; ++r) {
                const double a = std::abs(M[static_cast<size_t>(r) * K2 + k]);
                if (a > best) { best = a; piv = r; }
            }
            pivot_min = std::min(pivot_min, best);
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

new_native = """        /* Eliminación gaussiana con pivoteo parcial y umbral relativo. */
        std::vector<double> M_backup(M.begin(), M.end());
        std::vector<double> Z_backup(Z.begin(), Z.end());
        
        bool needs_tikhonov = false;
        double pivot_min = std::numeric_limits<double>::infinity();
        
        for (uint32_t k = 0; k < K2; ++k) {
            uint32_t piv = k;
            double best = std::abs(M[static_cast<size_t>(k) * K2 + k]);
            for (uint32_t r = k + 1; r < K2; ++r) {
                const double a = std::abs(M[static_cast<size_t>(r) * K2 + k]);
                if (a > best) { best = a; piv = r; }
            }
            pivot_min = std::min(pivot_min, best);
            if (!(best > pivot_thr)) {
                needs_tikhonov = true;
                break;
            }
        }
        
        if (needs_tikhonov) {
            // Restore M and Z, apply Tikhonov globally to original M
            M = M_backup;
            Z = Z_backup;
            double lambda = std::max(1e-15, tol.pivot_rel * m_inf); // Removed 1e-12 floor
            for (uint32_t i = 0; i < K2; ++i) {
                M[static_cast<size_t>(i) * K2 + i] += lambda * (M[static_cast<size_t>(i) * K2 + i] >= 0 ? 1.0 : -1.0);
            }
        }
        
        // Final LU Pass (either pristine or perfectly Tikhonov-regularized)
        for (uint32_t k = 0; k < K2; ++k) {
            uint32_t piv = k;
            double best = std::abs(M[static_cast<size_t>(k) * K2 + k]);
            for (uint32_t r = k + 1; r < K2; ++r) {
                const double a = std::abs(M[static_cast<size_t>(r) * K2 + k]);
                if (a > best) { best = a; piv = r; }
            }
            if (!(best > pivot_thr) && !needs_tikhonov) {
                // If it still fails after Tikhonov (or threshold is insanely high), abort
                if (report) report->pivot_min = pivot_min;
                return POLYDIM_ERR_NUMERICAL_INSTABILITY;
            }"""

if old_native in content:
    open('src/polydim_kernel.cpp', 'w').write(content.replace(old_native, new_native))
    print('Native path updated successfully')
else:
    print('Error: Could not find old Native path exactly')
