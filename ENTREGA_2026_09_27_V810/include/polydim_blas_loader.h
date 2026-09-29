/**
 * @file polydim_blas_loader.h
 * @brief Cross-Platform Dynamic BLAS Loader (OpenBLAS / oneMKL) with Smoke Test and Tiled Fallback.
 *        V774: Added POSIX dlopen/dlsym support (Linux/macOS) alongside Win32 LoadLibrary.
 *        Silicon Contract: No hardcoded hardware parameters.
 * @copyright POLYDIM Architecture - 2026
 */

#ifndef POLYDIM_BLAS_LOADER_H
#define POLYDIM_BLAS_LOADER_H

/* ===== Platform-Specific Dynamic Loading Abstraction ===== */
#if defined(_WIN32) || defined(_WIN64)
  #define POLYDIM_PLATFORM_WINDOWS 1
  #define WIN32_LEAN_AND_MEAN
  #include <windows.h>
  typedef HMODULE polydim_dl_handle_t;
  #define POLYDIM_DL_NULL nullptr
#else
  #define POLYDIM_PLATFORM_POSIX 1
  #include <dlfcn.h>
  #include <sys/stat.h>
  typedef void* polydim_dl_handle_t;
  #define POLYDIM_DL_NULL nullptr
#endif

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <string>
#include <vector>
#include <memory>
#include <algorithm>

#if defined(_OPENMP)
#include <omp.h>
#endif

/* ===== CBLAS Enums (Portable) ===== */
enum CBLAS_LAYOUT : int { CblasRowMajor = 101, CblasColMajor = 102 };
enum CBLAS_TRANSPOSE : int { CblasNoTrans = 111, CblasTrans = 112, CblasConjTrans = 113 };
enum CBLAS_UPLO : int { CblasUpper = 121, CblasLower = 122 };

using blas_int = int32_t;
using cblas_dsyrk_fn = void (*)(int layout, int uplo, int trans, blas_int n, blas_int k,
                                double alpha, const double* a, blas_int lda,
                                double beta, double* c, blas_int ldc);

/* ===== Backend Handle ===== */
struct BlasBackend {
    polydim_dl_handle_t module = POLYDIM_DL_NULL;
    cblas_dsyrk_fn dsyrk = nullptr;
    std::string path;
    std::string name;

    bool available() const noexcept {
        return module != POLYDIM_DL_NULL && dsyrk != nullptr;
    }

    void unload() noexcept {
        if (module != POLYDIM_DL_NULL) {
#if defined(POLYDIM_PLATFORM_WINDOWS)
            FreeLibrary(module);
#else
            dlclose(module);
#endif
            module = POLYDIM_DL_NULL;
            dsyrk = nullptr;
        }
    }

    ~BlasBackend() {
        unload();
    }
};

/* ===== Main Loader Class (Singleton) ===== */
class BlasLoader {
public:
    static BlasLoader& instance() {
        static BlasLoader loader;
        return loader;
    }

    bool is_blas_loaded() const noexcept {
        return backend_ && backend_->available();
    }

    const char* backend_name() const noexcept {
        return backend_ ? backend_->name.c_str() : "tiled_fallback";
    }

    void compute_dsyrk(
        int layout, int uplo, int trans,
        size_t n, size_t k,
        double alpha, const double* a, size_t lda,
        double beta, double* c, size_t ldc,
        uint32_t num_threads
    ) {
        if (is_blas_loaded() && n <= static_cast<size_t>(INT32_MAX) && k <= static_cast<size_t>(INT32_MAX)) {
            backend_->dsyrk(
                layout, uplo, trans,
                static_cast<blas_int>(n), static_cast<blas_int>(k),
                alpha, a, static_cast<blas_int>(lda),
                beta, c, static_cast<blas_int>(ldc)
            );
            return;
        }
        tiled_dsyrk(layout, uplo, trans, n, k, alpha, a, lda, beta, c, ldc, num_threads);
    }

private:
    std::unique_ptr<BlasBackend> backend_;

    BlasLoader() {
        backend_ = load_blas_runtime();
    }

    static polydim_dl_handle_t safe_load_lib(const std::string& path) {
#if defined(POLYDIM_PLATFORM_WINDOWS)
        DWORD attrs = GetFileAttributesA(path.c_str());
        if (attrs == INVALID_FILE_ATTRIBUTES || (attrs & FILE_ATTRIBUTE_DIRECTORY)) {
            return POLYDIM_DL_NULL;
        }
        return LoadLibraryExA(
            path.c_str(),
            nullptr,
            LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS
        );
#else
        struct stat st;
        if (stat(path.c_str(), &st) != 0 || S_ISDIR(st.st_mode)) {
            return POLYDIM_DL_NULL;
        }
        return dlopen(path.c_str(), RTLD_NOW | RTLD_LOCAL);
#endif
    }

    static void unload_lib(polydim_dl_handle_t handle) {
        if (handle == POLYDIM_DL_NULL) return;
#if defined(POLYDIM_PLATFORM_WINDOWS)
        FreeLibrary(handle);
#else
        dlclose(handle);
#endif
    }

    static void* resolve_symbol(polydim_dl_handle_t handle, const char* symbol_name) {
        if (handle == POLYDIM_DL_NULL) return nullptr;
#if defined(POLYDIM_PLATFORM_WINDOWS)
        return reinterpret_cast<void*>(GetProcAddress(handle, symbol_name));
#else
        return dlsym(handle, symbol_name);
#endif
    }

    static cblas_dsyrk_fn resolve_dsyrk_symbol(polydim_dl_handle_t module) {
        if (module == POLYDIM_DL_NULL) return nullptr;
        void* sym = resolve_symbol(module, "cblas_dsyrk");
        if (sym) return reinterpret_cast<cblas_dsyrk_fn>(sym);
        sym = resolve_symbol(module, "cblas_dsyrk_");
        if (sym) return reinterpret_cast<cblas_dsyrk_fn>(sym);
        return nullptr;
    }

    static bool smoke_test_dsyrk(cblas_dsyrk_fn fn) {
        if (!fn) return false;
        const double a[6] = { 1.0, 2.0, 3.0, 4.0, 5.0, 6.0 };
        double c[9] = { 0.0 };
        fn(CblasRowMajor, CblasUpper, CblasNoTrans, 3, 2, 1.0, a, 2, 0.0, c, 3);
        if (std::abs(c[0] - 5.0)  > 1e-10) return false;
        if (std::abs(c[1] - 11.0) > 1e-10) return false;
        if (std::abs(c[2] - 17.0) > 1e-10) return false;
        if (std::abs(c[4] - 25.0) > 1e-10) return false;
        if (std::abs(c[5] - 33.0) > 1e-10) return false;
        if (std::abs(c[8] - 61.0) > 1e-10) return false;
        return true;
    }

    static std::string get_env(const char* name) {
#if defined(POLYDIM_PLATFORM_WINDOWS)
        char buf[32768];
        DWORD len = GetEnvironmentVariableA(name, buf, sizeof(buf));
        if (len > 0 && len < sizeof(buf)) return std::string(buf, len);
        return {};
#else
        const char* val = std::getenv(name);
        return val ? std::string(val) : std::string{};
#endif
    }

    static std::vector<std::string> get_candidate_paths() {
        std::vector<std::string> paths;

        auto explicit_path = get_env("POLYDIM_BLAS_DLL");
        if (!explicit_path.empty()) paths.push_back(explicit_path);

        auto mklroot = get_env("MKLROOT");
        if (!mklroot.empty()) {
#if defined(POLYDIM_PLATFORM_WINDOWS)
            paths.push_back(mklroot + "\\bin\\mkl_rt.dll");
#else
            paths.push_back(mklroot + "/lib/libmkl_rt.so");
            paths.push_back(mklroot + "/lib/libmkl_rt.dylib");
#endif
        }

        auto openblas = get_env("OPENBLAS_HOME");
        if (!openblas.empty()) {
#if defined(POLYDIM_PLATFORM_WINDOWS)
            paths.push_back(openblas + "\\bin\\libopenblas.dll");
            paths.push_back(openblas + "\\libopenblas.dll");
#else
            paths.push_back(openblas + "/lib/libopenblas.so");
            paths.push_back(openblas + "/lib/libopenblas.dylib");
#endif
        }

        auto conda = get_env("CONDA_PREFIX");
        if (!conda.empty()) {
#if defined(POLYDIM_PLATFORM_WINDOWS)
            paths.push_back(conda + "\\Library\\bin\\mkl_rt.dll");
            paths.push_back(conda + "\\Library\\bin\\libopenblas.dll");
#else
            paths.push_back(conda + "/lib/libmkl_rt.so");
            paths.push_back(conda + "/lib/libopenblas.so");
#endif
        }

#if defined(POLYDIM_PLATFORM_WINDOWS)
        paths.push_back("E:\\winlibs_gcc14_zip\\mingw64\\bin\\libopenblas.dll");
        paths.push_back("C:\\Python314\\Lib\\site-packages\\numpy.libs\\libopenblas.dll");
#else
        paths.push_back("/usr/lib/x86_64-linux-gnu/libopenblas.so");
        paths.push_back("/usr/lib/libopenblas.so");
        paths.push_back("/usr/local/lib/libopenblas.so");
        paths.push_back("/opt/OpenBLAS/lib/libopenblas.so");
        paths.push_back("/opt/conda/lib/libopenblas.so");
        paths.push_back("/usr/lib/x86_64-linux-gnu/libblas.so");
#endif

        return paths;
    }

    static std::unique_ptr<BlasBackend> load_blas_runtime() {
        auto candidates = get_candidate_paths();
        for (const auto& path : candidates) {
            auto mod = safe_load_lib(path);
            if (mod == POLYDIM_DL_NULL) continue;

            auto fn = resolve_dsyrk_symbol(mod);
            if (!fn) { unload_lib(mod); continue; }

            if (!smoke_test_dsyrk(fn)) { unload_lib(mod); continue; }

            auto backend = std::make_unique<BlasBackend>();
            backend->module = mod;
            backend->dsyrk = fn;
            backend->path = path;
            backend->name = (path.find("mkl") != std::string::npos) ? "oneMKL" : "OpenBLAS";
            return backend;
        }
        return nullptr;
    }

    static void tiled_dsyrk(
        int layout, int uplo, int trans,
        size_t n, size_t k,
        double alpha, const double* a, size_t lda,
        double beta, double* c, size_t ldc,
        uint32_t num_threads
    ) {
        constexpr size_t TILE_N = 32;
        constexpr size_t TILE_K = 32;

        int threads = (num_threads > 0) ? (int)num_threads : 1;
#if defined(_OPENMP)
        if (threads > 1) omp_set_num_threads(threads);
#endif

        if (trans == CblasTrans) {
            #pragma omp parallel for schedule(static) collapse(2)
            for (int64_t i0 = 0; i0 < (int64_t)n; i0 += TILE_N) {
                for (int64_t j0 = 0; j0 < (int64_t)n; j0 += TILE_N) {
                    if (j0 < i0) continue;
                    size_t i_max = std::min((size_t)(i0 + TILE_N), n);
                    size_t j_max = std::min((size_t)(j0 + TILE_N), n);
                    for (size_t k0 = 0; k0 < k; k0 += TILE_K) {
                        size_t k_max = std::min(k0 + TILE_K, k);
                        for (size_t i = (size_t)i0; i < i_max; ++i) {
                            size_t j_start = (i0 == j0) ? std::max(i, (size_t)j0) : (size_t)j0;
                            for (size_t j = j_start; j < j_max; ++j) {
                                double acc = 0.0;
                                #pragma omp simd reduction(+:acc)
                                for (size_t p = k0; p < k_max; ++p) {
                                    acc += a[p * lda + i] * a[p * lda + j];
                                }
                                #pragma omp atomic
                                c[i * ldc + j] += alpha * acc;
                            }
                        }
                    }
                }
            }
        } else {
            #pragma omp parallel for schedule(static) collapse(2)
            for (int64_t i0 = 0; i0 < (int64_t)n; i0 += TILE_N) {
                for (int64_t j0 = 0; j0 < (int64_t)n; j0 += TILE_N) {
                    if (j0 < i0) continue;
                    size_t i_max = std::min((size_t)(i0 + TILE_N), n);
                    size_t j_max = std::min((size_t)(j0 + TILE_N), n);
                    for (size_t k0 = 0; k0 < k; k0 += TILE_K) {
                        size_t k_max = std::min(k0 + TILE_K, k);
                        for (size_t i = (size_t)i0; i < i_max; ++i) {
                            size_t j_start = (i0 == j0) ? std::max(i, (size_t)j0) : (size_t)j0;
                            for (size_t j = j_start; j < j_max; ++j) {
                                double acc = 0.0;
                                #pragma omp simd reduction(+:acc)
                                for (size_t p = k0; p < k_max; ++p) {
                                    acc += a[i * lda + p] * a[j * lda + p];
                                }
                                #pragma omp atomic
                                c[i * ldc + j] += alpha * acc;
                            }
                        }
                    }
                }
            }
        }
    }
};

#endif /* POLYDIM_BLAS_LOADER_H */
