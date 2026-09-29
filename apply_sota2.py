import os
import re

cpp = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808\kernel_cpp_v808_1.cpp"
with open(cpp, "r", encoding="utf-8") as f: code = f.read()

code = code.replace("#include <atomic>", "#include <atomic>\n#include <immintrin.h>")

# Patch stream copy
old_stream = """extern "C" POLYDIM_API void polydim_stream_copy_nt(double* dest, const double* src, size_t count) {
    if (!dest || !src) return;
    size_t i = 0;
    if ((reinterpret_cast<uintptr_t>(dest) % 16 == 0) && count >= 2) {
        for (; i + 1 < count; i += 2) {
            std::atomic_thread_fence(std::memory_order_seq_cst);
        }
    }
    for (; i < count; ++i) dest[i] = src[i];
}"""

# Actually, the file had _mm_sfence() replaced by atomic fence earlier.
# Let's just regex replace the whole function.
new_stream = """extern "C" POLYDIM_API void polydim_stream_copy_nt(double* __restrict__ dest, const double* __restrict__ src, size_t count) {
    if (!dest || !src) return;
    size_t i = 0;
#if defined(__AVX512F__)
    if ((reinterpret_cast<uintptr_t>(dest) % 64 == 0) && count >= 8) {
        for (; i + 7 < count; i += 8) {
            _mm512_stream_pd(&dest[i], _mm512_loadu_pd(&src[i]));
        }
    }
#elif defined(__AVX__)
    if ((reinterpret_cast<uintptr_t>(dest) % 32 == 0) && count >= 4) {
        for (; i + 3 < count; i += 4) {
            _mm256_stream_pd(&dest[i], _mm256_loadu_pd(&src[i]));
        }
    }
#endif
    for (; i < count; ++i) dest[i] = src[i];
    std::atomic_thread_fence(std::memory_order_seq_cst);
}"""

code = re.sub(r'extern "C" POLYDIM_API void polydim_stream_copy_nt.*?\}', new_stream, code, flags=re.DOTALL)

# Patch compute_VtZ
old_vtz = """void compute_VtZ(const double* V, const double* Z, double* VtZ, size_t D, size_t K) {
    std::fill(VtZ, VtZ + K * K, 0.0);
    #pragma omp parallel
    {
        std::vector<double> local(K * K, 0.0);
        #pragma omp for schedule(static)
        for (int64_t d = 0; d < (int64_t)D; ++d) {
            for (size_t i = 0; i < K; ++i) {
                double vd = V[d * K + i];
                for (size_t j = 0; j < K; ++j) {
                    local[i * K + j] += vd * Z[d * K + j];
                }
            }
        }
        #pragma omp critical
        {
            for (size_t t = 0; t < K * K; ++t) VtZ[t] += local[t];
        }
    }
}"""
new_vtz = """void compute_VtZ(const double* __restrict__ V, const double* __restrict__ Z, double* __restrict__ VtZ, size_t D, size_t K) {
    std::fill(VtZ, VtZ + K * K, 0.0);
    int num_threads = omp_get_max_threads();
    std::vector<double> scratch(num_threads * K * K, 0.0);
    #pragma omp parallel
    {
        int tid = omp_get_thread_num();
        double* __restrict__ local = &scratch[tid * K * K];
        #pragma omp for schedule(static)
        for (int64_t d = 0; d < (int64_t)D; ++d) {
            for (size_t i = 0; i < K; ++i) {
                double vd = V[d * K + i];
                for (size_t j = 0; j < K; ++j) {
                    local[i * K + j] += vd * Z[d * K + j];
                }
            }
        }
        #pragma omp for schedule(static)
        for (int64_t t = 0; t < (int64_t)(K * K); ++t) {
            double sum = 0;
            for (int th = 0; th < num_threads; ++th) sum += scratch[th * K * K + t];
            VtZ[t] = sum;
        }
    }
}"""

if "void compute_VtZ" in code:
    code = re.sub(r'void compute_VtZ.*?\}\n\}', new_vtz, code, flags=re.DOTALL)
else:
    print("compute_VtZ not found, relying on previous definition")

with open(cpp, "w", encoding="utf-8") as f: f.write(code)
print("C++ Kernel SOTA Optimizations applied.")
