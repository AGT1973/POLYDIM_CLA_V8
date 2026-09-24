import sys
import re

content = open('src/polydim_kernel.cpp').read()

# 1. PMTP Fix
old_pmtp = re.search(r'struct PMTP_Control \{.*?char _pad\[64\];.*?};', content, re.DOTALL).group(0)
new_pmtp = """struct alignas(64) PMTP_Control {
    std::atomic<uint64_t> seq[3];
    std::atomic<uint8_t> state;
};"""
content = content.replace(old_pmtp, new_pmtp)

old_pmtp_funcs = re.search(r'extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_init.*?extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_free', content, re.DOTALL).group(0)
new_pmtp_funcs = """extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_init(PMTP_Control* c) {
    if (!c) return;
    c->state.store((0) | (1 << 2) | (2 << 4), std::memory_order_seq_cst);
    c->seq[0].store(0, std::memory_order_seq_cst);
    c->seq[1].store(0, std::memory_order_seq_cst);
    c->seq[2].store(0, std::memory_order_seq_cst);
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_begin_write(PMTP_Control* c, uint64_t* slot_out) {
    if (!c || !slot_out) return POLYDIM_ERR_NULL_POINTER;
    uint8_t s = c->state.load(std::memory_order_acquire);
    uint64_t slot = (s >> 4) & 3; 
    c->seq[slot].fetch_add(1, std::memory_order_acquire); 
    *slot_out = slot;
    return POLYDIM_SUCCESS;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_commit_write(PMTP_Control* c, uint64_t slot) {
    if (!c) return POLYDIM_ERR_NULL_POINTER;
    c->seq[slot].fetch_add(1, std::memory_order_release); 
    uint8_t current = c->state.load(std::memory_order_acquire);
    while (true) {
        uint8_t old_o = current & 3;
        uint8_t old_m = (current >> 2) & 3;
        uint8_t old_n = (current >> 4) & 3;
        uint8_t next_s = (old_m) | (old_n << 2) | (old_o << 4);
        if (c->state.compare_exchange_weak(current, next_s, std::memory_order_release, std::memory_order_relaxed)) break;
    }
    return POLYDIM_SUCCESS;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_acquire_read(
    PMTP_Control* c, uint64_t* observed_seq, uint64_t* slot_out, uint64_t* ticket_out)
{
    if (!c || !observed_seq || !slot_out || !ticket_out) return POLYDIM_ERR_NULL_POINTER;
    uint8_t s = c->state.load(std::memory_order_acquire);
    uint64_t slot = s & 3; 
    uint64_t seq = c->seq[slot].load(std::memory_order_acquire);
    *slot_out = slot;
    *ticket_out = seq;
    *observed_seq = seq;
    if (seq % 2 != 0) return 0; 
    return 1; 
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_validate_read(
    const PMTP_Control* c, uint64_t slot, uint64_t ticket)
{
    if (!c) return POLYDIM_ERR_NULL_POINTER;
    std::atomic_thread_fence(std::memory_order_acquire);
    uint64_t current_seq = c->seq[slot].load(std::memory_order_acquire);
    if (current_seq != ticket || (current_seq % 2 != 0)) return POLYDIM_ERR_SEQLOCK_RACE;
    return POLYDIM_SUCCESS;
}

extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_free"""
content = content.replace(old_pmtp_funcs, new_pmtp_funcs)

# 2. Arena Fix in polydim_stiefel_cayley_smw_f64
old_arena = """    std::vector<double> arena;
    try { arena.assign(static_cast<size_t>(nthreads) * KK2, 0.0); }
    catch (const std::bad_alloc&) { return POLYDIM_ERR_BUFFER_OVERFLOW; }"""
new_arena = """    const size_t stride_doubles = (static_cast<size_t>(KK2) + 15) & ~15ULL;
    std::vector<double> arena;
    try { arena.assign(static_cast<size_t>(nthreads) * stride_doubles + 16, 0.0); }
    catch (const std::bad_alloc&) { return POLYDIM_ERR_BUFFER_OVERFLOW; }
    void* raw_ptr = arena.data();
    size_t space = arena.size() * sizeof(double);
    double* aligned_arena = static_cast<double*>(std::align(128, nthreads * stride_doubles * sizeof(double), raw_ptr, space));
    if (!aligned_arena) aligned_arena = arena.data();"""
content = content.replace(old_arena, new_arena)

old_tid = "double* L = arena.data() + static_cast<size_t>(tid) * KK2;"
new_tid = "double* L = aligned_arena + static_cast<size_t>(tid) * stride_doubles;"
content = content.replace(old_tid, new_tid)

old_sum = "for (int t = 0; t < nthreads; ++t) s += arena[static_cast<size_t>(t) * KK2 + j];"
new_sum = "for (int t = 0; t < nthreads; ++t) s += aligned_arena[static_cast<size_t>(t) * stride_doubles + j];"
content = content.replace(old_sum, new_sum)

# OpenMP bug fix
content = content.replace("bad_value = 1;", "bad_value |= 1;")
content = content.replace("#pragma omp simd", "// #pragma omp simd")

# 3. Native LU Tikhonov Fallback
old_native = re.search(r'/\* Eliminación gaussiana con pivoteo parcial.*?(?:const double diag = M\[static_cast<size_t>\(k\) \* K2 \+ k\];)', content, re.DOTALL).group(0)
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
content = content.replace(old_native, new_native)

# 4. BLAS Tikhonov Fallback
old_blas = re.search(r'// \*\*\* INICIO BLOQUE BLAS \*\*\*.*?// \*\*\* FIN BLOQUE BLAS \*\*\*', content, re.DOTALL).group(0)
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
content = content.replace(old_blas, new_blas)

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

open('src/polydim_kernel.cpp', 'w').write(content)
print("Safe and perfect rewrite complete")
