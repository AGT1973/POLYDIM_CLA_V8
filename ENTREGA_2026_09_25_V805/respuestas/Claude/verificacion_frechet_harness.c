#include <stdio.h>
#include <string.h>
#include <stdint.h>

typedef struct __attribute__((aligned(128))) {
    int32_t status;
    uint32_t num_candidates;
    uint32_t dimension;
    uint32_t connected_components_betti0;
    int64_t cycles_betti1;
    uint32_t consensus_node_idx;
    uint32_t active_swarm_count;
    uint32_t rejected_outliers_count;
    double frechet_residual;
    unsigned char is_consensus_certified;
} PolydimFrechetBettiResult;

extern int32_t polydim_rust_frechet_betti_filter(
    const double* candidates_ptr,
    uint32_t num_candidates,
    uint32_t dimension,
    double dist_threshold,
    int64_t max_tau_betti1,
    double* out_consensus_vector,
    PolydimFrechetBettiResult* out_result
);

int main() {
    uint32_t n = 5, d = 4;
    double candidates[20];
    for (uint32_t i = 0; i < n; i++)
        for (uint32_t k = 0; k < d; k++)
            candidates[i*d+k] = 1.0;  // agentes idénticos -> varianza EXACTA = 0

    double out_consensus[4];
    PolydimFrechetBettiResult out_result;

    memset(out_consensus, 0xAB, sizeof(out_consensus));
    memset(&out_result, 0xCD, sizeof(out_result));

    int32_t status = polydim_rust_frechet_betti_filter(
        candidates, n, d, 1.0, 100, out_consensus, &out_result);

    printf("=== RESULTADO EMPIRICO ===\n");
    printf("NativeStatus devuelto: %d  (0 = Ok)\n", status);
    printf("out_consensus_vector tras la llamada: %.2f %.2f %.2f %.2f  (veneno 0xAB = -21.06 en double repr basura)\n",
           out_consensus[0], out_consensus[1], out_consensus[2], out_consensus[3]);
    printf("out_result.active_swarm_count = %u  (si quedo en veneno: %u)\n",
           out_result.active_swarm_count, 0xCDCDCDCDu);
    printf("out_result.is_consensus_certified (byte crudo) = 0x%02X (veneno = 0xCD)\n",
           out_result.is_consensus_certified);
    return 0;
}
