/**
 * @file polydim_blas_loader.h
 * @brief Cargador Dinámico Seguro de BLAS (OpenBLAS / oneMKL) en Runtime con Smoke Test y Fallback Tiled.
 * @copyright POLYDIM Architecture - 2026
 */

#ifndef POLYDIM_BLAS_LOADER_H
#define POLYDIM_BLAS_LOADER_H

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
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

enum CBLAS_LAYOUT : int { CblasRowMajor = 101, CblasColMajor = 102 };
enum CBLAS_TRANSPOSE : int { CblasNoTrans = 111, CblasTrans = 112, CblasConjTrans = 113 };
enum CBLAS_UPLO : int { CblasUpper = 121, CblasLower = 122 };

using blas_int = int32_t;
using cblas_dsyrk_fn = void (*)(int layout, int uplo, int trans, blas_int n, blas_int k, 
                                double alpha, const double* a, blas_int lda, 
                                double beta, double* c, blas_int ldc);

struct BlasBackend {
    HMODULE module = nullptr;
    cblas_dsyrk_fn dsyrk = nullptr;
    std::wstring path;
    std::string name;

    bool available() const noexcept {
        return module != nullptr && dsyrk != nullptr;
    }

    void unload() noexcept {
        if (module) {
            FreeLibrary(module);
            module = nullptr;
            dsyrk = nullptr;
        }
    }

    ~BlasBackend() {
        unload();
    }
};

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

    const std::wstring& backend_path() const noexcept {
        static const std::wstring empty_wstr;
        return backend_ ? backend_->path : empty_wstr;
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

        // Fallback: Micro-kernel Tiled L1/L2
        tiled_dsyrk(layout, uplo, trans, n, k, alpha, a, lda, beta, c, ldc, num_threads);
    }

private:
    std::unique_ptr<BlasBackend> backend_;

    BlasLoader() {
        backend_ = load_blas_runtime();
    }

    static HMODULE safe_load_dll(const std::wstring& path) {
        DWORD attrs = GetFileAttributesW(path.c_str());
        if (attrs == INVALID_FILE_ATTRIBUTES || (attrs & FILE_ATTRIBUTE_DIRECTORY)) {
            return nullptr;
        }
        return LoadLibraryExW(
            path.c_str(),
            nullptr,
            LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS
        );
    }

    static cblas_dsyrk_fn resolve_dsyrk_symbol(HMODULE module) {
        if (!module) return nullptr;
        FARPROC sym = GetProcAddress(module, "cblas_dsyrk");
        if (sym) return reinterpret_cast<cblas_dsyrk_fn>(sym);

        sym = GetProcAddress(module, "cblas_dsyrk_");
        if (sym) return reinterpret_cast<cblas_dsyrk_fn>(sym);

        return nullptr;
    }

    static bool smoke_test_dsyrk(cblas_dsyrk_fn fn) {
        if (!fn) return false;
        // Matriz A (3x2):
        // [ 1.0, 2.0 ]
        // [ 3.0, 4.0 ]
        // [ 5.0, 6.0 ]
        // A * A^T = [ 5, 11, 17 ]
        //           [ 11, 25, 33 ]
        //           [ 17, 33, 61 ]
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

    static std::vector<std::wstring> get_candidate_paths() {
        std::vector<std::wstring> paths;
        wchar_t buf[32768];

        // 1. Variable explícita POLYDIM_BLAS_DLL
        DWORD len = GetEnvironmentVariableW(L"POLYDIM_BLAS_DLL", buf, 32768);
        if (len > 0 && len < 32768) {
            paths.emplace_back(buf);
        }

        // 2. MKLROOT
        len = GetEnvironmentVariableW(L"MKLROOT", buf, 32768);
        if (len > 0 && len < 32768) {
            paths.emplace_back(std::wstring(buf) + L"\\bin\\mkl_rt.dll");
        }

        // 3. OPENBLAS_HOME
        len = GetEnvironmentVariableW(L"OPENBLAS_HOME", buf, 32768);
        if (len > 0 && len < 32768) {
            paths.emplace_back(std::wstring(buf) + L"\\bin\\libopenblas.dll");
            paths.emplace_back(std::wstring(buf) + L"\\libopenblas.dll");
        }

        // 4. CONDA_PREFIX
        len = GetEnvironmentVariableW(L"CONDA_PREFIX", buf, 32768);
        if (len > 0 && len < 32768) {
            paths.emplace_back(std::wstring(buf) + L"\\Library\\bin\\mkl_rt.dll");
            paths.emplace_back(std::wstring(buf) + L"\\Library\\bin\\libopenblas.dll");
        }

        // 5. Rutas estándar locales conocidas en el workspace
        paths.emplace_back(L"E:\\winlibs_gcc14_zip\\mingw64\\bin\\libopenblas.dll");
        paths.emplace_back(L"C:\\Python314\\Lib\\site-packages\\numpy.libs\\libopenblas.dll");
        paths.emplace_back(L"C:\\Users\\eluithi\\AppData\\Roaming\\Python\\Python314\\site-packages\\numpy.libs\\libopenblas.dll");

        return paths;
    }

    static std::unique_ptr<BlasBackend> load_blas_runtime() {
        auto candidates = get_candidate_paths();
        for (const auto& path : candidates) {
            HMODULE mod = safe_load_dll(path);
            if (!mod) continue;

            auto fn = resolve_dsyrk_symbol(mod);
            if (!fn) {
                FreeLibrary(mod);
                continue;
            }

            if (!smoke_test_dsyrk(fn)) {
                FreeLibrary(mod);
                continue;
            }

            auto backend = std::make_unique<BlasBackend>();
            backend->module = mod;
            backend->dsyrk = fn;
            backend->path = path;
            if (path.find(L"mkl") != std::wstring::npos) {
                backend->name = "oneMKL";
            } else {
                backend->name = "OpenBLAS";
            }
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
            // A es K x N (lda = N), calculamos A^T * A donde A^T es N x K
            #pragma omp parallel for schedule(static) collapse(2)
            for (size_t i0 = 0; i0 < n; i0 += TILE_N) {
                for (size_t j0 = 0; j0 < n; j0 += TILE_N) {
                    if (j0 < i0) continue; // Solo triángulo superior

                    size_t i_max = std::min(i0 + TILE_N, n);
                    size_t j_max = std::min(j0 + TILE_N, n);

                    for (size_t k0 = 0; k0 < k; k0 += TILE_K) {
                        size_t k_max = std::min(k0 + TILE_K, k);

                        for (size_t i = i0; i < i_max; ++i) {
                            size_t j_start = (i0 == j0) ? std::max(i, j0) : j0;
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
            // A es N x K (lda = K), calculamos A * A^T (N x N)
            #pragma omp parallel for schedule(static) collapse(2)
            for (size_t i0 = 0; i0 < n; i0 += TILE_N) {
                for (size_t j0 = 0; j0 < n; j0 += TILE_N) {
                    if (j0 < i0) continue;

                    size_t i_max = std::min(i0 + TILE_N, n);
                    size_t j_max = std::min(j0 + TILE_N, n);

                    for (size_t k0 = 0; k0 < k; k0 += TILE_K) {
                        size_t k_max = std::min(k0 + TILE_K, k);

                        for (size_t i = i0; i < i_max; ++i) {
                            size_t j_start = (i0 == j0) ? std::max(i, j0) : j0;
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

#endif // POLYDIM_BLAS_LOADER_H
