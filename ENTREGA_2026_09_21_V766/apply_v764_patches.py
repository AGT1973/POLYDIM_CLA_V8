import os
import re

base_dir = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_20_V764"
cpp_file = os.path.join(base_dir, "src", "polydim_kernel.cpp")
h_file = os.path.join(base_dir, "include", "polydim.h")

with open(cpp_file, 'r', encoding='utf-8') as f:
    cpp_content = f.read()

with open(h_file, 'r', encoding='utf-8') as f:
    h_content = f.read()

# PATCH A: PMTP Wait-Free SPSC Triple Buffer
pmtp_old = r'''struct PMTP_Control \{.*?char _pad\[64\];.*?};'''
pmtp_new = '''struct PMTP_Control {
    alignas(64) std::atomic<uint8_t> state;
};'''
cpp_content = re.sub(pmtp_old, pmtp_new, cpp_content, flags=re.DOTALL)

# Reemplazo de funciones PMTP
funcs_old = r'extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_init.*?POLYDIM_ERR_SEQLOCK_RACE;\s*}'
funcs_new = '''extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_init(PMTP_Control* c) {
    if (!c) return;
    c->state.store(0x24, std::memory_order_release);
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_begin_write(PMTP_Control* c, uint64_t* slot_out) {
    if (!c || !slot_out) return POLYDIM_ERR_NULL_POINTER;
    uint8_t s = c->state.load(std::memory_order_acquire);
    *slot_out = (s >> 4) & 3;
    return POLYDIM_SUCCESS;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_commit_write(PMTP_Control* c, uint64_t slot) {
    if (!c) return POLYDIM_ERR_NULL_POINTER;
    uint8_t s = c->state.load(std::memory_order_relaxed);
    uint8_t next_s;
    do {
        uint8_t oldest = s & 3;
        uint8_t middle = (s >> 2) & 3;
        uint8_t newest = (s >> 4) & 3;
        next_s = oldest | (newest << 2) | (middle << 4) | (1 << 6);
    } while (!c->state.compare_exchange_weak(s, next_s, std::memory_order_release, std::memory_order_relaxed));
    return POLYDIM_SUCCESS;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_acquire_read(
    PMTP_Control* c, uint64_t* observed_seq, uint64_t* slot_out, uint64_t* ticket_out)
{
    if (!c || !observed_seq || !slot_out || !ticket_out) return POLYDIM_ERR_NULL_POINTER;
    uint8_t s = c->state.load(std::memory_order_acquire);
    if (!(s & (1 << 6))) return 0;
    uint8_t next_s;
    do {
        uint8_t oldest = s & 3;
        uint8_t middle = (s >> 2) & 3;
        uint8_t newest = (s >> 4) & 3;
        next_s = middle | (oldest << 2) | (newest << 4);
    } while (!c->state.compare_exchange_weak(s, next_s, std::memory_order_acquire, std::memory_order_relaxed));
    *slot_out = middle;
    *observed_seq = 1;
    *ticket_out = 0;
    return 1;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_validate_read(
    const PMTP_Control* c, uint64_t slot, uint64_t ticket)
{
    if (!c) return POLYDIM_ERR_NULL_POINTER;
    return POLYDIM_SUCCESS;
}'''
cpp_content = re.sub(funcs_old, funcs_new, cpp_content, flags=re.DOTALL)

# PATCH B: Retracción Tangente en Cayley-SMW
patch_b_anchor = r'    /\* Y = X \+ tau \* U Z,  U = \[G X\].'
patch_b_code = '''    /* B. Retracción Tangente en Cayley-SMW: Z_2 <- Z_2 - 0.5 * X^T G Z_1 */
    #pragma omp parallel for num_threads(nthreads) schedule(static)
    for (int64_t r = K; r < static_cast<int64_t>(K2); ++r) {
        for (uint32_t c = 0; c < K; ++c) {
            double s = 0.0;
            for (uint32_t q = 0; q < K; ++q) {
                s += XtG(static_cast<uint32_t>(r - K), q) * Z[static_cast<size_t>(q) * K + c];
            }
            Z[static_cast<size_t>(r) * K + c] -= 0.5 * s;
        }
    }

    /* Y = X + tau * U Z,  U = [G X].'''
cpp_content = re.sub(patch_b_anchor, patch_b_code, cpp_content)

# PATCH C: Hardening FFI
def add_restrict(c):
    replacements = [
        ("const double* y, const double* u, const double* v, double* y_out",
         "const double* __restrict__ y, const double* __restrict__ u, const double* __restrict__ v, double* __restrict__ y_out"),
        ("const double* y, double* y_out",
         "const double* __restrict__ y, double* __restrict__ y_out"),
        ("double* u, double* v",
         "double* __restrict__ u, double* __restrict__ v"),
        ("const double* X, const double* G, double* Y_out",
         "const double* __restrict__ X, const double* __restrict__ G, double* __restrict__ Y_out"),
        ("const double* X, const double* G, double* G_out",
         "const double* __restrict__ X, const double* __restrict__ G, double* __restrict__ G_out"),
        ("const PolydimTolerances* tol_in, PolydimReport* report",
         "const PolydimTolerances* __restrict__ tol_in, PolydimReport* __restrict__ report"),
        ("const PolydimTolerances* tol, PolydimReport* report",
         "const PolydimTolerances* __restrict__ tol, PolydimReport* __restrict__ report"),
        ("uint64_t D, PolydimReport* report",
         "uint64_t D, PolydimReport* __restrict__ report")
    ]
    for o, n in replacements:
        c = c.replace(o, n)
    return c

cpp_content = add_restrict(cpp_content)
h_content = add_restrict(h_content)

with open(cpp_file, 'w', encoding='utf-8') as f:
    f.write(cpp_content)
with open(h_file, 'w', encoding='utf-8') as f:
    f.write(h_content)

print("Patches A, B, y C aplicados en C++ y H.")
