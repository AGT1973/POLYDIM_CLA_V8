#include <cstdint>
#include <cmath>
#include <cfloat>
#include <limits>
#include <atomic>
#include <stdexcept>
#include <cstring>
#include <omp.h>

#if defined(__x86_64__) || defined(_M_X64)
#include <immintrin.h>
#endif

#if defined(_WIN32)
#include <windows.h>
#else
#include <unistd.h>
#include <sys/types.h>
#include <linux/futex.h>
#include <sys/syscall.h>
#endif

// ============================================================================
// POLYDIM V801 - LATENT OS (GHOST PROTOCOL)
// SOTA C++ KERNEL - ASYMPTOTIC D=10^7, K<=512
//
// CHANGELOG vs V800 (see CHANGELOG_V801.md for full rationale + file:line refs):
//   [FIX-01] Removed ThreadScratchpad / PmtpHeader / pmtp_store_release.
//            They were declared but never instantiated or called anywhere in
//            V800 (confirmed by grep across the full source dossier). Dead
//            code that *looks* like a working IPC layer is worse than no
//            code: it implies a guarantee that does not exist. The PMTP
//            Zero-Copy IPC bus is NOT implemented in this version. Tracked
//            as future work, not shipped as a stub pretending to be real.
//   [FIX-02] polydim_wait_on_address: fixed 64->32 bit truncation on the
//            Linux futex path (was comparing only the low 32 bits of a
//            64-bit atomic via a naive int* cast -> UB / wrong on BE hosts).
//   [FIX-03] Y_out is no longer left "poisoned" with propagated garbage when
//            NaN/Inf is detected for a given element: that element is now
//            explicitly written as quiet_NaN so a caller that ignores the
//            non-zero return code still gets an unambiguous signal instead
//            of a plausible-looking wrong number.
//   [FIX-04] Added polydim_check_isa_support_v801(): a *runtime* CPUID probe
//            (Rule 27: "software interrogates, not assumes"). V800's build
//            recipe used -mavx2 on an AMD A4-6300 (Piledriver/Richland),
//            which does NOT support AVX2 (verified against public CPU
//            specs). The binary happened not to crash only because the
//            branchy NaN/Inf check blocked auto-vectorization of the hot
//            loop -- an accident, not a guarantee. This probe fails fast
//            with a clear diagnostic instead of a silent SIGILL risk.
//   [FIX-05] MAX_K_TILED renamed to MAX_K: V800 implied K-dimension cache
//            tiling that was never implemented (it was only ever used as a
//            validation bound, never as a blocking factor). Renamed to stop
//            over-promising; no tiling is actually needed for this kernel
//            since it is a single streaming pass with zero data reuse.
//   [FIX-06] Poison check rewritten as direct comparisons (x != x, fabs(x) >
//            DBL_MAX) instead of std::isnan/std::isinf calls: friendlier to
//            the auto-vectorizer, and avoids relying on <cmath>'s call ABI
//            in the hot loop.
//   [FIX-07] Added POLYDIM_STRICT_SUBNORMALS compile-time switch: V800's
//            FpuFtzDazGuard silently flushed ALL subnormal intermediate
//            values to zero for the entire thread -- including compensation
//            error terms `e` produced by two_sum/two_prod under catastrophic
//            cancellation, which directly undercuts the precision goal of
//            the Ogita-Rump-Oishi compensation on the same code path. That
//            trade-off is now explicit and can be turned off by the caller
//            who wants argument-value precision over legacy-CPU throughput.
//   [FIX-08] extern "C" exports use a POLYDIM_EXPORT macro instead of a bare
//            __declspec(dllexport), so this file also builds (and is now
//            compile-tested in this delivery) on non-Windows hosts.
// ============================================================================

#if defined(_WIN32)
  #define POLYDIM_EXPORT __declspec(dllexport)
#else
  #define POLYDIM_EXPORT __attribute__((visibility("default")))
#endif

constexpr int64_t MAX_K = 512; // [FIX-05] validation bound only, not a tile size.

// 3. FPU FTZ/DAZ GUARD
// [FIX-07] Documented trade-off: forcing DAZ/FTZ avoids the well-known
// subnormal microcode penalty on legacy AMD Bulldozer/Piledriver-family
// parts (e.g. the A4-6300 referenced in the Silicon Contract), but it also
// flushes any subnormal *compensation error term* produced mid-computation
// by two_sum/two_prod to zero, silently discarding part of what the
// Ogita-Rump-Oishi scheme exists to preserve. Define
// POLYDIM_STRICT_SUBNORMALS at compile time to disable the guard and keep
// full subnormal fidelity at the cost of throughput on affected CPUs.
class FpuFtzDazGuard {
#if !defined(POLYDIM_STRICT_SUBNORMALS) && (defined(__x86_64__) || defined(_M_X64))
    unsigned int original_mxcsr;
public:
    FpuFtzDazGuard() {
        original_mxcsr = _mm_getcsr();
        _mm_setcsr(original_mxcsr | 0x8040); // DAZ (0x0040) + FTZ (0x8000)
    }
    ~FpuFtzDazGuard() {
        _mm_setcsr(original_mxcsr);
    }
#elif !defined(POLYDIM_STRICT_SUBNORMALS) && defined(__aarch64__)
    uint64_t original_fpcr;
public:
    FpuFtzDazGuard() {
        __asm__ __volatile__("mrs %0, fpcr" : "=r"(original_fpcr));
        uint64_t new_fpcr = original_fpcr | (1ULL << 24) | (1ULL << 25); // FZ + FZDN (DAZ)
        __asm__ __volatile__("msr fpcr, %0" : : "r"(new_fpcr));
    }
    ~FpuFtzDazGuard() {
        __asm__ __volatile__("msr fpcr, %0" : : "r"(original_fpcr));
    }
#else
public:
    FpuFtzDazGuard() {}
    ~FpuFtzDazGuard() {}
#endif
};

// 4. VECTOR COMPENSATED SUMMATION (Ogita-Rump-Oishi) -- unchanged from V800,
// re-verified: two_sum (Knuth, unconditional) and two_prod (Dekker split +
// FMA fast path) are both correct error-free transforms.
inline void two_sum(double a, double b, double& s, double& e) {
    s = a + b;
    double bb = s - a;
    e = (a - (s - bb)) + (b - bb);
}

inline void two_prod(double a, double b, double& p, double& e) {
    p = a * b;
#if defined(__FMA__)
    e = std::fma(a, b, -p);
#else
    double C = 134217729.0; // 2^27 + 1
    double a1 = (a * C) - ((a * C) - a);
    double a2 = a - a1;
    double b1 = (b * C) - ((b * C) - b);
    double b2 = b - b1;
    e = (a2 * b2) - (((p - (a1 * b1)) - (a2 * b1)) - (a1 * b2));
#endif
}

inline void fma_two_sum(double a, double b, double c, double& s, double& e) {
    double p, err;
    two_prod(a, b, p, err);
    double s1, e1;
    two_sum(c, p, s1, e1);
    double e2, tmp;
    two_sum(e1, err, e2, tmp);
    s = s1;
    e = e2 + tmp;
}

extern "C" {

POLYDIM_EXPORT uint32_t polydim_abi_version() {
    return 801; // V801
}

// [FIX-04] Runtime ISA capability guard. Call this ONCE at process/library
// load time before any kernel call. Returns 0 if the binary's compiled
// instruction-set requirements are satisfied by the running CPU; a negative
// code otherwise, so the caller can fail fast with a clear message instead
// of risking SIGILL mid-computation.
POLYDIM_EXPORT int32_t polydim_check_isa_support_v801() {
#if defined(__GNUC__) && (defined(__x86_64__) || defined(_M_X64))
    __builtin_cpu_init();
#if defined(__AVX2__)
    if (!__builtin_cpu_supports("avx2")) return -10; // built for AVX2, CPU lacks it
#endif
#if defined(__FMA__)
    if (!__builtin_cpu_supports("fma")) return -11; // built for FMA3, CPU lacks it
#endif
#if defined(__AVX__) && !defined(__AVX2__)
    if (!__builtin_cpu_supports("avx")) return -12;
#endif
    return 0;
#else
    return 0; // Non-x86 (e.g. aarch64) or non-GCC/Clang: nothing to probe here.
#endif
}

POLYDIM_EXPORT int32_t polydim_kernel_cayley_smw_v801(
    double* __restrict X, double* __restrict U, double* __restrict V,
    int64_t D, int64_t K, double* __restrict Y_out)
{
    try {
        if (!X || !U || !V || !Y_out) return -1;
        if (D <= 0 || K <= 0 || K > MAX_K) return -2;

        uint64_t global_nan_flag = 0;
        const double qnan = std::numeric_limits<double>::quiet_NaN();

        // PARALLEL OVER D (ZERO HEAP ALLOCATION ON HOT PATH)
        #pragma omp parallel reduction(|:global_nan_flag)
        {
            FpuFtzDazGuard fpu_guard;
            uint64_t local_nan = 0;

            #pragma omp for schedule(static)
            for (int64_t i = 0; i < D; ++i) {
                for (int64_t j = 0; j < K; ++j) {
                    int64_t idx = i * K + j;
                    double x_val = X[idx];
                    double u_val = U[idx];
                    double v_val = V[idx];

                    // [FIX-06] direct-comparison poison check instead of
                    // std::isnan/std::isinf: friendlier to auto-vectorization.
                    bool poisoned =
                        (x_val != x_val) || (u_val != u_val) || (v_val != v_val) ||
                        (std::fabs(x_val) > DBL_MAX) ||
                        (std::fabs(u_val) > DBL_MAX) ||
                        (std::fabs(v_val) > DBL_MAX);

                    if (poisoned) {
                        local_nan |= 1;
                        Y_out[idx] = qnan; // [FIX-03] mark, don't propagate garbage
                        continue;
                    }

                    double s, e;
                    fma_two_sum(u_val, v_val, x_val, s, e);
                    Y_out[idx] = s + e;
                }
            }

            global_nan_flag |= local_nan;
        } // omp parallel

        if (global_nan_flag) {
            return -99; // ERR_NUMERICAL_NAN_OR_INF (Y_out has quiet_NaN at every poisoned index)
        }

        return 0; // Success

    } catch (...) {
        return -999; // C++ Exception caught at FFI boundary
    }
}

// [FIX-02] Corrected 64-bit-safe wait. NOTE: this still only compares the
// low 32 bits of the 64-bit word on Linux (FUTEX_WAIT is fundamentally a
// 32-bit-word primitive) -- but it now addresses the CORRECT 32-bit half
// (endianness-aware) and compares against a correctly masked expected
// value, instead of silently truncating via an `int` cast. Callers that
// need full 64-bit ABA-safety should pair this with a dedicated
// std::atomic<uint32_t> futex word rather than aliasing into a uint64_t.
POLYDIM_EXPORT void polydim_wait_on_address_v801(std::atomic<uint64_t>* addr, uint64_t expected_val, uint32_t timeout_ms) {
#if defined(_WIN32)
    WaitOnAddress(addr, &expected_val, sizeof(uint64_t), timeout_ms);
#else
    struct timespec ts = { static_cast<time_t>(timeout_ms / 1000), static_cast<long>((timeout_ms % 1000) * 1000000) };
    static_assert(sizeof(std::atomic<uint64_t>) == 8, "unexpected atomic<uint64_t> size");
    auto* word_ptr = reinterpret_cast<uint32_t*>(addr);
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
    uint32_t* target = word_ptr + 1;
#else
    uint32_t* target = word_ptr;
#endif
    uint32_t expected_low = static_cast<uint32_t>(expected_val & 0xFFFFFFFFULL);
    syscall(SYS_futex, target, FUTEX_WAIT_PRIVATE, expected_low, &ts, nullptr, 0);
#endif
}

} // extern "C"
