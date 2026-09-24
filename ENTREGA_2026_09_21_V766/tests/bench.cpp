/* Benchmark de la retracción Stiefel. Mismos (D,K) que la auditoría de V761. */
#include "polydim.h"
#include <vector>
#include <cstdio>
#include <cmath>
#include <random>
#include <chrono>
#include <algorithm>

int main() {
    std::mt19937_64 rng(7);
    std::uniform_real_distribution<double> ud(-1.0, 1.0);
    std::printf("%-14s %12s %12s %14s\n", "D,K", "ms/retrac", "max|YtY-I|", "hilos");
    struct C { uint64_t D; uint32_t K; };
    for (C c : {C{4096,16}, C{4096,64}, C{16384,32}, C{16384,128}, C{65536,64}}) {
        const uint64_t D = c.D; const uint32_t K = c.K;
        std::vector<double> X(D*K), G(D*K), Y(D*K), Gt(D*K);
        for (auto& x : X) x = ud(rng);
        auto cdot = [&](uint32_t j, uint32_t k) {
            double s=0,cc=0;
            for (uint64_t i=0;i<D;++i){double p=X[i*K+j]*X[i*K+k];double t=s+p;
                cc += (std::abs(s)>=std::abs(p))?((s-t)+p):((p-t)+s); s=t;}
            return s+cc; };
        for (uint32_t k=0;k<K;++k){
            for (int p=0;p<2;++p) for (uint32_t j=0;j<k;++j){
                double d=cdot(j,k); for(uint64_t i=0;i<D;++i) X[i*K+k]-=d*X[i*K+j];}
            double n=std::sqrt(cdot(k,k)); for(uint64_t i=0;i<D;++i) X[i*K+k]/=n;}
        for (auto& g : G) g = 0.01*ud(rng);
        polydim_project_tangent_stiefel_f64(X.data(), G.data(), Gt.data(), D, K);

        PolydimReport r; int reps = 3;
        polydim_stiefel_cayley_smw_f64(X.data(),Gt.data(),Y.data(),D,K,0.1,nullptr,&r); /* warm */
        std::vector<double> t_ms;
        for (int i=0;i<reps;++i){
            auto t0 = std::chrono::steady_clock::now();
            int32_t rc = polydim_stiefel_cayley_smw_f64(X.data(),Gt.data(),Y.data(),D,K,0.1,nullptr,&r);
            auto t1 = std::chrono::steady_clock::now();
            if (rc != POLYDIM_SUCCESS) { std::printf("rc=%d %s\n", rc, polydim_status_string(rc)); break; }
            t_ms.push_back(std::chrono::duration<double,std::milli>(t1-t0).count());
        }
        std::sort(t_ms.begin(), t_ms.end());
        char lbl[32]; std::snprintf(lbl,sizeof lbl,"%llu,%u",(unsigned long long)D,K);
        std::printf("%-14s %12.2f %12.3e %14llu\n", lbl,
                    t_ms.empty()?-1.0:t_ms[t_ms.size()/2], r.ortho_err,
                    (unsigned long long)r.threads_used);
    }
    return 0;
}
