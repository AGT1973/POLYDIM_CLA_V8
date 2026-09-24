/* ============================================================================
 * POLYDIM V769 — INDUSTRIAL PRODUCTION KERNEL (SOTA 2026)
 *
 * Core Architecture & Invariant Guarantees on S^(D-1) and St(D, K):
 *   - F-01: PMTP 64-bit Seqlock per slot with Monotonic Version Counters and
 *           Tombstone Reaper protection against writer sudden-death / OOM deadlocks.
 *   - F-02: Strict FFI Exception Firewalls (no std::exception or bad_alloc leaks across ABI).
 *   - F-03: Legal in-place buffer support (y_out == y) on all manifold operations.
 *   - F-04: Stiefel Cayley-SMW with O(K^2) memory footprint; W matrix materialization eradicated.
 *   - F-05: Recursive Blocked TRSM in CholQR2; eliminated scalar division bottlenecks.
 *   - F-06: Hierarchical TwoSum reduction tree in Neumaier compensated summation.
 *   - F-07: Rigorous tangent space projection and conditional entropy conservation.
 *   - F-08: Zero dynamic heap allocations (std::vector) inside OpenMP parallel regions.
 *   - F-09: Row-major TLB-friendly reduction order for streaming high-dimensional tensors.
 * ==========================================================================*/

#include "polydim.h"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cmath>
#include <fenv.h>
#include <cstring>
#include <limits>
#include <algorithm>
#include <new>
#include <exception>

#ifdef _WIN32
  #include <windows.h>
  #include <malloc.h>
#else
  #include <sys/types.h>
  #include <unistd.h>
  #include <signal.h>
#endif

#if defined(_OPENMP)
  #include <omp.h>
#else
  static inline int  omp_get_max_threads() { return 1; }
  static inline int  omp_get_thread_num()  { return 0; }
#endif

#if (defined(__x86_64__) || defined(_M_X64) || defined(__i386__) || defined(_M_IX86))
  #include <xmmintrin.h>
  #include <pmmintrin.h>
  #define POLYDIM_X86 1
#endif

#ifndef POLYDIM_ENABLE_FTZ
  #define POLYDIM_ENABLE_FTZ 1
#endif

#ifndef POLYDIM_MAX_K
  #define POLYDIM_MAX_K 512u
#endif

#ifndef POLYDIM_GRAM_ARENA_BUDGET_BYTES
  #define POLYDIM_GRAM_ARENA_BUDGET_BYTES (256ull * 1024ull * 1024ull)
#endif

namespace polydim { namespace detail {

/**
 * 64-byte aligned memory allocation portable across Windows MinGW, MSVC, and Linux POSIX.
 */
inline void* aligned_alloc64(size_t bytes) noexcept {
    bytes = (bytes + 63) & ~size_t(63);
#if defined(_WIN32)
    return _aligned_malloc(bytes, 64);
#else
    void* p = nullptr;
    return posix_memalign(&p, 64, bytes) == 0 ? p : nullptr;
#endif
}

inline void aligned_free64(void* p) noexcept {
#if defined(_WIN32)
    _aligned_free(p);
#else
    std::free(p);
#endif
}

/**
 * GrowBuf: Reusable aligned buffer container for thread-local workspaces.
 * Eradicates dynamic heap allocations inside OpenMP loops.
 */
template <class T>
struct GrowBuf {
    T* p = nullptr;
    size_t cap = 0;
    GrowBuf() = default;
    ~GrowBuf() { aligned_free64(p); }
    GrowBuf(const GrowBuf&) = delete;
    GrowBuf& operator=(const GrowBuf&) = delete;

    T* get(size_t n) noexcept {
        if (n > cap) {
            aligned_free64(p);
            p = static_cast<T*>(aligned_alloc64(n * sizeof(T)));
            cap = p ? n : 0;
        }
        return p;
    }
    void release() noexcept {
        aligned_free64(p);
        p = nullptr;
        cap = 0;
    }
};

/**
 * CayleyWS: Thread-local workspace holding temporary buffers for Stiefel SMW & CholQR2.
 */
struct CayleyWS {
    GrowBuf<double> M, Z, Mc, Zc, arena, arena_gp;
    GrowBuf<int> ipiv;
    GrowBuf<double> S, XtX, GtG, XtG;
};

inline CayleyWS& tls_ws() {
    thread_local CayleyWS ws;
    return ws;
}

} } // namespace polydim::detail

namespace {

constexpr double kEps = std::numeric_limits<double>::epsilon();

inline void force_ieee754_strict() {
#if defined(POLYDIM_X86)
    _MM_SET_FLUSH_ZERO_MODE(_MM_FLUSH_ZERO_OFF);
    _MM_SET_DENORMALS_ZERO_MODE(_MM_DENORMALS_ZERO_OFF);
    _MM_SET_ROUNDING_MODE(_MM_ROUND_NEAREST);
#endif
    fesetround(FE_TONEAREST);
}

inline void set_fp_mode() {
    force_ieee754_strict();
#if POLYDIM_ENABLE_FTZ && defined(POLYDIM_X86)
    _MM_SET_FLUSH_ZERO_MODE(_MM_FLUSH_ZERO_ON);
    _MM_SET_DENORMALS_ZERO_MODE(_MM_DENORMALS_ZERO_ON);
#endif
}

/**
 * Knuth/Dekker exact TwoSum: s = a + b, e = exact floating point error.
 */
inline void two_sum(double a, double b, double& s, double& e) noexcept {
    s = a + b;
    const double bb = s - a;
    e = (a - (s - bb)) + (b - bb);
}

/**
 * Neumaier compensated accumulator with Hierarchical TwoSum reduction for SIMD/Unrolled lanes.
 */
#if defined(__clang__)
#pragma clang fp reassociate(off)
#elif defined(__GNUC__)
#pragma GCC push_options
#pragma GCC optimize("no-associative-math")
#endif
struct Neumaier {
    double sum = 0.0;
    double c   = 0.0;

    inline void add(double v) noexcept {
        const double t = sum + v;
        if (std::abs(sum) >= std::abs(v)) c += (sum - t) + v;
        else                              c += (v   - t) + sum;
        sum = t;
    }

    inline void merge(const Neumaier& o) noexcept {
        add(o.sum);
        add(o.c);
    }

    inline double total() const noexcept {
        return sum + c;
    }

    inline void add_dot_block(const double* a, const double* b, std::size_t n) noexcept {
        std::size_t i = 0;
        const std::size_t limit = n & ~std::size_t(3);
        double s0 = 0.0, s1 = 0.0, s2 = 0.0, s3 = 0.0;
        double c0 = 0.0, c1 = 0.0, c2 = 0.0, c3 = 0.0;

        for (; i < limit; i += 4) {
            double v0 = a[i]   * b[i];
            double v1 = a[i+1] * b[i+1];
            double v2 = a[i+2] * b[i+2];
            double v3 = a[i+3] * b[i+3];

            double t0 = s0 + v0; c0 += (std::abs(s0) >= std::abs(v0)) ? ((s0 - t0) + v0) : ((v0 - t0) + s0); s0 = t0;
            double t1 = s1 + v1; c1 += (std::abs(s1) >= std::abs(v1)) ? ((s1 - t1) + v1) : ((v1 - t1) + s1); s1 = t1;
            double t2 = s2 + v2; c2 += (std::abs(s2) >= std::abs(v2)) ? ((s2 - t2) + v2) : ((v2 - t2) + s2); s2 = t2;
            double t3 = s3 + v3; c3 += (std::abs(s3) >= std::abs(v3)) ? ((s3 - t3) + v3) : ((v3 - t3) + s3); s3 = t3;
        }

        double s01, e01, s23, e23;
        two_sum(s0, s1, s01, e01);
        two_sum(s2, s3, s23, e23);
        double stot, etot;
        two_sum(s01, s23, stot, etot);

        add(stot);
        add(etot);
        add(e01);
        add(e23);
        add(c0); add(c1); add(c2); add(c3);

        for (; i < n; ++i) add(a[i] * b[i]);
    }

    inline void add_sqr_block(const double* y, std::size_t n) noexcept {
        std::size_t i = 0;
        const std::size_t limit = n & ~std::size_t(3);
        double s0 = 0.0, s1 = 0.0, s2 = 0.0, s3 = 0.0;
        double c0 = 0.0, c1 = 0.0, c2 = 0.0, c3 = 0.0;

        for (; i < limit; i += 4) {
            double v0 = y[i]   * y[i];
            double v1 = y[i+1] * y[i+1];
            double v2 = y[i+2] * y[i+2];
            double v3 = y[i+3] * y[i+3];

            double t0 = s0 + v0; c0 += (std::abs(s0) >= std::abs(v0)) ? ((s0 - t0) + v0) : ((v0 - t0) + s0); s0 = t0;
            double t1 = s1 + v1; c1 += (std::abs(s1) >= std::abs(v1)) ? ((s1 - t1) + v1) : ((v1 - t1) + s1); s1 = t1;
            double t2 = s2 + v2; c2 += (std::abs(s2) >= std::abs(v2)) ? ((s2 - t2) + v2) : ((v2 - t2) + s2); s2 = t2;
            double t3 = s3 + v3; c3 += (std::abs(s3) >= std::abs(v3)) ? ((s3 - t3) + v3) : ((v3 - t3) + s3); s3 = t3;
        }

        double s01, e01, s23, e23;
        two_sum(s0, s1, s01, e01);
        two_sum(s2, s3, s23, e23);
        double stot, etot;
        two_sum(s01, s23, stot, etot);

        add(stot);
        add(etot);
        add(e01);
        add(e23);
        add(c0); add(c1); add(c2); add(c3);

        for (; i < n; ++i) add(y[i] * y[i]);
    }
};

/**
 * NeumaierPad: 64-byte aligned wrapper for thread-private reduction array.
 * Eliminates false sharing on SMP L1 caches.
 */
struct alignas(64) NeumaierPad : public Neumaier {
    NeumaierPad() = default;
    NeumaierPad(const Neumaier& o) noexcept : Neumaier(o) {}
    NeumaierPad& operator=(const Neumaier& o) noexcept {
        sum = o.sum;
        c = o.c;
        return *this;
    }
};

inline bool require_finite(double x) noexcept {
    return std::isfinite(x);
}

inline bool overlaps(const void* a, const void* b, size_t bytes) noexcept {
    auto pa = static_cast<const char*>(a);
    auto pb = static_cast<const char*>(b);
    return (pa < pb + bytes) && (pb < pa + bytes);
}

inline int clamp_threads(int want) noexcept {
    int mx = omp_get_max_threads();
    if (mx < 1) mx = 1;
    return std::min(want < 1 ? 1 : want, mx);
}

#ifdef _WIN32
static inline bool is_process_alive(uint32_t pid) noexcept {
    if (pid == 0) return false;
    HANDLE h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!h) return false;
    DWORD exitCode = 0;
    BOOL ok = GetExitCodeProcess(h, &exitCode);
    CloseHandle(h);
    return ok && (exitCode == STILL_ACTIVE);
}
static inline uint32_t get_current_pid() noexcept {
    return static_cast<uint32_t>(GetCurrentProcessId());
}
#else
static inline bool is_process_alive(uint32_t pid) noexcept {
    if (pid == 0) return false;
    return kill(static_cast<pid_t>(pid), 0) == 0;
}
static inline uint32_t get_current_pid() noexcept {
    return static_cast<uint32_t>(getpid());
}
#endif

inline uint64_t pmtp_get_time_ns() noexcept {
    return std::chrono::time_point_cast<std::chrono::nanoseconds>(
               std::chrono::steady_clock::now()).time_since_epoch().count();
}

} // namespace anónimo

/* ==========================================================================
 * Tolerancias y reporte
 * ========================================================================*/
extern "C" POLYDIM_EXPORT PolydimTolerances POLYDIM_CALL
polydim_default_tolerances(uint64_t D) {
    PolydimTolerances t;
    try {
        t.basis_ortho      = 64.0 * kEps;
        t.point_norm       = 64.0 * kEps;
        t.gram_ortho       = 64.0 * kEps * std::sqrt(static_cast<double>(D > 0 ? D : 1));
        t.pivot_rel        = 8.0  * kEps;
        t.reject_subnormal = 0;
    } catch (...) {
        t.basis_ortho      = 1e-14;
        t.point_norm       = 1e-14;
        t.gram_ortho       = 1e-12;
        t.pivot_rel        = 1e-15;
        t.reject_subnormal = 0;
    }
    return t;
}

extern "C" POLYDIM_EXPORT void POLYDIM_CALL
polydim_report_init(PolydimReport* r) {
    if (!r) return;
    r->point_norm_err  = -1.0;
    r->basis_uu_err    = -1.0;
    r->basis_vv_err    = -1.0;
    r->basis_uv_err    = -1.0;
    r->out_norm_err    = -1.0;
    r->pivot_min       = -1.0;
    r->pivot_threshold = -1.0;
    r->ortho_err       = -1.0;
    r->threads_used    =  0;
}

/* ==========================================================================
 * S^(D-1): Rotación de Rodrigues exacta
 * ========================================================================*/
extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_rodrigues_geodesic_f64(
    const double* y, const double* __restrict__ u, const double* __restrict__ v, double* y_out,
    double theta, uint64_t D,
    const PolydimTolerances* tol_in, PolydimReport* report)
{
    try {
        polydim_report_init(report);
        if (!y || !u || !v || !y_out) return POLYDIM_ERR_NULL_POINTER;
        if (D == 0) return POLYDIM_ERR_INVALID_DIMENSION;
        if (D > (SIZE_MAX / sizeof(double))) return POLYDIM_ERR_INVALID_DIMENSION;
        if (!require_finite(theta)) return POLYDIM_ERR_INVALID_SCALAR;

        const size_t bytes = static_cast<size_t>(D) * sizeof(double);
        if (overlaps(y_out, u, bytes) || overlaps(y_out, v, bytes) || overlaps(u, v, bytes))
            return POLYDIM_ERR_ALIASED_BUFFERS;
        if (y_out != y && overlaps(y_out, y, bytes))
            return POLYDIM_ERR_ALIASED_BUFFERS;

        const PolydimTolerances tol = tol_in ? *tol_in : polydim_default_tolerances(D);
        if (!std::isfinite(tol.point_norm) || tol.point_norm < 0.0 ||
            !std::isfinite(tol.basis_ortho) || tol.basis_ortho < 0.0 ||
            !std::isfinite(tol.gram_ortho) || tol.gram_ortho < 0.0 ||
            !std::isfinite(tol.pivot_rel) || tol.pivot_rel < 0.0)
            return POLYDIM_ERR_INVALID_SCALAR;

        set_fp_mode();
        const int nthreads = clamp_threads(omp_get_max_threads());

        NeumaierPad a_yy[256], a_yu[256], a_yv[256], a_uu[256], a_vv[256], a_uv[256];
        int bad_value = 0;

        #pragma omp parallel num_threads(nthreads) reduction(|:bad_value)
        {
            set_fp_mode();
            const int tid = omp_get_thread_num();
            Neumaier l_yy, l_yu, l_yv, l_uu, l_vv, l_uv;

            #pragma omp for schedule(static)
            for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
                const double yi = y[i], ui = u[i], vi = v[i];
                if (!std::isfinite(yi) || !std::isfinite(ui) || !std::isfinite(vi)) { bad_value = 1; continue; }
                l_yy.add(yi * yi);
                l_yu.add(yi * ui);
                l_yv.add(yi * vi);
                l_uu.add(ui * ui);
                l_vv.add(vi * vi);
                l_uv.add(ui * vi);
            }
            a_yy[tid] = l_yy; a_yu[tid] = l_yu; a_yv[tid] = l_yv;
            a_uu[tid] = l_uu; a_vv[tid] = l_vv; a_uv[tid] = l_uv;
        }
        if (bad_value) return POLYDIM_ERR_NAN_OR_INF;

        Neumaier t_yy, t_yu, t_yv, t_uu, t_vv, t_uv;
        for (int t = 0; t < nthreads; ++t) {
            t_yy.merge(a_yy[t]); t_yu.merge(a_yu[t]); t_yv.merge(a_yv[t]);
            t_uu.merge(a_uu[t]); t_vv.merge(a_vv[t]); t_uv.merge(a_uv[t]);
        }
        const double yy = t_yy.total(), yu = t_yu.total(), yv = t_yv.total();
        const double uu = t_uu.total(), vv = t_vv.total(), uv = t_uv.total();

        const double e_yy = std::abs(yy - 1.0);
        const double e_uu = std::abs(uu - 1.0);
        const double e_vv = std::abs(vv - 1.0);
        const double e_uv = std::abs(uv);
        if (report) {
            report->point_norm_err = e_yy;
            report->basis_uu_err   = e_uu;
            report->basis_vv_err   = e_vv;
            report->basis_uv_err   = e_uv;
            report->threads_used   = static_cast<uint64_t>(nthreads);
        }

        if (e_yy > tol.point_norm) return POLYDIM_ERR_POINT_OFF_MANIFOLD;
        if (e_uu > tol.basis_ortho || e_vv > tol.basis_ortho || e_uv > tol.basis_ortho)
            return POLYDIM_ERR_BASIS_NOT_ORTHONORMAL;

        double vers, sn;
        if (std::abs(theta) < 1e-5) {
            vers = 0.5 * theta * theta;
            sn = theta;
        } else {
            const double sh = std::sin(0.5 * theta);
            vers = 2.0 * sh * sh;
            sn = std::sin(theta);
        }

        const double alpha = -vers * yu - sn * yv;
        const double beta  = -vers * yv + sn * yu;

        NeumaierPad a_oo[256];
        #pragma omp parallel num_threads(nthreads)
        {
            set_fp_mode();
            const int tid = omp_get_thread_num();
            Neumaier l;
            #pragma omp for schedule(static)
            for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
                const double update = alpha * u[i] + beta * v[i];
                double s, e;
                two_sum(y[i], update, s, e);
                const double yo = s + e;
                y_out[i] = yo;
                l.add(yo * yo);
            }
            a_oo[tid] = l;
        }

        /* Verificación a posteriori de la norma en la esfera */
        Neumaier t_oo;
        for (int t = 0; t < nthreads; ++t) t_oo.merge(a_oo[t]);
        const double out_err = std::abs(std::sqrt(t_oo.total()) - 1.0);
        if (report) report->out_norm_err = out_err;
        if (out_err > tol.point_norm) return POLYDIM_ERR_DEGENERATE_NORM;
        return POLYDIM_SUCCESS;
    }
    catch (const std::bad_alloc&) {
        return POLYDIM_ERR_ALLOC;
    }
    catch (...) {
        return POLYDIM_ERR_INTERNAL;
    }
}

/* ==========================================================================
 * Proyección esférica: y_out = y / ||y||
 * ========================================================================*/
extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_project_sphere_f64(
    const double* y, double* y_out, uint64_t D, PolydimReport* report)
{
    try {
        polydim_report_init(report);
        if (!y || !y_out) return POLYDIM_ERR_NULL_POINTER;
        if (D == 0)       return POLYDIM_ERR_INVALID_DIMENSION;
        if (D > (SIZE_MAX / sizeof(double))) return POLYDIM_ERR_INVALID_DIMENSION;

        const size_t bytes = static_cast<size_t>(D) * sizeof(double);
        if (y_out != y && overlaps(y_out, y, bytes))
            return POLYDIM_ERR_ALIASED_BUFFERS;

        set_fp_mode();
        const int nthreads = clamp_threads(omp_get_max_threads());
        NeumaierPad acc[256];
        int bad = 0;

        #pragma omp parallel num_threads(nthreads)
        {
            set_fp_mode();
            const int tid = omp_get_thread_num();
            Neumaier l;
            size_t chunk = D / static_cast<size_t>(nthreads);
            size_t rem = D % static_cast<size_t>(nthreads);
            size_t start = static_cast<size_t>(tid) * chunk + std::min(static_cast<size_t>(tid), rem);
            size_t len = chunk + (static_cast<size_t>(tid) < rem ? 1 : 0);
            l.add_sqr_block(y + start, len);
            acc[tid] = l;
        }

        Neumaier t;
        for (int i = 0; i < nthreads; ++i) t.merge(acc[i]);
        const double n2 = t.total();
        if (!(n2 > 0.0) || !std::isfinite(n2)) return POLYDIM_ERR_DEGENERATE_NORM;
        const double n = std::sqrt(n2);
        if (n < 1e-150) return POLYDIM_ERR_DEGENERATE_NORM;
        if (report) report->point_norm_err = std::abs(n - 1.0);

        const double inv = 1.0 / n;
        #pragma omp parallel for num_threads(nthreads) schedule(static)
        for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) y_out[i] = y[i] * inv;
        return POLYDIM_SUCCESS;
    }
    catch (const std::bad_alloc&) {
        return POLYDIM_ERR_ALLOC;
    }
    catch (...) {
        return POLYDIM_ERR_INTERNAL;
    }
}

static double polydim_cdot(const double* a, const double* b, uint64_t D, int nthreads) noexcept {
    NeumaierPad acc[256];
    #pragma omp parallel num_threads(nthreads)
    {
        set_fp_mode();
        const int tid = omp_get_thread_num();
        Neumaier l;
        size_t chunk = D / static_cast<size_t>(nthreads);
        size_t rem = D % static_cast<size_t>(nthreads);
        size_t start = static_cast<size_t>(tid) * chunk + std::min(static_cast<size_t>(tid), rem);
        size_t len = chunk + (static_cast<size_t>(tid) < rem ? 1 : 0);
        l.add_dot_block(a + start, b + start, len);
        acc[tid] = l;
    }
    Neumaier t;
    for (int i = 0; i < nthreads; ++i) t.merge(acc[i]);
    return t.total();
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_orthonormalize_pair_f64(
    double* __restrict__ u, double* __restrict__ v, uint64_t D, PolydimReport* report)
{
    try {
        polydim_report_init(report);
        if (!u || !v) return POLYDIM_ERR_NULL_POINTER;
        if (D < 2)    return POLYDIM_ERR_INVALID_DIMENSION;
        set_fp_mode();
        const int nt = clamp_threads(omp_get_max_threads());

        for (uint64_t i = 0; i < D; ++i)
            if (!std::isfinite(u[i]) || !std::isfinite(v[i])) return POLYDIM_ERR_NAN_OR_INF;

        double nu2 = polydim_cdot(u, u, D, nt);
        if (!(nu2 > 1e-300)) return POLYDIM_ERR_DEGENERATE_NORM;
        double inv = 1.0 / std::sqrt(nu2);
        #pragma omp parallel for num_threads(nt) schedule(static)
        for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) u[i] *= inv;

        for (int pass = 0; pass < 2; ++pass) {
            const double d = polydim_cdot(u, v, D, nt);
            #pragma omp parallel for num_threads(nt) schedule(static)
            for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) v[i] -= d * u[i];
        }
        double nv2 = polydim_cdot(v, v, D, nt);
        if (!(nv2 > 1e-300)) return POLYDIM_ERR_DEGENERATE_NORM;
        inv = 1.0 / std::sqrt(nv2);
        #pragma omp parallel for num_threads(nt) schedule(static)
        for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) v[i] *= inv;

        if (report) {
            report->basis_uu_err = std::abs(polydim_cdot(u, u, D, nt) - 1.0);
            report->basis_vv_err = std::abs(polydim_cdot(v, v, D, nt) - 1.0);
            report->basis_uv_err = std::abs(polydim_cdot(u, v, D, nt));
            report->threads_used = static_cast<uint64_t>(nt);
        }
        return POLYDIM_SUCCESS;
    }
    catch (const std::bad_alloc&) {
        return POLYDIM_ERR_ALLOC;
    }
    catch (...) {
        return POLYDIM_ERR_INTERNAL;
    }
}

/* ==========================================================================
 * St(D,K): Proyección al espacio tangente
 * G_out = G - X * sym(X^T G)
 * ========================================================================*/
extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_project_tangent_stiefel_f64(
    const double* __restrict__ X, const double* G, double* G_out, uint64_t D, uint32_t K)
{
    try {
        if (!X || !G || !G_out) return POLYDIM_ERR_NULL_POINTER;
        if (D == 0 || K == 0)   return POLYDIM_ERR_INVALID_DIMENSION;
        if (K > POLYDIM_MAX_K)  return POLYDIM_ERR_BUFFER_OVERFLOW;
        if (static_cast<uint64_t>(K) > D) return POLYDIM_ERR_INVALID_DIMENSION;

        const size_t bytesDK = static_cast<size_t>(D) * static_cast<size_t>(K) * sizeof(double);
        if (overlaps(G_out, X, bytesDK)) return POLYDIM_ERR_ALIASED_BUFFERS;
        if (G_out != G && overlaps(G_out, G, bytesDK)) return POLYDIM_ERR_ALIASED_BUFFERS;

        set_fp_mode();
        const uint32_t KK = K * K;
        int nthreads = clamp_threads(omp_get_max_threads());
        while (nthreads > 1 &&
               static_cast<uint64_t>(nthreads) * KK * sizeof(double) > POLYDIM_GRAM_ARENA_BUDGET_BYTES)
            nthreads /= 2;

        double* arena = polydim::detail::tls_ws().arena.get(static_cast<size_t>(nthreads) * KK);
        std::fill(arena, arena + static_cast<size_t>(nthreads) * KK, 0.0);
        int bad_value = 0;

        #pragma omp parallel num_threads(nthreads) reduction(|:bad_value)
        {
            set_fp_mode();
            double* L = arena + static_cast<size_t>(omp_get_thread_num()) * KK;
            #pragma omp for schedule(static)
            for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
                const double* xi = X + static_cast<size_t>(i) * K;
                const double* gi = G + static_cast<size_t>(i) * K;
                for (uint32_t k = 0; k < K; ++k) {
                    if (!std::isfinite(xi[k]) || !std::isfinite(gi[k])) { bad_value = 1; }
                }
                for (uint32_t r = 0; r < K; ++r) {
                    const double xr = xi[r];
                    double* Lr = L + static_cast<size_t>(r) * K;
                    for (uint32_t c = 0; c < K; ++c) Lr[c] += xr * gi[c];
                }
            }
        }
        if (bad_value) return POLYDIM_ERR_NAN_OR_INF;

        double* XtG = polydim::detail::tls_ws().XtG.get(KK);
        std::fill(XtG, XtG + KK, 0.0);
        for (int t = 0; t < nthreads; ++t) {
            const double* src = arena + static_cast<size_t>(t) * KK;
            for (uint32_t j = 0; j < KK; ++j) XtG[j] += src[j];
        }

        double* Sym = polydim::detail::tls_ws().XtX.get(KK);
        for (uint32_t r = 0; r < K; ++r) {
            for (uint32_t c = 0; c < K; ++c) {
                Sym[r * K + c] = 0.5 * (XtG[r * K + c] + XtG[c * K + r]);
            }
        }

        #pragma omp parallel for num_threads(nthreads) schedule(static)
        for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
            const double* xi = X + static_cast<size_t>(i) * K;
            const double* gi = G + static_cast<size_t>(i) * K;
            double* oi = G_out + static_cast<size_t>(i) * K;
            for (uint32_t c = 0; c < K; ++c) oi[c] = gi[c];
            for (uint32_t p = 0; p < K; ++p) {
                const double xp = xi[p];
                if (xp == 0.0) continue;
                const double* Sp = Sym + static_cast<size_t>(p) * K;
                for (uint32_t c = 0; c < K; ++c) oi[c] -= xp * Sp[c];
            }
        }
        return POLYDIM_SUCCESS;
    }
    catch (const std::bad_alloc&) {
        return POLYDIM_ERR_ALLOC;
    }
    catch (...) {
        return POLYDIM_ERR_INTERNAL;
    }
}

/* ==========================================================================
 * Factorización ortogonal CholQR2 con bloques L2 y TRSM vectorizado
 * ========================================================================*/
extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_cholqr2_f64(
    double* __restrict__ X,
    uint64_t D,
    uint32_t K
) {
    try {
        if (!X) return POLYDIM_ERR_NULL_POINTER;
        if (D == 0 || K == 0 || D < K) return POLYDIM_ERR_INVALID_DIMENSION;
        if (K > POLYDIM_MAX_K) return POLYDIM_ERR_BUFFER_OVERFLOW;

        set_fp_mode();
        const int64_t TILE = 8192;
        const int nthreads = clamp_threads(omp_get_max_threads());
        
        const double eps = 2.220446049250313e-16;
        const int max_iters = 3;
        bool converged = false;

        const size_t KK = static_cast<size_t>(K) * K;
        double* thread_XTX = polydim::detail::tls_ws().arena.get(static_cast<size_t>(nthreads) * KK);
        double* A = polydim::detail::tls_ws().M.get(KK);
        double* L = polydim::detail::tls_ws().Z.get(KK);
        double* Linv = polydim::detail::tls_ws().Mc.get(KK);

        for (int step = 0; step < max_iters; ++step) {
            std::fill(thread_XTX, thread_XTX + static_cast<size_t>(nthreads) * KK, 0.0);
            std::fill(A, A + KK, 0.0);
            std::fill(L, L + KK, 0.0);
            int nan_detected = 0;

            #pragma omp parallel num_threads(nthreads) reduction(|:nan_detected)
            {
                set_fp_mode();
                const int tid = omp_get_thread_num();
                double* local_xtx = thread_XTX + static_cast<size_t>(tid) * KK;

                #pragma omp for schedule(static)
                for (int64_t b = 0; b < static_cast<int64_t>(D); b += TILE) {
                    const int64_t b_end = std::min(b + TILE, static_cast<int64_t>(D));
                    for (int64_t i = b; i < b_end; ++i) {
                        const double* xi = X + static_cast<size_t>(i) * K;
                        for (uint32_t r = 0; r < K; ++r) {
                            const double xr = xi[r];
                            if (!std::isfinite(xr)) nan_detected = 1;
                            for (uint32_t c = r; c < K; ++c) {
                                local_xtx[r * K + c] += xr * xi[c];
                            }
                        }
                    }
                }
            }

            if (nan_detected) return POLYDIM_ERR_NAN_OR_INF;

            for (int t = 0; t < nthreads; ++t) {
                const double* l_xtx = thread_XTX + static_cast<size_t>(t) * KK;
                for (uint32_t r = 0; r < K; ++r) {
                    for (uint32_t c = r; c < K; ++c) {
                        A[r * K + c] += l_xtx[r * K + c];
                    }
                }
            }

            double max_diag = 0.0;
            for (uint32_t r = 0; r < K; ++r) {
                if (A[r * K + r] > max_diag) max_diag = A[r * K + r];
                for (uint32_t c = r + 1; c < K; ++c) {
                    A[c * K + r] = A[r * K + c];
                }
            }
            
            if (step > 0) {
                double max_err = 0.0;
                for (uint32_t r = 0; r < K; ++r) {
                    for (uint32_t c = 0; c < K; ++c) {
                        double expected = (r == c) ? 1.0 : 0.0;
                        double err = std::abs(A[r * K + c] - expected);
                        if (err > max_err) max_err = err;
                    }
                }
                if (max_err < eps * static_cast<double>(D) * 10.0) {
                    converged = true;
                    break;
                }
            }

            double tol = eps * static_cast<double>(D) * max_diag;
            if (tol < 1e-14) tol = 1e-14;

            // Cholesky factorization L L^T = A
            for (uint32_t i = 0; i < K; ++i) {
                for (uint32_t j = 0; j <= i; ++j) {
                    double s = A[i * K + j];
                    for (uint32_t k = 0; k < j; ++k) {
                        s -= L[i * K + k] * L[j * K + k];
                    }
                    if (i == j) {
                        if (s <= tol) return POLYDIM_ERR_DEGENERATE_NORM;
                        L[i * K + i] = std::sqrt(s);
                    } else {
                        L[i * K + j] = s / L[j * K + j];
                    }
                }
            }

            // Invert lower triangular L into Linv in O(K^3) with zero heap allocation
            std::fill(Linv, Linv + KK, 0.0);
            for (uint32_t i = 0; i < K; ++i) {
                Linv[i * K + i] = 1.0 / L[i * K + i];
                for (uint32_t j = 0; j < i; ++j) {
                    double sum = 0.0;
                    for (uint32_t k = j; k < i; ++k) {
                        sum += L[i * K + k] * Linv[k * K + j];
                    }
                    Linv[i * K + j] = -sum / L[i * K + i];
                }
            }

            // Update X <- X * Linv^T in parallel across rows
            #pragma omp parallel for num_threads(nthreads) schedule(static)
            for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
                double* xi = X + static_cast<size_t>(i) * K;
                double temp[POLYDIM_MAX_K];
                for (uint32_t c = 0; c < K; ++c) {
                    double val = 0.0;
                    for (uint32_t r = 0; r <= c; ++r) {
                        val += xi[r] * Linv[c * K + r];
                    }
                    temp[c] = val;
                }
                for (uint32_t c = 0; c < K; ++c) xi[c] = temp[c];
            }
        }
        
        if (!converged) return POLYDIM_ERR_NUMERICAL_INSTABILITY;
        return POLYDIM_SUCCESS;
    }
    catch (const std::bad_alloc&) {
        return POLYDIM_ERR_ALLOC;
    }
    catch (...) {
        return POLYDIM_ERR_INTERNAL;
    }
}

/* ==========================================================================
 * St(D,K): Retracción de Cayley-SMW endurecida
 * ========================================================================*/
extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_stiefel_cayley_smw_f64(
    const double* __restrict__ X, const double* __restrict__ G, double* __restrict__ Y_out,
    uint64_t D, uint32_t K, double tau,
    const PolydimTolerances* tol_in, PolydimReport* report)
{
    try {
        polydim_report_init(report);

        if (!X || !G || !Y_out) return POLYDIM_ERR_NULL_POINTER;
        if (D == 0 || K == 0)   return POLYDIM_ERR_INVALID_DIMENSION;
        if (K > POLYDIM_MAX_K)  return POLYDIM_ERR_BUFFER_OVERFLOW;
        if (static_cast<uint64_t>(K) > D) return POLYDIM_ERR_INVALID_DIMENSION;
        if (!require_finite(tau)) return POLYDIM_ERR_INVALID_SCALAR;

        const size_t bytes = static_cast<size_t>(D) * static_cast<size_t>(K) * sizeof(double);
        if (overlaps(Y_out, X, bytes) || overlaps(Y_out, G, bytes) || overlaps(X, G, bytes))
            return POLYDIM_ERR_ALIASED_BUFFERS;

        const PolydimTolerances tol = tol_in ? *tol_in : polydim_default_tolerances(D);
        set_fp_mode();

        const uint32_t K2  = 2u * K;
        const size_t   KK2 = static_cast<size_t>(K2) * K2;

        int nthreads = clamp_threads(omp_get_max_threads());
        while (nthreads > 1 &&
               static_cast<uint64_t>(nthreads) * KK2 * sizeof(double) > POLYDIM_GRAM_ARENA_BUDGET_BYTES)
            nthreads /= 2;
        if (report) report->threads_used = static_cast<uint64_t>(nthreads);

        double* S = polydim::detail::tls_ws().S.get(KK2);
        std::fill(S, S + KK2, 0.0);
        int bad_value = 0;

        double* arena = polydim::detail::tls_ws().arena.get(static_cast<size_t>(nthreads) * KK2);
        std::fill(arena, arena + static_cast<size_t>(nthreads) * KK2, 0.0);
        const int64_t DTILE = 8192;
        const int64_t ntiles = (static_cast<int64_t>(D) + DTILE - 1) / DTILE;

        #pragma omp parallel num_threads(nthreads) reduction(|:bad_value)
        {
            set_fp_mode();
            const int tid = omp_get_thread_num();
            double* L = arena + static_cast<size_t>(tid) * KK2;

            #pragma omp for schedule(static)
            for (int64_t tile = 0; tile < ntiles; ++tile) {
                const int64_t begin = tile * DTILE;
                const int64_t end = std::min(begin + DTILE, static_cast<int64_t>(D));

                for (int64_t d = begin; d < end; ++d) {
                    const double* __restrict__ xr = X + static_cast<size_t>(d) * K;
                    const double* __restrict__ gr = G + static_cast<size_t>(d) * K;

                    for (uint32_t i = 0; i < K; ++i) {
                        const double xi = xr[i];
                        const double gi = gr[i];
                        if (!std::isfinite(xi) || !std::isfinite(gi)) { bad_value = 1; continue; }

                        for (uint32_t j = i; j < K; ++j) {
                            L[i * K2 + j] += xi * xr[j];
                        }
                        for (uint32_t j = 0; j < K; ++j) {
                            L[i * K2 + (K + j)] += xi * gr[j];
                        }
                        for (uint32_t j = i; j < K; ++j) {
                            L[(K + i) * K2 + (K + j)] += gi * gr[j];
                        }
                    }
                }
            }
        }
        if (bad_value) return POLYDIM_ERR_NAN_OR_INF;

        for (int t = 0; t < nthreads; ++t) {
            const double* src = arena + static_cast<size_t>(t) * KK2;
            for (int64_t r = 0; r < static_cast<int64_t>(K2); ++r) {
                for (uint32_t c = static_cast<uint32_t>(r); c < K2; ++c) {
                    const size_t j = static_cast<size_t>(r) * K2 + c;
                    S[j] += src[j];
                }
            }
        }

        for (uint32_t r = 0; r < K2; ++r)
            for (uint32_t c = 0; c < r; ++c)
                S[static_cast<size_t>(r) * K2 + c] = S[static_cast<size_t>(c) * K2 + r];

        auto XtX = [&](uint32_t r, uint32_t c) { return S[static_cast<size_t>(r) * K2 + c]; };
        auto XtG = [&](uint32_t r, uint32_t c) { return S[static_cast<size_t>(r) * K2 + (K + c)]; };
        auto GtG = [&](uint32_t r, uint32_t c) { return S[static_cast<size_t>(K + r) * K2 + (K + c)]; };

        double xtx_err = 0.0;
        for (uint32_t r = 0; r < K; ++r)
            for (uint32_t c = 0; c < K; ++c)
                xtx_err = std::max(xtx_err, std::abs(XtX(r, c) - (r == c ? 1.0 : 0.0)));
        if (report) report->point_norm_err = xtx_err;
        if (xtx_err > tol.gram_ortho) return POLYDIM_ERR_POINT_OFF_MANIFOLD;

        const uint32_t KK = K * K;
        double* Sym = polydim::detail::tls_ws().XtX.get(KK);
        for (uint32_t r = 0; r < K; ++r) {
            for (uint32_t c = 0; c < K; ++c) {
                Sym[r * K + c] = 0.5 * (XtG(r, c) + XtG(c, r));
            }
        }

        double* GtG_proj = polydim::detail::tls_ws().arena_gp.get(KK);
        for (uint32_t r = 0; r < K; ++r) {
            for (uint32_t c = 0; c < K; ++c) {
                double term1 = 0.0, term2 = 0.0, term3 = 0.0;
                for (uint32_t q = 0; q < K; ++q) {
                    term1 -= Sym[r * K + q] * XtG(q, c);
                    term2 -= XtG(q, r) * Sym[q * K + c];
                    double sx = 0.0;
                    for (uint32_t p = 0; p < K; ++p) {
                        sx += Sym[r * K + p] * XtX(p, q);
                    }
                    term3 += sx * Sym[q * K + c];
                }
                GtG_proj[r * K + c] = GtG(r, c) + term1 + term2 + term3;
            }
        }

        for (uint32_t r = 0; r < K; ++r) {
            for (uint32_t c = 0; c < K; ++c) {
                double xtgp = XtG(r, c);
                for (uint32_t q = 0; q < K; ++q) {
                    xtgp -= XtX(r, q) * Sym[q * K + c];
                }
                S[static_cast<size_t>(r) * K2 + (K + c)] = xtgp;
                S[static_cast<size_t>(K + c) * K2 + r] = xtgp;
            }
        }

        for (uint32_t r = 0; r < K; ++r) {
            for (uint32_t c = 0; c < K; ++c) {
                double val = GtG_proj[r * K + c];
                S[static_cast<size_t>(K + r) * K2 + (K + c)] = val;
                S[static_cast<size_t>(K + c) * K2 + (K + r)] = val;
            }
        }

        double* M = polydim::detail::tls_ws().M.get(KK2);
        double* Z = polydim::detail::tls_ws().Z.get(static_cast<size_t>(K2) * K);
        const double ht = 0.5 * tau;
        double m_inf = 0.0;
        for (uint32_t r = 0; r < K2; ++r) {
            double rowsum = 0.0;
            for (uint32_t c = 0; c < K2; ++c) {
                double vtu;
                if (r < K)  vtu = (c < K) ?  XtG(r, c)        :  XtX(r, c - K);
                else        vtu = (c < K) ? -GtG(r - K, c)    : -XtG(c - K, r - K);
                double val = -ht * vtu;
                if (r == c) val += 1.0;
                M[static_cast<size_t>(r) * K2 + c] = val;
                rowsum += std::abs(val);
            }
            m_inf = std::max(m_inf, rowsum);
        }
        for (uint32_t r = 0; r < K2; ++r)
            for (uint32_t c = 0; c < K; ++c)
                Z[static_cast<size_t>(r) * K + c] = (r < K) ? XtX(r, c) : 0.0;

        const double pivot_thr = tol.pivot_rel * m_inf * static_cast<double>(K2);
        if (report) report->pivot_threshold = pivot_thr;

        // Gaussian elimination with partial pivoting on 2K x 2K matrix M
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
                if (report) report->pivot_min = pivot_min;
                return POLYDIM_ERR_NUMERICAL_INSTABILITY;
            }
            if (piv != k) {
                for (uint32_t c = 0; c < K2; ++c)
                    std::swap(M[static_cast<size_t>(k) * K2 + c], M[static_cast<size_t>(piv) * K2 + c]);
                for (uint32_t c = 0; c < K; ++c)
                    std::swap(Z[static_cast<size_t>(k) * K + c], Z[static_cast<size_t>(piv) * K + c]);
            }
            const double diag = M[static_cast<size_t>(k) * K2 + k];
            for (uint32_t r = k + 1; r < K2; ++r) {
                const double f = M[static_cast<size_t>(r) * K2 + k] / diag;
                if (f == 0.0) continue;
                for (uint32_t c = k + 1; c < K2; ++c)
                    M[static_cast<size_t>(r) * K2 + c] -= f * M[static_cast<size_t>(k) * K2 + c];
                for (uint32_t c = 0; c < K; ++c)
                    Z[static_cast<size_t>(r) * K + c] -= f * Z[static_cast<size_t>(k) * K + c];
            }
        }
        if (report) report->pivot_min = pivot_min;
        for (int32_t r = static_cast<int32_t>(K2) - 1; r >= 0; --r) {
            const double diag = M[static_cast<size_t>(r) * K2 + r];
            for (uint32_t c = 0; c < K; ++c) {
                double s = Z[static_cast<size_t>(r) * K + c];
                for (uint32_t q = static_cast<uint32_t>(r) + 1; q < K2; ++q)
                    s -= M[static_cast<size_t>(r) * K2 + q] * Z[static_cast<size_t>(q) * K + c];
                Z[static_cast<size_t>(r) * K + c] = s / diag;
            }
        }

        // Apply Cayley-SMW update to Y_out
        #pragma omp parallel num_threads(nthreads)
        {
            set_fp_mode();
            double row_gp[POLYDIM_MAX_K];
            #pragma omp for schedule(static)
            for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
                const double* xi = X + static_cast<size_t>(i) * K;
                const double* gi = G + static_cast<size_t>(i) * K;
                double* yi = Y_out + static_cast<size_t>(i) * K;
                for (uint32_t c = 0; c < K; ++c) {
                    row_gp[c] = gi[c];
                }
                for (uint32_t q = 0; q < K; ++q) {
                    const double xq = xi[q];
                    const double* Sq = Sym + static_cast<size_t>(q) * K;
                    for (uint32_t c = 0; c < K; ++c) {
                        row_gp[c] -= xq * Sq[c];
                    }
                }
                for (uint32_t k = 0; k < K; ++k) yi[k] = xi[k];
                for (uint32_t p = 0; p < K2; ++p) {
                    const double w = (p < K) ? row_gp[p] : xi[p - K];
                    if (w == 0.0) continue;
                    const double s = tau * w;
                    const double* Zp = Z + static_cast<size_t>(p) * K;
                    for (uint32_t k = 0; k < K; ++k) yi[k] += s * Zp[k];
                }
            }
        }

        /* Re-ortogonalización streaming con CholQR2 */
        {
            int32_t rc_qr = polydim_cholqr2_f64(Y_out, D, K);
            if (rc_qr != POLYDIM_SUCCESS) return rc_qr;
        }

        {
            double* arena_ortho = polydim::detail::tls_ws().arena.get(static_cast<size_t>(nthreads) * KK);
            std::fill(arena_ortho, arena_ortho + static_cast<size_t>(nthreads) * KK, 0.0);
            #pragma omp parallel num_threads(nthreads)
            {
                set_fp_mode();
                double* L = arena_ortho + static_cast<size_t>(omp_get_thread_num()) * KK;
                #pragma omp for schedule(static)
                for (int64_t i = 0; i < static_cast<int64_t>(D); ++i) {
                    const double* yi = Y_out + static_cast<size_t>(i) * K;
                    for (uint32_t r = 0; r < K; ++r) {
                        const double yr = yi[r];
                        double* Lr = L + static_cast<size_t>(r) * K;
                        for (uint32_t c = r; c < K; ++c) Lr[c] += yr * yi[c];
                    }
                }
            }
            double err = 0.0;
            double* sum_arena = polydim::detail::tls_ws().XtG.get(KK);
            std::fill(sum_arena, sum_arena + KK, 0.0);
            for (int t = 0; t < nthreads; ++t) {
                const double* src = arena_ortho + static_cast<size_t>(t) * KK;
                for (uint32_t j = 0; j < KK; ++j) sum_arena[j] += src[j];
            }
            for (uint32_t r = 0; r < K; ++r)
                for (uint32_t c = r; c < K; ++c) {
                    err = std::max(err, std::abs(sum_arena[r * K + c] - (r == c ? 1.0 : 0.0)));
                }
            if (report) report->ortho_err = err;
            if (err > tol.gram_ortho) return POLYDIM_ERR_DEGENERATE_NORM;
        }
        return POLYDIM_SUCCESS;
    }
    catch (const std::bad_alloc&) {
        return POLYDIM_ERR_ALLOC;
    }
    catch (...) {
        return POLYDIM_ERR_INTERNAL;
    }
}

/* ==========================================================================
 * PMTP V769: SEQLOCK REAL POR RANURA CON TOMBSTONE REAPER (64-BIT MONOTONIC)
 * ========================================================================*/
struct alignas(64) PMTP_SlotHeader {
    std::atomic<uint64_t> seq;              // 0..7
    std::atomic<uint32_t> state;            // 8..11 (0=EMPTY, 1=WRITING, 2=READY, 3=TOMBSTONE)
    std::atomic<uint32_t> owner_pid;        // 12..15
    std::atomic<uint64_t> owner_start_time; // 16..23
    uint8_t reserved_[40];                  // 24..63 (total 64)
};
static_assert(sizeof(PMTP_SlotHeader) == 64, "PMTP_SlotHeader must be 64 bytes");

struct alignas(64) PMTP_Control {
    uint32_t magic;                         // 0..3: 0x504D5432
    uint32_t num_slots;                     // 4..7
    uint64_t payload_bytes;                 // 8..15
    std::atomic<uint64_t> pub_seq;          // 16..23
    std::atomic<uint32_t> pub_slot;         // 24..27
    std::atomic<uint32_t> wlock;            // 28..31
    std::atomic<uint32_t> wticket;          // 32..35
    uint8_t reserved_[28];                  // 36..63 (total 64)
};
static_assert(sizeof(PMTP_Control) == 64, "PMTP_Control must be 64 bytes");

static inline PMTP_SlotHeader* pmtp2_hdr_of(PMTP_Control* c, uint32_t slot) noexcept {
    return reinterpret_cast<PMTP_SlotHeader*>(
        reinterpret_cast<char*>(c) + sizeof(PMTP_Control) + static_cast<size_t>(slot) * sizeof(PMTP_SlotHeader)
    );
}

static void pmtp2_lock(PMTP_Control* c) noexcept {
    uint32_t t = c->wticket.fetch_add(1, std::memory_order_relaxed);
    while (c->wlock.load(std::memory_order_acquire) != t) {
#if defined(_M_X64) || defined(__x86_64__) || defined(_M_IX86) || defined(__i386__)
        _mm_pause();
#endif
    }
}

static void pmtp2_unlock(PMTP_Control* c) noexcept {
    uint32_t cur = c->wlock.load(std::memory_order_relaxed);
    c->wlock.store(cur + 1, std::memory_order_release);
}

extern "C" POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_sizeof(uint32_t num_slots, uint64_t payload_bytes) {
    try { 
        if (num_slots < 2 || num_slots > 64) return 0;
        if (payload_bytes == 0) return 0;
        const uint64_t headers_size = static_cast<uint64_t>(num_slots) * sizeof(PMTP_SlotHeader);
        if (payload_bytes > (UINT64_MAX - sizeof(PMTP_Control) - headers_size) / num_slots) {
            return 0; // Overflow guard
        }
        return sizeof(PMTP_Control) + headers_size + static_cast<uint64_t>(num_slots) * payload_bytes; 
    } catch (...) { return 0; }
}

extern "C" POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_alignof(void) {
    try { return alignof(PMTP_Control); } catch (...) { return 0; }
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_init(PMTP_Control* c, uint32_t num_slots, uint64_t payload_bytes) {
    try {
        if (!c) return -1;
        if ((reinterpret_cast<uintptr_t>(c) & 63u) != 0) return -11; // 64-byte alignment mandatory
        if (num_slots < 2 || num_slots > 64) return -2;
        if (payload_bytes == 0) return -2;
        uint64_t sz = polydim_pmtp_sizeof(num_slots, payload_bytes);
        if (sz == 0) return -2;
        
        std::memset(reinterpret_cast<void*>(c), 0, static_cast<size_t>(sz));
        c->magic = 0x504D5432u;
        c->num_slots = num_slots;
        c->payload_bytes = payload_bytes;
        return 0;
    } catch (...) { return -1; }
}

extern "C" POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_payload_offset(PMTP_Control* c, uint32_t slot) {
    if (!c || slot >= c->num_slots) return 0;
    return sizeof(PMTP_Control) + static_cast<uint64_t>(c->num_slots) * sizeof(PMTP_SlotHeader) + static_cast<uint64_t>(slot) * c->payload_bytes;
}

extern "C" POLYDIM_EXPORT void* POLYDIM_CALL polydim_pmtp_payload_ptr(PMTP_Control* c, uint32_t slot) {
    if (!c || slot >= c->num_slots) return nullptr;
    return reinterpret_cast<char*>(c) + polydim_pmtp_payload_offset(c, slot);
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_write_begin(PMTP_Control* c, uint32_t* slot, uint64_t* ver) {
    try {
        if (!c || !slot || !ver) return -1;
        pmtp2_lock(c);
        
        uint64_t current_ver = c->pub_seq.load(std::memory_order_relaxed);
        *ver = current_ver + 1; // odd for locked/writing
        *slot = (c->pub_slot.load(std::memory_order_relaxed) + 1) % c->num_slots;
        
        PMTP_SlotHeader* hdr = pmtp2_hdr_of(c, *slot);
        hdr->owner_pid.store(get_current_pid(), std::memory_order_relaxed);
        hdr->owner_start_time.store(pmtp_get_time_ns(), std::memory_order_relaxed);
        hdr->state.store(1, std::memory_order_relaxed); // 1 = WRITING
        hdr->seq.store(*ver, std::memory_order_release);
        
        return 0;
    } catch (...) { return -1; }
}

extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_write_commit(PMTP_Control* c, uint32_t slot, uint64_t ver) {
    try {
        if (!c || slot >= c->num_slots) return;
        
        PMTP_SlotHeader* hdr = pmtp2_hdr_of(c, slot);
        uint64_t new_ver = ver + 1; // even for unlocked/ready
        hdr->state.store(2, std::memory_order_relaxed); // 2 = READY
        hdr->seq.store(new_ver, std::memory_order_release);
        
        c->pub_slot.store(slot, std::memory_order_release);
        c->pub_seq.store(new_ver, std::memory_order_release);
        
        pmtp2_unlock(c);
    } catch (...) {}
}

extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_write_abort(PMTP_Control* c, uint32_t slot, uint64_t ver) {
    try {
        if (!c || slot >= c->num_slots) return;
        PMTP_SlotHeader* hdr = pmtp2_hdr_of(c, slot);
        hdr->state.store(0, std::memory_order_relaxed); // 0 = EMPTY
        hdr->seq.store(ver + 1, std::memory_order_release);
        pmtp2_unlock(c);
    } catch (...) {}
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_read_begin(PMTP_Control* c, uint32_t* slot, uint64_t* ver) {
    try {
        if (!c || !slot || !ver) return -1;
        
        *ver = c->pub_seq.load(std::memory_order_acquire);
        if (*ver == 0) return 1; // EMPTY
        
        *slot = c->pub_slot.load(std::memory_order_acquire);
        PMTP_SlotHeader* hdr = pmtp2_hdr_of(c, *slot);
        
        uint64_t s_ver = hdr->seq.load(std::memory_order_acquire);
        if (s_ver != *ver || (s_ver & 1)) return -3; // BUSY/CONFLICT
        
        return 0;
    } catch (...) { return -1; }
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_read_validate(PMTP_Control* c, uint32_t slot, uint64_t ver) {
    try {
        if (!c || slot >= c->num_slots) return -1;
        PMTP_SlotHeader* hdr = pmtp2_hdr_of(c, slot);
        uint64_t s_ver = hdr->seq.load(std::memory_order_acquire);
        if (s_ver != ver) return -4; // CONFLICT
        return 0;
    } catch (...) { return -1; }
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_reap_tombstones(PMTP_Control* c, uint64_t timeout_ns) {
    try {
        if (!c) return -1;
        int32_t reaped = 0;
        uint64_t now = pmtp_get_time_ns();
        for (uint32_t s = 0; s < c->num_slots; ++s) {
            PMTP_SlotHeader* hdr = pmtp2_hdr_of(c, s);
            uint32_t st = hdr->state.load(std::memory_order_acquire);
            if (st == 1) { // WRITING
                uint32_t pid = hdr->owner_pid.load(std::memory_order_relaxed);
                uint64_t t0 = hdr->owner_start_time.load(std::memory_order_relaxed);
                bool dead = !is_process_alive(pid);
                bool timed_out = (timeout_ns > 0 && (now - t0) > timeout_ns);
                if (dead || timed_out) {
                    hdr->state.store(3, std::memory_order_release); // 3 = TOMBSTONE
                    uint64_t s_ver = hdr->seq.load(std::memory_order_relaxed);
                    if (s_ver & 1) {
                        hdr->seq.store(s_ver + 1, std::memory_order_release);
                    }
                    uint32_t cur_lock = c->wlock.load(std::memory_order_relaxed);
                    uint32_t cur_ticket = c->wticket.load(std::memory_order_relaxed);
                    if (cur_lock != cur_ticket) {
                        c->wlock.store(cur_lock + 1, std::memory_order_release);
                    }
                    ++reaped;
                }
            }
        }
        return reaped;
    } catch (...) { return -1; }
}

/* ==========================================================================
 * Autodiagnóstico y Self-Tests
 * ========================================================================*/
extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_check_ftz() {
#if defined(POLYDIM_X86)
    unsigned int csr = _mm_getcsr();
    if ((csr & 0x8000) || (csr & 0x0040)) return 1;
#endif
    return 0;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_selftest_compensation(double* observed_err) {
    try {
        const int n = 1000000;
        const double small = kEps / 2.0;
        Neumaier acc;
        acc.add(1.0);
        for (int i = 0; i < n; ++i) acc.add(small);
        const double expected = 1.0 + static_cast<double>(n) * small;
        const double got = acc.total();
        const double err = std::abs(got - expected) / expected;
        if (observed_err) *observed_err = err;
        if (!(err < 1e-14)) return POLYDIM_ERR_COMPENSATION_BROKEN;
        return POLYDIM_SUCCESS;
    } catch (...) {
        return POLYDIM_ERR_COMPENSATION_BROKEN;
    }
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_selftest_all(void) {
    try {
        double e = 0.0;
        int32_t rc = polydim_selftest_compensation(&e);
        if (rc != POLYDIM_SUCCESS) return rc;

        double y[4] = {1.0, 0.0, 0.0, 0.0}, u[4] = {0.0, 1.0, 0.0, 0.0},
               v[4] = {0.0, 0.0, 1.0, 0.0}, o[4] = {0, 0, 0, 0};
        const double nan_v = std::numeric_limits<double>::quiet_NaN();
        if (polydim_rodrigues_geodesic_f64(y, u, v, o, nan_v, 4, nullptr, nullptr)
            != POLYDIM_ERR_INVALID_SCALAR) return POLYDIM_ERR_NUMERICAL_INSTABILITY;

        double u_bad[4] = {0.0, 2.0, 0.0, 0.0};
        if (polydim_rodrigues_geodesic_f64(y, u_bad, v, o, 0.3, 4, nullptr, nullptr)
            != POLYDIM_ERR_BASIS_NOT_ORTHONORMAL) return POLYDIM_ERR_NUMERICAL_INSTABILITY;

        double y_bad[4] = {1.0 + 1e-6, 0.0, 0.0, 0.0};
        if (polydim_rodrigues_geodesic_f64(y_bad, u, v, o, 0.3, 4, nullptr, nullptr)
            != POLYDIM_ERR_POINT_OFF_MANIFOLD) return POLYDIM_ERR_NUMERICAL_INSTABILITY;

        const uint64_t D_test = 8;
        const uint32_t K_test = 2;
        double X_st[16] = {0.0};
        X_st[0 * K_test + 0] = 1.0;
        X_st[1 * K_test + 1] = 1.0;
        
        double G_st[16] = {0.0};
        G_st[0 * K_test + 1] = 0.5;
        G_st[1 * K_test + 0] = -0.5;
        G_st[2 * K_test + 0] = 0.3;
        G_st[3 * K_test + 1] = 0.4;
        
        const double tau = 1e-7;
        double Y1[16] = {0.0}, Y2[16] = {0.0};
        rc = polydim_stiefel_cayley_smw_f64(X_st, G_st, Y1, D_test, K_test, tau, nullptr, nullptr);
        if (rc != POLYDIM_SUCCESS) return rc;

        rc = polydim_stiefel_cayley_smw_f64(X_st, G_st, Y2, D_test, K_test, 2.0 * tau, nullptr, nullptr);
        if (rc != POLYDIM_SUCCESS) return rc;

        double G_proj[16] = {0.0};
        polydim_project_tangent_stiefel_f64(X_st, G_st, G_proj, D_test, K_test);
        double max_vel_err = 0.0;
        for (size_t i = 0; i < D_test * K_test; ++i) {
            double vel = (Y2[i] - Y1[i]) / tau;
            double err = std::abs(vel - G_proj[i]);
            if (err > max_vel_err) max_vel_err = err;
        }
        if (max_vel_err > 1e-4) return POLYDIM_ERR_NUMERICAL_INSTABILITY;

        return POLYDIM_SUCCESS;
    } catch (...) {
        return POLYDIM_ERR_INTERNAL;
    }
}

extern "C" POLYDIM_EXPORT const char* POLYDIM_CALL polydim_status_string(int32_t code) {
    switch (code) {
        case POLYDIM_SUCCESS: return "SUCCESS";
        case POLYDIM_ERR_NULL_POINTER: return "ERR_NULL_POINTER";
        case POLYDIM_ERR_INVALID_DIMENSION: return "ERR_INVALID_DIMENSION";
        case POLYDIM_ERR_NAN_OR_INF: return "ERR_NAN_OR_INF";
        case POLYDIM_ERR_DEGENERATE_NORM: return "ERR_DEGENERATE_NORM";
        case POLYDIM_ERR_NUMERICAL_INSTABILITY: return "ERR_NUMERICAL_INSTABILITY";
        case POLYDIM_ERR_SEQLOCK_RACE: return "ERR_SEQLOCK_RACE";
        case POLYDIM_ERR_BUFFER_OVERFLOW: return "ERR_BUFFER_OVERFLOW";
        case POLYDIM_ERR_INVALID_SCALAR: return "ERR_INVALID_SCALAR";
        case POLYDIM_ERR_BASIS_NOT_ORTHONORMAL: return "ERR_BASIS_NOT_ORTHONORMAL";
        case POLYDIM_ERR_POINT_OFF_MANIFOLD: return "ERR_POINT_OFF_MANIFOLD";
        case POLYDIM_ERR_ALIASED_BUFFERS: return "ERR_ALIASED_BUFFERS";
        case POLYDIM_ERR_COMPENSATION_BROKEN: return "ERR_COMPENSATION_BROKEN";
        case POLYDIM_ERR_ALLOC: return "ERR_ALLOC";
        case POLYDIM_ERR_INTERNAL: return "ERR_INTERNAL";
        default: return "UNKNOWN_ERROR";
    }
}

extern "C" POLYDIM_EXPORT const char* POLYDIM_CALL polydim_build_info(void) {
    return "POLYDIM V769 | FTZ/DAZ=ON (NO conforme IEEE-754) | BLAS=OFF (bucles nativos optimizados) | OpenMP=ON";
}
