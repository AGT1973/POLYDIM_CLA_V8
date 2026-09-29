import os

# Patch ipc_futex_v808_1.cpp
futex_path = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808\ipc_futex_v808_1.cpp"
with open(futex_path, "r") as f:
    futex_code = f.read()

if "#include <cstdint>" not in futex_code:
    futex_code = futex_code.replace("#include <stdio.h>", "#include <stdio.h>\n#include <cstdint>\n#include <atomic>")

with open(futex_path, "w") as f:
    f.write(futex_code)


# Patch kernel_cpp_v808_1.cpp
kernel_path = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808\kernel_cpp_v808_1.cpp"
with open(kernel_path, "r") as f:
    kernel_code = f.read()

cblas_enums = """
enum CBLAS_ORDER { CblasRowMajor=101, CblasColMajor=102 };
enum CBLAS_TRANSPOSE { CblasNoTrans=111, CblasTrans=112, CblasConjTrans=113 };
enum CBLAS_UPLO { CblasUpper=121, CblasLower=122 };

static void tiled_dsyrk_fixed(int trans, size_t n, size_t k,
                              double alpha, const double* a, size_t lda,
                              double beta, double* c, size_t ldc);
"""

if "enum CBLAS_ORDER" not in kernel_code:
    kernel_code = kernel_code.replace("#define TILE_D 32", cblas_enums + "\n#define TILE_D 32")

# Replace BlasLoader usage
kernel_code = kernel_code.replace(
    "BlasLoader::instance().compute_dsyrk(CblasRowMajor, CblasUpper, CblasTrans,\n            K, D, 1.0, X, K, 0.0, K_out, K, num_threads);",
    "tiled_dsyrk_fixed(CblasTrans, K, D, 1.0, X, K, 0.0, K_out, K);"
)
kernel_code = kernel_code.replace(
    "BlasLoader::instance().compute_dsyrk(CblasRowMajor, CblasUpper, CblasTrans, K, D, 1.0, X, K, 0.0, K_out, K, num_threads);",
    "tiled_dsyrk_fixed(CblasTrans, K, D, 1.0, X, K, 0.0, K_out, K);"
)


with open(kernel_path, "w") as f:
    f.write(kernel_code)

print("Patching applied natively.")
