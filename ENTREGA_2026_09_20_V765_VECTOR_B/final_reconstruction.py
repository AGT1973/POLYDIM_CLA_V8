import sys
import re

content = open('src/polydim_kernel.cpp').read()

# 1. PMTP_Control Fix
old_pmtp = """struct PMTP_Control {
    std::atomic<uint8_t> state; // Oldest(0:2), Middle(2:2), Newest(4:2), Dirty(6:1)
    std::atomic<uint32_t> seq[3];
    char _pad[64 - sizeof(std::atomic<uint8_t>) - 3*sizeof(std::atomic<uint32_t>)]; 
};"""
new_pmtp = """struct alignas(64) PMTP_Control {
    std::atomic<uint64_t> seq[3];
    std::atomic<uint8_t> state;
};"""
content = content.replace(old_pmtp, new_pmtp)

# 2. Arena Alignment Fix (128 bytes)
old_arena = """    // Pad thread arena to 64 bytes (8 doubles) to strictly prevent false sharing
    const size_t stride_doubles = (static_cast<size_t>(KK2) + 7) & ~7ULL;
    std::vector<double> arena;
    try { arena.assign(static_cast<size_t>(nthreads) * stride_doubles, 0.0); }
    catch (const std::bad_alloc&) { return POLYDIM_ERR_BUFFER_OVERFLOW; }"""
new_arena = """    // Pad thread arena to 128 bytes (16 doubles) for NVIDIA Grace and Sapphire Rapids
    const size_t stride_doubles = (static_cast<size_t>(KK2) + 15) & ~15ULL;
    size_t arena_bytes = static_cast<size_t>(nthreads) * stride_doubles * sizeof(double);
#if defined(_WIN32)
    double* arena_ptr = static_cast<double*>(_aligned_malloc(arena_bytes, 128));
#else
    void* ptr = nullptr;
    if (posix_memalign(&ptr, 128, arena_bytes) != 0) return POLYDIM_ERR_BUFFER_OVERFLOW;
    double* arena_ptr = static_cast<double*>(ptr);
#endif
    if (!arena_ptr) return POLYDIM_ERR_BUFFER_OVERFLOW;
    for(size_t i = 0; i < nthreads * stride_doubles; ++i) arena_ptr[i] = 0.0;"""
content = content.replace(old_arena, new_arena)

# Replace arena.data() with arena_ptr
content = content.replace("arena.data()", "arena_ptr")
content = content.replace("arena[", "arena_ptr[")

# Free arena_ptr at the end of function
content = content.replace("    if (report) report->ortho_error = err;", """    if (report) report->ortho_error = err;
#if defined(_WIN32)
    _aligned_free(arena_ptr);
#else
    free(arena_ptr);
#endif""")
content = content.replace("return POLYDIM_ERR_DEGENERATE_NORM;", """{
#if defined(_WIN32)
    _aligned_free(arena_ptr);
#else
    free(arena_ptr);
#endif
        return POLYDIM_ERR_DEGENERATE_NORM;
    }""")

# 3. Tikhonov Fix Native LU
old_native_tik = """double lambda = std::max(1e-15, tol.pivot_rel * m_inf); // Removed 1e-12 floor"""
new_native_tik = """double lambda = std::max(K2 * 2.22e-16 * m_inf, tol.pivot_rel * m_inf);"""
content = content.replace(old_native_tik, new_native_tik)

old_native_bypass = """            if (!(best > pivot_thr) && !needs_tikhonov) {
                // If it still fails after Tikhonov (or threshold is insanely high), abort
                if (report) report->pivot_min = pivot_min;
                return POLYDIM_ERR_NUMERICAL_INSTABILITY;
            }"""
new_native_bypass = """            if (!(best > pivot_thr)) {
                // Abort if pivot collapses even with Tikhonov
                if (report) report->pivot_min = pivot_min;
                return POLYDIM_ERR_NUMERICAL_INSTABILITY;
            }"""
content = content.replace(old_native_bypass, new_native_bypass)

# Tikhonov Fix BLAS
old_blas_tik = """double lambda = std::max(1e-15, tol.pivot_rel * m_inf); // Removed 1e-12 hardcoded floor"""
content = content.replace(old_blas_tik, new_native_tik)

# NaN Geometry Check
old_err = """        for (uint32_t c = i; c < K; ++c) {
            double s = 0.0;
            for (uint32_t j = 0; j < D; ++j) s += Y_out[j * K + r] * Y_out[j * K + c];
            err = std::max(err, std::abs(s - (r == c ? 1.0 : 0.0)));
        }"""
new_err = """        for (uint32_t c = i; c < K; ++c) {
            double s = 0.0;
            for (uint32_t j = 0; j < D; ++j) s += Y_out[j * K + r] * Y_out[j * K + c];
            if (std::isnan(s) || std::isinf(s)) {
#if defined(_WIN32)
                _aligned_free(arena_ptr);
#else
                free(arena_ptr);
#endif
                return POLYDIM_ERR_NAN_OR_INF;
            }
            err = std::max(err, std::abs(s - (r == c ? 1.0 : 0.0)));
        }"""
content = content.replace(old_err, new_err)

open('src/polydim_kernel.cpp', 'w').write(content)
print("Final reconstruction complete")
