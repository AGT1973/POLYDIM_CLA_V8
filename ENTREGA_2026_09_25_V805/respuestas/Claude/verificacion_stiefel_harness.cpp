// Arnes: alimenta stiefel_cholqr con 2 columnas IDENTICAS (rank-deficient a
// proposito: exactamente el caso "agentes duplicados" que ya vimos romper el
// filtro de Rust). num_rows=8, num_cols=2.
#include "polydim_stiefel_v805.h"
#include <cstdio>
#include <cmath>

int main() {
    const size_t rows = 8, cols = 2;
    float input[rows*cols];
    for (size_t r = 0; r < rows; ++r) {
        input[0*rows + r] = (float)(r + 1);       // columna 0
        input[1*rows + r] = (float)(r + 1);       // columna 1 = columna 0 (rank-deficient)
    }
    float output[rows*cols];
    stiefel_cholqr(input, output, rows, cols);

    bool any_nan_or_inf = false;
    for (size_t i = 0; i < rows*cols; ++i) {
        if (std::isnan(output[i]) || std::isinf(output[i])) any_nan_or_inf = true;
    }
    printf("output[] = ");
    for (size_t i = 0; i < rows*cols; ++i) printf("%f ", output[i]);
    printf("\n%s\n", any_nan_or_inf ? "*** NaN/Inf PRODUCIDO ***" : "sin NaN/Inf");
    return 0;
}
