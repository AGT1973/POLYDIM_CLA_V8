import sys

content = open('src/polydim_kernel.cpp').read()

# OpenMP bug fix
content = content.replace("bad_value = 1;", "bad_value |= 1;")
content = content.replace("#pragma omp simd", "// #pragma omp simd")

# 2. Arena Fix in polydim_stiefel_cayley_smw_f64
start_arena = content.find('std::vector<double> arena;')
end_arena = content.find('catch (const std::bad_alloc&) { return POLYDIM_ERR_BUFFER_OVERFLOW; }', start_arena) + 71

new_arena = """    const size_t stride_doubles = (static_cast<size_t>(KK2) + 15) & ~15ULL;
    std::vector<double> arena;
    try { arena.assign(static_cast<size_t>(nthreads) * stride_doubles + 16, 0.0); }
    catch (const std::bad_alloc&) { return POLYDIM_ERR_BUFFER_OVERFLOW; }
    void* raw_ptr = arena.data();
    size_t space = arena.size() * sizeof(double);
    double* aligned_arena = static_cast<double*>(std::align(128, nthreads * stride_doubles * sizeof(double), raw_ptr, space));
    if (!aligned_arena) aligned_arena = arena.data();"""

if start_arena != -1:
    content = content[:start_arena] + new_arena + content[end_arena:]

old_tid = "double* L = arena.data() + static_cast<size_t>(tid) * KK2;"
new_tid = "double* L = aligned_arena + static_cast<size_t>(tid) * stride_doubles;"
content = content.replace(old_tid, new_tid)

old_sum = "for (int t = 0; t < nthreads; ++t) s += arena[static_cast<size_t>(t) * KK2 + j];"
new_sum = "for (int t = 0; t < nthreads; ++t) s += aligned_arena[static_cast<size_t>(t) * stride_doubles + j];"
content = content.replace(old_sum, new_sum)

# 3. Native LU Tikhonov Fallback
start_lu = content.find('/* Eliminación gaussiana con pivoteo parcial y umbral relativo. */')
end_lu = content.find('const double diag = M[static_cast<size_t>(k) * K2 + k];', start_lu) + 55

new_native = """/* Eliminación gaussiana con pivoteo parcial y umbral relativo. */
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
            M = M_backup;
            Z = Z_backup;
            double lambda = std::max(K2 * 2.22e-16 * m_inf, tol.pivot_rel * m_inf); 
            for (uint32_t i = 0; i < K2; ++i) {
                M[static_cast<size_t>(i) * K2 + i] += lambda * (M[static_cast<size_t>(i) * K2 + i] >= 0 ? 1.0 : -1.0);
            }
        }
        
        for (uint32_t k = 0; k < K2; ++k) {
            uint32_t piv = k;
            double best = std::abs(M[static_cast<size_t>(k) * K2 + k]);
            for (uint32_t r = k + 1; r < K2; ++r) {
                const double a = std::abs(M[static_cast<size_t>(r) * K2 + k]);
                if (a > best) { best = a; piv = r; }
            }
            if (!(best > pivot_thr)) {
                if (report) report->pivot_min = pivot_min;
                return POLYDIM_ERR_NUMERICAL_INSTABILITY;
            }
            if (piv != k) {
                for (uint32_t c = 0; c < K2; ++c)
                    std::swap(M[static_cast<size_t>(k) * K2 + c], M[static_cast<size_t>(piv) * K2 + c]);
                for (uint32_t c = 0; c < K; ++c)
                    std::swap(Z[static_cast<size_t>(k) * K + c], Z[static_cast<size_t>(piv) * K + c]);
            }
            const double diag = M[static_cast<size_t>(k) * K2 + k];"""

if start_lu != -1:
    content = content[:start_lu] + new_native + content[end_lu:]

# 4. BLAS Tikhonov Fallback
start_blas = content.find('// *** INICIO BLOQUE BLAS ***')
end_blas = content.find('// *** FIN BLOQUE BLAS ***', start_blas) + 26

new_blas = """// *** INICIO BLOQUE BLAS ***
        std::vector<int> jpvt(K2, 0);
        std::vector<double> tau_qr(K2);
        std::vector<double> work(1);
        int lwork = -1;
        int info = 0;
        int n = static_cast<int>(K2);
        
        std::vector<double> Mc(KK2), Zc(static_cast<size_t>(K2) * K);
        for (uint32_t r = 0; r < K2; ++r) for (uint32_t c = 0; c < K2; ++c)
            Mc[static_cast<size_t>(c) * K2 + r] = M[static_cast<size_t>(r) * K2 + c];
        for (uint32_t r = 0; r < K2; ++r) for (uint32_t c = 0; c < K; ++c)
            Zc[static_cast<size_t>(c) * K2 + r] = Z[static_cast<size_t>(r) * K + c];
            
        dgeqp3_(&n, &n, Mc.data(), &n, jpvt.data(), tau_qr.data(), work.data(), &lwork, &info);
        lwork = static_cast<int>(work[0]);
        work.resize(lwork);
        dgeqp3_(&n, &n, Mc.data(), &n, jpvt.data(), tau_qr.data(), work.data(), &lwork, &info);
        
        double rcond = 0.0;
        std::vector<int> iwork(n);
        dtrcon_("1", "U", "N", &n, Mc.data(), &n, &rcond, work.data(), iwork.data(), &info);
        double pmin = std::abs(Mc[static_cast<size_t>(n - 1) * n + (n - 1)]);
        
        if (rcond < tol.pivot_rel || pmin < pivot_thr || std::isnan(rcond)) {
            double lambda = std::max(K2 * 2.22e-16 * m_inf, tol.pivot_rel * m_inf);
            for (uint32_t r = 0; r < K2; ++r) {
                for (uint32_t c = 0; c < K2; ++c) {
                    Mc[static_cast<size_t>(c) * K2 + r] = M[static_cast<size_t>(r) * K2 + c];
                }
                Mc[static_cast<size_t>(r) * K2 + r] += lambda * (Mc[static_cast<size_t>(r) * K2 + r] >= 0 ? 1.0 : -1.0);
            }
            std::fill(jpvt.begin(), jpvt.end(), 0);
            dgeqp3_(&n, &n, Mc.data(), &n, jpvt.data(), tau_qr.data(), work.data(), &lwork, &info);
            if (info != 0) return POLYDIM_ERR_NUMERICAL_INSTABILITY;
        }
        
        int nrhs = static_cast<int>(K);
        dormqr_("L", "T", &n, &nrhs, &n, Mc.data(), &n, tau_qr.data(), Zc.data(), &n, work.data(), &lwork, &info);
        dtrtrs_("U", "N", "N", &n, &nrhs, Mc.data(), &n, Zc.data(), &n, &info);
        
        for (uint32_t i = 0; i < K2; ++i) {
            int orig_col = jpvt[i] - 1;
            for (uint32_t c = 0; c < K; ++c) {
                Y[static_cast<size_t>(orig_col) * K + c] = Zc[static_cast<size_t>(c) * K2 + i];
            }
        }
// *** FIN BLOQUE BLAS ***"""

if start_blas != -1:
    content = content[:start_blas] + new_blas + content[end_blas:]

# 5. NaN verification bug
old_err = """        for (uint32_t c = i; c < K; ++c) {
            double s = 0.0;
            for (uint32_t j = 0; j < D; ++j) s += Y_out[j * K + r] * Y_out[j * K + c];
            err = std::max(err, std::abs(s - (r == c ? 1.0 : 0.0)));
        }"""
new_err = """        for (uint32_t c = i; c < K; ++c) {
            double s = 0.0;
            for (uint32_t j = 0; j < D; ++j) s += Y_out[j * K + r] * Y_out[j * K + c];
            if (std::isnan(s) || std::isinf(s)) return POLYDIM_ERR_NAN_OR_INF;
            err = std::max(err, std::abs(s - (r == c ? 1.0 : 0.0)));
        }"""
content = content.replace(old_err, new_err)

# Also fix the #include for std::align
if '#include <memory>' not in content:
    content = content.replace('#include <vector>', '#include <vector>\n#include <memory>')

open('src/polydim_kernel.cpp', 'w').write(content)
print("Rest of patches applied cleanly")
