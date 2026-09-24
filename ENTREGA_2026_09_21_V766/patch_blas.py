import sys

new_blas = """        int n = static_cast<int>(K2), nrhs = static_cast<int>(K), info = 0;
        std::vector<int> jpvt(K2, 0);
        std::vector<double> tau_qr(K2);
        
        double work_query = 0;
        int lwork = -1;
        dgeqp3_(&n, &n, Mc.data(), &n, jpvt.data(), tau_qr.data(), &work_query, &lwork, &info);
        lwork = static_cast<int>(work_query);
        std::vector<double> work(lwork);
        
        dgeqp3_(&n, &n, Mc.data(), &n, jpvt.data(), tau_qr.data(), work.data(), &lwork, &info);
        if (info != 0) return POLYDIM_ERR_NUMERICAL_INSTABILITY;
        
        double rcond = 0.0;
        std::vector<int> iwork(n);
        std::vector<double> work_trcon(3*n);
        dtrcon_("1", "U", "N", &n, Mc.data(), &n, &rcond, work_trcon.data(), iwork.data(), &info);
        
        double pmin = std::numeric_limits<double>::infinity();
        for (uint32_t k = 0; k < K2; ++k)
            pmin = std::min(pmin, std::abs(Mc[static_cast<size_t>(k) * K2 + k]));
        if (report) report->pivot_min = pmin;
        
        if (rcond < tol.pivot_rel || pmin < pivot_thr || rcond != rcond) {
            double lambda = std::max(1e-12, tol.pivot_rel * m_inf);
            for (int i = 0; i < n; ++i) {
                Mc[i * n + i] += lambda * (Mc[i * n + i] >= 0 ? 1.0 : -1.0);
            }
        }
        
        lwork = -1;
        dormqr_("L", "T", &n, &nrhs, &n, Mc.data(), &n, tau_qr.data(), Zc.data(), &n, &work_query, &lwork, &info);
        lwork = static_cast<int>(work_query);
        work.assign(lwork, 0.0);
        dormqr_("L", "T", &n, &nrhs, &n, Mc.data(), &n, tau_qr.data(), Zc.data(), &n, work.data(), &lwork, &info);
        
        dtrtrs_("U", "N", "N", &n, &nrhs, Mc.data(), &n, Zc.data(), &n, &info);
        if (info != 0) return POLYDIM_ERR_NUMERICAL_INSTABILITY;
        
        std::vector<double> Zc_permuted(K2 * K);
        for(int i = 0; i < n; ++i) {
            int orig_col = jpvt[i] - 1;
            for(int j = 0; j < nrhs; ++j) {
                Zc_permuted[orig_col + j*n] = Zc[i + j*n];
            }
        }
        Zc = Zc_permuted;"""

old_blas = """        int n = static_cast<int>(K2), nrhs = static_cast<int>(K), info = 0;
        std::vector<int> ipiv(K2);
        dgesv_(&n, &nrhs, Mc.data(), &n, ipiv.data(), Zc.data(), &n, &info);
        if (info != 0) return POLYDIM_ERR_NUMERICAL_INSTABILITY;
        double pmin = std::numeric_limits<double>::infinity();
        for (uint32_t k = 0; k < K2; ++k)
            pmin = std::min(pmin, std::abs(Mc[static_cast<size_t>(k) * K2 + k]));
        if (report) report->pivot_min = pmin;
        if (pmin < pivot_thr) return POLYDIM_ERR_NUMERICAL_INSTABILITY;"""

content = open('src/polydim_kernel.cpp').read()
if old_blas in content:
    open('src/polydim_kernel.cpp', 'w').write(content.replace(old_blas, new_blas))
    print('BLAS path updated successfully')
else:
    print('Error: Could not find old BLAS path exactly')
