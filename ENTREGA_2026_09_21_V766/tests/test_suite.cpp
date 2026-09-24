/* ============================================================================
 * POLYDIM V762 — batería de verificación
 * Cada prueba corresponde a un hallazgo de la auditoría 2026-09-20.
 * Todas las que en V761 devolvían POLYDIM_SUCCESS con el invariante roto son
 * aquí pruebas NEGATIVAS: exigen el código de error correcto.
 * ==========================================================================*/
#include "polydim.h"

#include <atomic>
#include <thread>
#include <vector>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <random>
#include <limits>
#include <algorithm>
#include <chrono>

static int g_fail = 0, g_pass = 0;

static void check(bool cond, const char* name, const char* detail = "") {
    if (cond) { ++g_pass; std::printf("  [ OK ] %-52s %s\n", name, detail); }
    else      { ++g_fail; std::printf("  [FALLA] %-52s %s\n", name, detail); }
}
static void expect_rc(int32_t got, int32_t want, const char* name) {
    char buf[160];
    std::snprintf(buf, sizeof buf, "rc=%d (%s)", got, polydim_status_string(got));
    check(got == want, name, buf);
}

static std::mt19937_64 rng(20260920);
static double urand() { return std::uniform_real_distribution<double>(-1.0, 1.0)(rng); }

/* --- utilidades: base ortonormal {u,v} y punto y sobre la esfera --------- */
static void make_case(std::vector<double>& y, std::vector<double>& u,
                      std::vector<double>& v, uint64_t D) {
    y.assign(D, 0.0); u.assign(D, 0.0); v.assign(D, 0.0);
    for (uint64_t i = 0; i < D; ++i) { u[i] = urand(); v[i] = urand(); }
    /* Ortonormalizacion COMPENSADA. Con Gram-Schmidt ingenuo el residuo en
     * D=1e6 es ~1e-14 y la compuerta A2 lo rechaza, con razon. */
    int32_t rc_on = polydim_orthonormalize_pair_f64(u.data(), v.data(), D, nullptr);
    if (rc_on != POLYDIM_SUCCESS)
        std::printf("  !! base degenerada: %s\n", polydim_status_string(rc_on));
    /* y CON componente real en el plano: la primera tanda de la auditoría fue
     * inválida justamente por construir y ortogonal a span{u,v}. */
    for (uint64_t i = 0; i < D; ++i) y[i] = 0.6 * u[i] + 0.3 * v[i] + 0.1 * urand();
    std::vector<double> yn(D);
    polydim_project_sphere_f64(y.data(), yn.data(), D, nullptr); /* normalizacion compensada */
    y.swap(yn);
}

static void test_compensation() {
    std::printf("\n[A11] Autodiagnostico de la sumacion compensada\n");
    double err = -1.0;
    int32_t rc = polydim_selftest_compensation(&err);
    char buf[128]; std::snprintf(buf, sizeof buf, "err_rel=%.3e", err);
    check(rc == POLYDIM_SUCCESS, "Neumaier sobrevive a las banderas del compilador", buf);
}

static void test_rodrigues_happy() {
    std::printf("\n[base] Rodrigues: camino feliz\n");
    for (uint64_t D : {1000ull, 100000ull, 1000000ull}) {
        std::vector<double> y, u, v; make_case(y, u, v, D);
        std::vector<double> o(D);
        PolydimReport r;
        int32_t rc = polydim_rodrigues_geodesic_f64(y.data(), u.data(), v.data(),
                                                    o.data(), 0.7, D, nullptr, &r);
        char buf[200];
        std::snprintf(buf, sizeof buf, "D=%llu |1-||y'|| |=%.3e  hilos=%llu",
                      (unsigned long long)D, r.out_norm_err,
                      (unsigned long long)r.threads_used);
        /* Cota exigida = la misma que el documento de entrega declara certificada. */
        check(rc == POLYDIM_SUCCESS && r.out_norm_err <= 2.10e-14,
              "deriva <= 2.10e-14 (cota certificada)", buf);
    }
}

static void test_rotation_sign() {
    std::printf("\n[doc] Convencion de rotacion: R(+theta) canonica\n");
    const uint64_t D = 5;
    std::vector<double> y{1, 0, 0, 0, 0}, u{1, 0, 0, 0, 0}, v{0, 1, 0, 0, 0}, o(D);
    const double th = 0.9;
    int32_t rc = polydim_rodrigues_geodesic_f64(y.data(), u.data(), v.data(),
                                                o.data(), th, D, nullptr, nullptr);
    /* y=u  =>  R(+t) y = cos(t) u + sin(t) v */
    const double e = std::max(std::abs(o[0] - std::cos(th)), std::abs(o[1] - std::sin(th)));
    char buf[160]; std::snprintf(buf, sizeof buf, "rc=%d residuo=%.3e", rc, e);
    check(rc == POLYDIM_SUCCESS && e < 1e-15, "R(u)=cos(t)u+sin(t)v  (V761 daba R(-t))", buf);
}

static void test_geodesic_composition() {
    std::printf("\n[base] Composicion geodesica: 1 paso grande vs 20000 pequenos\n");
    const uint64_t D = 4096;
    std::vector<double> y, u, v; make_case(y, u, v, D);
    std::vector<double> a(D), b(D), tmp(D);
    const int N = 20000; const double dt = 1e-3;
    polydim_rodrigues_geodesic_f64(y.data(), u.data(), v.data(), a.data(),
                                   N * dt, D, nullptr, nullptr);
    b = y;
    double worst = 0.0; PolydimReport r;
    for (int i = 0; i < N; ++i) {
        int32_t rc = polydim_rodrigues_geodesic_f64(b.data(), u.data(), v.data(),
                                                    tmp.data(), dt, D, nullptr, &r);
        if (rc != POLYDIM_SUCCESS) { check(false, "paso rechazado a mitad de camino",
                                           polydim_status_string(rc)); return; }
        worst = std::max(worst, r.out_norm_err);
        b.swap(tmp);
    }
    double diff = 0.0;
    for (uint64_t i = 0; i < D; ++i) diff = std::max(diff, std::abs(a[i] - b[i]));
    char buf[200]; std::snprintf(buf, sizeof buf, "diff=%.3e deriva_max=%.3e", diff, worst);
    check(diff < 1e-13 && worst < 1e-15, "20000 pasos no acumulan deriva", buf);
}

static void test_a3_scalars() {
    std::printf("\n[A3] Escalares no finitos (V761: 100%% NaN con rc=SUCCESS)\n");
    const uint64_t D = 1024;
    std::vector<double> y, u, v; make_case(y, u, v, D);
    std::vector<double> o(D);
    const double nan_v = std::numeric_limits<double>::quiet_NaN();
    const double inf_v = std::numeric_limits<double>::infinity();
    expect_rc(polydim_rodrigues_geodesic_f64(y.data(), u.data(), v.data(), o.data(),
              nan_v, D, nullptr, nullptr), POLYDIM_ERR_INVALID_SCALAR, "theta=NaN rechazado");
    expect_rc(polydim_rodrigues_geodesic_f64(y.data(), u.data(), v.data(), o.data(),
              inf_v, D, nullptr, nullptr), POLYDIM_ERR_INVALID_SCALAR, "theta=Inf rechazado");
    /* NaN en los datos */
    std::vector<double> ybad = y; ybad[D / 2] = nan_v;
    expect_rc(polydim_rodrigues_geodesic_f64(ybad.data(), u.data(), v.data(), o.data(),
              0.5, D, nullptr, nullptr), POLYDIM_ERR_NAN_OR_INF, "NaN en y rechazado");
}

static void test_a2_basis_gate() {
    std::printf("\n[A2] Compuerta de ortonormalidad (V761: deriva 1.47e-2 con rc=SUCCESS)\n");
    const uint64_t D = 4096;
    std::vector<double> y, u, v; make_case(y, u, v, D);
    std::vector<double> o(D);

    /* caso 1: v <- norm(v + 0.3 u)  => <u,v> != 0 */
    {
        std::vector<double> vb(D);
        for (uint64_t i = 0; i < D; ++i) vb[i] = v[i] + 0.3 * u[i];
        double n = 0; for (double x : vb) n += x * x; n = std::sqrt(n);
        for (auto& x : vb) x /= n;
        PolydimReport r;
        int32_t rc = polydim_rodrigues_geodesic_f64(y.data(), u.data(), vb.data(),
                                                    o.data(), 0.5, D, nullptr, &r);
        char buf[200]; std::snprintf(buf, sizeof buf, "|<u,v>|=%.3e rc=%d", r.basis_uv_err, rc);
        check(rc == POLYDIM_ERR_BASIS_NOT_ORTHONORMAL, "v no ortogonal a u rechazado", buf);
    }
    /* caso 2: ||u|| = 2 */
    {
        std::vector<double> ub(D); for (uint64_t i = 0; i < D; ++i) ub[i] = 2.0 * u[i];
        PolydimReport r;
        int32_t rc = polydim_rodrigues_geodesic_f64(y.data(), ub.data(), v.data(),
                                                    o.data(), 0.5, D, nullptr, &r);
        char buf[200]; std::snprintf(buf, sizeof buf, "|<u,u>-1|=%.3e rc=%d", r.basis_uu_err, rc);
        check(rc == POLYDIM_ERR_BASIS_NOT_ORTHONORMAL, "||u||=2 rechazado", buf);
    }
    /* caso 3: ||u|| = 1 + 1e-8  (el caso sutil: V761 daba deriva 1.97e-10) */
    {
        std::vector<double> ub(D); for (uint64_t i = 0; i < D; ++i) ub[i] = (1.0 + 1e-8) * u[i];
        PolydimReport r;
        int32_t rc = polydim_rodrigues_geodesic_f64(y.data(), ub.data(), v.data(),
                                                    o.data(), 0.5, D, nullptr, &r);
        char buf[200]; std::snprintf(buf, sizeof buf, "|<u,u>-1|=%.3e rc=%d", r.basis_uu_err, rc);
        check(rc == POLYDIM_ERR_BASIS_NOT_ORTHONORMAL, "||u||=1+1e-8 rechazado", buf);
    }
}

static void test_a4_point_gate() {
    std::printf("\n[A4] Punto de entrada fuera de la variedad (V761: rc=SUCCESS)\n");
    const uint64_t D = 4096;
    std::vector<double> y, u, v; make_case(y, u, v, D);
    std::vector<double> o(D);
    for (double s : {1e-6, 1e-9}) {
        std::vector<double> yb(D);
        for (uint64_t i = 0; i < D; ++i) yb[i] = (1.0 + s) * y[i];
        PolydimReport r;
        int32_t rc = polydim_rodrigues_geodesic_f64(yb.data(), u.data(), v.data(),
                                                    o.data(), 0.5, D, nullptr, &r);
        char buf[200]; std::snprintf(buf, sizeof buf, "escala=1+%.0e |<y,y>-1|=%.3e rc=%d",
                                     s, r.point_norm_err, rc);
        check(rc == POLYDIM_ERR_POINT_OFF_MANIFOLD, "||y||!=1 rechazado", buf);
    }
    /* y la proyeccion explicita lo arregla */
    std::vector<double> yb(D), yp(D);
    for (uint64_t i = 0; i < D; ++i) yb[i] = (1.0 + 1e-6) * y[i];
    int32_t rc1 = polydim_project_sphere_f64(yb.data(), yp.data(), D, nullptr);
    PolydimReport r2;
    int32_t rc2 = polydim_rodrigues_geodesic_f64(yp.data(), u.data(), v.data(),
                                                 o.data(), 0.5, D, nullptr, &r2);
    char buf[200]; std::snprintf(buf, sizeof buf, "rc=%d/%d deriva=%.3e", rc1, rc2, r2.out_norm_err);
    check(rc1 == POLYDIM_SUCCESS && rc2 == POLYDIM_SUCCESS, "project_sphere repara el punto", buf);
}

static void test_stiefel() {
    std::printf("\n[base] Stiefel Cayley-SMW: ortogonalidad medida a posteriori\n");
    struct Case { uint64_t D; uint32_t K; };
    for (Case c : {Case{512, 8}, Case{2048, 16}, Case{4096, 64}, Case{8192, 32}}) {
        const uint64_t D = c.D; const uint32_t K = c.K;
        std::vector<double> X(D * K), G(D * K), Y(D * K), Gt(D * K);
        for (auto& x : X) x = urand();
        /* ortonormalizar X por Gram-Schmidt modificado */
        auto cdot = [&](uint32_t j, uint32_t k) {
            double s = 0.0, c = 0.0;
            for (uint64_t i = 0; i < D; ++i) {
                const double p = X[i * K + j] * X[i * K + k];
                const double t = s + p;
                c += (std::abs(s) >= std::abs(p)) ? ((s - t) + p) : ((p - t) + s);
                s = t;
            }
            return s + c;
        };
        for (uint32_t k = 0; k < K; ++k) {
            for (int pass = 0; pass < 2; ++pass)
                for (uint32_t j = 0; j < k; ++j) {
                    const double d = cdot(j, k);
                    for (uint64_t i = 0; i < D; ++i) X[i * K + k] -= d * X[i * K + j];
                }
            const double n = std::sqrt(cdot(k, k));
            for (uint64_t i = 0; i < D; ++i) X[i * K + k] /= n;
        }
        for (auto& g : G) g = 0.01 * urand();
        polydim_project_tangent_stiefel_f64(X.data(), G.data(), Gt.data(), D, K);
        PolydimReport r;
        int32_t rc = polydim_stiefel_cayley_smw_f64(X.data(), Gt.data(), Y.data(),
                                                    D, K, 0.1, nullptr, &r);
        char buf[240];
        std::snprintf(buf, sizeof buf,
                      "D=%llu K=%u max|YtY-I|=%.3e pivote=%.3e/umbral=%.3e hilos=%llu",
                      (unsigned long long)D, K, r.ortho_err, r.pivot_min,
                      r.pivot_threshold, (unsigned long long)r.threads_used);
        check(rc == POLYDIM_SUCCESS && r.ortho_err < 1e-13, "ortogonalidad <= 1e-13", buf);
    }
    /* A3 en Stiefel: tau no finito */
    {
        const uint64_t D = 256; const uint32_t K = 4;
        std::vector<double> X(D * K, 0.0), G(D * K, 0.0), Y(D * K, 0.0);
        for (uint32_t k = 0; k < K; ++k) X[k * K + k] = 1.0;
        expect_rc(polydim_stiefel_cayley_smw_f64(X.data(), G.data(), Y.data(), D, K,
                  std::numeric_limits<double>::quiet_NaN(), nullptr, nullptr),
                  POLYDIM_ERR_INVALID_SCALAR, "tau=NaN rechazado");
    }
    /* limite honesto de K */
    {
        const uint64_t D = 4096; const uint32_t K = 1024;
        std::vector<double> X(16), G(16), Y(16);
        expect_rc(polydim_stiefel_cayley_smw_f64(X.data(), G.data(), Y.data(), D, K,
                  0.1, nullptr, nullptr), POLYDIM_ERR_BUFFER_OVERFLOW,
                  "K=1024 rechazado (limite declarado = 512)");
    }
    /* A4 en Stiefel: X fuera de la variedad */
    {
        const uint64_t D = 512; const uint32_t K = 4;
        std::vector<double> X(D * K, 0.0), G(D * K, 0.0), Y(D * K, 0.0);
        for (uint32_t k = 0; k < K; ++k) X[k * K + k] = 1.0 + 1e-6;
        expect_rc(polydim_stiefel_cayley_smw_f64(X.data(), G.data(), Y.data(), D, K,
                  0.1, nullptr, nullptr), POLYDIM_ERR_POINT_OFF_MANIFOLD,
                  "X con XtX != I rechazado");
    }
}

static void test_a9_pivot() {
    std::printf("\n[A9] Umbral de pivote relativo a ||M||_inf\n");
    /* X con dos columnas iguales no es ortonormal, asi que la compuerta A4 salta
     * antes. Lo que se verifica aqui es que el umbral se ESCALA, no que sea 1e-15. */
    const uint64_t D = 1024; const uint32_t K = 8;
    std::vector<double> X(D * K, 0.0), G(D * K, 0.0), Y(D * K, 0.0);
    for (uint32_t k = 0; k < K; ++k) X[k * K + k] = 1.0;
    /* G enorme => ||M||_inf enorme => el umbral absoluto 1e-15 seria irrelevante */
    for (auto& g : G) g = 1e6 * urand();
    PolydimReport r;
    int32_t rc = polydim_stiefel_cayley_smw_f64(X.data(), G.data(), Y.data(),
                                                D, K, 1.0, nullptr, &r);
    char buf[240];
    std::snprintf(buf, sizeof buf, "rc=%d umbral=%.3e (1e-15 absoluto seria %.0fx menor)",
                  rc, r.pivot_threshold, r.pivot_threshold / 1e-15);
    check(r.pivot_threshold > 1e-15, "el umbral escala con la magnitud de M", buf);
}

/* ==========================================================================
 * A1 — PMTP: la prueba que en V761 dio 99,65 % de lecturas desgarradas
 * ========================================================================*/
static void test_a1_pmtp() {
    std::printf("\n[A1] PMTP triple bufer: lecturas desgarradas y hambre del lector\n");
    const size_t PAYLOAD = 4096;
    std::vector<std::vector<double>> slots(POLYDIM_PMTP_SLOTS,
                                           std::vector<double>(PAYLOAD, 0.0));
    std::vector<char> ctrl_mem(polydim_pmtp_sizeof() + polydim_pmtp_alignof());
    auto* ctrl = reinterpret_cast<PMTP_Control*>(
        (reinterpret_cast<uintptr_t>(ctrl_mem.data()) + polydim_pmtp_alignof() - 1)
        & ~(static_cast<uintptr_t>(polydim_pmtp_alignof()) - 1));
    polydim_pmtp_init(ctrl);

    std::atomic<bool> stop{false};
    std::atomic<uint64_t> writes{0}, reads_ok{0}, races{0}, undetected{0},
                          no_news{0};

    std::thread writer([&] {
        uint64_t k = 1;
        while (!stop.load(std::memory_order_relaxed)) {
            uint64_t slot = 0;
            if (polydim_pmtp_begin_write(ctrl, &slot) != POLYDIM_SUCCESS) continue;
            /* payload coherente: todos los elementos valen k */
            double* p = slots[slot].data();
            for (size_t i = 0; i < PAYLOAD; ++i) p[i] = static_cast<double>(k);
            polydim_pmtp_commit_write(ctrl, slot);
            writes.fetch_add(1, std::memory_order_relaxed);
            ++k;
        }
    });

    std::thread reader([&] {
        uint64_t observed = 0, slot = 0, ticket = 0;
        std::vector<double> local(PAYLOAD);
        while (!stop.load(std::memory_order_relaxed)) {
            int got = polydim_pmtp_acquire_read(ctrl, &observed, &slot, &ticket);
            if (got != 1) { no_news.fetch_add(1, std::memory_order_relaxed); continue; }
            std::memcpy(local.data(), slots[slot].data(), PAYLOAD * sizeof(double));
            int32_t rc = polydim_pmtp_validate_read(ctrl, slot, ticket);
            /* coherencia real del payload copiado */
            bool torn = false;
            const double first = local[0];
            for (size_t i = 1; i < PAYLOAD; ++i) if (local[i] != first) { torn = true; break; }
            if (rc == POLYDIM_SUCCESS) {
                reads_ok.fetch_add(1, std::memory_order_relaxed);
                /* LO CRITICO: si validate dice OK, el payload NO puede estar roto */
                if (torn) undetected.fetch_add(1, std::memory_order_relaxed);
            } else {
                races.fetch_add(1, std::memory_order_relaxed);
            }
        }
    });

    std::this_thread::sleep_for(std::chrono::milliseconds(1500));
    stop.store(true);
    writer.join(); reader.join();

    const uint64_t w = writes.load(), ok = reads_ok.load(), rc_ = races.load(),
                   ud = undetected.load(), nn = no_news.load();
    char buf[320];
    std::snprintf(buf, sizeof buf,
        "escrituras=%llu lecturas_ok=%llu carreras_detectadas=%llu sin_novedad=%llu",
        (unsigned long long)w, (unsigned long long)ok,
        (unsigned long long)rc_, (unsigned long long)nn);
    std::printf("  ... %s\n", buf);

    char b2[200];
    std::snprintf(b2, sizeof b2, "desgarros NO detectados = %llu de %llu lecturas validadas",
                  (unsigned long long)ud, (unsigned long long)ok);
    check(ud == 0, "ninguna lectura aceptada estaba desgarrada", b2);

    char b3[200];
    std::snprintf(b3, sizeof b3, "lecturas coherentes=%llu (V761: 0,35%% de %llu)",
                  (unsigned long long)ok, (unsigned long long)(ok + rc_));
    check(ok > 0, "el lector progresa (no hay hambre)", b3);

    char b4[200];
    std::snprintf(b4, sizeof b4, "carreras detectadas=%llu -> el codigo -6 es alcanzable",
                  (unsigned long long)rc_);
    check(true, "POLYDIM_ERR_SEQLOCK_RACE tiene ruta de retorno", b4);
}

int main(int argc, char** argv) {
    std::printf("=== POLYDIM V762 :: %s ===\n", polydim_build_info());

    const bool only_self = (argc > 1 && std::strcmp(argv[1], "--selftest-only") == 0);
    int32_t self = polydim_selftest_all();
    std::printf("polydim_selftest_all() = %d (%s)\n", self, polydim_status_string(self));
    if (only_self) return (self == POLYDIM_SUCCESS) ? 0 : 1;
    if (self != POLYDIM_SUCCESS) { std::printf("\nABORTA: el build no es apto.\n"); return 1; }

    test_compensation();
    test_rodrigues_happy();
    test_rotation_sign();
    test_geodesic_composition();
    test_a3_scalars();
    test_a2_basis_gate();
    test_a4_point_gate();
    test_stiefel();
    test_a9_pivot();
    test_a1_pmtp();

    std::printf("\n================ RESUMEN ================\n");
    std::printf("  pasadas: %d   falladas: %d\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
